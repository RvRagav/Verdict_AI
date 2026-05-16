"""State machine for tender lifecycle and evaluation status.

Pure functions. No I/O. Returns next-state names; the caller persists.

The state machine is documentation that becomes enforcement: every API
endpoint that mutates a tender consults this module first. Illegal
transitions raise StateError, surfaced to the client as HTTP 409.
"""

from __future__ import annotations

from typing import Optional


class StateError(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, from_state: str, target: str, allowed: list[str]):
        self.from_state = from_state
        self.target = target
        self.allowed = allowed
        super().__init__(
            f"Illegal transition: {from_state} → {target}. Allowed: {', '.join(allowed)}"
        )


# ─── Tender state machine ──────────────────────────────────────────────


TENDER_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["DOCUMENTS_PENDING"],
    "DOCUMENTS_PENDING": ["DOCUMENTS_PROCESSING", "CRITERIA_EXTRACTING"],
    "DOCUMENTS_PROCESSING": ["DOCUMENTS_READY", "DOCUMENTS_PENDING"],
    "DOCUMENTS_READY": ["CRITERIA_EXTRACTING"],
    "CRITERIA_EXTRACTING": ["CRITERIA_PENDING_REVIEW"],
    "CRITERIA_PENDING_REVIEW": ["CRITERIA_APPROVED", "CRITERIA_EXTRACTING"],
    "CRITERIA_APPROVED": ["CHECKLIST_PENDING", "CRITERIA_EXTRACTING"],
    "CHECKLIST_PENDING": ["PRELIMINARY_DONE"],
    "PRELIMINARY_DONE": ["EVALUATING"],
    "EVALUATING": ["EVALUATIONS_COMPUTED"],
    "EVALUATIONS_COMPUTED": ["HITL_PENDING", "EVALUATION_COMPLETE"],
    "HITL_PENDING": ["EVALUATION_COMPLETE", "EVALUATING"],
    "EVALUATION_COMPLETE": ["REPORT_GENERATED", "EVALUATING"],
    "REPORT_GENERATED": ["FINALIZED"],
    "FINALIZED": [],
}


# Friendly progress percentage shown to the user in the step indicator.
TENDER_PROGRESS_PCT: dict[str, int] = {
    "DRAFT": 5,
    "DOCUMENTS_PENDING": 10,
    "DOCUMENTS_PROCESSING": 20,
    "DOCUMENTS_READY": 30,
    "CRITERIA_EXTRACTING": 35,
    "CRITERIA_PENDING_REVIEW": 45,
    "CRITERIA_APPROVED": 55,
    "CHECKLIST_PENDING": 60,
    "PRELIMINARY_DONE": 65,
    "EVALUATING": 75,
    "EVALUATIONS_COMPUTED": 85,
    "HITL_PENDING": 90,
    "EVALUATION_COMPLETE": 95,
    "REPORT_GENERATED": 98,
    "FINALIZED": 100,
}


def can_transition(from_state: str, target: str) -> bool:
    return target in TENDER_TRANSITIONS.get(from_state, [])


def transition(from_state: str, target: str) -> str:
    if not can_transition(from_state, target):
        raise StateError(from_state, target, TENDER_TRANSITIONS.get(from_state, []))
    return target


def progress_pct(state: str) -> int:
    return TENDER_PROGRESS_PCT.get(state, 0)


# ─── Step grouping for the UI ──────────────────────────────────────────

# The Tender Space shows a horizontal step indicator with five steps.
# Each underlying state maps to one of these steps.
TENDER_STEP_NAMES: list[str] = [
    "setup",
    "documents",
    "criteria",
    "evaluation",
    "report",
]


def step_for_state(state: str) -> str:
    if state in ("DRAFT",):
        return "setup"
    if state in ("DOCUMENTS_PENDING", "DOCUMENTS_PROCESSING", "DOCUMENTS_READY"):
        return "documents"
    if state in ("CRITERIA_EXTRACTING", "CRITERIA_PENDING_REVIEW",
                 "CRITERIA_APPROVED", "CHECKLIST_PENDING", "PRELIMINARY_DONE"):
        return "criteria"
    if state in ("EVALUATING", "EVALUATIONS_COMPUTED", "HITL_PENDING",
                 "EVALUATION_COMPLETE"):
        return "evaluation"
    return "report"


# ─── Evaluation state machine ──────────────────────────────────────────


EVALUATION_TRANSITIONS: dict[str, list[str]] = {
    "pending_review": ["resolved", "pending_second_officer"],
    "pending_second_officer": ["resolved", "pending_review"],
    "auto_committed": [],
    "resolved": [],
}


def can_eval_transition(from_state: str, target: str) -> bool:
    return target in EVALUATION_TRANSITIONS.get(from_state, [])


def eval_transition(from_state: str, target: str) -> str:
    if not can_eval_transition(from_state, target):
        raise StateError(from_state, target, EVALUATION_TRANSITIONS.get(from_state, []))
    return target
