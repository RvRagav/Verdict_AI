"""Brief endpoints — Pre-Mortem Brief get / regenerate."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_actor, get_db
from backend.services import brief_service


router = APIRouter(prefix="/tenders/{tender_id}/brief", tags=["brief"])


@router.get("")
def get_brief(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return brief_service.get_or_generate(conn, tender_id=tender_id, actor=actor)


@router.post("/regenerate")
def regenerate(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    return brief_service.generate(conn, tender_id=tender_id, actor=actor)
