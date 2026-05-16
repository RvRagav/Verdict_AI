"""File type detection and accepted formats."""

from __future__ import annotations

from pathlib import Path


PDF_EXTS  = {".pdf"}
DOCX_EXTS = {".docx"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

ACCEPTED_EXTS = PDF_EXTS | DOCX_EXTS | IMAGE_EXTS


def detect_format(filename: str) -> str:
    """Return one of: 'pdf', 'docx', 'image', 'unknown'."""
    ext = Path(filename).suffix.lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in IMAGE_EXTS:
        return "image"
    return "unknown"


def is_accepted(filename: str) -> bool:
    return detect_format(filename) != "unknown"
