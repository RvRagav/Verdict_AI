"""Tender CRUD + state transition endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_actor, get_db
from backend.core.state_machine import StateError
from backend.services import tender_service


router = APIRouter(prefix="/tenders", tags=["tenders"])


class TenderCreate(BaseModel):
    tender_number: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=512)
    department: str = Field(..., min_length=1, max_length=128)
    category: str = Field(..., min_length=1, max_length=128)
    estimated_cost: Optional[int] = None
    emd_amount: Optional[int] = None
    bid_open_date: Optional[str] = None
    bid_close_date: Optional[str] = None
    metadata: Optional[dict] = None


class TenderTransition(BaseModel):
    target_state: str


class TenderMetadata(BaseModel):
    metadata: dict


@router.post("")
def create_tender(
    payload: TenderCreate,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return tender_service.create_tender(
            conn, **payload.model_dump(), created_by=actor,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
def list_tenders(
    state: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 100,
    conn=Depends(get_db),
):
    return {
        "tenders": tender_service.list_tenders(
            conn, state=state, department=department, limit=limit,
        )
    }


@router.get("/{tender_id}")
def get_tender(tender_id: str, conn=Depends(get_db)):
    t = tender_service.get_tender(conn, tender_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tender not found")
    return t


@router.post("/{tender_id}/transitions")
def transition_state(
    tender_id: str,
    payload: TenderTransition,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return tender_service.transition_state(
            conn, tender_id=tender_id, target_state=payload.target_state,
            actor=actor,
        )
    except StateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{tender_id}/metadata")
def update_metadata(
    tender_id: str,
    payload: TenderMetadata,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return tender_service.update_metadata(
        conn, tender_id=tender_id, metadata=payload.metadata, actor=actor,
    )


@router.delete("/{tender_id}")
def delete_tender(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    tender_service.soft_delete(conn, tender_id=tender_id, actor=actor)
    return {"ok": True}
