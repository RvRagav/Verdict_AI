"""Criteria endpoints — extraction, list, edit, approve."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.services import criteria_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/criteria", tags=["criteria"])
criterion_router = APIRouter(prefix="/criteria", tags=["criteria"])


class CriterionEdit(BaseModel):
    criterion_text: Optional[str] = None
    threshold_value: Optional[dict] = None
    is_mandatory: Optional[bool] = None
    gfr_rule_number: Optional[str] = None


@tender_router.post("/extract")
def extract(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return criteria_service.extract_for_tender(
            conn, tender_id=tender_id, actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")


@tender_router.get("")
def list_criteria(tender_id: str, conn=Depends(get_db)):
    return {"criteria": criteria_service.list_criteria(conn, tender_id)}


@tender_router.post("/approve-all")
def approve_all(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return criteria_service.approve_all(
        conn, tender_id=tender_id, officer_id=actor,
    )


@criterion_router.get("/{criterion_id}")
def get_criterion(criterion_id: str, conn=Depends(get_db)):
    c = criteria_service.get_criterion(conn, criterion_id)
    if not c:
        raise HTTPException(status_code=404, detail="Criterion not found")
    return c


@criterion_router.patch("/{criterion_id}")
def edit_criterion(
    criterion_id: str,
    payload: CriterionEdit,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return criteria_service.edit_criterion(
            conn, criterion_id=criterion_id, actor=actor,
            **payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@criterion_router.post("/{criterion_id}/approve")
def approve_criterion(
    criterion_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return criteria_service.approve_criterion(
        conn, criterion_id=criterion_id, officer_id=actor,
    )


@criterion_router.post("/{criterion_id}/reject")
def reject_criterion(
    criterion_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return criteria_service.reject_criterion(
        conn, criterion_id=criterion_id, officer_id=actor,
    )


@criterion_router.get("/{criterion_id}/versions")
def list_versions(criterion_id: str, conn=Depends(get_db)):
    """Return every historical version of a criterion (append-only)."""
    return {"versions": criteria_service.list_versions(conn, criterion_id)}
