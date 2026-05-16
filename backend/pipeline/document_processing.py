"""Document processing pipeline (L1).

Takes an uploaded file and produces:
- a `documents` row with sha256 + page count + processing state
- one `pages` row per page (with raw_text + image_path + ocr_confidence)
- many `word_objects` rows (per-word bboxes for source-highlighting)
- audit events: `document_received`, `document_processed`

Format dispatch:
    .pdf  → pdfplumber for text + pdf2image for raster + Tesseract on scanned pages
    .docx → python-docx, treated as a single logical page, no OCR
    image → Pillow normalise + OpenCV preprocess + Tesseract OCR

The function is idempotent on file_path × tender_id × bidder_id (the
caller's responsibility — we don't dedupe here).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.ai import vision_ocr
from backend.config import settings
from backend.core import audit_chain
from backend.utils.file_types import detect_format
from backend.utils.hashing import sha256_file
from backend.utils import pdf_io, ocr

logger = logging.getLogger(__name__)


def process_document(
    conn,
    *,
    tender_id: str,
    bidder_id: str | None,
    doc_type: str,
    file_path: str,
    actor: str = "system",
) -> dict:
    """Run the full L1 pipeline for one file. Returns the document dict."""
    document_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    uploaded_at = datetime.now(timezone.utc).isoformat()

    file_hash = sha256_file(file_path)
    fmt = detect_format(filename)

    if fmt == "pdf":
        parsed = pdf_io.parse_pdf(file_path)
    elif fmt == "docx":
        parsed = pdf_io.parse_docx(file_path)
    elif fmt == "image":
        parsed = pdf_io.parse_image(file_path)
    else:
        parsed = {"error": True, "message": f"Unsupported format: {fmt}",
                  "page_count": 0, "pages": [], "is_scanned": False}

    # Capture which criterion-version was in effect for THIS tender at the
    # time this bidder uploaded — the Calcutta HC defensibility. Bidder
    # submissions get the current max criterion version; tender-level docs
    # (NIT, corrigendum) keep it NULL.
    crit_version_at_upload = None
    if doc_type == "bidder_submission" or bidder_id:
        max_v = conn.execute(
            """SELECT MAX(current_version) AS v FROM criteria
               WHERE tender_id = ? AND state = 'approved'""",
            (tender_id,),
        ).fetchone()
        if max_v and max_v["v"] is not None:
            crit_version_at_upload = int(max_v["v"])

    # Insert documents row up front so we have an ID for FK references
    conn.execute(
        """INSERT INTO documents
           (id, tender_id, bidder_id, doc_type, filename, file_path,
            sha256_hash, page_count, avg_ocr_conf, processing_state,
            metadata, uploaded_at, criterion_version_at_upload)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (
            document_id, tender_id, bidder_id, doc_type, filename, file_path,
            file_hash, parsed.get("page_count", 0),
            "error" if parsed.get("error") else "processing",
            None, uploaded_at, crit_version_at_upload,
        ),
    )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="document_received",
        event_data={
            "document_id": document_id,
            "filename": filename,
            "doc_type": doc_type,
            "format": fmt,
            "sha256_hash": file_hash,
            "page_count": parsed.get("page_count", 0),
        },
        actor=actor,
    )

    if parsed.get("error"):
        return _doc_dict(document_id, tender_id, bidder_id, doc_type,
                         filename, file_path, file_hash, 0, 0.0,
                         "error", uploaded_at, [],
                         error=parsed.get("message"))

    # Rasterise pages for the inline viewer + OCR if scanned
    page_dir = os.path.join(settings.pages_dir, document_id)
    Path(page_dir).mkdir(parents=True, exist_ok=True)

    if fmt == "pdf":
        page_images = pdf_io.rasterise_pdf(file_path, page_dir)
    elif fmt == "image":
        page_images = pdf_io.copy_image_as_page(file_path, page_dir)
    else:
        page_images = []

    is_scanned = parsed.get("is_scanned", False)
    page_confidences: list[float] = []
    pages_out: list[dict] = []

    for idx, page_meta in enumerate(parsed["pages"]):
        page_id = str(uuid.uuid4())
        page_number = page_meta["page_number"]
        embedded_text = page_meta.get("text", "")
        image_path = page_images[idx] if idx < len(page_images) else None

        if fmt == "docx":
            raw_text = embedded_text
            words: list[dict] = _synth_words_from_text(page_id, raw_text)
            page_conf = 0.95
            processed_image = ""
        elif image_path and (is_scanned or not embedded_text.strip()):
            # Vision-first OCR: try Bedrock vision (Claude Sonnet 4.5
            # multimodal), fall back to Tesseract if it fails or is
            # disabled. Cached on image hash so re-running is free.
            vision_result = vision_ocr.ocr_image(
                image_path, conn=conn, tender_id=tender_id,
            )
            if vision_result.error or not vision_result.raw_text.strip():
                # Fallback path
                processed_image = ocr.preprocess(image_path)
                ocr_result = ocr.ocr_image(processed_image)
                raw_text = ocr_result["raw_text"]
                words = ocr_result["words"]
                page_conf = ocr_result["page_confidence"]
            else:
                # Vision succeeded
                processed_image = image_path  # original; vision needs no preprocess
                raw_text = vision_result.raw_text
                words = vision_result.words
                page_conf = vision_result.page_confidence
            for w in words:
                w["page_id"] = page_id
        else:
            raw_text = embedded_text
            words = _synth_words_from_text(page_id, raw_text)
            page_conf = 0.95
            processed_image = image_path or ""

        page_confidences.append(page_conf)

        conn.execute(
            """INSERT INTO pages
               (id, document_id, page_number, image_path, raw_text,
                ocr_confidence, processing_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (page_id, document_id, page_number, processed_image,
             raw_text, page_conf, fmt),
        )

        for w in words:
            word_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO word_objects
                   (id, page_id, text_content, x_min, y_min, x_max, y_max,
                    confidence, source_engine)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (word_id, page_id, w["text_content"],
                 w["x_min"], w["y_min"], w["x_max"], w["y_max"],
                 w["confidence"], w.get("source_engine", "embedded")),
            )

        pages_out.append({
            "id": page_id, "page_number": page_number,
            "image_path": processed_image, "raw_text": raw_text,
            "ocr_confidence": page_conf,
        })

    avg_conf = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0

    conn.execute(
        "UPDATE documents SET avg_ocr_conf = ?, processing_state = 'complete' "
        "WHERE id = ?",
        (avg_conf, document_id),
    )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="document_processed",
        event_data={
            "document_id": document_id,
            "page_count": parsed["page_count"],
            "avg_ocr_conf": round(avg_conf, 4),
            "is_scanned": is_scanned,
        },
        actor=actor,
    )

    return _doc_dict(document_id, tender_id, bidder_id, doc_type,
                     filename, file_path, file_hash,
                     parsed["page_count"], avg_conf,
                     "complete", uploaded_at, pages_out)


def _doc_dict(*args, error: str | None = None):
    (document_id, tender_id, bidder_id, doc_type, filename, file_path,
     file_hash, page_count, avg_conf, state, uploaded_at, pages) = args
    out = {
        "id": document_id,
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "doc_type": doc_type,
        "filename": filename,
        "file_path": file_path,
        "sha256_hash": file_hash,
        "page_count": page_count,
        "avg_ocr_conf": round(avg_conf, 4),
        "processing_state": state,
        "uploaded_at": uploaded_at,
        "pages": pages,
    }
    if error:
        out["error"] = error
    return out


def _synth_words_from_text(page_id: str, text: str) -> list[dict]:
    """For embedded-text pages we don't have real bboxes; lay tokens out
    on a deterministic grid so source highlighting still shows *something*.

    The frontend prefers the OCR pipeline's true bboxes; this is a fallback.
    """
    words: list[dict] = []
    if not text:
        return words
    x_cursor = 0.05
    y_cursor = 0.05
    line_height = 0.018
    char_width = 0.0065
    for token in text.split():
        if not token.strip():
            continue
        w = len(token) * char_width
        if x_cursor + w > 0.95:
            x_cursor = 0.05
            y_cursor += line_height
        if y_cursor > 0.95:
            break  # don't synthesise off-page boxes
        words.append({
            "text_content": token,
            "x_min": round(x_cursor, 4),
            "y_min": round(y_cursor, 4),
            "x_max": round(x_cursor + w, 4),
            "y_max": round(y_cursor + 0.014, 4),
            "confidence": 0.95,
            "source_engine": "embedded",
        })
        x_cursor += w + 0.005
    return words
