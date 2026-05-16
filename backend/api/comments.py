"""Per-cell officer comment threads."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.services import comment_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/comments", tags=["comments"])
eval_router = APIRouter(prefix="/evaluations/{evaluation_id}/comments", tags=["comments"])


class CommentBody(BaseModel):
    body: str
    evaluation_id: Optional[str] = None
    bidder_id: Optional[str] = None
    criterion_id: Optional[str] = None


@tender_router.get("")
def list_for_tender(tender_id: str, conn=Depends(get_db)):
    return {"comments": comment_service.list_for_tender(conn, tender_id)}


@tender_router.post("")
def add_for_tender(
    tender_id: str,
    payload: CommentBody,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return comment_service.add_comment(
            conn,
            tender_id=tender_id,
            evaluation_id=payload.evaluation_id,
            bidder_id=payload.bidder_id,
            criterion_id=payload.criterion_id,
            officer_id=actor,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@eval_router.get("")
def list_for_evaluation(evaluation_id: str, conn=Depends(get_db)):
    return {"comments": comment_service.list_for_evaluation(conn, evaluation_id)}


@eval_router.post("")
def add_for_evaluation(
    evaluation_id: str,
    payload: CommentBody,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    # Look up tender_id from evaluation
    row = conn.execute(
        "SELECT tender_id, bidder_id, criterion_id FROM evaluations WHERE id = ?",
        (evaluation_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    try:
        return comment_service.add_comment(
            conn,
            tender_id=row["tender_id"],
            evaluation_id=evaluation_id,
            bidder_id=row["bidder_id"],
            criterion_id=row["criterion_id"],
            officer_id=actor,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
