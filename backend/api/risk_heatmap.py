"""Risk Heatmap — per-cell risk score for the evaluation matrix.

Each (bidder × criterion) cell gets a risk score (0.0 to 1.0):
  - 0.0 = clean (no anomalies, no dissent, high confidence)
  - 1.0 = maximum risk (high-severity anomalies + high dissent + low confidence)

Score formula:
  risk = w1 * anomaly_factor + w2 * dissent_factor + w3 * (1 - confidence)

Where:
  anomaly_factor = min(1, high_count * 0.4 + medium_count * 0.2 + low_count * 0.05)
  dissent_factor = 1.0 if severity=high, 0.5 if medium, 0.2 if low, 0 if none
  confidence = the cell's composite confidence (0-1)

Weights: w1=0.4, w2=0.3, w3=0.3
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_db


router = APIRouter(prefix="/tenders/{tender_id}/risk-heatmap", tags=["risk-heatmap"])


@router.get("")
def get_heatmap(tender_id: str, conn=Depends(get_db)):
    """Compute risk heatmap for the evaluation matrix."""

    # Load all evaluations with their anomaly + dissent data
    evals = conn.execute(
        """SELECT e.id, e.bidder_id, e.criterion_id, e.confidence,
                  e.dissent_branch, b.company_name, c.criterion_text
           FROM evaluations e
           JOIN bidders b ON b.id = e.bidder_id
           JOIN criteria c ON c.id = e.criterion_id
           WHERE e.tender_id = ?""",
        (tender_id,),
    ).fetchall()

    # Load anomaly counts per bidder
    anomaly_counts = {}
    for row in conn.execute(
        """SELECT bidder_id, evaluation_id, severity, COUNT(*) c
           FROM anomaly_flags WHERE tender_id = ?
           GROUP BY bidder_id, evaluation_id, severity""",
        (tender_id,),
    ).fetchall():
        key = (row["bidder_id"], row["evaluation_id"])
        if key not in anomaly_counts:
            anomaly_counts[key] = {"high": 0, "medium": 0, "low": 0}
        anomaly_counts[key][row["severity"]] += row["c"]

    cells = []
    for ev in evals:
        ev = dict(ev)
        bid_id = ev["bidder_id"]
        eval_id = ev["id"]

        # Anomaly factor
        counts = anomaly_counts.get((bid_id, eval_id), {"high": 0, "medium": 0, "low": 0})
        # Also check bidder-level anomalies (no specific eval_id)
        bidder_counts = anomaly_counts.get((bid_id, None), {"high": 0, "medium": 0, "low": 0})
        high = counts["high"] + bidder_counts.get("high", 0)
        medium = counts["medium"] + bidder_counts.get("medium", 0)
        low = counts["low"] + bidder_counts.get("low", 0)
        anomaly_factor = min(1.0, high * 0.4 + medium * 0.2 + low * 0.05)

        # Dissent factor
        dissent_factor = 0.0
        try:
            dissent = json.loads(ev["dissent_branch"]) if ev["dissent_branch"] else None
        except (json.JSONDecodeError, TypeError):
            dissent = None
        if dissent:
            sev = dissent.get("severity", "")
            if sev == "high": dissent_factor = 1.0
            elif sev == "medium": dissent_factor = 0.5
            elif sev == "low": dissent_factor = 0.2

        # Confidence inverse
        conf_inverse = 1.0 - (ev["confidence"] or 0)

        # Weighted risk score
        risk = 0.4 * anomaly_factor + 0.3 * dissent_factor + 0.3 * conf_inverse
        risk = min(1.0, max(0.0, risk))

        # Classify
        if risk >= 0.6: level = "high"
        elif risk >= 0.3: level = "medium"
        else: level = "low"

        cells.append({
            "evaluation_id": eval_id,
            "bidder_id": bid_id,
            "criterion_id": ev["criterion_id"],
            "risk_score": round(risk, 3),
            "risk_level": level,
            "factors": {
                "anomaly": round(anomaly_factor, 2),
                "dissent": round(dissent_factor, 2),
                "confidence_gap": round(conf_inverse, 2),
            },
        })

    return {
        "tender_id": tender_id,
        "cells": cells,
        "summary": {
            "total": len(cells),
            "high_risk": sum(1 for c in cells if c["risk_level"] == "high"),
            "medium_risk": sum(1 for c in cells if c["risk_level"] == "medium"),
            "low_risk": sum(1 for c in cells if c["risk_level"] == "low"),
        },
    }
