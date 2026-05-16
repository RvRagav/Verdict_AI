"""Evidence citations — bidirectional source link.

Every time an evaluation cites a phrase from a document, we record one
or more rows in `evidence_citations`. The forward direction lets the UI
draw bbox highlights on the cited PDF page; the reverse direction lets
the user hover any word in the PDF and see which evaluations rely on it.

A citation can target the page level (when we don't have an exact word
match) or the word level (when we do). The PDFViewer renders both.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain


def record(
    conn,
    *,
    evaluation_id: str,
    document_id: str,
    page_id: Optional[str] = None,
    word_object_id: Optional[str] = None,
    quote: Optional[str] = None,
    role: str = "supporting_quote",
    confidence: float = 1.0,
    actor: str = "system",
    audit: bool = False,
) -> str:
    """Insert one citation row. Idempotent on (evaluation_id, word_object_id)."""
    if word_object_id:
        existing = conn.execute(
            "SELECT id FROM evidence_citations "
            "WHERE evaluation_id = ? AND word_object_id = ? AND role = ?",
            (evaluation_id, word_object_id, role),
        ).fetchone()
        if existing:
            return existing["id"]

    citation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO evidence_citations
           (id, evaluation_id, document_id, page_id, word_object_id,
            quote, role, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (citation_id, evaluation_id, document_id, page_id, word_object_id,
         quote, role, confidence, now),
    )
    if audit:
        eval_row = conn.execute(
            "SELECT tender_id FROM evaluations WHERE id = ?", (evaluation_id,),
        ).fetchone()
        if eval_row:
            audit_chain.append(
                conn,
                tender_id=eval_row["tender_id"],
                event_type="evidence_citation_recorded",
                event_data={
                    "evaluation_id": evaluation_id,
                    "document_id": document_id,
                    "role": role,
                },
                actor=actor,
            )
    return citation_id


def list_for_evaluation(conn, evaluation_id: str) -> list[dict]:
    """Forward direction — every cited word/page for an evaluation."""
    rows = conn.execute(
        """SELECT ec.*, w.text_content, w.x_min, w.y_min, w.x_max, w.y_max,
                  p.page_number
           FROM evidence_citations ec
           LEFT JOIN word_objects w ON w.id = ec.word_object_id
           LEFT JOIN pages p ON p.id = ec.page_id
           WHERE ec.evaluation_id = ?
           ORDER BY ec.created_at""",
        (evaluation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_for_word(conn, word_object_id: str) -> list[dict]:
    """Reverse direction — every evaluation that cites this word."""
    rows = conn.execute(
        """SELECT ec.*, e.bidder_id, e.criterion_id, e.verdict, e.confidence,
                  c.criterion_text, b.company_name
           FROM evidence_citations ec
           JOIN evaluations e ON e.id = ec.evaluation_id
           JOIN criteria c ON c.id = e.criterion_id
           JOIN bidders b ON b.id = e.bidder_id
           WHERE ec.word_object_id = ?
           ORDER BY ec.created_at DESC""",
        (word_object_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_for_page(conn, page_id: str) -> list[dict]:
    """Every citation that lands on a given page (for overlay rendering)."""
    rows = conn.execute(
        """SELECT ec.*, w.x_min, w.y_min, w.x_max, w.y_max, w.text_content
           FROM evidence_citations ec
           LEFT JOIN word_objects w ON w.id = ec.word_object_id
           WHERE ec.page_id = ?
           ORDER BY ec.created_at""",
        (page_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def record_from_evaluation_evidence(
    conn,
    *,
    evaluation_id: str,
    evidence: dict,
    actor: str = "system",
) -> int:
    """Best-effort: lift citation rows from an evidence dict produced by L3.

    Looks at evidence.source_doc_id + evidence.source_page (and the
    'source_quote' or 'value.source_quote' field if present) and creates
    citation rows. Returns the number created.
    """
    doc_id = evidence.get("source_doc_id")
    if not doc_id:
        return 0
    page_num = evidence.get("source_page")
    page_id: Optional[str] = None
    if page_num is not None:
        row = conn.execute(
            "SELECT id FROM pages WHERE document_id = ? AND page_number = ?",
            (doc_id, page_num),
        ).fetchone()
        if row:
            page_id = row["id"]

    quote = None
    val = evidence.get("value")
    if isinstance(val, dict):
        quote = val.get("source_quote") or val.get("key_quote")

    # Find a word object that contains the first 30 chars of the quote
    # so the front-end can highlight it.
    word_object_id: Optional[str] = None
    if quote and page_id:
        needle = quote.lower().strip().split()
        if needle:
            row = conn.execute(
                """SELECT id FROM word_objects
                   WHERE page_id = ? AND lower(text_content) = ?
                   LIMIT 1""",
                (page_id, needle[0]),
            ).fetchone()
            if row:
                word_object_id = row["id"]

    citation_id = record(
        conn,
        evaluation_id=evaluation_id,
        document_id=doc_id,
        page_id=page_id,
        word_object_id=word_object_id,
        quote=quote,
        role="extracted_value",
        confidence=float(evidence.get("extraction_confidence") or 0.7),
        actor=actor,
        audit=False,
    )
    return 1 if citation_id else 0
