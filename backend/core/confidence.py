"""Confidence routing — implements the Confidence Veil.

Routing rules (in priority order):
1. Mandatory criterion FAIL → mandatory_review (always)
2. Any anomaly with severity=high → mandatory_review
3. Any LLM-based FAIL → hitl_review (never auto-commit a disqualification)
4. Confidence below review_floor → mandatory_review
5. Confidence below auto_commit threshold → hitl_review
6. High confidence + deterministic + no anomalies → auto_commit

Cold-start mode (CPM has < calibration_threshold rows): use conservative
thresholds. After enough precedents accumulate the system relaxes.

Confidence breakdown — the "Mosaic" — is a dict of named components with
individual scores. The composite confidence is the harmonic mean of the
components (penalises any single weak component). This is how the UI
shows the officer *which part* is uncertain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.config import settings


@dataclass
class ConfidenceBreakdown:
    """Per-component confidence scores. All fields in [0, 1]."""

    ocr_quality: Optional[float] = None
    field_extraction: Optional[float] = None
    entity_match: Optional[float] = None
    date_parsing: Optional[float] = None
    semantic_match: Optional[float] = None
    rules_branch: Optional[float] = None
    llm_branch: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def composite(self) -> float:
        """Harmonic mean of present components. Penalises weakest link."""
        present = [v for v in self.__dict__.values() if v is not None]
        if not present:
            return 0.0
        if any(v <= 0 for v in present):
            return 0.0
        n = len(present)
        return n / sum(1.0 / v for v in present)


@dataclass
class RoutingDecision:
    """The router's verdict for one evaluation."""

    route: str               # auto_commit | hitl_review | mandatory_review
    reason: str              # human-readable
    requires_second_officer: bool = False
    triggers: list[str] = field(default_factory=list)


def route_evaluation(
    *,
    verdict: str,
    confidence: float,
    criterion_type: str,
    is_mandatory: bool,
    gfr_override_permitted: bool,
    anomalies: list[dict],
    cpm_count: int = 0,
) -> RoutingDecision:
    """Apply the routing rules in priority order.

    Args:
        verdict: PASS | FAIL | REVIEW
        confidence: composite confidence in [0, 1]
        criterion_type: one of the 5 types
        is_mandatory: True if criterion is GFR-mandatory
        gfr_override_permitted: True if GFR allows officer override
        anomalies: list of {flag_type, severity, ...} from smell test
        cpm_count: number of precedents in the corpus (for cold-start)
    """
    triggers: list[str] = []

    # Cold-start uses stricter thresholds
    if cpm_count < settings.cpm_calibration_threshold:
        auto_commit = settings.confidence.cold_start_auto_commit
        review_floor = settings.confidence.cold_start_review_floor
        triggers.append("cold_start_thresholds")
    else:
        auto_commit = settings.confidence.auto_commit
        review_floor = settings.confidence.review_floor

    high_severity_anomaly = any(a.get("severity") == "high" for a in anomalies)
    medium_severity_anomaly = any(a.get("severity") == "medium" for a in anomalies)

    # Rule 1: mandatory FAIL → mandatory review
    if is_mandatory and verdict == "FAIL":
        return RoutingDecision(
            route="mandatory_review",
            reason="Mandatory criterion failed; officer confirmation required before exclusion.",
            requires_second_officer=gfr_override_permitted,
            triggers=triggers + ["mandatory_fail"],
        )

    # Rule 2: high-severity anomaly → mandatory review
    if high_severity_anomaly:
        return RoutingDecision(
            route="mandatory_review",
            reason="High-severity anomaly detected; officer must confirm before commitment.",
            requires_second_officer=False,
            triggers=triggers + ["high_severity_anomaly"],
        )

    # Rule 3: LLM-based FAIL never auto-commits
    if verdict == "FAIL" and criterion_type == "qualitative_assessment":
        return RoutingDecision(
            route="hitl_review",
            reason="Qualitative FAIL is never auto-committed.",
            triggers=triggers + ["llm_fail_no_auto"],
        )

    # Rule 4: very low confidence → mandatory review
    if confidence < review_floor:
        return RoutingDecision(
            route="mandatory_review",
            reason=f"Confidence {confidence:.0%} is below the {review_floor:.0%} floor; officer judgement required.",
            triggers=triggers + ["low_confidence"],
        )

    # Rule 5: medium-severity anomaly OR mid-band confidence → HITL
    if medium_severity_anomaly:
        return RoutingDecision(
            route="hitl_review",
            reason="Medium-severity anomaly noted; officer should review.",
            triggers=triggers + ["medium_severity_anomaly"],
        )
    if confidence < auto_commit:
        return RoutingDecision(
            route="hitl_review",
            reason=f"Confidence {confidence:.0%} is below the {auto_commit:.0%} auto-commit threshold.",
            triggers=triggers + ["mid_confidence"],
        )

    # Rule 6: deterministic + high confidence + no flags → auto-commit
    deterministic_types = {"numeric_threshold", "categorical_presence", "temporal_recency"}
    if criterion_type in deterministic_types:
        return RoutingDecision(
            route="auto_commit",
            reason=f"High-confidence deterministic evaluation ({confidence:.0%}).",
            triggers=triggers + ["deterministic_high_confidence"],
        )

    # Default: qualitative cases never auto-commit even at high confidence
    return RoutingDecision(
        route="hitl_review",
        reason="Qualitative criteria always go to officer review.",
        triggers=triggers + ["qualitative_default_hitl"],
    )
