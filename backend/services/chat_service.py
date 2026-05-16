"""Tender Copilot chat — context assembly + streamed response.

The Copilot is the right-side AI panel inside every Tender Space.
It answers free-form questions about the current tender. Context is
assembled from the DB (criteria, bidders, evaluations, anomalies)
and passed to Claude via the COPILOT_CHAT system prompt, which
mandates:
- never invent facts
- always cite sources via [doc:DOC_ID#page=N]
- be concise
- never tell the officer what to decide

Both the user message and the assistant response are persisted to
tender_chats.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Iterator, Optional

from backend.ai import bedrock_client
from backend.ai.prompts import COPILOT_CHAT
from backend.core import audit_chain


def list_messages(conn, tender_id: str, *, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tender_chats WHERE tender_id = ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (tender_id, limit),
    ).fetchall()
    out = [_row_to_dict(r) for r in rows]
    out.reverse()
    return out


def post_message_streaming(
    conn,
    *,
    tender_id: str,
    question: str,
    officer_id: Optional[str] = None,
) -> Iterator[dict]:
    """Yield SSE-style events {"type": ..., "text": ...}.

    Persists both the user question and the assistant response.
    """
    # 1. Persist user message
    user_msg_id = _insert_message(
        conn, tender_id=tender_id, role="user", content=question,
        officer_id=officer_id,
    )
    yield {"type": "user_persisted", "id": user_msg_id}

    # 2. Build context
    context = _build_context(conn, tender_id)
    system_prompt = COPILOT_CHAT.system.format(context=context)
    user_prompt = COPILOT_CHAT.user_template.format(question=question)

    # 3. Stream
    full_text = ""
    invocation_id: Optional[str] = None
    for evt in bedrock_client.invoke_stream(
        invocation_type="copilot_chat",
        system=system_prompt,
        user=user_prompt,
        prompt_version=COPILOT_CHAT.version,
        tender_id=tender_id,
        conn=conn,
        use_cache=False,  # chat is intentionally non-cached
    ):
        if evt["type"] == "delta":
            full_text += evt["text"]
            yield evt
        elif evt["type"] == "done":
            full_text = evt.get("text", full_text)
            invocation_id = evt.get("invocation_id")
            # 4. Persist assistant message
            assistant_id = _insert_message(
                conn, tender_id=tender_id, role="assistant",
                content=full_text, officer_id=None,
                llm_invocation_id=invocation_id,
            )
            audit_chain.append(
                conn,
                tender_id=tender_id,
                event_type="copilot_message",
                event_data={
                    "user_message_id": user_msg_id,
                    "assistant_message_id": assistant_id,
                    "officer_id": officer_id,
                },
                actor=officer_id or "system",
            )
            yield {
                "type": "done",
                "text": full_text,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_id,
                "invocation_id": invocation_id,
            }
        elif evt["type"] == "error":
            yield evt


# ─── Context assembly ────────────────────────────────────────────────


def _build_context(conn, tender_id: str) -> str:
    """Build a compact textual context the model can reason over.

    Includes: tender metadata, criteria, bidders + verdicts, anomalies,
    document checklist status, verification results, uploaded documents,
    officer comments (classified), concurrence decisions, and TEC draft
    sections. This ensures the copilot knows EVERYTHING about the tender
    — officer thinking, AI analysis, and decisions are one unified view.

    Capped at ~8000 chars to keep latency/cost reasonable.
    """
    parts: list[str] = []

    tender = conn.execute(
        "SELECT tender_number, title, department, category, state, "
        "       estimated_cost, emd_amount FROM tenders WHERE id = ?",
        (tender_id,),
    ).fetchone()
    if tender:
        parts.append(
            f"Tender: {tender['tender_number']} — {tender['title']}\n"
            f"Department: {tender['department']} | Category: {tender['category']}\n"
            f"State: {tender['state']}"
        )

    # Criteria summary
    criteria = conn.execute(
        "SELECT criterion_text, criterion_type, is_mandatory, state "
        "FROM criteria WHERE tender_id = ? ORDER BY created_at LIMIT 25",
        (tender_id,),
    ).fetchall()
    if criteria:
        lines = ["\nCriteria:"]
        for c in criteria:
            mark = "M" if c["is_mandatory"] else " "
            lines.append(f"  [{mark}] ({c['criterion_type']}) {c['criterion_text'][:120]}")
        parts.append("\n".join(lines))

    # Bidders + verdicts
    bidders = conn.execute(
        "SELECT id, company_name, state, debarment_state FROM bidders "
        "WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()
    if bidders:
        parts.append("\nBidders:")
        for b in bidders:
            ev_counts = conn.execute(
                "SELECT verdict, COUNT(*) AS c FROM evaluations "
                "WHERE bidder_id = ? GROUP BY verdict",
                (b["id"],),
            ).fetchall()
            counts = {r["verdict"]: r["c"] for r in ev_counts}
            parts.append(
                f"  - {b['company_name']} (state={b['state']}, debarment={b['debarment_state']}) "
                f"PASS={counts.get('PASS', 0)} FAIL={counts.get('FAIL', 0)} "
                f"REVIEW={counts.get('REVIEW', 0)}"
            )

    # Open anomalies
    anomalies = conn.execute(
        "SELECT flag_type, severity, message FROM anomaly_flags "
        "WHERE tender_id = ? AND state = 'open' "
        "ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END "
        "LIMIT 8",
        (tender_id,),
    ).fetchall()
    if anomalies:
        parts.append("\nOpen anomaly flags:")
        for a in anomalies:
            parts.append(f"  [{a['severity'].upper()}] ({a['flag_type']}) {a['message']}")

    # Document checklist status per bidder
    if bidders:
        checklist_lines = []
        for b in bidders:
            responses = conn.execute(
                """SELECT cr.state, dc.document_label, dc.is_mandatory
                   FROM checklist_responses cr
                   JOIN document_checklist dc ON dc.id = cr.checklist_item_id
                   WHERE cr.tender_id = ? AND cr.bidder_id = ?""",
                (tender_id, b["id"]),
            ).fetchall()
            if responses:
                missing = [r for r in responses if r["state"] == "missing" and r["is_mandatory"]]
                present = [r for r in responses if r["state"] == "present"]
                partial = [r for r in responses if r["state"] in ("partial", "unclear")]
                line = f"  {b['company_name']}: {len(present)} present, {len(partial)} partial"
                if missing:
                    line += f", {len(missing)} MISSING mandatory: {', '.join(r['document_label'][:30] for r in missing[:3])}"
                checklist_lines.append(line)
        if checklist_lines:
            parts.append("\nDocument checklist status:")
            parts.extend(checklist_lines)

    # Verification results (GST, PAN, debarment checks)
    verifications = conn.execute(
        """SELECT v.bidder_id, v.verifier_name, v.status, v.notes, b.company_name
           FROM verification_results v
           JOIN bidders b ON b.id = v.bidder_id
           WHERE v.tender_id = ?
           ORDER BY b.company_name, v.verifier_name""",
        (tender_id,),
    ).fetchall()
    if verifications:
        parts.append("\nVerification results:")
        for v in verifications:
            note = f" ({v['notes'][:50]})" if v['notes'] else ""
            parts.append(f"  {v['company_name']} | {v['verifier_name']}: {v['status']}{note}")

    # Documents uploaded per bidder (summary)
    if bidders:
        doc_lines = []
        for b in bidders:
            docs = conn.execute(
                "SELECT doc_type, COUNT(*) AS c, SUM(page_count) AS pages "
                "FROM documents WHERE tender_id = ? AND bidder_id = ? "
                "GROUP BY doc_type",
                (tender_id, b["id"]),
            ).fetchall()
            if docs:
                doc_summary = ", ".join(f"{d['doc_type']}({d['c']})" for d in docs)
                total_pages = sum(d["pages"] or 0 for d in docs)
                doc_lines.append(f"  {b['company_name']}: {doc_summary} ({total_pages} pages total)")
        if doc_lines:
            parts.append("\nDocuments uploaded:")
            parts.extend(doc_lines)

    # Officer comments — the human's thinking, classified by AI
    comments = conn.execute(
        """SELECT c.body, c.category, c.affects_verdict, c.key_insight,
                  c.suggested_action, o.name AS officer_name, c.created_at
           FROM officer_comments c
           JOIN officers o ON o.id = c.officer_id
           WHERE c.tender_id = ?
           ORDER BY c.created_at DESC LIMIT 15""",
        (tender_id,),
    ).fetchall()
    if comments:
        parts.append("\nOfficer comments (most recent first):")
        for c in comments:
            cat_tag = f"[{c['category']}]" if c['category'] else ""
            verdict_flag = " ⚠️AFFECTS_VERDICT" if c['affects_verdict'] else ""
            insight = f" → AI insight: {c['key_insight']}" if c['key_insight'] else ""
            parts.append(
                f"  {c['officer_name']} {cat_tag}{verdict_flag}: "
                f"{c['body'][:150]}{insight}"
            )

    # Concurrence decisions — second-officer sign-offs
    concurrences = conn.execute(
        """SELECT cr.state, cr.request_reason, cr.decision_note,
                  o1.name AS requester, o2.name AS decider, cr.decided_at
           FROM concurrence_requests cr
           JOIN officers o1 ON o1.id = cr.requested_by
           LEFT JOIN officers o2 ON o2.id = cr.decided_by
           WHERE cr.tender_id = ?
           ORDER BY cr.created_at DESC LIMIT 5""",
        (tender_id,),
    ).fetchall()
    if concurrences:
        parts.append("\nConcurrence decisions:")
        for cr in concurrences:
            decider = cr['decider'] or 'pending'
            parts.append(
                f"  [{cr['state'].upper()}] {cr['requester']} → {decider}: "
                f"{cr['request_reason'][:80]}"
                f"{(' | Note: ' + cr['decision_note'][:80]) if cr['decision_note'] else ''}"
            )

    # TEC draft sections (if any) — so copilot knows what's been written
    tec_sections = conn.execute(
        """SELECT ts.section_label, ts.authored_by, ts.body
           FROM tec_report_sections ts
           JOIN tec_report_drafts td ON td.id = ts.draft_id
           WHERE td.tender_id = ? AND td.state = 'draft'
           ORDER BY ts.sort_order LIMIT 10""",
        (tender_id,),
    ).fetchall()
    if tec_sections:
        parts.append("\nTEC Report draft sections:")
        for s in tec_sections:
            parts.append(
                f"  [{s['authored_by']}] {s['section_label']}: "
                f"{s['body'][:200]}…"
            )

    text = "\n".join(parts)
    if len(text) > 8000:
        text = text[:8000] + "\n[truncated]"
    return text


# ─── Persistence ─────────────────────────────────────────────────────


def _insert_message(
    conn,
    *,
    tender_id: str,
    role: str,
    content: str,
    officer_id: Optional[str] = None,
    llm_invocation_id: Optional[str] = None,
    citations: Optional[list[dict]] = None,
) -> str:
    msg_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO tender_chats
           (id, tender_id, role, content, citations, officer_id,
            llm_invocation_id, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            msg_id, tender_id, role, content,
            json.dumps(citations) if citations else None,
            officer_id, llm_invocation_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return msg_id


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("citations"):
        try:
            d["citations"] = json.loads(d["citations"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
