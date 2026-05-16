"""Tender Copilot chat — list + SSE streaming."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.dependencies import get_db
from backend.services import chat_service


router = APIRouter(prefix="/tenders/{tender_id}/chat", tags=["chat"])


class ChatMessage(BaseModel):
    question: str


@router.get("/messages")
def list_messages(tender_id: str, limit: int = 50, conn=Depends(get_db)):
    return {"messages": chat_service.list_messages(conn, tender_id, limit=limit)}


@router.post("/stream")
def stream_message(
    tender_id: str,
    payload: ChatMessage,
    x_officer_id: Optional[str] = Header(None),
    conn=Depends(get_db),
):
    """Server-Sent Events stream for one chat turn.

    Each event is a JSON-encoded line prefixed with `data: ` and
    terminated by a blank line, per the SSE spec. Frontend uses
    EventSource() or a fetch+ReadableStream to consume.
    """
    def event_stream():
        for evt in chat_service.post_message_streaming(
            conn,
            tender_id=tender_id,
            question=payload.question,
            officer_id=x_officer_id,
        ):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
