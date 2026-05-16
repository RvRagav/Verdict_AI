"""Document upload + L1 dispatch.

Files are saved to the upload_dir and immediately processed by the
L1 pipeline (`pipeline.document_processing.process_document`). The
result includes the document row + per-page OCR + per-word bboxes.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

from backend.config import settings
from backend.pipeline import document_processing


def save_and_process(
    conn,
    *,
    tender_id: str,
    bidder_id: Optional[str],
    doc_type: str,
    filename: str,
    file_obj: BinaryIO,
    actor: str = "system",
) -> dict:
    """Persist the upload to disk, run L1, return the processed document."""
    target_dir = os.path.join(settings.upload_dir, tender_id)
    Path(target_dir).mkdir(parents=True, exist_ok=True)

    safe_name = _sanitise_filename(filename)
    target_path = os.path.join(target_dir, safe_name)

    # Avoid overwriting if the same name was used twice
    target_path = _resolve_collision(target_path)

    with open(target_path, "wb") as out:
        shutil.copyfileobj(file_obj, out)

    return document_processing.process_document(
        conn,
        tender_id=tender_id,
        bidder_id=bidder_id,
        doc_type=doc_type,
        file_path=target_path,
        actor=actor,
    )


def save_path_and_process(
    conn,
    *,
    tender_id: str,
    bidder_id: Optional[str],
    doc_type: str,
    src_path: str,
    actor: str = "system",
) -> dict:
    """Copy an existing file into the tender's upload dir, then process it.

    Used by the demo seed script — keeps demo files separate from the
    runtime upload directory.
    """
    target_dir = os.path.join(settings.upload_dir, tender_id)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    safe_name = _sanitise_filename(os.path.basename(src_path))
    target_path = _resolve_collision(os.path.join(target_dir, safe_name))
    shutil.copy2(src_path, target_path)
    return document_processing.process_document(
        conn,
        tender_id=tender_id,
        bidder_id=bidder_id,
        doc_type=doc_type,
        file_path=target_path,
        actor=actor,
    )


def get_document(conn, document_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ? AND deleted_at IS NULL",
        (document_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_documents(
    conn,
    *,
    tender_id: str,
    bidder_id: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> list[dict]:
    sql = "SELECT * FROM documents WHERE tender_id = ? AND deleted_at IS NULL"
    params: list = [tender_id]
    if bidder_id is not None:
        sql += " AND bidder_id = ?"
        params.append(bidder_id)
    if doc_type:
        sql += " AND doc_type = ?"
        params.append(doc_type)
    sql += " ORDER BY uploaded_at ASC"
    return [_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def get_pages(conn, document_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, page_number, image_path, raw_text, ocr_confidence, "
        "       width_px, height_px, processing_notes "
        "FROM pages WHERE document_id = ? ORDER BY page_number",
        (document_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_word_objects(conn, page_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, text_content, x_min, y_min, x_max, y_max, "
        "       confidence, source_engine "
        "FROM word_objects WHERE page_id = ? ORDER BY y_min, x_min",
        (page_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _sanitise_filename(name: str) -> str:
    """Strip path components and replace whitespace."""
    base = os.path.basename(name)
    return base.replace(" ", "_")


def _resolve_collision(path: str) -> str:
    """If the path exists, append _1, _2, … to the stem."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{base}_{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
