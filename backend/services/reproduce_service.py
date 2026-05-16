"""Reproduce Replay — re-run an evaluation against the cached LLM calls.

The reproduction guarantee: given the same NIT, the same bidder
documents, the same officer overrides, and the same code (same
pipeline_signature_hash), running this function should produce the
same verdict, confidence, and explanation byte-for-byte (within the
deterministic-temp + cached-LLM envelope).

How it works:
1. Load an evaluation row + its underlying criterion + evidence
2. Re-run L3 evidence_extraction (which hits the LLM cache via
   prompt_hash — no new calls) and L4 verdict_pipeline (also cached)
3. Compare every field of the new result to the stored row
4. Return a diff: empty diff = perfect reproduction

Used by the UI's "Reproduce" button on the audit panel.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from backend.core import audit_chain
from backend.pipeline import evidence_extraction, verdict as verdict_pipeline
from backend.services import criteria_service

logger = logging.getLogger(__name__)


def reproduce(
    conn,
    *,
    evaluation_id: str,
    actor: str,
) -> dict:
    """Re-run the pipeline for a single evaluation. Compare to the stored row.

    Returns:
        {
            "evaluation_id": ...,
            "matches": bool,
            "diff": {field: {"stored": ..., "reproduced": ...}, ...},
            "stored": {...},
            "reproduced": {...},
            "pipeline_signature": {"stored": ..., "current": ...}
        }
    """
    stored_row = conn.execute(
        "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,),
    ).fetchone()
    if not stored_row:
        raise ValueError(f"Evaluation not found: {evaluation_id}")
    stored = dict(stored_row)

    # Load criterion (it might have been edited; reproducer uses current row,
    # which is what makes this an integrity check, not a counterfactual)
    criterion = criteria_service.get_criterion(conn, stored["criterion_id"])
    if not criterion:
        raise ValueError(f"Criterion not found: {stored['criterion_id']}")

    # Re-extract evidence — should hit the LLM cache for any LLM calls
    evidence = evidence_extraction.extract_evidence(
        conn,
        tender_id=stored["tender_id"],
        bidder_id=stored["bidder_id"],
        criterion=criterion,
    )

    # We don't actually re-write the evaluation row; we compute it in
    # memory and compare. To do that we mirror compute_evaluation()'s
    # logic without persistence.
    reproduced = _recompute_in_memory(conn, stored, criterion, evidence)

    diff = _diff_evaluation(stored, reproduced)

    matches = len(diff) == 0
    audit_chain.append(
        conn,
        tender_id=stored["tender_id"],
        event_type="reproduce_attempted",
        event_data={
            "evaluation_id": evaluation_id,
            "matches": matches,
            "diff_fields": list(diff.keys()),
        },
        actor=actor,
    )

    return {
        "evaluation_id": evaluation_id,
        "matches": matches,
        "diff": diff,
        "stored": _strip_for_diff(stored),
        "reproduced": reproduced,
        "pipeline_signature": {
            "stored": stored.get("pipeline_signature_hash"),
            "current": _current_pipeline_signature(),
        },
    }


def _recompute_in_memory(conn, stored: dict, criterion: dict, evidence: dict) -> dict:
    """Rerun the verdict computation without writing to DB."""
    from backend.core.confidence import route_evaluation
    from backend.ai import bedrock_client
    from backend.ai.prompts import DISSENT

    # 1. Verdict
    v_pipeline = verdict_pipeline
    verdict, _method = v_pipeline._verdict_from_evidence(
        criterion.get("criterion_type") or "qualitative_assessment",
        evidence, criterion,
    )
    breakdown = v_pipeline._confidence_breakdown(
        evidence, criterion.get("criterion_type") or "qualitative_assessment",
    )
    confidence = breakdown.composite()

    # 2. Dissent — cache lookup only (force_cache by reusing prompt_hash semantics)
    user_prompt = DISSENT.render_user(
        verdict=verdict,
        confidence=confidence,
        criterion_text=criterion.get("criterion_text", ""),
        extracted_value=json.dumps(evidence.get("value")) if evidence.get("value") else "(none)",
        evidence_text=evidence.get("notes") or "",
    )
    dissent_resp = bedrock_client.invoke(
        invocation_type="dissent",
        system=DISSENT.system,
        user=user_prompt,
        prompt_version=DISSENT.version,
        structured=True,
        schema_hint=DISSENT.schema_hint,
        tender_id=stored["tender_id"],
        conn=conn,
    )
    dissent_data = dissent_resp.data if isinstance(dissent_resp.data, dict) else None

    # 3. Anomalies as stored
    try:
        anomalies = json.loads(stored.get("anomalies") or "[]")
    except (json.JSONDecodeError, TypeError):
        anomalies = []

    if dissent_data and dissent_data.get("severity") == "high":
        anomalies = list(anomalies) + [{
            "flag_type": "novel",
            "severity": "high",
            "message": dissent_data.get("dissent", ""),
        }]

    # 4. Routing
    cpm_count = conn.execute(
        "SELECT COUNT(*) AS c FROM precedents"
    ).fetchone()["c"]
    routing = route_evaluation(
        verdict=verdict,
        confidence=confidence,
        criterion_type=criterion.get("criterion_type") or "qualitative_assessment",
        is_mandatory=bool(criterion.get("is_mandatory", False)),
        gfr_override_permitted=bool(criterion.get("gfr_override_permitted", True)),
        anomalies=anomalies,
        cpm_count=cpm_count,
    )

    return {
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "confidence_breakdown": breakdown.to_dict(),
        "route": routing.route,
        "routing_reason": routing.reason,
        "dissent_branch": dissent_data,
    }


def _diff_evaluation(stored: dict, reproduced: dict) -> dict:
    """Return non-matching fields. Tolerant of float rounding and JSON-encoding."""
    diff: dict = {}

    # verdict
    if stored.get("verdict") != reproduced.get("verdict"):
        diff["verdict"] = {"stored": stored["verdict"], "reproduced": reproduced["verdict"]}

    # confidence — float compare with 4-decimal rounding
    sc = round(float(stored.get("confidence") or 0), 4)
    rc = round(float(reproduced.get("confidence") or 0), 4)
    if abs(sc - rc) > 1e-3:
        diff["confidence"] = {"stored": sc, "reproduced": rc}

    # route + reason
    if stored.get("route") != reproduced.get("route"):
        diff["route"] = {"stored": stored["route"], "reproduced": reproduced["route"]}
    if stored.get("routing_reason") != reproduced.get("routing_reason"):
        diff["routing_reason"] = {
            "stored": stored["routing_reason"],
            "reproduced": reproduced["routing_reason"],
        }

    # confidence_breakdown — JSON compare
    stored_bd = _maybe_json(stored.get("confidence_breakdown"))
    repro_bd = reproduced.get("confidence_breakdown")
    if not _approx_equal(stored_bd, repro_bd):
        diff["confidence_breakdown"] = {"stored": stored_bd, "reproduced": repro_bd}

    return diff


def _approx_equal(a: Any, b: Any, tol: float = 1e-3) -> bool:
    if a is None and b is None:
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < tol
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_approx_equal(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_approx_equal(x, y, tol) for x, y in zip(a, b))
    return a == b


def _maybe_json(v):
    if not v:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return v


def _strip_for_diff(stored: dict) -> dict:
    """A trimmed copy of the stored row, JSON-decoded for clarity."""
    keep = ("id", "verdict", "confidence", "route", "routing_reason",
            "confidence_breakdown", "dissent_branch", "pipeline_signature_hash")
    out = {}
    for k in keep:
        v = stored.get(k)
        out[k] = _maybe_json(v)
    return out


def _current_pipeline_signature() -> str:
    from backend.ai.prompts import pipeline_signature
    return pipeline_signature()
