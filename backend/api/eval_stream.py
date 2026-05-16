"""Live Evaluation Stream — SSE endpoint that streams cell results as they complete.

When the officer clicks "Run Evaluation", instead of waiting 5 minutes for all
cells to complete, this endpoint streams each cell result as it finishes.

Events:
  - {type: "started", cells_total: N, bidders: [...], criteria: [...]}
  - {type: "cell_complete", bidder_id, bidder_name, criterion_id, criterion_text, verdict, confidence, cells_done, cells_total}
  - {type: "progress", cells_done, cells_total, pass_count, fail_count, review_count}
  - {type: "done", summary: {total, pass, fail, review, errors}}
  - {type: "error", message: str}
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from typing import Optional

from backend.api.dependencies import get_db


router = APIRouter(prefix="/tenders/{tender_id}/evaluate/stream", tags=["evaluation-stream"])


@router.post("")
def stream_evaluation(
    tender_id: str,
    x_officer_id: Optional[str] = Header(None),
    conn=Depends(get_db),
):
    """Run evaluation with SSE streaming — each cell result is sent as it completes."""

    def event_stream():
        from backend.services import evaluation_service, bidder_service, criteria_service
        from backend.pipeline import verdict as verdict_pipeline
        from backend.pipeline import anomaly_pipeline
        from backend.core import audit_chain
        import traceback

        actor = x_officer_id or "system"

        try:
            # Load bidders + criteria
            bidders = bidder_service.list_bidders(conn, tender_id)
            criteria = [c for c in criteria_service.list_criteria(conn, tender_id)
                        if c["state"] == "approved"]

            if not bidders or not criteria:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No bidders or criteria found.'})}\n\n"
                return

            cells_total = len(bidders) * len(criteria)
            cells_done = 0
            pass_count = 0
            fail_count = 0
            review_count = 0
            errors = 0

            # Send start event
            start_data = {
                'type': 'started',
                'cells_total': cells_total,
                'bidders': [{'id': b['id'], 'name': b['company_name']} for b in bidders],
                'criteria': [{'id': c['id'], 'text': c['criterion_text'][:60]} for c in criteria],
            }
            yield f"data: {json.dumps(start_data)}\n\n"

            # Evaluate each cell
            for bidder in bidders:
                for criterion in criteria:
                    try:
                        # Check if already evaluated
                        existing = conn.execute(
                            "SELECT id, verdict, confidence FROM evaluations "
                            "WHERE tender_id = ? AND bidder_id = ? AND criterion_id = ?",
                            (tender_id, bidder["id"], criterion["id"]),
                        ).fetchone()

                        if existing:
                            v = existing["verdict"]
                            conf = existing["confidence"]
                        else:
                            # Run the evaluation pipeline for this single cell
                            result = verdict_pipeline.compute_evaluation(
                                conn,
                                tender_id=tender_id,
                                bidder_id=bidder["id"],
                                criterion=criterion,
                            )
                            v = result.get("verdict", "REVIEW") if result else "REVIEW"
                            conf = result.get("confidence", 0) if result else 0

                        cells_done += 1
                        if v == "PASS": pass_count += 1
                        elif v == "FAIL": fail_count += 1
                        else: review_count += 1

                        # Send cell complete event
                        yield f"data: {json.dumps({'type': 'cell_complete', 'bidder_id': bidder['id'], 'bidder_name': bidder['company_name'], 'criterion_id': criterion['id'], 'criterion_text': criterion['criterion_text'][:60], 'verdict': v, 'confidence': round(conf, 2), 'cells_done': cells_done, 'cells_total': cells_total})}\n\n"

                    except Exception as exc:
                        cells_done += 1
                        errors += 1
                        yield f"data: {json.dumps({'type': 'cell_error', 'bidder_id': bidder['id'], 'criterion_id': criterion['id'], 'error': str(exc)[:100], 'cells_done': cells_done, 'cells_total': cells_total})}\n\n"

                # After each bidder, run anomaly detection
                try:
                    anomaly_pipeline.detect_anomalies(
                        conn, tender_id=tender_id, bidder_id=bidder["id"],
                        use_llm=False, actor=actor,
                    )
                except Exception:
                    pass

                # Send progress event after each bidder
                yield f"data: {json.dumps({'type': 'progress', 'cells_done': cells_done, 'cells_total': cells_total, 'pass_count': pass_count, 'fail_count': fail_count, 'review_count': review_count, 'bidder_complete': bidder['company_name']})}\n\n"

            # Done
            yield f"data: {json.dumps({'type': 'done', 'summary': {'total': cells_total, 'pass': pass_count, 'fail': fail_count, 'review': review_count, 'errors': errors}})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:200]})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
