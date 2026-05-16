"""Audit trail endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_db
from backend.core import audit_chain


router = APIRouter(prefix="/tenders/{tender_id}/audit", tags=["audit"])


@router.get("")
def get_trail(
    tender_id: str,
    event_type: Optional[str] = None,
    cursor: Optional[int] = None,
    limit: int = 100,
    order: str = "asc",
    conn=Depends(get_db),
):
    """List audit events for a tender.

    `order=desc` returns the most recent events first (useful for UIs that
    want the latest activity). Default is `asc` for stable cursor pagination.
    """
    items, next_cursor = audit_chain.get_trail(
        conn, tender_id, event_type=event_type, limit=limit, cursor=cursor,
        order=order,
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/verify")
def verify(tender_id: str, conn=Depends(get_db)):
    ok, error = audit_chain.verify(conn, tender_id)
    return {"ok": ok, "error": error}
