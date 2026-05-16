"""Report generation — Tender Evaluation Committee (TEC) PDF.

The report is the official output: signed by the officers, given to
the procurement committee, and archived. It must contain enough detail
that anyone reading it later can reconstruct the decision logic.

Implementation notes:
- Uses ReportLab (already in requirements.txt) for portability
- Saves to settings.reports_dir/<tender_id>/<timestamp>.pdf
- File hash is recorded in the reports table (anti-tamper)
- An audit event 'report_generated' chains to the rest of the trail
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.core import audit_chain
from backend.services import (
    bidder_service,
    criteria_service,
    evaluation_service,
    tender_service,
)
from backend.utils.hashing import sha256_file


def generate_report(
    conn,
    *,
    tender_id: str,
    officer_id: str,
) -> dict:
    """Generate the TEC PDF for a tender. Returns the report row."""
    tender = tender_service.get_tender(conn, tender_id)
    if not tender:
        raise ValueError(f"Tender not found: {tender_id}")

    out_dir = os.path.join(settings.reports_dir, tender_id)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(out_dir, f"TEC_{stamp}.pdf")

    bidders = bidder_service.list_bidders(conn, tender_id)
    criteria = [c for c in criteria_service.list_criteria(conn, tender_id)
                if c["state"] == "approved"]
    evaluations = evaluation_service.list_evaluations(conn, tender_id=tender_id)
    by_pair = {(e["bidder_id"], e["criterion_id"]): e for e in evaluations}

    _render_pdf(
        out_path=out_path,
        tender=tender,
        bidders=bidders,
        criteria=criteria,
        by_pair=by_pair,
        officer_id=officer_id,
    )

    file_hash = sha256_file(out_path)
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO reports
           (id, tender_id, file_path, sha256_hash, generated_by, generated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (report_id, tender_id, out_path, file_hash, officer_id, now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="report_generated",
        event_data={
            "report_id": report_id,
            "file_path": out_path,
            "sha256_hash": file_hash,
        },
        actor=officer_id,
    )
    if tender["state"] == "EVALUATION_COMPLETE":
        tender_service.transition_state(
            conn, tender_id=tender_id, target_state="REPORT_GENERATED",
            actor=officer_id,
        )

    return {
        "id": report_id,
        "tender_id": tender_id,
        "file_path": out_path,
        "sha256_hash": file_hash,
        "generated_by": officer_id,
        "generated_at": now,
    }


def list_reports(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM reports WHERE tender_id = ? ORDER BY generated_at DESC",
        (tender_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_report(conn, report_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return dict(row) if row else None


# ─── Co-authored draft rendering ────────────────────────────────────


def generate_report_from_draft(
    conn,
    *,
    tender_id: str,
    officer_id: str,
    sections: list[dict],
) -> dict:
    """Render a finalised TEC draft (officer-edited section bodies) to
    PDF. Each section's authored_by is stamped beside the heading so
    the reader sees who wrote what.
    """
    tender = tender_service.get_tender(conn, tender_id)
    if not tender:
        raise ValueError(f"Tender not found: {tender_id}")

    out_dir = os.path.join(settings.reports_dir, tender_id)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(out_dir, f"TEC_{stamp}.pdf")

    _render_draft_pdf(
        out_path=out_path,
        tender=tender,
        officer_id=officer_id,
        sections=sections,
    )

    file_hash = sha256_file(out_path)
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO reports
           (id, tender_id, file_path, sha256_hash, generated_by, generated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (report_id, tender_id, out_path, file_hash, officer_id, now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="report_generated",
        event_data={
            "report_id": report_id,
            "file_path": out_path,
            "sha256_hash": file_hash,
            "from_draft": True,
            "section_count": len(sections),
        },
        actor=officer_id,
    )
    if tender["state"] == "EVALUATION_COMPLETE":
        tender_service.transition_state(
            conn, tender_id=tender_id, target_state="REPORT_GENERATED",
            actor=officer_id,
        )

    return {
        "id": report_id,
        "tender_id": tender_id,
        "file_path": out_path,
        "sha256_hash": file_hash,
        "generated_by": officer_id,
        "generated_at": now,
    }


# ─── PDF rendering ──────────────────────────────────────────────────


def _render_pdf(
    *,
    out_path: str,
    tender: dict,
    bidders: list[dict],
    criteria: list[dict],
    by_pair: dict[tuple[str, str], dict],
    officer_id: str,
) -> None:
    """Render the TEC report. Uses reportlab.platypus for a real document."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=18,
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=14,
        textColor=colors.HexColor("#1a3a5c"), spaceBefore=14, spaceAfter=6,
    )
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=8, leading=11,
        textColor=colors.HexColor("#555"),
    )

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    flow = []
    flow.append(Paragraph("Tender Evaluation Committee Report", title_style))
    flow.append(Paragraph(
        f"Tender No. <b>{tender['tender_number']}</b><br/>"
        f"<b>{tender['title']}</b>", body))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(
        f"Department: {tender['department']} &nbsp;&nbsp; "
        f"Category: {tender['category']}<br/>"
        f"Generated by: {officer_id} &nbsp;&nbsp; "
        f"Generated at (UTC): {datetime.now(timezone.utc).isoformat()}",
        small,
    ))

    flow.append(Paragraph("Summary", h2))
    summary_rows = [
        ["Bidders evaluated", str(len(bidders))],
        ["Criteria evaluated", str(len(criteria))],
        ["Total cells", str(len(bidders) * len(criteria))],
    ]
    summary_tbl = Table(summary_rows, colWidths=[6*cm, 6*cm])
    summary_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaa")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ddd")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(summary_tbl)

    # Comparative matrix
    flow.append(Paragraph("Comparative Matrix", h2))
    header = ["Criterion"] + [b["company_name"][:18] for b in bidders]
    matrix_rows = [header]
    for c in criteria:
        row_cells = [c["criterion_text"][:60] + ("…" if len(c["criterion_text"]) > 60 else "")]
        for b in bidders:
            ev = by_pair.get((b["id"], c["id"]))
            if ev:
                row_cells.append(f"{ev['verdict']} ({int(ev['confidence']*100)}%)")
            else:
                row_cells.append("—")
        matrix_rows.append(row_cells)

    col_widths = [7*cm] + [(11*cm)/max(1, len(bidders))] * len(bidders)
    tbl = Table(matrix_rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ccc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaa")),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]
    # colour each verdict cell
    for row_i, row_cells in enumerate(matrix_rows[1:], start=1):
        for col_i, txt in enumerate(row_cells[1:], start=1):
            colour = None
            if txt.startswith("PASS"):
                colour = colors.HexColor("#e7f6e7")
            elif txt.startswith("FAIL"):
                colour = colors.HexColor("#fbe3e3")
            elif txt.startswith("REVIEW"):
                colour = colors.HexColor("#fff5d6")
            if colour:
                style.append(("BACKGROUND", (col_i, row_i), (col_i, row_i), colour))
    tbl.setStyle(TableStyle(style))
    flow.append(tbl)

    # Per-bidder detail
    for b in bidders:
        flow.append(PageBreak())
        flow.append(Paragraph(f"Bidder: {b['company_name']}", h2))
        flow.append(Paragraph(
            f"PAN: {b.get('pan_number') or '-'} &nbsp;&nbsp; "
            f"GSTIN: {b.get('gstin') or '-'}<br/>"
            f"State: {b['state']} &nbsp;&nbsp; "
            f"Debarment: {b['debarment_state']}",
            small,
        ))
        for c in criteria:
            ev = by_pair.get((b["id"], c["id"]))
            flow.append(Spacer(1, 6))
            flow.append(Paragraph(f"<b>{c['criterion_text']}</b>", body))
            if not ev:
                flow.append(Paragraph("Not evaluated.", small))
                continue
            flow.append(Paragraph(
                f"Verdict: <b>{ev['verdict']}</b> "
                f"(confidence {int(ev['confidence']*100)}%) — "
                f"Route: {ev['route']}",
                body,
            ))
            if ev.get("routing_reason"):
                flow.append(Paragraph(ev["routing_reason"], small))

    doc.build(flow)


# ─── Co-authored draft → PDF renderer ───────────────────────────────


def _render_draft_pdf(
    *,
    out_path: str,
    tender: dict,
    officer_id: str,
    sections: list[dict],
) -> None:
    """Render an officer-curated draft (already-edited section bodies)
    into a TEC PDF. Each section heading carries an authored_by chip
    so the reader sees who wrote what.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=18,
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=14,
        textColor=colors.HexColor("#1a3a5c"), spaceBefore=14, spaceAfter=6,
    )
    h3 = ParagraphStyle(
        "h3", parent=styles["Heading3"], fontSize=12,
        textColor=colors.HexColor("#1a3a5c"), spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=8, leading=11,
        textColor=colors.HexColor("#555"),
    )
    chip_ai = ParagraphStyle(
        "chip_ai", parent=styles["BodyText"], fontSize=8, leading=10,
        textColor=colors.HexColor("#7c4dff"),
    )
    chip_co = ParagraphStyle(
        "chip_co", parent=styles["BodyText"], fontSize=8, leading=10,
        textColor=colors.HexColor("#0a7d34"),
    )
    chip_off = ParagraphStyle(
        "chip_off", parent=styles["BodyText"], fontSize=8, leading=10,
        textColor=colors.HexColor("#0a4d8c"),
    )

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    flow = []
    flow.append(Paragraph("Tender Evaluation Committee Report", title))
    flow.append(Paragraph(
        f"Tender No. <b>{tender['tender_number']}</b><br/>"
        f"<b>{tender['title']}</b>",
        body,
    ))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(
        f"Department: {tender['department']} &nbsp;&nbsp; "
        f"Category: {tender['category']}<br/>"
        f"Finalised by: {officer_id} &nbsp;&nbsp; "
        f"At (UTC): {datetime.now(timezone.utc).isoformat()}",
        small,
    ))
    flow.append(Spacer(1, 8))

    chip_for = {
        "ai": ("AI draft", chip_ai),
        "co-authored": ("Co-authored", chip_co),
        "officer": ("Officer-authored", chip_off),
    }

    for sec in sections:
        flow.append(PageBreak() if sec["sort_order"] > 0 else Spacer(1, 6))
        flow.append(Paragraph(sec["section_label"], h2))
        chip_text, chip_style = chip_for.get(
            sec["authored_by"], ("Unknown", small),
        )
        flow.append(Paragraph(f"[{chip_text}]", chip_style))
        flow.append(Spacer(1, 4))
        for para in _markdown_to_paragraphs(sec["body"], body, h3):
            flow.append(para)

    doc.build(flow)


def _markdown_to_paragraphs(md: str, body_style, h3_style):
    """Lightweight Markdown → reportlab.Paragraph list. Handles
    headings (## / ###), bullets (- / *), bold (**x**), italics (_x_),
    blank-line paragraph breaks. Good enough for officer-edited TEC prose.
    """
    from reportlab.platypus import Paragraph, Spacer
    out = []
    if not md:
        return out
    # Strip leading "## Heading" the section already shows the label
    lines = (md or "").splitlines()
    buf: list[str] = []

    def flush_buf():
        if not buf:
            return
        text = " ".join(buf).strip()
        if text:
            out.append(Paragraph(_md_inline(text), body_style))
            out.append(Spacer(1, 4))
        buf.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_buf()
            continue
        if line.startswith("## "):
            flush_buf()
            # already shown as section heading; render as h3 if duplicated
            heading = line[3:].strip()
            out.append(Paragraph(_md_inline(heading), h3_style))
            continue
        if line.startswith("### "):
            flush_buf()
            out.append(Paragraph(_md_inline(line[4:].strip()), h3_style))
            continue
        if line.lstrip().startswith(("- ", "* ", "• ")):
            flush_buf()
            item = line.lstrip()[2:].strip()
            out.append(Paragraph(f"• {_md_inline(item)}", body_style))
            continue
        buf.append(line)
    flush_buf()
    return out


def _md_inline(text: str) -> str:
    """Convert a small subset of Markdown inline markup into reportlab's
    mini-HTML (safe + sufficient for TEC prose).
    """
    import re
    # Escape HTML special chars first
    safe = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    # Bold **text**
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    # Italic _text_  (only between word chars to avoid eating dashes)
    safe = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<i>\1</i>", safe)
    # Inline code `text`
    safe = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", safe)
    return safe
