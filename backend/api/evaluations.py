"""Evaluation endpoints — run, list, decide, second-officer, matrix,
replay, reproduce, post-review checks."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db, require_officer
from backend.pipeline import post_review
from backend.services import (
    evaluation_service,
    replay_service,
    reproduce_service,
)


tender_router = APIRouter(prefix="/tenders/{tender_id}", tags=["evaluations"])
eval_router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class EvalDecision(BaseModel):
    decision: str                          # confirmed | overridden
    structured_reason: Optional[str] = None
    reason_text: Optional[str] = None
    new_verdict: Optional[str] = None      # required when overridden


class SecondOfficerDecision(BaseModel):
    decision: str                          # approve | reject


class CheckAnswer(BaseModel):
    answer: str  # yes | no | not_applicable


# ─── Tender-scoped ─────────────────────────────────────────────────


@tender_router.post("/evaluate")
def run_evaluation(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        summary = evaluation_service.run_evaluation(
            conn, tender_id=tender_id, actor=actor,
        )
        return summary
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@tender_router.get("/evaluations")
def list_evaluations(
    tender_id: str,
    bidder_id: Optional[str] = None,
    criterion_id: Optional[str] = None,
    state: Optional[str] = None,
    route: Optional[str] = None,
    conn=Depends(get_db),
):
    return {
        "evaluations": evaluation_service.list_evaluations(
            conn,
            tender_id=tender_id, bidder_id=bidder_id, criterion_id=criterion_id,
            state=state, route=route,
        )
    }


@tender_router.get("/matrix")
def get_matrix(tender_id: str, conn=Depends(get_db)):
    return evaluation_service.matrix(conn, tender_id)


# ─── Evaluation-scoped ─────────────────────────────────────────────


@eval_router.get("/{evaluation_id}")
def get_evaluation(evaluation_id: str, conn=Depends(get_db)):
    e = evaluation_service.get_evaluation(conn, evaluation_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    # Lazy emit post-review checks if the cell isn't auto-committed
    if e["route"] != "auto_commit" and not e.get("post_review_checks"):
        post_review.emit_post_review_checks(conn, evaluation_id=evaluation_id)
        e = evaluation_service.get_evaluation(conn, evaluation_id)
    return e


@eval_router.post("/{evaluation_id}/decide")
def decide(
    evaluation_id: str,
    payload: EvalDecision,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return evaluation_service.decide_evaluation(
            conn,
            evaluation_id=evaluation_id,
            decision=payload.decision,
            officer_id=actor,
            structured_reason=payload.structured_reason,
            reason_text=payload.reason_text,
            new_verdict=payload.new_verdict,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@eval_router.post("/{evaluation_id}/second-officer")
def second_officer(
    evaluation_id: str,
    payload: SecondOfficerDecision,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return evaluation_service.second_officer_decide(
            conn,
            evaluation_id=evaluation_id,
            decision=payload.decision,
            officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@eval_router.post("/{evaluation_id}/replay/capture")
def capture_replay(
    evaluation_id: str,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return replay_service.capture(
            conn, evaluation_id=evaluation_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@eval_router.get("/{evaluation_id}/replays")
def list_replays(evaluation_id: str, conn=Depends(get_db)):
    return {"replays": replay_service.list_replays(conn, evaluation_id)}


@eval_router.post("/{evaluation_id}/reproduce")
def reproduce(
    evaluation_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return reproduce_service.reproduce(
            conn, evaluation_id=evaluation_id, actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@eval_router.post("/post-review-checks/{check_id}/answer")
def answer_check(
    check_id: str,
    payload: CheckAnswer,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return post_review.answer_check(
            conn, check_id=check_id, answer=payload.answer, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─── Replay detail ─────────────────────────────────────────────────


replay_router = APIRouter(prefix="/replays", tags=["evaluations"])


@replay_router.get("/{replay_id}")
def get_replay(replay_id: str, conn=Depends(get_db)):
    r = replay_service.get_replay(conn, replay_id)
    if not r:
        raise HTTPException(status_code=404, detail="Replay not found")
    return r
