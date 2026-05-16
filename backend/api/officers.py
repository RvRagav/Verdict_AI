"""Officer picker endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_db


router = APIRouter(prefix="/officers", tags=["officers"])


@router.get("")
def list_officers(conn=Depends(get_db)):
    rows = conn.execute(
        "SELECT id, name, department, role, created_at FROM officers ORDER BY name"
    ).fetchall()
    return {"officers": [dict(r) for r in rows]}


@router.get("/{officer_id}")
def get_officer(officer_id: str, conn=Depends(get_db)):
    row = conn.execute(
        "SELECT id, name, department, role, created_at FROM officers WHERE id = ?",
        (officer_id,),
    ).fetchone()
    return dict(row) if row else {}
