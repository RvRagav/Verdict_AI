"""Corrigendum lifecycle.

A corrigendum is an amendment to the NIT issued during the bid period.
Indian procurement law (and Calcutta HC / SC rulings) treats the criterion
text the bidder responded against as the legally relevant version. So
the system must:

    - record every corrigendum as a first-class document
    - summarise it with Bedrock so the officer can read at a glance
    - let the officer apply specific amendments to specific criteria
    - bump the criterion version and write to criterion_versions
      (append-only) — the prior text is preserved forever
    - emit audit events at every step

This file holds the *workflow*. The append-only writes go through
`criterion_extraction._write_criterion_version`.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import PromptTemplate
from backend.core import audit_chain
from backend.pipeline.criterion_extraction import _write_criterion_version

logger = logging.getLogger(__name__)


# ─── Prompt — corrigendum summary ───────────────────────────────────


CORRIGENDUM_SUMMARY = PromptTemplate(
    name="corrigendum_summary",
    version="1.0.0",
    system=(
        "You are a procurement compliance expert. You summarise a tender "
        "corrigendum (an amendment issued during the bid period) into a "
        "short bullet list of concrete changes the officer can review. "
        "\n\n"
        "For each change, identify:\n"
        "  - the section / clause it amends (verbatim if present)\n"
        "  - what was changed (paraphrased, neutral language)\n"
        "  - whether it widens, narrows or clarifies the criterion\n"
        "\n"
        "Be precise. If a numeric threshold changed, state old and new "
        "values. If a deadline changed, state old and new dates. Do not "
        "speculate on intent."
    ),
    user_template=(
        "CORRIGENDUM TEXT:\n{corrigendum_text}\n\n"
        "Return JSON only."
    ),
    schema_hint=(
        '{'
        '"summary": str, '
        '"changes": [{'
        '"clause_ref": str|null, '
        '"old_text": str|null, '
        '"new_text": str|null, '
        '"change_kind": "widen|narrow|clarify|deadline|other", '
        '"impact_summary": str'
        '}]'
        '}'
    ),
)


# ─── Public API ──────────────────────────────────────────────────────


def register_corrigendum(
    conn,
    *,
    tender_id: str,
    document_id: str,
    title: str,
    issued_date: Optional[str],
    actor: str,
) -> dict:
    """Register a freshly-uploaded corrigendum doc as a corrigendum row.

    Calls Bedrock to summarise it. Idempotent: re-calling with the same
    document_id is a no-op.
    """
    existing = conn.execute(
        "SELECT id FROM corrigenda WHERE document_id = ?", (document_id,),
    ).fetchone()
    if existing:
        return get_corrigendum(conn, existing["id"])

    seq = _next_sequence(conn, tender_id)
    corrigendum_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    summary_data = _summarise(conn, document_id=document_id, tender_id=tender_id)
    summary_text = summary_data.get("summary") or "(no summary available)"

    conn.execute(
        """INSERT INTO corrigenda
           (id, tender_id, document_id, sequence_number, title, issued_date,
            summary, state, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_apply', ?)""",
        (corrigendum_id, tender_id, document_id, seq, title, issued_date,
         summary_text, now),
    )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="corrigendum_received",
        event_data={
            "corrigendum_id": corrigendum_id,
            "document_id": document_id,
            "sequence_number": seq,
            "title": title,
        },
        actor=actor,
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="corrigendum_summarised",
        event_data={
            "corrigendum_id": corrigendum_id,
            "change_count": len(summary_data.get("changes") or []),
        },
        actor="system",
    )
    return get_corrigendum(conn, corrigendum_id)


def list_corrigenda(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM corrigenda WHERE tender_id = ? ORDER BY sequence_number",
        (tender_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_corrigendum(conn, corrigendum_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM corrigenda WHERE id = ?", (corrigendum_id,),
    ).fetchone()
    return dict(row) if row else None


def apply_amendment(
    conn,
    *,
    corrigendum_id: str,
    criterion_id: str,
    new_text: str,
    new_threshold: Optional[dict],
    new_is_mandatory: Optional[bool],
    new_gfr_rule_number: Optional[str],
    actor: str,
) -> dict:
    """Apply a corrigendum amendment to a single criterion.

    Bumps the criterion's current_version, writes the new version into
    the append-only history, and stamps `last_amended_by`/`last_amended_at`
    on the criterion.
    """
    corrig = get_corrigendum(conn, corrigendum_id)
    if not corrig:
        raise ValueError(f"Corrigendum not found: {corrigendum_id}")

    criterion = conn.execute(
        "SELECT * FROM criteria WHERE id = ?", (criterion_id,),
    ).fetchone()
    if not criterion:
        raise ValueError(f"Criterion not found: {criterion_id}")
    crit = dict(criterion)
    if crit["tender_id"] != corrig["tender_id"]:
        raise ValueError("Criterion does not belong to this tender.")

    new_version = int(crit.get("current_version") or 1) + 1
    now = datetime.now(timezone.utc).isoformat()

    # Update the criterion's current row
    fields = ["criterion_text = ?", "state = 'edited'",
              "current_version = ?", "last_amended_by = ?", "last_amended_at = ?"]
    params: list = [new_text, new_version, corrigendum_id, now]
    if new_threshold is not None:
        fields.insert(1, "threshold_value = ?")
        params.insert(1, json.dumps(new_threshold))
    if new_is_mandatory is not None:
        fields.insert(1, "is_mandatory = ?")
        params.insert(1, 1 if new_is_mandatory else 0)
    if new_gfr_rule_number is not None:
        fields.insert(1, "gfr_rule_number = ?")
        params.insert(1, new_gfr_rule_number)
    params.append(criterion_id)

    conn.execute(
        f"UPDATE criteria SET {', '.join(fields)} WHERE id = ?",
        params,
    )

    # Append the new historical version
    threshold_for_history = new_threshold
    if threshold_for_history is None and crit.get("threshold_value"):
        try:
            threshold_for_history = json.loads(crit["threshold_value"])
        except (json.JSONDecodeError, TypeError):
            threshold_for_history = None

    _write_criterion_version(
        conn,
        criterion_id=criterion_id,
        version=new_version,
        criterion_text=new_text,
        criterion_type=crit["criterion_type"],
        threshold_value=threshold_for_history,
        is_mandatory=bool(new_is_mandatory if new_is_mandatory is not None else crit["is_mandatory"]),
        gfr_rule_number=new_gfr_rule_number or crit.get("gfr_rule_number"),
        source_clause_ref=crit.get("source_clause_ref"),
        source_page=crit.get("source_page"),
        change_source="corrigendum",
        corrigendum_id=corrigendum_id,
        changed_by=actor,
        change_note=f"Applied corrigendum #{corrig['sequence_number']}",
        now=now,
    )

    audit_chain.append(
        conn,
        tender_id=corrig["tender_id"],
        event_type="criterion_amended",
        event_data={
            "criterion_id": criterion_id,
            "corrigendum_id": corrigendum_id,
            "new_version": new_version,
        },
        actor=actor,
    )
    return {
        "criterion_id": criterion_id,
        "new_version": new_version,
        "corrigendum_id": corrigendum_id,
    }


def mark_applied(
    conn, *, corrigendum_id: str, actor: str,
) -> dict:
    """Mark a corrigendum as fully applied (officer signs off)."""
    corrig = get_corrigendum(conn, corrigendum_id)
    if not corrig:
        raise ValueError(f"Corrigendum not found: {corrigendum_id}")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE corrigenda SET state = 'applied', applied_by = ?, applied_at = ? "
        "WHERE id = ?",
        (actor, now, corrigendum_id),
    )
    audit_chain.append(
        conn,
        tender_id=corrig["tender_id"],
        event_type="corrigendum_applied",
        event_data={"corrigendum_id": corrigendum_id},
        actor=actor,
    )
    return get_corrigendum(conn, corrigendum_id)


# ─── Helpers ─────────────────────────────────────────────────────────


def _next_sequence(conn, tender_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(sequence_number) AS s FROM corrigenda WHERE tender_id = ?",
        (tender_id,),
    ).fetchone()
    return (row["s"] or 0) + 1


def _summarise(conn, *, document_id: str, tender_id: str) -> dict:
    """Run Bedrock to summarise a corrigendum's text."""
    text_rows = conn.execute(
        "SELECT raw_text FROM pages WHERE document_id = ? ORDER BY page_number",
        (document_id,),
    ).fetchall()
    full_text = "\n\n".join((r["raw_text"] or "") for r in text_rows)
    if not full_text.strip():
        return {"summary": "(empty corrigendum)", "changes": []}

    if len(full_text) > 30_000:
        full_text = full_text[:30_000] + "\n\n[truncated]"

    user = CORRIGENDUM_SUMMARY.render_user(corrigendum_text=full_text)
    resp = bedrock_client.invoke(
        invocation_type="corrigendum_summary",
        system=CORRIGENDUM_SUMMARY.system,
        user=user,
        prompt_version=CORRIGENDUM_SUMMARY.version,
        structured=True,
        schema_hint=CORRIGENDUM_SUMMARY.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not isinstance(resp.data, dict):
        return {"summary": "Summarisation failed; officer to review manually.",
                "changes": []}
    return resp.data
