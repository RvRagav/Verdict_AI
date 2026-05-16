"""Audit Replay — Time-Travel to any point in the dossier's history.

Given an audit event ID, reconstructs the evaluation matrix state
AS OF that moment. Uses decision_replays (snapshots captured at every
officer decision) + walks evaluations created before that timestamp.

The officer sees: "This is what the matrix looked like when Officer
Kumar made decision X."
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_db


router = APIRouter(prefix="/tenders/{tender_id}/audit/replay", tags=["audit-replay"])


@router.get("")
def get_replay_at(tender_id: str, at_event: int, conn=Depends(get_db)):
    """Reconstruct the dossier state at a specific audit event.

    Returns the evaluation matrix as it existed at that point in time.
    """

    # Get the target event
    target = conn.execute(
        "SELECT * FROM audit_events WHERE tender_id = ? AND id = ?",
        (tender_id, at_event),
    ).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Audit event not found")

    target = dict(target)
    target_time = target["timestamp"]

    # Get all evaluations that existed at that point
    # (created_at <= target_time)
    evals_at_time = conn.execute(
        """SELECT e.id, e.bidder_id, e.criterion_id, e.verdict, e.confidence,
                  e.route, e.state, e.officer_decision, e.officer_id, e.decided_at,
                  b.company_name, c.criterion_text, c.criterion_type
           FROM evaluations e
           JOIN bidders b ON b.id = e.bidder_id
           JOIN criteria c ON c.id = e.criterion_id
           WHERE e.tender_id = ? AND e.created_at <= ?
           ORDER BY e.created_at""",
        (tender_id, target_time),
    ).fetchall()

    # For each evaluation, determine its state AT that time
    # If it was decided after target_time, show it as undecided
    matrix_at_time = []
    for ev in evals_at_time:
        ev = dict(ev)
        decided_at = ev.get("decided_at")
        if decided_at and decided_at > target_time:
            # Decision hadn't happened yet — show as pending
            ev["officer_decision"] = None
            ev["state"] = "pending_review"
        matrix_at_time.append({
            "evaluation_id": ev["id"],
            "bidder_id": ev["bidder_id"],
            "bidder_name": ev["company_name"],
            "criterion_id": ev["criterion_id"],
            "criterion_text": ev["criterion_text"][:80],
            "verdict": ev["verdict"],
            "confidence": ev["confidence"],
            "route": ev["route"],
            "state": ev["state"],
            "officer_decision": ev["officer_decision"],
        })

    # Get the tender state at that time
    tender_events = conn.execute(
        """SELECT event_data FROM audit_events
           WHERE tender_id = ? AND event_type = 'tender_state_transition' AND timestamp <= ?
           ORDER BY id DESC LIMIT 1""",
        (tender_id, target_time),
    ).fetchone()
    tender_state_at_time = "UNKNOWN"
    if tender_events:
        try:
            data = json.loads(tender_events["event_data"])
            tender_state_at_time = data.get("target_state", "UNKNOWN")
        except (json.JSONDecodeError, TypeError):
            pass

    # Count decisions made before vs after this point
    decisions_before = sum(1 for m in matrix_at_time if m["officer_decision"])
    decisions_total = conn.execute(
        "SELECT COUNT(*) c FROM evaluations WHERE tender_id = ? AND officer_decision IS NOT NULL",
        (tender_id,),
    ).fetchone()["c"]

    # Get events around this point for context
    context_events = conn.execute(
        """SELECT id, event_type, actor, timestamp FROM audit_events
           WHERE tender_id = ? AND id BETWEEN ? AND ?
           ORDER BY id""",
        (tender_id, max(1, at_event - 3), at_event + 3),
    ).fetchall()

    return {
        "tender_id": tender_id,
        "at_event": {
            "id": target["id"],
            "event_type": target["event_type"],
            "actor": target["actor"],
            "timestamp": target["timestamp"],
            "data": json.loads(target["event_data"]) if target["event_data"] else {},
        },
        "tender_state_at_time": tender_state_at_time,
        "matrix_at_time": matrix_at_time,
        "stats": {
            "cells_existed": len(matrix_at_time),
            "decisions_made_by_then": decisions_before,
            "decisions_total_now": decisions_total,
            "pass_at_time": sum(1 for m in matrix_at_time if m["verdict"] == "PASS"),
            "fail_at_time": sum(1 for m in matrix_at_time if m["verdict"] == "FAIL"),
            "review_at_time": sum(1 for m in matrix_at_time if m["verdict"] == "REVIEW"),
        },
        "context_events": [dict(e) for e in context_events],
    }


@router.get("/timeline")
def get_decision_timeline(tender_id: str, conn=Depends(get_db)):
    """Get all decision points (audit events where officer acted) for the timeline slider."""

    events = conn.execute(
        """SELECT id, event_type, actor, timestamp, event_data
           FROM audit_events
           WHERE tender_id = ? AND event_type IN (
               'evaluation_decided', 'second_officer_decided',
               'concurrence_decided', 'tec_report_finalised',
               'criteria_approved', 'tender_state_transition'
           )
           ORDER BY id""",
        (tender_id,),
    ).fetchall()

    timeline = []
    for e in events:
        e = dict(e)
        try:
            data = json.loads(e["event_data"])
        except (json.JSONDecodeError, TypeError):
            data = {}
        timeline.append({
            "event_id": e["id"],
            "event_type": e["event_type"],
            "actor": e["actor"],
            "timestamp": e["timestamp"],
            "summary": _summarize_event(e["event_type"], data),
        })

    return {"tender_id": tender_id, "timeline": timeline, "count": len(timeline)}


def _summarize_event(event_type: str, data: dict) -> str:
    if event_type == "evaluation_decided":
        return f"Officer {data.get('decision', '?')} → {data.get('final_verdict', '?')}"
    if event_type == "second_officer_decided":
        return f"Second officer {data.get('decision', '?')}"
    if event_type == "concurrence_decided":
        return f"Concurrence {data.get('decision', '?')}"
    if event_type == "tec_report_finalised":
        return f"TEC report sealed ({data.get('section_count', '?')} sections)"
    if event_type == "criteria_approved":
        return f"Criteria approved ({data.get('criteria_count', '?')} criteria)"
    if event_type == "tender_state_transition":
        return f"State → {data.get('target_state', '?')}"
    return event_type.replace("_", " ")
