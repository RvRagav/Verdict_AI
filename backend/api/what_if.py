"""What-If Simulator — show consequences before the officer decides.

Given an evaluation cell and a proposed action (confirm/override),
compute what changes across the dossier:
  - Does the bidder's eligibility status change?
  - Does this trigger a concurrence requirement?
  - How many cells share the same source document?
  - What's the new pass/fail/review distribution for this bidder?
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from typing import Optional

from backend.api.dependencies import get_db


router = APIRouter(prefix="/evaluations/{evaluation_id}/what-if", tags=["what-if"])


class WhatIfRequest(BaseModel):
    action: str  # "confirm" | "override"
    new_verdict: Optional[str] = None  # required if action == "override"


@router.post("")
def simulate(evaluation_id: str, payload: WhatIfRequest, conn=Depends(get_db)):
    """Simulate the consequence of confirming or overriding this cell."""

    # Load the evaluation
    ev = conn.execute(
        """SELECT e.*, b.company_name, c.is_mandatory, c.criterion_text
           FROM evaluations e
           JOIN bidders b ON b.id = e.bidder_id
           JOIN criteria c ON c.id = e.criterion_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    ev = dict(ev)
    bidder_id = ev["bidder_id"]
    tender_id = ev["tender_id"]

    # Current verdict distribution for this bidder
    all_cells = conn.execute(
        "SELECT id, verdict, route FROM evaluations WHERE tender_id = ? AND bidder_id = ?",
        (tender_id, bidder_id),
    ).fetchall()

    current_pass = sum(1 for c in all_cells if c["verdict"] == "PASS")
    current_fail = sum(1 for c in all_cells if c["verdict"] == "FAIL")
    current_review = sum(1 for c in all_cells if c["verdict"] == "REVIEW")
    total = len(all_cells)

    # Simulate the change
    if payload.action == "confirm":
        # Confirming keeps the current verdict
        new_verdict = ev["verdict"]
    elif payload.action == "override":
        if not payload.new_verdict:
            raise HTTPException(status_code=400, detail="new_verdict required for override")
        new_verdict = payload.new_verdict
    else:
        raise HTTPException(status_code=400, detail="action must be 'confirm' or 'override'")

    # Compute new distribution
    old_verdict = ev["verdict"]
    sim_pass = current_pass
    sim_fail = current_fail
    sim_review = current_review

    # Remove old verdict count
    if old_verdict == "PASS": sim_pass -= 1
    elif old_verdict == "FAIL": sim_fail -= 1
    elif old_verdict == "REVIEW": sim_review -= 1

    # Add new verdict count
    if new_verdict == "PASS": sim_pass += 1
    elif new_verdict == "FAIL": sim_fail += 1
    elif new_verdict == "REVIEW": sim_review += 1

    # Determine eligibility change
    def is_eligible(p, f, t):
        if t == 0: return False
        return f <= t * 0.3  # ≤30% FAIL = eligible

    was_eligible = is_eligible(current_pass, current_fail, total)
    will_be_eligible = is_eligible(sim_pass, sim_fail, total)

    eligibility_change = None
    if not was_eligible and will_be_eligible:
        eligibility_change = f"{ev['company_name']} moves from NOT ELIGIBLE → ELIGIBLE"
    elif was_eligible and not will_be_eligible:
        eligibility_change = f"{ev['company_name']} moves from ELIGIBLE → NOT ELIGIBLE"

    # Concurrence requirement
    is_mandatory = bool(ev["is_mandatory"])
    is_override = payload.action == "override"
    route_mandatory = ev["route"] == "mandatory_review"
    concurrence_required = is_override and route_mandatory

    # Shared source document — how many other cells use the same source doc?
    shared_cells = []
    if ev.get("source_doc_id"):
        shared = conn.execute(
            """SELECT e.id, c.criterion_text, e.verdict
               FROM evaluations e
               JOIN criteria c ON c.id = e.criterion_id
               WHERE e.source_doc_id = ? AND e.id != ? AND e.bidder_id = ?""",
            (ev["source_doc_id"], evaluation_id, bidder_id),
        ).fetchall()
        shared_cells = [
            {"id": s["id"], "criterion": s["criterion_text"][:60], "verdict": s["verdict"]}
            for s in shared
        ]

    # Build consequence summary
    consequences = []
    if eligibility_change:
        consequences.append({"type": "eligibility", "text": eligibility_change, "severity": "high"})
    if concurrence_required:
        consequences.append({"type": "concurrence", "text": "This triggers a concurrence request to a second officer.", "severity": "medium"})
    if shared_cells:
        consequences.append({
            "type": "shared_source",
            "text": f"{len(shared_cells)} other cell(s) reference the same source document.",
            "severity": "low",
        })

    # Verdict change description
    verdict_change = None
    if old_verdict != new_verdict:
        verdict_change = f"Cell verdict: {old_verdict} → {new_verdict}"

    # ─── AI-powered reasoning about the consequence ───────────────────
    ai_reasoning = _generate_ai_reasoning(
        conn, ev, payload.action, new_verdict, old_verdict,
        eligibility_change, concurrence_required, shared_cells,
        sim_pass, sim_fail, total,
    )
    if ai_reasoning:
        consequences.append({"type": "ai_reasoning", "text": ai_reasoning, "severity": "info"})

    return {
        "evaluation_id": evaluation_id,
        "action": payload.action,
        "current_verdict": old_verdict,
        "simulated_verdict": new_verdict,
        "verdict_change": verdict_change,
        "bidder": {
            "name": ev["company_name"],
            "current": {"pass": current_pass, "fail": current_fail, "review": current_review, "total": total},
            "simulated": {"pass": sim_pass, "fail": sim_fail, "review": sim_review, "total": total},
            "was_eligible": was_eligible,
            "will_be_eligible": will_be_eligible,
            "eligibility_change": eligibility_change,
        },
        "concurrence_required": concurrence_required,
        "shared_source_cells": shared_cells,
        "consequences": consequences,
        "ai_reasoning": ai_reasoning,
    }


def _generate_ai_reasoning(conn, ev, action, new_verdict, old_verdict,
                           eligibility_change, concurrence_required, shared_cells,
                           sim_pass, sim_fail, total) -> Optional[str]:
    """Use Bedrock to reason about the consequence of this decision.

    Returns a 2-3 sentence intelligent analysis that helps the officer
    understand the IMPACT of their decision — not just the numbers.
    """
    try:
        from backend.ai import bedrock_client

        # Build context for the AI
        criterion_text = ev.get("criterion_text", "")[:200]
        extracted = ev.get("extracted_value", "")
        confidence = int(ev.get("confidence", 0) * 100)
        company = ev.get("company_name", "")

        prompt = (
            f"You are advising a procurement officer about the consequence of their decision. "
            f"Be concise (2-3 sentences max). Be specific to this case.\n\n"
            f"CONTEXT:\n"
            f"- Criterion: {criterion_text}\n"
            f"- Bidder: {company}\n"
            f"- Current AI verdict: {old_verdict} ({confidence}% confident)\n"
            f"- Officer wants to: {action} → {new_verdict}\n"
            f"- Bidder's current score: {sim_pass} PASS / {sim_fail} FAIL out of {total}\n"
            f"- Concurrence required: {'Yes' if concurrence_required else 'No'}\n"
            f"- Shared source docs: {len(shared_cells)} other cells use the same document\n"
            f"- Eligibility impact: {eligibility_change or 'No change'}\n\n"
            f"Give the officer a brief, intelligent analysis of what this decision means. "
            f"Mention any risks or things they should verify. "
            f"If the override is defensible, say why. If risky, say why."
        )

        resp = bedrock_client.invoke(
            invocation_type="what_if_reasoning",
            system="You are a senior procurement advisor. Give brief, actionable advice. 2-3 sentences max.",
            user=prompt,
            prompt_version="1.0.0",
            tender_id=ev.get("tender_id"),
            conn=conn,
            max_tokens=200,
        )
        if resp.text and not resp.error:
            return resp.text.strip()
    except Exception:
        pass
    return None
