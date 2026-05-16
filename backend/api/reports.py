"""Report generation + download."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.dependencies import get_actor, get_db
from backend.services import report_service


tender_router = APIRouter(prefix="/tenders/{tender_id}/reports", tags=["reports"])
report_router = APIRouter(prefix="/reports", tags=["reports"])


@tender_router.post("")
def generate(
    tender_id: str,
    actor: str = Depends(get_actor),
    conn=Depends(get_db),
):
    try:
        return report_service.generate_report(
            conn, tender_id=tender_id, officer_id=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")


@tender_router.get("")
def list_reports(tender_id: str, conn=Depends(get_db)):
    return {"reports": report_service.list_reports(conn, tender_id)}


@report_router.get("/{report_id}")
def get_report(report_id: str, conn=Depends(get_db)):
    r = report_service.get_report(conn, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return r


@report_router.get("/{report_id}/download")
def download_report(report_id: str, conn=Depends(get_db)):
    r = report_service.get_report(conn, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(r["file_path"]):
        raise HTTPException(status_code=404, detail="Report file missing")
    filename = os.path.basename(r["file_path"])
    return FileResponse(r["file_path"], filename=filename, media_type="application/pdf")
