"""Concurrence endpoints — second-officer inbox + decide + rich review context."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_actor, get_db, require_officer
from backend.services import concurrence_service, comment_service, evaluation_service


router = APIRouter(prefix="/concurrence", tags=["concurrence"])


class OpenRequest(BaseModel):
    evaluation_id: str
    request_reason: str = Field(..., min_length=1)
    target_officer_id: Optional[str] = None


class DecideRequest(BaseModel):
    decision: str  # 'concurred' | 'rejected'
    decision_note: str


@router.get("/inbox")
def inbox(
    state: str = "open",
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return {"requests": concurrence_service.list_inbox(conn, actor, state=state)}


@router.get("/{request_id}/review-context")
def review_context(
    request_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    """Rich review context for the second officer — includes full evaluation,
    officer comments, anomalies, source documents, and the conditions that
    triggered the concurrence request."""
    req = concurrence_service.get_request(conn, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Concurrence request not found")

    # Full evaluation with post-review checks and anomalies
    evaluation = evaluation_service.get_evaluation(conn, req["evaluation_id"])
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # All officer comments on this cell
    comments = comment_service.list_for_evaluation(conn, req["evaluation_id"])

    # Actionable comments (AI-flagged as affecting verdict)
    actionable_comments = comment_service.get_actionable_comments(conn, req["evaluation_id"])

    # Get criterion details
    criterion = conn.execute(
        "SELECT * FROM criteria WHERE id = ?", (evaluation["criterion_id"],)
    ).fetchone()
    criterion_data = dict(criterion) if criterion else None

    # Get bidder details
    bidder = conn.execute(
        "SELECT * FROM bidders WHERE id = ?", (evaluation["bidder_id"],)
    ).fetchone()
    bidder_data = dict(bidder) if bidder else None

    # Get source document info if available
    source_doc = None
    if evaluation.get("source_doc_id"):
        doc_row = conn.execute(
            "SELECT id, filename, doc_type, page_count FROM documents WHERE id = ?",
            (evaluation["source_doc_id"],)
        ).fetchone()
        if doc_row:
            source_doc = dict(doc_row)

    # Get anomalies for this bidder
    anomalies = conn.execute(
        """SELECT * FROM anomaly_flags
           WHERE (evaluation_id = ? OR bidder_id = ?)
           AND state != 'dismissed'
           ORDER BY severity DESC""",
        (req["evaluation_id"], evaluation["bidder_id"]),
    ).fetchall()
    anomaly_list = [dict(a) for a in anomalies]

    # Get the requesting officer's info
    requesting_officer = conn.execute(
        "SELECT id, name, role, department FROM officers WHERE id = ?",
        (req["requested_by"],)
    ).fetchone()

    return {
        "request": req,
        "evaluation": evaluation,
        "criterion": criterion_data,
        "bidder": bidder_data,
        "comments": comments,
        "actionable_comments": actionable_comments,
        "anomalies": anomaly_list,
        "source_document": source_doc,
        "requesting_officer": dict(requesting_officer) if requesting_officer else None,
    }


@router.post("/{request_id}/decide")
def decide(
    request_id: str,
    payload: DecideRequest,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return concurrence_service.decide(
            conn,
            request_id=request_id,
            decision=payload.decision,
            decision_note=payload.decision_note,
            decided_by=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{request_id}/withdraw")
def withdraw(
    request_id: str,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return concurrence_service.withdraw(conn, request_id=request_id, by=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
