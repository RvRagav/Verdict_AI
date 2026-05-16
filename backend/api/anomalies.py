"""Anomaly flag endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.core import audit_chain


tender_router = APIRouter(prefix="/tenders/{tender_id}/anomalies", tags=["anomalies"])
anomaly_router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyDecision(BaseModel):
    decision: str  # reviewed | dismissed | confirmed


@tender_router.get("")
def list_anomalies(
    tender_id: str,
    state: Optional[str] = None,
    bidder_id: Optional[str] = None,
    conn=Depends(get_db),
):
    sql = "SELECT * FROM anomaly_flags WHERE tender_id = ?"
    params: list = [tender_id]
    if state:
        sql += " AND state = ?"; params.append(state)
    if bidder_id:
        sql += " AND bidder_id = ?"; params.append(bidder_id)
    sql += " ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at"
    rows = conn.execute(sql, params).fetchall()
    return {"anomalies": [dict(r) for r in rows]}


@anomaly_router.post("/{anomaly_id}/decide")
def decide(
    anomaly_id: str,
    payload: AnomalyDecision,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    if payload.decision not in ("reviewed", "dismissed", "confirmed"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    row = conn.execute(
        "SELECT id, tender_id FROM anomaly_flags WHERE id = ?", (anomaly_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE anomaly_flags SET state = ?, reviewed_by = ?, reviewed_at = ? "
        "WHERE id = ?",
        (payload.decision, actor, now, anomaly_id),
    )
    audit_chain.append(
        conn,
        tender_id=row["tender_id"],
        event_type="anomaly_dismissed" if payload.decision == "dismissed"
                   else "anomaly_flagged",  # not perfect but valid type
        event_data={"anomaly_id": anomaly_id, "decision": payload.decision},
        actor=actor,
    )
    new = conn.execute(
        "SELECT * FROM anomaly_flags WHERE id = ?", (anomaly_id,),
    ).fetchone()
    return dict(new)
