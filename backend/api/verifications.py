"""Verification endpoints — run, list, matrix."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_actor, get_db
from backend.services import verification_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/verifications",
                           tags=["verifications"])


@tender_router.post("/run")
def run(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return verification_service.run_for_tender(
        conn, tender_id=tender_id, actor=actor,
    )


@tender_router.post("/run/{bidder_id}")
def run_one(
    tender_id: str,
    bidder_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        results = verification_service.run_for_bidder(
            conn, tender_id=tender_id, bidder_id=bidder_id, actor=actor,
        )
        return {"bidder_id": bidder_id, "results": results}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@tender_router.get("")
def list_(tender_id: str, conn=Depends(get_db)):
    return {"verifications": verification_service.list_for_tender(conn, tender_id)}


@tender_router.get("/matrix")
def matrix(tender_id: str, conn=Depends(get_db)):
    return verification_service.matrix(conn, tender_id)
