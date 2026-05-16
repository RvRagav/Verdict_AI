"""Checklist endpoints — auto-match, list, decide, finalize."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.services import checklist_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/checklist", tags=["checklist"])
response_router = APIRouter(prefix="/checklist-responses", tags=["checklist"])


class ResponseDecision(BaseModel):
    decision: str  # accepted | rejected
    notes: Optional[str] = None


@tender_router.get("")
def list_checklist(tender_id: str, conn=Depends(get_db)):
    return {"items": checklist_service.list_checklist(conn, tender_id)}


@tender_router.post("/auto-match")
def auto_match(
    tender_id: str,
    bidder_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return {
        "responses": checklist_service.auto_match(
            conn, tender_id=tender_id, bidder_id=bidder_id, actor=actor,
        )
    }


@tender_router.get("/responses")
def list_responses(
    tender_id: str,
    bidder_id: Optional[str] = None,
    conn=Depends(get_db),
):
    return {
        "responses": checklist_service.list_responses(
            conn, tender_id=tender_id, bidder_id=bidder_id,
        )
    }


@tender_router.post("/finalize")
def finalize(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return checklist_service.finalize_preliminary(
        conn, tender_id=tender_id, actor=actor,
    )


@response_router.post("/{response_id}/decide")
def decide_response(
    response_id: str,
    payload: ResponseDecision,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return checklist_service.decide_response(
            conn, response_id=response_id, decision=payload.decision,
            officer_id=actor, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
