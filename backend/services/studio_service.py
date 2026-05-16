"""Document Studio — officer-authored docs co-written with AI.

Lives inside the Copilot panel as a second tab. Officer types a vague
need ("brief for my CO covering the smell-test signals"), AI clarifies
once if needed, then drafts. Officer chats with edits ("shorten section
2"). Each AI turn returns the FULL revised document. Once the officer
is happy, they click Finalise — the doc renders to PDF + lands in the
File Vault tagged officer_authored=true.

Streaming chat keeps the conversation alive; every turn is persisted.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from backend.ai import bedrock_client
from backend.ai.prompts import STUDIO_AUTHOR
from backend.config import settings
from backend.core import audit_chain
from backend.utils.hashing import sha256_file


_DOC_TAG = re.compile(r"<document>(.*?)</document>", re.DOTALL | re.IGNORECASE)


# ─── Doc CRUD ───────────────────────────────────────────────────────


def create_doc(
    conn, *,
    tender_id: str,
    officer_id: str,
    title: str,
    doc_kind: str = "brief",
) -> dict:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO studio_documents
           (id, tender_id, officer_id, title, doc_kind,
            rendered_body, state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '', 'draft', ?, ?)""",
        (doc_id, tender_id, officer_id, title.strip() or "Untitled",
         doc_kind, now, now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="studio_doc_created",
        event_data={
            "doc_id": doc_id,
            "title": title,
            "doc_kind": doc_kind,
        },
        actor=officer_id,
    )
    return get_doc(conn, doc_id)


def get_doc(conn, doc_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM studio_documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    return dict(row) if row else None


def list_docs(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM studio_documents WHERE tender_id = ? "
        "ORDER BY updated_at DESC",
        (tender_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_messages(conn, doc_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM studio_messages WHERE document_id = ? "
        "ORDER BY timestamp ASC",
        (doc_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Streaming chat ─────────────────────────────────────────────────


def post_message_streaming(
    conn,
    *,
    doc_id: str,
    message: str,
    officer_id: Optional[str] = None,
) -> Iterator[dict]:
    """Officer sends a message. Yields SSE events:
       - delta: assistant text chunks
       - done:  final text + extracted_body (if a <document> block was
                returned), and the persisted IDs.
    """
    doc = get_doc(conn, doc_id)
    if not doc:
        yield {"type": "error", "error": "doc_not_found"}
        return
    if doc["state"] == "finalised":
        yield {"type": "error", "error": "doc_finalised"}
        return

    tender_id = doc["tender_id"]
    user_msg_id = _insert_message(
        conn, doc_id=doc_id, role="user", content=message,
    )
    yield {"type": "user_persisted", "id": user_msg_id}

    history = _format_history(conn, doc_id)
    context = _build_tender_context(conn, tender_id)

    user_prompt = STUDIO_AUTHOR.user_template.format(
        context=context,
        history=history or "(this is the start of the conversation)",
        message=message,
    )

    full_text = ""
    invocation_id: Optional[str] = None

    for evt in bedrock_client.invoke_stream(
        invocation_type="studio_author",
        system=STUDIO_AUTHOR.system,
        user=user_prompt,
        prompt_version=STUDIO_AUTHOR.version,
        tender_id=tender_id,
        conn=conn,
        use_cache=False,
        max_tokens=3000,
    ):
        if evt["type"] == "delta":
            full_text += evt["text"]
            yield evt
        elif evt["type"] == "done":
            full_text = evt.get("text", full_text)
            invocation_id = evt.get("invocation_id")

            extracted = _extract_doc_body(full_text)
            assistant_msg_id = _insert_message(
                conn,
                doc_id=doc_id,
                role="assistant",
                content=full_text,
                rendered_body=extracted,
                llm_invocation_id=invocation_id,
            )
            if extracted:
                _update_rendered_body(conn, doc_id, extracted)

            audit_chain.append(
                conn,
                tender_id=tender_id,
                event_type="studio_doc_message",
                event_data={
                    "doc_id": doc_id,
                    "user_message_id": user_msg_id,
                    "assistant_message_id": assistant_msg_id,
                    "body_updated": bool(extracted),
                },
                actor=officer_id or "system",
            )
            yield {
                "type": "done",
                "text": full_text,
                "rendered_body": extracted,
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
            }
        elif evt["type"] == "error":
            yield evt


# ─── Finalise ───────────────────────────────────────────────────────


def finalise_doc(
    conn, *, doc_id: str, officer_id: str,
) -> dict:
    """Render the doc's current rendered_body to a Markdown file on
    disk + sha256-stamp it. (PDF rendering is the same path as TEC
    later — for now Markdown is what officers download.)
    """
    doc = get_doc(conn, doc_id)
    if not doc:
        raise ValueError(f"Doc not found: {doc_id}")
    if doc["state"] == "finalised":
        return doc
    if not (doc["rendered_body"] or "").strip():
        raise ValueError("Cannot finalise an empty document.")

    out_dir = os.path.join(settings.reports_dir, doc["tender_id"], "studio")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", doc["title"]).strip("_") or "studio_doc"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(out_dir, f"{safe_title}_{stamp}.pdf")

    _render_studio_pdf(
        out_path=out_path,
        title=doc["title"],
        body_md=doc["rendered_body"],
        officer_id=officer_id,
        tender_id=doc["tender_id"],
    )

    file_hash = sha256_file(out_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE studio_documents
           SET state = 'finalised', file_path = ?, sha256_hash = ?,
               finalised_at = ?, updated_at = ?
           WHERE id = ?""",
        (out_path, file_hash, now, now, doc_id),
    )
    audit_chain.append(
        conn,
        tender_id=doc["tender_id"],
        event_type="studio_doc_finalised",
        event_data={
            "doc_id": doc_id,
            "file_path": out_path,
            "sha256_hash": file_hash,
        },
        actor=officer_id,
    )
    return get_doc(conn, doc_id)


def _render_studio_pdf(
    *, out_path: str, title: str, body_md: str, officer_id: str, tender_id: str,
) -> None:
    """Render a Studio Markdown body to a PDF, reusing the TEC inline
    Markdown→reportlab helper. Cover-page header carries title +
    authored-by + tender ref + sha-stamp footer."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    from backend.services.report_service import _markdown_to_paragraphs

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=20,
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=14,
    )
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=10.5, leading=15,
    )
    h3 = ParagraphStyle(
        "h3", parent=styles["Heading3"], fontSize=12,
        textColor=colors.HexColor("#1a3a5c"), spaceBefore=8, spaceAfter=4,
    )
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=8, leading=11,
        textColor=colors.HexColor("#666"),
    )

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    flow = []
    flow.append(Paragraph(title, title_style))
    flow.append(Paragraph(
        f"Authored by {officer_id} · "
        f"{datetime.now(timezone.utc).strftime('%d %b %Y · %H:%M UTC')} · "
        f"Tender {tender_id[:8]}",
        small,
    ))
    flow.append(Spacer(1, 10))
    for para in _markdown_to_paragraphs(body_md or "", body, h3):
        flow.append(para)
    doc.build(flow)


# ─── Helpers ────────────────────────────────────────────────────────


def _insert_message(
    conn, *,
    doc_id: str, role: str, content: str,
    rendered_body: Optional[str] = None,
    llm_invocation_id: Optional[str] = None,
) -> str:
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO studio_messages
           (id, document_id, role, content, rendered_body,
            llm_invocation_id, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (msg_id, doc_id, role, content, rendered_body,
         llm_invocation_id, now),
    )
    return msg_id


def _update_rendered_body(conn, doc_id: str, body: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE studio_documents SET rendered_body = ?, updated_at = ? "
        "WHERE id = ?",
        (body, now, doc_id),
    )


def _format_history(conn, doc_id: str) -> str:
    rows = conn.execute(
        "SELECT role, content FROM studio_messages "
        "WHERE document_id = ? ORDER BY timestamp ASC",
        (doc_id,),
    ).fetchall()
    if not rows:
        return ""
    lines = ["CONVERSATION SO FAR:"]
    for r in rows[-10:]:           # last 10 turns is plenty
        speaker = "Officer" if r["role"] == "user" else "Studio"
        snippet = (r["content"] or "")[:1200]
        lines.append(f"{speaker}: {snippet}")
    return "\n\n".join(lines)


def _build_tender_context(conn, tender_id: str) -> str:
    """Compact tender state — same shape Copilot uses, slimmer."""
    parts: list[str] = []
    t = conn.execute(
        "SELECT tender_number, title, department, category, state, "
        "       estimated_cost FROM tenders WHERE id = ?",
        (tender_id,),
    ).fetchone()
    if t:
        parts.append(
            f"Tender: {t['tender_number']} — {t['title']}\n"
            f"Department: {t['department']} | Category: {t['category']} | "
            f"State: {t['state']}"
        )
    bidders = conn.execute(
        "SELECT id, company_name, state FROM bidders "
        "WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()
    if bidders:
        parts.append("Bidders:")
        for b in bidders:
            counts = {r["verdict"]: r["c"] for r in conn.execute(
                "SELECT verdict, COUNT(*) c FROM evaluations "
                "WHERE bidder_id = ? GROUP BY verdict",
                (b["id"],),
            ).fetchall()}
            parts.append(
                f"  - {b['company_name']} ({b['state']}) "
                f"PASS={counts.get('PASS', 0)} "
                f"FAIL={counts.get('FAIL', 0)} "
                f"REVIEW={counts.get('REVIEW', 0)}"
            )
    crit_count = conn.execute(
        "SELECT COUNT(*) c FROM criteria WHERE tender_id = ? AND state = 'approved'",
        (tender_id,),
    ).fetchone()["c"]
    parts.append(f"Approved criteria: {crit_count}")

    anomalies = conn.execute(
        "SELECT flag_type, severity, message FROM anomaly_flags "
        "WHERE tender_id = ? AND state = 'open' AND severity = 'high' "
        "LIMIT 5",
        (tender_id,),
    ).fetchall()
    if anomalies:
        parts.append("High-severity smell-test signals:")
        for a in anomalies:
            parts.append(f"  - [{a['flag_type']}] {a['message'][:140]}")

    text = "\n".join(parts)
    return text[:3500]


def _extract_doc_body(text: str) -> Optional[str]:
    if not text:
        return None
    m = _DOC_TAG.search(text)
    if not m:
        return None
    return m.group(1).strip()
