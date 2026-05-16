"""Defence Vault endpoints — generate, list, download."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.dependencies import get_db, require_officer
from backend.services import vault_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/vaults", tags=["vault"])
vault_router = APIRouter(prefix="/vaults", tags=["vault"])


@tender_router.post("")
def generate(
    tender_id: str,
    actor: str = Depends(require_officer),
    conn=Depends(get_db),
):
    try:
        return vault_service.generate_vault(
            conn, tender_id=tender_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vault failed: {exc}")


@tender_router.get("")
def list_(tender_id: str, conn=Depends(get_db)):
    return {"vaults": vault_service.list_vaults(conn, tender_id)}


@vault_router.get("/{vault_id}")
def get(vault_id: str, conn=Depends(get_db)):
    v = vault_service.get_vault(conn, vault_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vault not found")
    return v


@vault_router.get("/{vault_id}/download")
def download(vault_id: str, conn=Depends(get_db)):
    v = vault_service.get_vault(conn, vault_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vault not found")
    if not os.path.exists(v["file_path"]):
        raise HTTPException(status_code=404, detail="Vault file missing on disk")
    return FileResponse(
        v["file_path"],
        filename=os.path.basename(v["file_path"]),
        media_type="application/zip",
    )
