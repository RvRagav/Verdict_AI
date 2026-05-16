"""Verdict computation (L4) + Dissent (L6) + Routing.

Inputs: an extracted Evidence dict (from L3) and the criterion.
Outputs: a complete Evaluation row + dissent + officer-grade explanation.

Process:
1. Compute verdict from evidence (rules-based per type, except qualitative)
2. Compute confidence breakdown (the Mosaic — 5 named components)
3. Run dissent (Bedrock devil's advocate)
4. Route via core.confidence
5. Build officer-grade explanation
6. Insert evaluations row + audit event

The whole thing is reproducible: every Bedrock call goes through the
cache, and the pipeline_signature_hash is stamped onto the row.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import DISSENT, pipeline_signature
from backend.core import audit_chain
from backend.core.confidence import (
    ConfidenceBreakdown,
    route_evaluation,
)


logger = logging.getLogger(__name__)


# ─── Driver ──────────────────────────────────────────────────────────────


def compute_evaluation(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    criterion: dict,
    evidence: dict,
    cpm_count: int = 0,
    actor: str = "system",
) -> dict:
    """Compute the verdict, dissent, route, and persist the evaluation."""
    ctype = criterion.get("criterion_type") or "qualitative_assessment"
    is_mandatory = bool(criterion.get("is_mandatory", False))
    gfr_override = bool(criterion.get("gfr_override_permitted", True))

    # 1. Verdict
    verdict, verdict_method = _verdict_from_evidence(ctype, evidence, criterion)

    # 2. Confidence breakdown (the Mosaic)
    breakdown = _confidence_breakdown(evidence, ctype)
    confidence = breakdown.composite()

    # 3. Anomalies (smell-test results pre-attached on evidence, if any)
    anomalies = evidence.get("anomalies") or []

    # 3b. Branch disagreement is itself a routing signal
    union = evidence.get("union") or {}
    if union.get("agreement") == "disagree":
        anomalies = list(anomalies) + [{
            "flag_type": "novel",
            "severity": "medium",
            "message": "Rules and LLM extractors disagreed on the value.",
            "evidence_data": {"branches": evidence.get("branches", {})},
        }]

    # 4. Dissent (Bedrock devil's-advocate)
    dissent_data, dissent_hash = _run_dissent(
        conn, tender_id=tender_id, criterion=criterion,
        evidence=evidence, verdict=verdict, confidence=confidence,
    )

    # If dissent is high severity, treat as an anomaly for routing
    if dissent_data and dissent_data.get("severity") == "high":
        anomalies = list(anomalies) + [{
            "flag_type": "novel",
            "severity": "high",
            "message": dissent_data.get("dissent", "Dissent flagged this verdict."),
        }]

    # 5. Route
    routing = route_evaluation(
        verdict=verdict, confidence=confidence,
        criterion_type=ctype,
        is_mandatory=is_mandatory,
        gfr_override_permitted=gfr_override,
        anomalies=anomalies,
        cpm_count=cpm_count,
    )

    # 6. Officer-grade explanation
    explanation = _build_explanation(criterion, evidence, verdict, confidence,
                                      breakdown, dissent_data, routing)

    # 7. Persist
    evaluation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    eval_state = "auto_committed" if routing.route == "auto_commit" else "pending_review"

    conn.execute(
        """INSERT INTO evaluations
           (id, tender_id, bidder_id, criterion_id,
            verdict, confidence, confidence_breakdown,
            route, routing_reason,
            extracted_value, source_doc_id, source_page, source_bbox,
            rules_branch, llm_branch, dissent_branch,
            branch_agreement, branch_agreement_score,
            anomalies, entity_match_flag,
            explanation,
            state, requires_second_officer,
            extraction_prompt_hash, verdict_prompt_hash, dissent_prompt_hash,
            pipeline_signature_hash,
            criterion_version,
            created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            evaluation_id, tender_id, bidder_id, criterion["id"],
            verdict, round(confidence, 4),
            json.dumps(breakdown.to_dict()),
            routing.route, routing.reason,
            json.dumps(evidence.get("value")) if evidence.get("value") is not None else None,
            evidence.get("source_doc_id"),
            evidence.get("source_page"),
            json.dumps(evidence["source_bbox"]) if evidence.get("source_bbox") else None,
            json.dumps({"method": evidence.get("evaluation_method"),
                       "notes": evidence.get("notes"),
                       "extraction_confidence": evidence.get("extraction_confidence")}),
            json.dumps({"verdict": evidence.get("value", {}).get("verdict") if isinstance(evidence.get("value"), dict) else None,
                       "reasoning": evidence.get("value", {}).get("reasoning") if isinstance(evidence.get("value"), dict) else None}) if evidence.get("evaluation_method") == "llm" else None,
            json.dumps(dissent_data) if dissent_data else None,
            None, None,  # branch_agreement & score: filled by union evaluator (TODO)
            json.dumps(anomalies) if anomalies else None,
            1 if evidence.get("entity_match_flag") else 0,
            json.dumps(explanation),
            eval_state,
            1 if routing.requires_second_officer else 0,
            evidence.get("_extraction_prompt_hash"),
            None,  # verdict_prompt_hash (rules-derived for most types)
            dissent_hash,
            pipeline_signature(),
            int(criterion.get("current_version") or 1),
            now,
        ),
    )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="evaluation_computed",
        event_data={
            "evaluation_id": evaluation_id,
            "bidder_id": bidder_id,
            "criterion_id": criterion["id"],
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "route": routing.route,
        },
        actor=actor,
    )

    # Auto-capture a point-in-time snapshot the moment the evaluation
    # is born. The officer's later decision will create a second snapshot.
    try:
        from backend.services import replay_service
        replay_service.capture(
            conn, evaluation_id=evaluation_id, officer_id=actor,
        )
    except Exception as exc:
        logger.warning("Initial auto-replay capture failed: %s", exc)

    # Record evidence citations from the evidence dict so the PDFViewer
    # can render highlights AND the reverse index works.
    try:
        from backend.services import citation_service
        citation_service.record_from_evaluation_evidence(
            conn, evaluation_id=evaluation_id, evidence=evidence, actor=actor,
        )
    except Exception as exc:
        logger.warning("Citation recording failed: %s", exc)

    return {
        "id": evaluation_id,
        "verdict": verdict,
        "confidence": confidence,
        "route": routing.route,
        "routing_reason": routing.reason,
        "state": eval_state,
        "explanation": explanation,
        "anomalies": anomalies,
        "dissent": dissent_data,
    }


# ─── Verdict computation ───────────────────────────────────────────────


def _verdict_from_evidence(ctype: str, evidence: dict, criterion: dict) -> tuple[str, str]:
    """Determine PASS/FAIL/REVIEW from extracted evidence."""
    value = evidence.get("value")

    # Missing value: distinguish "we read the docs and the figure is
    # missing" from "we have no docs at all".
    if value is None:
        # If we've read the bidder's submission and the value isn't
        # there, this is a confident FAIL on a mandatory criterion —
        # the bidder did not produce the required evidence.
        # If we don't even have docs (extraction_confidence==0), it's
        # genuinely uncertain → REVIEW.
        ext_conf = float(evidence.get("extraction_confidence", 0.0) or 0.0)
        if ext_conf >= 0.5:
            return "FAIL", "evidence_missing_in_submission"
        return "REVIEW", "no_evidence"

    if ctype == "numeric_threshold":
        threshold = _parse_threshold(criterion)
        threshold_rupees = _threshold_in_rupees(threshold)
        rule = (threshold.get("measurement_period") or "single").lower()
        expected_n = int(threshold.get("period_n_years") or 1)

        # Multi-figure path: use the figures list from the reconciler
        if isinstance(value, dict) and isinstance(value.get("figures"), list):
            figures = value["figures"]
            found_count = len(figures)
            rupees_list = [int(f.get("rupees") or 0) for f in figures]

            if not threshold_rupees or not rupees_list:
                return "REVIEW", "rules_unclear"

            # Apply the rule
            if rule == "each_of_n_years":
                if found_count < expected_n:
                    # We don't have all required years → REVIEW (avoid silent FAIL)
                    return "REVIEW", f"missing_periods_found_{found_count}_of_{expected_n}"
                all_ok = all(r >= threshold_rupees for r in rupees_list[:expected_n])
                return ("PASS" if all_ok else "FAIL"), "rules_each_year"

            if rule == "average_of_n_years":
                if found_count < expected_n:
                    return "REVIEW", f"missing_periods_found_{found_count}_of_{expected_n}"
                avg = sum(rupees_list[:expected_n]) / expected_n
                return ("PASS" if avg >= threshold_rupees else "FAIL"), "rules_average"

            if rule == "any_of_n_years":
                any_ok = any(r >= threshold_rupees for r in rupees_list)
                return ("PASS" if any_ok else "FAIL"), "rules_any_year"

            if rule == "cumulative_n_years":
                if found_count < expected_n:
                    return "REVIEW", f"missing_periods_found_{found_count}_of_{expected_n}"
                total = sum(rupees_list[:expected_n])
                return ("PASS" if total >= threshold_rupees else "FAIL"), "rules_cumulative"

            # Default: single
            best = max(rupees_list)
            return ("PASS" if best >= threshold_rupees else "FAIL"), "rules_single"

        # Legacy single-figure path
        bidder_rupees = value.get("rupees", 0) if isinstance(value, dict) else 0
        if threshold_rupees and bidder_rupees:
            return ("PASS" if bidder_rupees >= threshold_rupees else "FAIL"), "rules_compare"
        return "REVIEW", "rules_unclear"

    if ctype == "categorical_presence":
        if not isinstance(value, dict):
            return "REVIEW", "rules_unclear"
        if not value.get("found"):
            return "FAIL", "rules_not_found"
        is_valid = value.get("is_valid")
        if is_valid is True:
            return "PASS", "rules_valid"
        if is_valid is False:
            return "FAIL", "rules_expired"
        return "REVIEW", "rules_validity_unclear"

    if ctype == "temporal_recency":
        if not isinstance(value, dict):
            return "REVIEW", "rules_unclear"
        count = int(value.get("qualifying_count", value.get("count", 0)) or 0)
        required = int(value.get("required_count", 3) or 3)
        return ("PASS" if count >= required else "FAIL"), "rules_count"

    if ctype == "qualitative_assessment":
        # Verdict is whatever the LLM said
        if isinstance(value, dict):
            v = value.get("verdict", "REVIEW")
            if v in ("PASS", "FAIL", "REVIEW"):
                return v, "llm"
        return "REVIEW", "llm_unclear"

    return "REVIEW", "unknown_type"


# ─── Confidence Mosaic ─────────────────────────────────────────────────


def _confidence_breakdown(evidence: dict, ctype: str) -> ConfidenceBreakdown:
    """Compute per-component confidence.

    Critical edge case: if both extractor branches *correctly* report
    'value not found in the bidder's documents', we treat that as
    HIGH-confidence negative evidence (the bidder is missing required
    information), NOT zero confidence. We omit the branch components
    from the Mosaic in that case so the composite reflects "I read
    the docs and the figure is missing", not "the AI is lost".
    """
    breakdown = ConfidenceBreakdown()
    breakdown.ocr_quality = float(evidence.get("ocr_confidence", 0.0) or 0.0)
    breakdown.field_extraction = float(evidence.get("extraction_confidence", 0.0) or 0.0)
    breakdown.entity_match = 0.0 if evidence.get("entity_match_flag") else 1.0

    branches = evidence.get("branches") or {}
    rules_branch = branches.get("rules") if isinstance(branches.get("rules"), dict) else {}
    llm_branch   = branches.get("llm")   if isinstance(branches.get("llm"),   dict) else {}

    rules_found = bool(rules_branch.get("found"))
    llm_found   = bool(llm_branch.get("found")) and not llm_branch.get("error")

    # If at least one branch FOUND a value, expose its branch confidence.
    if rules_found:
        breakdown.rules_branch = float(rules_branch.get("confidence") or 0.0)
    if llm_found:
        breakdown.llm_branch = float(llm_branch.get("confidence") or 0.0)

    # If NEITHER branch found, leave both branch fields out — the Mosaic
    # then shows OCR + extraction + entity-match (= "I read the docs;
    # the figure is missing") which is the truth.

    if ctype == "qualitative_assessment":
        # Qualitative is inherently LLM-only; always carry semantic_match
        sem = breakdown.llm_branch
        if sem is None:
            sem = float(evidence.get("extraction_confidence", 0.0) or 0.0)
        breakdown.semantic_match = sem

    if ctype in ("temporal_recency", "categorical_presence"):
        value = evidence.get("value") or {}
        if isinstance(value, dict):
            if value.get("validity_date") or value.get("projects"):
                breakdown.date_parsing = 0.85
            else:
                breakdown.date_parsing = 0.4

    return breakdown


# ─── Dissent ────────────────────────────────────────────────────────────


def _run_dissent(conn, *, tender_id: str, criterion: dict,
                 evidence: dict, verdict: str, confidence: float) -> tuple[Optional[dict], Optional[str]]:
    """Run the devil's advocate. Returns (dissent_dict, prompt_hash)."""
    user_prompt = DISSENT.render_user(
        verdict=verdict,
        confidence=confidence,
        criterion_text=criterion.get("criterion_text", ""),
        extracted_value=json.dumps(evidence.get("value")) if evidence.get("value") else "(none)",
        evidence_text=evidence.get("notes") or "",
    )
    resp = bedrock_client.invoke(
        invocation_type="dissent",
        system=DISSENT.system,
        user=user_prompt,
        prompt_version=DISSENT.version,
        structured=True,
        schema_hint=DISSENT.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not resp.data or not isinstance(resp.data, dict):
        return None, None
    return resp.data, resp.prompt_hash


# ─── Officer-grade explanation ─────────────────────────────────────────


def _build_explanation(
    criterion: dict, evidence: dict, verdict: str, confidence: float,
    breakdown: ConfidenceBreakdown, dissent: Optional[dict], routing,
) -> dict:
    """Compose a structured, human-friendly explanation for the UI.

    The Confidence Veil shows up here: the *headline* never says
    "This bidder PASSES" — it says "I'm 91% confident this passes,
    please confirm".
    """
    pct = int(round(confidence * 100))
    ctype = criterion.get("criterion_type", "")
    clause = criterion.get("source_clause_ref") or "the criterion"

    # Headline (Confidence Veil framing — AI never asserts the verdict)
    if verdict == "PASS":
        headline = f"I'm {pct}% confident this satisfies {clause}."
    elif verdict == "FAIL":
        headline = f"I'm {pct}% confident this does not satisfy {clause}."
    else:
        headline = f"I cannot determine this with confidence (currently {pct}%)."

    # Detail
    detail_parts = []
    value = evidence.get("value")
    branches = evidence.get("branches") or {}
    union = evidence.get("union") or {}
    notes = evidence.get("notes")

    if value is None:
        # Both branches looked and didn't find the figure
        if branches:
            detail_parts.append(
                "I read the bidder's submission but did not find this figure. "
                "Officer to verify whether the supporting document is missing."
            )
        else:
            detail_parts.append(
                "Bidder has not uploaded the relevant supporting document."
            )
    elif ctype == "numeric_threshold" and isinstance(value, dict):
        figures = value.get("figures")
        threshold = criterion.get("threshold_value") or {}
        if isinstance(threshold, str):
            try:
                threshold = json.loads(threshold)
            except (json.JSONDecodeError, TypeError):
                threshold = {}
        thr_rupees = (threshold or {}).get("rupees")
        if isinstance(figures, list) and figures:
            lines = []
            for f in figures:
                rups = int(f.get("rupees") or 0)
                if rups >= 10_000_000:
                    human = f"Rs. {rups / 10_000_000:.2f} Cr"
                elif rups >= 100_000:
                    human = f"Rs. {rups / 100_000:.2f} L"
                else:
                    human = f"Rs. {rups:,}"
                period = f.get("period_label") or "(unspecified)"
                ok = "✓" if (thr_rupees and rups >= thr_rupees) else "✗"
                lines.append(f"{ok} {period}: {human}")
            detail_parts.append("Figures found: " + " · ".join(lines))
            if value.get("found_count", 0) < value.get("expected_count", 0):
                detail_parts.append(
                    f"Note: criterion expects {value['expected_count']} period(s) "
                    f"but only {value['found_count']} found."
                )
        else:
            rups = int(value.get("rupees", 0) or 0)
            if rups >= 10_000_000:
                human = f"Rs. {rups / 10_000_000:.2f} crore"
            elif rups >= 100_000:
                human = f"Rs. {rups / 100_000:.2f} lakh"
            else:
                human = f"Rs. {rups:,}"
            detail_parts.append(f"Extracted figure: {human}")
    elif ctype == "categorical_presence" and isinstance(value, dict):
        if value.get("found"):
            detail_parts.append(
                f"Found {value.get('certificate_type', 'certificate').upper()}: "
                f"{value.get('registration_number')}"
            )
            if value.get("validity_date"):
                detail_parts.append(f"Validity: {value['validity_date']}")
        else:
            detail_parts.append("Required document was not found in the bidder's submission.")
    elif ctype == "temporal_recency" and isinstance(value, dict):
        detail_parts.append(
            f"Found {value.get('qualifying_count', value.get('count', 0))} qualifying project(s) "
            f"(required: {value.get('required_count', 0)})"
        )
    elif isinstance(value, dict) and value.get("reasoning"):
        detail_parts.append(value["reasoning"][:220])

    # Always surface union agreement when we have one
    agreement = union.get("agreement")
    if agreement == "disagree":
        detail_parts.append(
            "Note: rules and LLM extractors disagreed; officer review is recommended."
        )
    elif agreement == "partial":
        detail_parts.append("Note: only one extractor branch found a value.")

    detail = " ".join(detail_parts) if detail_parts else (notes or "Refer to the source document.")

    # Facts (the Mosaic, exposed)
    facts: list[str] = []
    bd = breakdown.to_dict()
    for k, v in bd.items():
        label = k.replace("_", " ").title()
        facts.append(f"{label}: {int(round(v * 100))}%")

    # Source reference
    source_ref = ""
    if evidence.get("source_doc_id"):
        if evidence.get("source_page"):
            source_ref = f"Source: doc {evidence['source_doc_id'][:8]}, page {evidence['source_page']}"
        else:
            source_ref = f"Source: doc {evidence['source_doc_id'][:8]}"

    # Confidence note
    confidence_note = (
        f"Composite confidence is the harmonic mean of the components above; "
        f"any one weak component pulls the total down."
    )

    # Next action — the routing reason, framed as guidance
    if routing.route == "auto_commit":
        next_action = "I will record this as confirmed unless you override."
    elif routing.route == "hitl_review":
        next_action = f"Please review and confirm. {routing.reason}"
    else:
        next_action = f"Officer review required. {routing.reason}"

    return {
        "headline": headline,
        "detail": detail,
        "facts": facts,
        "source_reference": source_ref,
        "confidence_note": confidence_note,
        "next_action": next_action,
        "dissent": dissent.get("dissent") if dissent else None,
        "dissent_severity": dissent.get("severity") if dissent else None,
    }


# ─── Threshold parsing ─────────────────────────────────────────────────


def _parse_threshold(criterion: dict) -> dict:
    raw = criterion.get("threshold_value")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _threshold_in_rupees(threshold: dict) -> int:
    """Convert a threshold spec to absolute rupees."""
    if not threshold:
        return 0
    if "rupees" in threshold:
        try:
            return int(threshold["rupees"])
        except (ValueError, TypeError):
            pass
    raw_value = threshold.get("value") or threshold.get("amount")
    unit = (threshold.get("unit") or "").lower().strip()
    if raw_value is None:
        return 0
    try:
        v = float(raw_value)
    except (ValueError, TypeError):
        return 0
    multipliers = {
        "crore": 10_000_000, "cr": 10_000_000,
        "lakh": 100_000, "lac": 100_000, "l": 100_000,
    }
    return int(v * multipliers.get(unit, 10_000_000 if v < 1000 else 1))
