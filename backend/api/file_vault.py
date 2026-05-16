"""File Vault read endpoint — every doc in the tender, in one shot."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_db
from backend.services import vault_browse_service


router = APIRouter(prefix="/tenders/{tender_id}/file-vault", tags=["file-vault"])


@router.get("")
def list_files(tender_id: str, conn=Depends(get_db)):
    return vault_browse_service.list_tender_files(conn, tender_id)
