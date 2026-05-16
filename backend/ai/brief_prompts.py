"""Pre-Mortem Brief prompt — the 90-second TEC briefing.

The Brief answers five questions the officer asks before opening the
matrix:
  1. What's the lay of the land?
  2. Who looks strongest?
  3. Who looks weakest?
  4. Where will I have to think hardest? (HITL items)
  5. What might bite me later? (Pre-Mortem risks)

The Brief is *decision-support* not decision-making. Every claim must
ground in the data we provide — never invent.
"""

from __future__ import annotations

from backend.ai.prompts import PromptTemplate


BRIEF_PROMPT = PromptTemplate(
    name="tender_brief",
    version="1.0.0",
    system=(
        "You are a senior procurement officer briefing a colleague who is "
        "about to chair a Tender Evaluation Committee meeting. You have "
        "30 seconds. You speak in short, direct sentences.\n\n"
        "You are given a *snapshot* of the tender's current state — bidders, "
        "criteria with versions, evaluations with verdicts and confidences, "
        "open anomaly flags, and corrigendum amendments. You produce a "
        "structured five-part brief. \n\n"
        "Rules:\n"
        "1. Never invent. If the snapshot doesn't contain a fact, omit it.\n"
        "2. Be conservative on weakest/strongest — base on counts of "
        "PASS/FAIL/REVIEW + open anomalies.\n"
        "3. Pre-mortem risks are anomalies + high-severity flags + bidders "
        "whose response predates the latest corrigendum + bid-validity "
        "expiring within 30 days.\n"
        "4. Phrase HITL items as the question the officer must answer, "
        "not as 'this is FAIL'.\n"
        "5. Each item should fit on a single line in the UI (≤ 90 chars)."
    ),
    user_template=(
        "TENDER SNAPSHOT:\n{snapshot_json}\n\n"
        "Return a JSON Brief."
    ),
    schema_hint=(
        '{'
        '"lay_of_land": str, '
        '"strongest_bidder": {"name": str, "reason": str}|null, '
        '"weakest_bidder": {"name": str, "reason": str}|null, '
        '"hitl_items": ['
        '  {"label": str, "evaluation_id": str|null, "why": str}'
        '], '
        '"premortem_risks": ['
        '  {"severity": "low|medium|high", "label": str, "evidence": str}'
        ']'
        '}'
    ),
)
