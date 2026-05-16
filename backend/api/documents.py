"""Document upload + read endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.api.dependencies import get_actor, get_db
from backend.services import document_service


router = APIRouter(prefix="/tenders/{tender_id}", tags=["documents"])


@router.post("/documents")
async def upload_document(
    tender_id: str,
    doc_type: str = Form(...),
    bidder_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    if doc_type not in {"nit", "corrigendum", "bidder_submission",
                         "certificate", "attachment"}:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type {doc_type!r}")
    return document_service.save_and_process(
        conn,
        tender_id=tender_id,
        bidder_id=bidder_id,
        doc_type=doc_type,
        filename=file.filename or "upload.bin",
        file_obj=file.file,
        actor=actor,
    )


@router.get("/documents")
def list_documents(
    tender_id: str,
    bidder_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    conn=Depends(get_db),
):
    return {
        "documents": document_service.list_documents(
            conn, tender_id=tender_id, bidder_id=bidder_id, doc_type=doc_type,
        )
    }


# ─── Document detail (separate prefix) ──────────────────────────────


detail_router = APIRouter(prefix="/documents", tags=["documents"])


@detail_router.get("/{document_id}")
def get_document(document_id: str, conn=Depends(get_db)):
    doc = document_service.get_document(conn, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    pages = document_service.get_pages(conn, document_id)
    doc["pages"] = pages
    return doc


@detail_router.get("/{document_id}/pages/{page_number}")
def get_page(document_id: str, page_number: int, conn=Depends(get_db)):
    pages = document_service.get_pages(conn, document_id)
    page = next((p for p in pages if p["page_number"] == page_number), None)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    page["word_objects"] = document_service.get_word_objects(conn, page["id"])
    return page


@detail_router.get("/{document_id}/file")
def get_file(document_id: str, conn=Depends(get_db)):
    doc = document_service.get_document(conn, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(doc["file_path"], filename=doc["filename"])


@detail_router.get("/{document_id}/pages/{page_number}/image")
def get_page_image(document_id: str, page_number: int, conn=Depends(get_db)):
    pages = document_service.get_pages(conn, document_id)
    page = next((p for p in pages if p["page_number"] == page_number), None)
    if not page or not page.get("image_path"):
        raise HTTPException(status_code=404, detail="Page image not found")
    import os
    if not os.path.exists(page["image_path"]):
        raise HTTPException(status_code=404, detail="Page image file missing")
    return FileResponse(page["image_path"])
