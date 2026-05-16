"""VerdictAI FastAPI application.

Wires together every API router, sets up CORS for the frontend (Vite
dev server on http://localhost:5173 by default), initialises the DB
on startup, and provides a /healthz endpoint for sanity checks.

Run locally:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before backend.config is imported anywhere
load_dotenv()

from backend.api import (
    anomalies,
    audit,
    bidders,
    briefs,
    chat,
    checklist,
    citations,
    comments,
    concurrence,
    corrigenda,
    criteria,
    debarment,
    documents,
    evaluations,
    evidence_graph,
    file_vault,
    officers,
    reports,
    studio,
    tec_drafts,
    tenders,
    vaults,
    verifications,
)
from backend.config import settings
from backend.database.connection import init_db


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB + create upload/reports/pages directories at startup."""
    for d in (settings.upload_dir, settings.reports_dir, settings.pages_dir):
        os.makedirs(d, exist_ok=True)
    init_db()
    logger.info("VerdictAI ready (db=%s region=%s model=%s)",
                settings.db_path, settings.bedrock.region, settings.bedrock.model_id)
    yield
    logger.info("VerdictAI shutting down.")


app = FastAPI(
    title="VerdictAI",
    description="AI-assisted tender evaluation for government procurement.",
    version=settings.pipeline_version,
    lifespan=lifespan,
)


# ─── CORS ────────────────────────────────────────────────────────────


_cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Officer-ID"],
)


# ─── Health ──────────────────────────────────────────────────────────


@app.get("/healthz")
@app.get("/api/v1/healthz")
def healthz():
    """Liveness probe + a peek at Bedrock config so the UI can show
    'connected to AWS' without the user opening DevTools."""
    from backend.ai import bedrock_client
    return {
        "ok": True,
        "version": settings.pipeline_version,
        "bedrock": {
            "region": settings.bedrock.region,
            "model_id": settings.bedrock.model_id,
            "configured": bedrock_client.is_configured(),
        },
    }


# ─── API routers ─────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(officers.router, prefix=API_PREFIX)
app.include_router(tenders.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(documents.detail_router, prefix=API_PREFIX)
app.include_router(bidders.router, prefix=API_PREFIX)
app.include_router(criteria.tender_router, prefix=API_PREFIX)
app.include_router(criteria.criterion_router, prefix=API_PREFIX)
app.include_router(checklist.tender_router, prefix=API_PREFIX)
app.include_router(checklist.response_router, prefix=API_PREFIX)
app.include_router(evaluations.tender_router, prefix=API_PREFIX)
app.include_router(evaluations.eval_router, prefix=API_PREFIX)
app.include_router(evaluations.replay_router, prefix=API_PREFIX)
app.include_router(anomalies.tender_router, prefix=API_PREFIX)
app.include_router(anomalies.anomaly_router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(reports.tender_router, prefix=API_PREFIX)
app.include_router(reports.report_router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)

# Sprint A additions
app.include_router(briefs.router, prefix=API_PREFIX)
app.include_router(vaults.tender_router, prefix=API_PREFIX)
app.include_router(vaults.vault_router, prefix=API_PREFIX)
app.include_router(concurrence.router, prefix=API_PREFIX)
app.include_router(corrigenda.tender_router, prefix=API_PREFIX)
app.include_router(corrigenda.corrig_router, prefix=API_PREFIX)
app.include_router(debarment.router, prefix=API_PREFIX)
app.include_router(citations.router, prefix=API_PREFIX)
app.include_router(file_vault.router, prefix=API_PREFIX)
app.include_router(verifications.tender_router, prefix=API_PREFIX)

# Sprint M2 — Module 4: HITL co-authoring + Document Studio
app.include_router(comments.tender_router, prefix=API_PREFIX)
app.include_router(comments.eval_router, prefix=API_PREFIX)
app.include_router(tec_drafts.tender_router, prefix=API_PREFIX)
app.include_router(tec_drafts.section_router, prefix=API_PREFIX)
app.include_router(tec_drafts.draft_router, prefix=API_PREFIX)
app.include_router(studio.tender_router, prefix=API_PREFIX)
app.include_router(studio.doc_router, prefix=API_PREFIX)
app.include_router(evidence_graph.router, prefix=API_PREFIX)

# Creative features — Evidence Graph, What-If, Precedents, Live Stream
from backend.api import what_if, precedents, eval_stream
app.include_router(what_if.router, prefix=API_PREFIX)
app.include_router(precedents.router, prefix=API_PREFIX)
app.include_router(eval_stream.router, prefix=API_PREFIX)

# Creative features — Bidder Radar, Risk Heatmap, Audit Replay
from backend.api import bidder_radar, risk_heatmap, audit_replay
app.include_router(bidder_radar.router, prefix=API_PREFIX)
app.include_router(risk_heatmap.router, prefix=API_PREFIX)
app.include_router(audit_replay.router, prefix=API_PREFIX)


@app.get("/")
def root():
    return {
        "service": "VerdictAI",
        "version": settings.pipeline_version,
        "docs": "/docs",
        "health": "/healthz",
    }
