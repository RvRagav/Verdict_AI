"""Bidder registration + debarment endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_actor, get_db
from backend.services import bidder_service


router = APIRouter(prefix="/tenders/{tender_id}/bidders", tags=["bidders"])


class BidderCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=256)
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    cin: Optional[str] = None
    udyam_number: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    emd_amount: Optional[int] = None
    emd_instrument: Optional[str] = None       # DD / BG / e-payment
    emd_instrument_no: Optional[str] = None
    emd_validity_date: Optional[str] = None
    emd_exempt: bool = False
    emd_exempt_reason: Optional[str] = None
    bid_validity_until: Optional[str] = None


class BidderStateUpdate(BaseModel):
    state: str


@router.post("")
def register_bidder(
    tender_id: str,
    payload: BidderCreate,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return bidder_service.register_bidder(
        conn, tender_id=tender_id, **payload.model_dump(), actor=actor,
    )


@router.get("")
def list_bidders(tender_id: str, conn=Depends(get_db)):
    return {"bidders": bidder_service.list_bidders(conn, tender_id)}


@router.get("/{bidder_id}")
def get_bidder(tender_id: str, bidder_id: str, conn=Depends(get_db)):
    b = bidder_service.get_bidder(conn, bidder_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bidder not found")
    return b


@router.post("/{bidder_id}/debarment-check")
def check_debarment(
    tender_id: str,
    bidder_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return bidder_service.check_debarment(
            conn, bidder_id=bidder_id, actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{bidder_id}/state")
def update_state(
    tender_id: str,
    bidder_id: str,
    payload: BidderStateUpdate,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return bidder_service.update_state(
            conn, bidder_id=bidder_id, state=payload.state, actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
