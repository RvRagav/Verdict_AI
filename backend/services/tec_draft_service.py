"""Co-authored TEC report — paragraph-level edits + diff trail.

The pre-M2 flow generated a TEC PDF in one shot. The officer never got
to put words in. That breaks the product's central promise: AI helps,
officer decides, every word in the file is attributed.

The new flow:

  1. Officer clicks "Generate TEC draft" → backend creates a
     `tec_report_drafts` row + a set of `tec_report_sections` rows
     (header / summary / per-bidder narrative / recommendation), each
     with `authored_by='ai'` and an initial revision in
     `tec_section_revisions`.

  2. Officer opens the Report tab, sees every section as an editable
     card. Edits a paragraph → POST /sections/:id/revise saves a new
     revision row (append-only) and bumps `authored_by` to 'co-authored'
     or 'officer'.

  3. Officer clicks "Regenerate this section" → AI rewrites just that
     section using fresh structured facts, append-only revision saved.

  4. Officer clicks "Finalise" → backend renders the current draft
     to PDF via report_service, hash-stamps it, marks the draft
     finalised, audit chain writes `tec_report_finalised`.

Every revision keeps body_before + body_after + change_source (ai_initial
| ai_suggestion | officer_edit | officer_revert) + edited_by.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import TEC_SECTION_DRAFT
from backend.core import audit_chain
from backend.services import (
    bidder_service,
    criteria_service,
    evaluation_service,
    tender_service,
)


# ─── Section blueprint ──────────────────────────────────────────────


def _section_blueprint(tender, bidders, criteria, evaluations) -> list[dict]:
    """Decide which sections this tender's TEC draft should contain."""
    sections: list[dict] = []
    sections.append({
        "key": "header",
        "label": "Committee constitution",
        "facts": {
            "tender_number": tender["tender_number"],
            "title": tender["title"],
            "department": tender["department"],
            "category": tender["category"],
            "estimated_cost": tender.get("estimated_cost"),
            "emd_amount": tender.get("emd_amount"),
            "bid_open_date": tender.get("bid_open_date"),
            "bid_close_date": tender.get("bid_close_date"),
        },
    })
    sections.append({
        "key": "summary",
        "label": "Summary of evaluation",
        "facts": _summary_facts(bidders, criteria, evaluations),
    })

    by_pair = {(e["bidder_id"], e["criterion_id"]): e for e in evaluations}
    for b in bidders:
        if b.get("deleted_at"):
            continue
        b_facts = {
            "company_name": b["company_name"],
            "pan_number": b.get("pan_number"),
            "gstin": b.get("gstin"),
            "state": b["state"],
            "debarment_state": b["debarment_state"],
            "criteria": [],
        }
        for c in criteria:
            ev = by_pair.get((b["id"], c["id"]))
            if not ev:
                continue
            b_facts["criteria"].append({
                "criterion_text": c["criterion_text"],
                "criterion_type": c["criterion_type"],
                "is_mandatory": bool(c["is_mandatory"]),
                "verdict": ev["verdict"],
                "confidence": ev["confidence"],
                "route": ev["route"],
                "officer_decision": ev.get("officer_decision"),
                "extracted_value": _safe_json(ev.get("extracted_value")),
            })
        sections.append({
            "key": f"bidder.{b['id']}",
            "label": f"Bidder evaluation — {b['company_name']}",
            "facts": b_facts,
        })

    sections.append({
        "key": "recommendation",
        "label": "Committee recommendation",
        "facts": {
            "qualified": [b["company_name"] for b in bidders
                          if b["state"] == "evaluated"],
            "excluded": [b["company_name"] for b in bidders
                        if b["state"] in ("preliminary_failed", "excluded")],
            "open_review_count": sum(
                1 for e in evaluations if e["state"] != "resolved"
            ),
        },
    })
    return sections


def _summary_facts(bidders, criteria, evaluations) -> dict:
    verdict_counts = {"PASS": 0, "FAIL": 0, "REVIEW": 0}
    for e in evaluations:
        verdict_counts[e["verdict"]] = verdict_counts.get(e["verdict"], 0) + 1
    return {
        "bidder_count": sum(1 for b in bidders if not b.get("deleted_at")),
        "criterion_count": sum(1 for c in criteria if c["state"] == "approved"),
        "cells_total": len(evaluations),
        "verdicts": verdict_counts,
        "open_review": sum(1 for e in evaluations if e["state"] != "resolved"),
    }


def _safe_json(v):
    if v is None:
        return None
    if isinstance(v, (dict, list, int, float, str, bool)):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return None


# ─── Public API ─────────────────────────────────────────────────────


def get_or_create_draft(conn, *, tender_id: str, officer_id: str) -> dict:
    """Return current 'draft' row for this tender; create one if none."""
    row = conn.execute(
        "SELECT * FROM tec_report_drafts "
        "WHERE tender_id = ? AND state = 'draft' "
        "ORDER BY generated_at DESC LIMIT 1",
        (tender_id,),
    ).fetchone()
    if row:
        return dict(row)

    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO tec_report_drafts
           (id, tender_id, state, generated_by, generated_at)
           VALUES (?, ?, 'draft', ?, ?)""",
        (draft_id, tender_id, officer_id, now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tec_draft_generated",
        event_data={"draft_id": draft_id},
        actor=officer_id,
    )
    return {
        "id": draft_id, "tender_id": tender_id, "state": "draft",
        "generated_by": officer_id, "generated_at": now,
        "finalised_at": None, "finalised_report_id": None,
    }


def populate_sections(
    conn,
    *,
    draft_id: str,
    tender_id: str,
    officer_id: str,
    use_llm: bool = True,
) -> list[dict]:
    """Generate all sections for a draft. Idempotent — if a section
    already exists for this draft+key, it is skipped.

    Each section has its initial body produced via Bedrock when
    use_llm=True (otherwise a structured fallback). The first revision
    is recorded in tec_section_revisions with change_source='ai_initial'.
    """
    tender = tender_service.get_tender(conn, tender_id)
    bidders = bidder_service.list_bidders(conn, tender_id)
    criteria = [c for c in criteria_service.list_criteria(conn, tender_id)
                if c["state"] == "approved"]
    evaluations = evaluation_service.list_evaluations(conn, tender_id=tender_id)
    blueprint = _section_blueprint(tender, bidders, criteria, evaluations)

    existing = {r["section_key"] for r in conn.execute(
        "SELECT section_key FROM tec_report_sections WHERE draft_id = ?",
        (draft_id,),
    ).fetchall()}

    out: list[dict] = []
    for sort_order, sec in enumerate(blueprint):
        if sec["key"] in existing:
            out.append(_get_section_by_key(conn, draft_id, sec["key"]))
            continue

        body = _draft_section_body(
            conn,
            tender_id=tender_id,
            label=sec["label"],
            facts=sec["facts"],
            use_llm=use_llm,
        )
        section = _insert_section(
            conn,
            draft_id=draft_id,
            section_key=sec["key"],
            section_label=sec["label"],
            sort_order=sort_order,
            body=body,
            authored_by="ai",
            officer_id=officer_id,
        )
        _insert_revision(
            conn,
            section_id=section["id"],
            revision=1,
            body_before=None,
            body_after=body,
            change_source="ai_initial",
            edited_by=officer_id,
            diff_summary="AI initial draft.",
        )
        audit_chain.append(
            conn,
            tender_id=tender_id,
            event_type="tec_section_authored",
            event_data={
                "draft_id": draft_id,
                "section_id": section["id"],
                "section_key": sec["key"],
                "authored_by": "ai",
            },
            actor=officer_id,
        )
        out.append(section)
    return out


def list_sections(conn, draft_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tec_report_sections WHERE draft_id = ? "
        "ORDER BY sort_order ASC",
        (draft_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_section(conn, section_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM tec_report_sections WHERE id = ?",
        (section_id,),
    ).fetchone()
    return dict(row) if row else None


def list_revisions(conn, section_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tec_section_revisions "
        "WHERE section_id = ? ORDER BY revision ASC",
        (section_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def revise_section(
    conn,
    *,
    section_id: str,
    new_body: str,
    officer_id: str,
    diff_summary: Optional[str] = None,
) -> dict:
    """Officer-driven edit. Append a new revision; update the section's
    current body + authored_by + last_edited_*.
    """
    section = get_section(conn, section_id)
    if not section:
        raise ValueError(f"Section not found: {section_id}")

    if (new_body or "").strip() == (section["body"] or "").strip():
        return section  # no-op

    revs = list_revisions(conn, section_id)
    next_rev = (revs[-1]["revision"] + 1) if revs else 1

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE tec_report_sections
           SET body = ?, authored_by = 'co-authored',
               last_edited_by = ?, last_edited_at = ?
           WHERE id = ?""",
        (new_body, officer_id, now, section_id),
    )
    _insert_revision(
        conn,
        section_id=section_id,
        revision=next_rev,
        body_before=section["body"],
        body_after=new_body,
        change_source="officer_edit",
        edited_by=officer_id,
        diff_summary=diff_summary or "Officer edit.",
    )

    # Look up tender_id via the draft for the audit log
    tender_id = conn.execute(
        "SELECT t.tender_id FROM tec_report_drafts t "
        "WHERE t.id = (SELECT draft_id FROM tec_report_sections WHERE id = ?)",
        (section_id,),
    ).fetchone()["tender_id"]
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tec_section_revised",
        event_data={
            "section_id": section_id,
            "revision": next_rev,
            "change_source": "officer_edit",
        },
        actor=officer_id,
    )
    return get_section(conn, section_id)


def regenerate_section(
    conn, *, section_id: str, officer_id: str,
) -> dict:
    """Ask the AI for a fresh draft of just this section. Saves a new
    revision with change_source='ai_suggestion' and authored_by becomes
    'ai' (officer hasn't accepted yet — the section state itself reflects
    that the latest body came from the AI).
    """
    section = get_section(conn, section_id)
    if not section:
        raise ValueError(f"Section not found: {section_id}")

    draft_row = conn.execute(
        "SELECT tender_id FROM tec_report_drafts WHERE id = ?",
        (section["draft_id"],),
    ).fetchone()
    tender_id = draft_row["tender_id"]

    # Re-derive structured facts for THIS section
    tender = tender_service.get_tender(conn, tender_id)
    bidders = bidder_service.list_bidders(conn, tender_id)
    criteria = [c for c in criteria_service.list_criteria(conn, tender_id)
                if c["state"] == "approved"]
    evaluations = evaluation_service.list_evaluations(conn, tender_id=tender_id)
    blueprint = _section_blueprint(tender, bidders, criteria, evaluations)
    facts = next((s["facts"] for s in blueprint
                  if s["key"] == section["section_key"]), None)
    if facts is None:
        facts = {"note": "section facts no longer available"}

    new_body = _draft_section_body(
        conn,
        tender_id=tender_id,
        label=section["section_label"],
        facts=facts,
        use_llm=True,
    )
    if new_body.strip() == (section["body"] or "").strip():
        return section

    revs = list_revisions(conn, section_id)
    next_rev = (revs[-1]["revision"] + 1) if revs else 1
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE tec_report_sections
           SET body = ?, authored_by = 'ai',
               last_edited_by = ?, last_edited_at = ?
           WHERE id = ?""",
        (new_body, officer_id, now, section_id),
    )
    _insert_revision(
        conn,
        section_id=section_id,
        revision=next_rev,
        body_before=section["body"],
        body_after=new_body,
        change_source="ai_suggestion",
        edited_by=officer_id,
        diff_summary="AI re-drafted section.",
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tec_section_revised",
        event_data={
            "section_id": section_id,
            "revision": next_rev,
            "change_source": "ai_suggestion",
        },
        actor=officer_id,
    )
    return get_section(conn, section_id)


def finalise_draft(
    conn, *, draft_id: str, officer_id: str,
) -> dict:
    """Render the draft to PDF via report_service, mark draft finalised."""
    from backend.services import report_service

    draft = conn.execute(
        "SELECT * FROM tec_report_drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    draft = dict(draft)
    if draft["state"] != "draft":
        raise ValueError(f"Draft is {draft['state']}, not draft.")

    sections = list_sections(conn, draft_id)
    # Render via report_service helper
    report = report_service.generate_report_from_draft(
        conn,
        tender_id=draft["tender_id"],
        officer_id=officer_id,
        sections=sections,
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE tec_report_drafts
           SET state = 'finalised', finalised_at = ?, finalised_report_id = ?
           WHERE id = ?""",
        (now, report["id"], draft_id),
    )
    audit_chain.append(
        conn,
        tender_id=draft["tender_id"],
        event_type="tec_report_finalised",
        event_data={
            "draft_id": draft_id,
            "report_id": report["id"],
            "section_count": len(sections),
            "co_authored_count": sum(1 for s in sections
                                     if s["authored_by"] in ("co-authored", "officer")),
        },
        actor=officer_id,
    )
    return {
        "draft_id": draft_id,
        "report_id": report["id"],
        "report_path": report["file_path"],
        "report_sha256": report["sha256_hash"],
        "section_count": len(sections),
    }


# ─── Internal helpers ───────────────────────────────────────────────


def _draft_section_body(
    conn, *, tender_id: str, label: str, facts: dict, use_llm: bool,
) -> str:
    """Produce the section body. LLM when available; structured fallback."""
    if not use_llm:
        return _fallback_body(label, facts)

    facts_json = json.dumps(facts, indent=2, default=str)[:4000]
    try:
        resp = bedrock_client.invoke(
            invocation_type="tec_section_draft",
            system=TEC_SECTION_DRAFT.system,
            user=TEC_SECTION_DRAFT.render_user(
                section_label=label,
                facts_json=facts_json,
            ),
            prompt_version=TEC_SECTION_DRAFT.version,
            tender_id=tender_id,
            conn=conn,
            max_tokens=1500,
        )
        if resp.error or not (resp.text or "").strip():
            return _fallback_body(label, facts)
        return resp.text.strip()
    except Exception:
        return _fallback_body(label, facts)


def _fallback_body(label: str, facts: dict) -> str:
    """Deterministic structured rendering when the LLM isn't available."""
    if "tender_number" in facts:
        return (
            f"## {label}\n\n"
            f"**Tender:** {facts.get('tender_number')} — {facts.get('title')}\n\n"
            f"Department: {facts.get('department')}\n\n"
            f"Category: {facts.get('category')}\n\n"
            f"Estimated cost: ₹{facts.get('estimated_cost') or '—'}\n\n"
            f"Bid open: {facts.get('bid_open_date') or '—'}; "
            f"close: {facts.get('bid_close_date') or '—'}.\n\n"
            f"_The Committee was constituted to evaluate the technical bids "
            f"received against this tender._"
        )
    if "verdicts" in facts:
        v = facts["verdicts"]
        return (
            f"## {label}\n\n"
            f"The Committee evaluated **{facts.get('bidder_count')} bidders** "
            f"against **{facts.get('criterion_count')} approved criteria**, "
            f"producing {facts.get('cells_total')} evaluation cells. "
            f"Pass: {v.get('PASS', 0)} · Fail: {v.get('FAIL', 0)} · "
            f"Review: {v.get('REVIEW', 0)}. "
            f"Open review items: {facts.get('open_review')}."
        )
    if "company_name" in facts:
        lines = [
            f"## {label}",
            "",
            f"**Bidder:** {facts['company_name']}  ",
            f"**PAN:** {facts.get('pan_number') or '—'} · "
            f"**GSTIN:** {facts.get('gstin') or '—'}  ",
            f"**State:** {facts.get('state')} · "
            f"**Debarment:** {facts.get('debarment_state')}",
            "",
        ]
        for c in facts.get("criteria", []):
            mark = {"PASS": "✓", "FAIL": "✗", "REVIEW": "?"}.get(c["verdict"], "·")
            mand = " [Mandatory]" if c.get("is_mandatory") else ""
            lines.append(
                f"- {mark} **{c['verdict']}**{mand} ({int(c['confidence']*100)}%) — "
                f"{c['criterion_text'][:140]}"
            )
        return "\n".join(lines)
    if "qualified" in facts:
        return (
            f"## {label}\n\n"
            f"**Qualified:** {', '.join(facts['qualified']) or 'None'}\n\n"
            f"**Excluded:** {', '.join(facts['excluded']) or 'None'}\n\n"
            f"Open items requiring further review: {facts.get('open_review_count')}.\n\n"
            f"_The Committee respectfully submits this report for the "
            f"competent authority's consideration._"
        )
    return f"## {label}\n\n_No content yet._"


def _insert_section(
    conn, *,
    draft_id: str, section_key: str, section_label: str,
    sort_order: int, body: str, authored_by: str, officer_id: str,
) -> dict:
    section_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO tec_report_sections
           (id, draft_id, section_key, section_label, sort_order,
            body, authored_by, last_edited_by, last_edited_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (section_id, draft_id, section_key, section_label, sort_order,
         body, authored_by, officer_id, now),
    )
    return {
        "id": section_id, "draft_id": draft_id, "section_key": section_key,
        "section_label": section_label, "sort_order": sort_order,
        "body": body, "authored_by": authored_by,
        "last_edited_by": officer_id, "last_edited_at": now,
    }


def _get_section_by_key(conn, draft_id: str, key: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM tec_report_sections "
        "WHERE draft_id = ? AND section_key = ?",
        (draft_id, key),
    ).fetchone()
    return dict(row) if row else None


def _insert_revision(
    conn, *,
    section_id: str, revision: int,
    body_before: Optional[str], body_after: str,
    change_source: str, edited_by: str, diff_summary: Optional[str],
) -> None:
    rev_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO tec_section_revisions
           (id, section_id, revision, body_before, body_after,
            diff_summary, change_source, edited_by, edited_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rev_id, section_id, revision, body_before, body_after,
         diff_summary, change_source, edited_by, now),
    )
