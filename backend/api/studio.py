"""Document Studio — officer-authored docs from the Copilot panel."""

from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.services import studio_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/studio", tags=["studio"])
doc_router = APIRouter(prefix="/studio", tags=["studio"])


class CreateDoc(BaseModel):
    title: str
    doc_kind: str = "brief"


class StudioMessage(BaseModel):
    message: str


@tender_router.get("/docs")
def list_for_tender(tender_id: str, conn=Depends(get_db)):
    return {"docs": studio_service.list_docs(conn, tender_id)}


@tender_router.post("/docs")
def create(
    tender_id: str,
    payload: CreateDoc,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return studio_service.create_doc(
            conn,
            tender_id=tender_id,
            officer_id=actor,
            title=payload.title,
            doc_kind=payload.doc_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@doc_router.get("/docs/{doc_id}")
def get(doc_id: str, conn=Depends(get_db)):
    doc = studio_service.get_doc(conn, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Studio doc not found")
    return doc


@doc_router.get("/docs/{doc_id}/messages")
def messages(doc_id: str, conn=Depends(get_db)):
    return {"messages": studio_service.list_messages(conn, doc_id)}


@doc_router.post("/docs/{doc_id}/stream")
def stream(
    doc_id: str,
    payload: StudioMessage,
    x_officer_id: Optional[str] = Header(None),
    conn=Depends(get_db),
):
    def event_stream():
        for evt in studio_service.post_message_streaming(
            conn,
            doc_id=doc_id,
            message=payload.message,
            officer_id=x_officer_id,
        ):
            yield f"data: {json.dumps(evt)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@doc_router.post("/docs/{doc_id}/finalise")
def finalise(
    doc_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return studio_service.finalise_doc(
            conn, doc_id=doc_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@doc_router.get("/docs/{doc_id}/download")
def download(doc_id: str, conn=Depends(get_db)):
    doc = studio_service.get_doc(conn, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Studio doc not found")
    if not doc.get("file_path") or not os.path.exists(doc["file_path"]):
        raise HTTPException(status_code=404, detail="Studio doc not finalised")
    filename = os.path.basename(doc["file_path"])
    # Serve with correct media type based on extension
    media = "application/pdf" if filename.endswith(".pdf") else "text/markdown"
    return FileResponse(doc["file_path"], filename=filename, media_type=media)
