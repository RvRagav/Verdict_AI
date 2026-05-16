"""Co-authored TEC report — draft + sections + revisions."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_actor, get_db
from backend.services import tec_draft_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/tec-draft", tags=["tec-draft"])
section_router = APIRouter(prefix="/tec-sections", tags=["tec-draft"])
draft_router = APIRouter(prefix="/tec-drafts", tags=["tec-draft"])


class ReviseBody(BaseModel):
    body: str
    diff_summary: Optional[str] = None


@tender_router.post("")
def get_or_create(
    tender_id: str,
    use_llm: bool = True,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        draft = tec_draft_service.get_or_create_draft(
            conn, tender_id=tender_id, officer_id=actor,
        )
        sections = tec_draft_service.populate_sections(
            conn,
            draft_id=draft["id"],
            tender_id=tender_id,
            officer_id=actor,
            use_llm=use_llm,
        )
        return {"draft": draft, "sections": sections}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TEC draft failed: {exc}")


@tender_router.get("")
def get_current(
    tender_id: str,
    conn=Depends(get_db),
):
    """Read current draft + sections without creating a new one."""
    row = conn.execute(
        "SELECT * FROM tec_report_drafts "
        "WHERE tender_id = ? AND state = 'draft' "
        "ORDER BY generated_at DESC LIMIT 1",
        (tender_id,),
    ).fetchone()
    if not row:
        return {"draft": None, "sections": []}
    draft = dict(row)
    sections = tec_draft_service.list_sections(conn, draft["id"])
    return {"draft": draft, "sections": sections}


@section_router.post("/{section_id}/revise")
def revise(
    section_id: str,
    payload: ReviseBody,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return tec_draft_service.revise_section(
            conn,
            section_id=section_id,
            new_body=payload.body,
            officer_id=actor,
            diff_summary=payload.diff_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@section_router.post("/{section_id}/regenerate")
def regenerate(
    section_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return tec_draft_service.regenerate_section(
            conn, section_id=section_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@section_router.get("/{section_id}/revisions")
def revisions(section_id: str, conn=Depends(get_db)):
    return {"revisions": tec_draft_service.list_revisions(conn, section_id)}


@draft_router.post("/{draft_id}/finalise")
def finalise(
    draft_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return tec_draft_service.finalise_draft(
            conn, draft_id=draft_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Finalise failed: {exc}")
