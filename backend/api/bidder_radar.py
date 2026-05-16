"""Bidder Comparison Radar — 5-dimension score per bidder.

Dimensions:
  1. Financial (turnover + net worth vs threshold)
  2. Experience (similar orders count + value)
  3. Compliance (% of categorical criteria passed)
  4. Risk (inverted anomaly density — 100 = clean)
  5. Confidence (average AI confidence across cells)

Each dimension is normalized to 0-100.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_db


router = APIRouter(prefix="/tenders/{tender_id}/bidder-radar", tags=["bidder-radar"])


@router.get("")
def get_radar(tender_id: str, conn=Depends(get_db)):
    """Compute radar chart data for all bidders in this tender."""

    bidders = conn.execute(
        "SELECT id, company_name FROM bidders WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()

    if not bidders:
        return {"bidders": [], "dimensions": ["Financial", "Experience", "Compliance", "Risk", "Confidence"]}

    criteria_count = conn.execute(
        "SELECT COUNT(*) c FROM criteria WHERE tender_id = ? AND state = 'approved'",
        (tender_id,),
    ).fetchone()["c"]

    results = []
    for b in bidders:
        bid_id = b["id"]

        # 1. Financial — % of numeric criteria passed
        numeric_evals = conn.execute(
            """SELECT e.verdict, e.confidence FROM evaluations e
               JOIN criteria c ON c.id = e.criterion_id
               WHERE e.tender_id = ? AND e.bidder_id = ? AND c.criterion_type = 'numeric_threshold'""",
            (tender_id, bid_id),
        ).fetchall()
        if numeric_evals:
            financial = sum(100 if e["verdict"] == "PASS" else (50 if e["verdict"] == "REVIEW" else 0) for e in numeric_evals) / len(numeric_evals)
        else:
            financial = 50

        # 2. Experience — temporal_recency + composite criteria pass rate
        exp_evals = conn.execute(
            """SELECT e.verdict FROM evaluations e
               JOIN criteria c ON c.id = e.criterion_id
               WHERE e.tender_id = ? AND e.bidder_id = ?
               AND c.criterion_type IN ('temporal_recency', 'composite')""",
            (tender_id, bid_id),
        ).fetchall()
        if exp_evals:
            experience = sum(100 if e["verdict"] == "PASS" else (50 if e["verdict"] == "REVIEW" else 0) for e in exp_evals) / len(exp_evals)
        else:
            experience = 50

        # 3. Compliance — categorical_presence criteria pass rate
        cat_evals = conn.execute(
            """SELECT e.verdict FROM evaluations e
               JOIN criteria c ON c.id = e.criterion_id
               WHERE e.tender_id = ? AND e.bidder_id = ? AND c.criterion_type = 'categorical_presence'""",
            (tender_id, bid_id),
        ).fetchall()
        if cat_evals:
            compliance = sum(100 if e["verdict"] == "PASS" else (50 if e["verdict"] == "REVIEW" else 0) for e in cat_evals) / len(cat_evals)
        else:
            compliance = 50

        # 4. Risk — inverted anomaly density (100 = clean, 0 = many high-severity)
        anomalies = conn.execute(
            "SELECT severity FROM anomaly_flags WHERE tender_id = ? AND bidder_id = ?",
            (tender_id, bid_id),
        ).fetchall()
        risk_score = 100
        for a in anomalies:
            if a["severity"] == "high": risk_score -= 8
            elif a["severity"] == "medium": risk_score -= 4
            else: risk_score -= 1
        risk_score = max(0, min(100, risk_score))

        # 5. Confidence — average across all cells
        all_evals = conn.execute(
            "SELECT confidence FROM evaluations WHERE tender_id = ? AND bidder_id = ?",
            (tender_id, bid_id),
        ).fetchall()
        if all_evals:
            confidence = sum(e["confidence"] for e in all_evals) / len(all_evals) * 100
        else:
            confidence = 0

        results.append({
            "bidder_id": bid_id,
            "company_name": b["company_name"],
            "scores": {
                "financial": round(financial, 1),
                "experience": round(experience, 1),
                "compliance": round(compliance, 1),
                "risk": round(risk_score, 1),
                "confidence": round(confidence, 1),
            },
            "overall": round((financial + experience + compliance + risk_score + confidence) / 5, 1),
        })

    # Sort by overall score descending
    results.sort(key=lambda x: x["overall"], reverse=True)

    return {
        "tender_id": tender_id,
        "dimensions": ["Financial", "Experience", "Compliance", "Risk", "Confidence"],
        "bidders": results,
    }
