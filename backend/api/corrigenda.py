"""Corrigendum endpoints — register, list, apply amendments, mark applied."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.dependencies import get_actor, get_db, require_officer
from backend.services import corrigendum_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/corrigenda", tags=["corrigenda"])
corrig_router = APIRouter(prefix="/corrigenda", tags=["corrigenda"])


class CorrigendumRegister(BaseModel):
    document_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=512)
    issued_date: Optional[str] = None


class AmendmentApply(BaseModel):
    criterion_id: str
    new_text: str
    new_threshold: Optional[dict] = None
    new_is_mandatory: Optional[bool] = None
    new_gfr_rule_number: Optional[str] = None


@tender_router.post("")
def register(
    tender_id: str,
    payload: CorrigendumRegister,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return corrigendum_service.register_corrigendum(
        conn, tender_id=tender_id,
        document_id=payload.document_id,
        title=payload.title,
        issued_date=payload.issued_date,
        actor=actor,
    )


@tender_router.get("")
def list_(tender_id: str, conn=Depends(get_db)):
    return {"corrigenda": corrigendum_service.list_corrigenda(conn, tender_id)}


@corrig_router.get("/{corrigendum_id}")
def get(corrigendum_id: str, conn=Depends(get_db)):
    c = corrigendum_service.get_corrigendum(conn, corrigendum_id)
    if not c:
        raise HTTPException(status_code=404, detail="Corrigendum not found")
    return c


@corrig_router.post("/{corrigendum_id}/amendments")
def apply_amendment(
    corrigendum_id: str,
    payload: AmendmentApply,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return corrigendum_service.apply_amendment(
            conn,
            corrigendum_id=corrigendum_id,
            criterion_id=payload.criterion_id,
            new_text=payload.new_text,
            new_threshold=payload.new_threshold,
            new_is_mandatory=payload.new_is_mandatory,
            new_gfr_rule_number=payload.new_gfr_rule_number,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@corrig_router.post("/{corrigendum_id}/applied")
def mark_applied(
    corrigendum_id: str,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return corrigendum_service.mark_applied(
            conn, corrigendum_id=corrigendum_id, actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
