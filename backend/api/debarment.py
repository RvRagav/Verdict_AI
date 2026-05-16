"""Debarment registry endpoints — list + add."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_db, require_officer
from backend.services import debarment_service


router = APIRouter(prefix="/debarment", tags=["debarment"])


class DebarmentEntry(BaseModel):
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    company_name: Optional[str] = None
    source: str = "department"
    reason: str
    debarred_until: Optional[str] = None
    notice_url: Optional[str] = None


@router.get("/entries")
def list_(source: Optional[str] = None, conn=Depends(get_db)):
    return {"entries": debarment_service.list_entries(conn, source=source)}


@router.post("/entries")
def add(
    payload: DebarmentEntry,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    return debarment_service.add_entry(conn, **payload.model_dump())


class CheckPayload(BaseModel):
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    company_name: Optional[str] = None


@router.post("/check")
def check(payload: CheckPayload, conn=Depends(get_db)):
    return debarment_service.check_bidder(conn, **payload.model_dump())
