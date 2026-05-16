"""Criteria management — extraction trigger + officer review/approval gate.

Officer flow:
1. Upload NIT → state=DOCUMENTS_READY → extract_for_tender() runs L2
2. Officer sees criteria in CRITERIA_PENDING_REVIEW
3. Officer can edit (text, threshold, mandatory flag), approve, or reject
4. When all criteria are approved → approve_all() → state=CRITERIA_APPROVED
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain
from backend.pipeline import criterion_extraction
from backend.services import tender_service


def extract_for_tender(
    conn,
    *,
    tender_id: str,
    actor: str,
) -> dict:
    """Run L2 on the tender's NIT document.

    Transitions the tender DOCUMENTS_READY → CRITERIA_EXTRACTING → CRITERIA_PENDING_REVIEW.
    Returns a summary: {criteria, checklist, nit_document_id}.
    """
    nit_row = conn.execute(
        "SELECT id FROM documents WHERE tender_id = ? AND doc_type = 'nit' "
        "AND deleted_at IS NULL AND processing_state = 'complete' "
        "ORDER BY uploaded_at ASC LIMIT 1",
        (tender_id,),
    ).fetchone()
    if not nit_row:
        raise ValueError("No processed NIT document found for tender.")
    nit_id = nit_row["id"]

    tender_service.transition_state(
        conn, tender_id=tender_id, target_state="CRITERIA_EXTRACTING", actor=actor,
    )

    criteria = criterion_extraction.extract_criteria(
        conn, tender_id=tender_id, nit_document_id=nit_id, actor=actor,
    )
    checklist = criterion_extraction.extract_checklist(
        conn, tender_id=tender_id, nit_document_id=nit_id, actor=actor,
    )

    tender_service.transition_state(
        conn, tender_id=tender_id, target_state="CRITERIA_PENDING_REVIEW", actor=actor,
    )

    return {
        "nit_document_id": nit_id,
        "criteria_count": len(criteria),
        "checklist_count": len(checklist),
        "criteria": criteria,
        "checklist": checklist,
    }


def list_criteria(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM criteria WHERE tender_id = ? ORDER BY created_at ASC",
        (tender_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_criterion(conn, criterion_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM criteria WHERE id = ?", (criterion_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def edit_criterion(
    conn,
    *,
    criterion_id: str,
    actor: str,
    criterion_text: Optional[str] = None,
    threshold_value: Optional[dict] = None,
    is_mandatory: Optional[bool] = None,
    gfr_rule_number: Optional[str] = None,
) -> dict:
    """Officer-facing edit. Marks state='edited' AND writes a new
    `criterion_versions` row so the history is preserved."""
    existing = get_criterion(conn, criterion_id)
    if not existing:
        raise ValueError(f"Criterion not found: {criterion_id}")

    fields = []
    params: list = []
    if criterion_text is not None:
        fields.append("criterion_text = ?"); params.append(criterion_text)
    if threshold_value is not None:
        fields.append("threshold_value = ?"); params.append(json.dumps(threshold_value))
    if is_mandatory is not None:
        fields.append("is_mandatory = ?"); params.append(1 if is_mandatory else 0)
    if gfr_rule_number is not None:
        fields.append("gfr_rule_number = ?"); params.append(gfr_rule_number)

    if not fields:
        return existing

    fields.append("state = 'edited'")
    new_version = int(existing.get("current_version") or 1) + 1
    fields.append("current_version = ?"); params.append(new_version)
    params.append(criterion_id)

    conn.execute(
        f"UPDATE criteria SET {', '.join(fields)} WHERE id = ?",
        params,
    )

    # Append the new version (append-only audit table)
    from backend.pipeline.criterion_extraction import _write_criterion_version
    now = datetime.now(timezone.utc).isoformat()
    merged = dict(existing)
    if criterion_text is not None: merged["criterion_text"] = criterion_text
    if threshold_value is not None: merged["threshold_value"] = threshold_value
    if is_mandatory is not None: merged["is_mandatory"] = is_mandatory
    if gfr_rule_number is not None: merged["gfr_rule_number"] = gfr_rule_number

    _write_criterion_version(
        conn,
        criterion_id=criterion_id,
        version=new_version,
        criterion_text=merged.get("criterion_text") or "",
        criterion_type=merged.get("criterion_type") or "qualitative_assessment",
        threshold_value=merged.get("threshold_value"),
        is_mandatory=bool(merged.get("is_mandatory")),
        gfr_rule_number=merged.get("gfr_rule_number"),
        source_clause_ref=merged.get("source_clause_ref"),
        source_page=merged.get("source_page"),
        change_source="officer_edit",
        corrigendum_id=None,
        changed_by=actor,
        change_note="Officer edit during review.",
        now=now,
    )

    audit_chain.append(
        conn,
        tender_id=existing["tender_id"],
        event_type="criterion_version_created",
        event_data={
            "criterion_id": criterion_id,
            "new_version": new_version,
            "change_source": "officer_edit",
            "fields": [f.split(" = ")[0] for f in fields if " = " in f
                       and f.split(" = ")[0] not in ("state", "current_version")],
        },
        actor=actor,
    )
    return get_criterion(conn, criterion_id)


def approve_criterion(
    conn,
    *,
    criterion_id: str,
    officer_id: str,
) -> dict:
    """Mark a single criterion approved by this officer."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE criteria SET state = 'approved', approved_by = ?, approved_at = ? "
        "WHERE id = ?",
        (officer_id, now, criterion_id),
    )
    return get_criterion(conn, criterion_id)


def reject_criterion(
    conn,
    *,
    criterion_id: str,
    officer_id: str,
) -> dict:
    """Mark a criterion rejected (excluded from evaluation)."""
    conn.execute(
        "UPDATE criteria SET state = 'rejected', approved_by = ?, approved_at = ? "
        "WHERE id = ?",
        (officer_id, datetime.now(timezone.utc).isoformat(), criterion_id),
    )
    return get_criterion(conn, criterion_id)


def approve_all(
    conn,
    *,
    tender_id: str,
    officer_id: str,
) -> dict:
    """Approve every still-pending criterion and advance the tender state."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE criteria SET state = 'approved', approved_by = ?, approved_at = ?
           WHERE tender_id = ? AND state IN ('extracted', 'edited')""",
        (officer_id, now, tender_id),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="criteria_approved",
        event_data={"approved_at": now},
        actor=officer_id,
    )
    tender_service.transition_state(
        conn, tender_id=tender_id, target_state="CRITERIA_APPROVED", actor=officer_id,
    )
    return tender_service.get_tender(conn, tender_id)


def _row_to_dict(row) -> dict:
    if row is None:
        return None  # type: ignore[return-value]
    d = dict(row)
    for col in ("threshold_value", "source_bbox", "amendment_history",
                "acceptable_evidence"):
        if d.get(col):
            try:
                d[col] = json.loads(d[col])
            except (json.JSONDecodeError, TypeError):
                pass
    d["is_mandatory"] = bool(d.get("is_mandatory"))
    d["gfr_override_permitted"] = bool(d.get("gfr_override_permitted"))
    return d


# ─── Version history (append-only) ────────────────────────────────


def list_versions(conn, criterion_id: str) -> list[dict]:
    """Return every historical version of a criterion, oldest first."""
    rows = conn.execute(
        """SELECT id, version, criterion_text, criterion_type, threshold_value,
                  is_mandatory, gfr_rule_number, source_clause_ref, source_page,
                  change_source, corrigendum_id, changed_by, change_note,
                  created_at
           FROM criterion_versions
           WHERE criterion_id = ?
           ORDER BY version ASC""",
        (criterion_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("threshold_value"):
            try:
                d["threshold_value"] = json.loads(d["threshold_value"])
            except (json.JSONDecodeError, TypeError):
                pass
        d["is_mandatory"] = bool(d.get("is_mandatory"))
        out.append(d)
    return out


def get_version(conn, criterion_id: str, version: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM criterion_versions WHERE criterion_id = ? AND version = ?",
        (criterion_id, version),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("threshold_value"):
        try:
            d["threshold_value"] = json.loads(d["threshold_value"])
        except (json.JSONDecodeError, TypeError):
            pass
    d["is_mandatory"] = bool(d.get("is_mandatory"))
    return d
