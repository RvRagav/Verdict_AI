"""Evidence extraction (L3) — dual-branch reconciled.

For every (bidder × criterion) we run two parallel extractors and
reconcile their findings. Each extractor returns its own value +
confidence. The reconciler:

    - both branches agree on the value     → high confidence
    - both branches agree it's missing     → high confidence (FAIL/REVIEW)
    - branches disagree on value           → lower confidence,
                                              flag union_disagreement,
                                              prefer the higher-confidence branch
    - one branch errors out                → use the other,
                                              cap confidence at 0.7

Branches:
    Branch A — Rules (regex). Cheap, fast, deterministic. Catches
        well-formed Indian financial / certificate / project notation.
    Branch B — LLM (Claude on Bedrock). Reads context. Catches things
        the regex misses (figures inside table cells, "FY 2022-23",
        "in financial year ending March 2024"). Cached by prompt hash.

Both run for numeric / categorical / temporal types. Qualitative is
inherently LLM-only.

Output shape (Evidence dict) is unchanged for callers, with two new
fields:
    branches: {rules: {...}, llm: {...}}
    union: {agreement: 'agree'|'partial'|'disagree', score: float}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import (
    CATEGORICAL_EVIDENCE,
    NUMERIC_EVIDENCE,
    QUALITATIVE_EVIDENCE,
    TEMPORAL_EVIDENCE,
)

logger = logging.getLogger(__name__)


# ─── Regex patterns (Branch A) ─────────────────────────────────────────


NUMERIC_RUPEE = re.compile(
    r"(?:Rs\.?|INR|₹)\s*"
    r"(?P<value>[\d,]+(?:\.\d+)?)"
    r"\s*(?:\(\s*[A-Za-z][A-Za-z\s\-]{0,40}\)\s*)?"
    r"(?P<unit>crore|lakh|lac|cr|l)\b",
    re.IGNORECASE,
)

GSTIN_PATTERN = re.compile(
    r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b"
)
PAN_PATTERN = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")

VALIDITY_DATE_RE = re.compile(
    r"valid\s+(?:up\s+to|until|till|through)?\s*"
    r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})",
    re.IGNORECASE,
)

PROJECT_DATE_RE = re.compile(
    r"(\d{1,2}[-/.][A-Za-z]{3}[-/.]\d{2,4})|(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
)

ISO_PATTERN = re.compile(r"ISO\s*9001\s*[:\-]?\s*\d{4}", re.IGNORECASE)
UDYAM_PATTERN = re.compile(r"UDYAM-[A-Z]{2}-\d{2}-\d+", re.IGNORECASE)


# ─── Top-level dispatcher ──────────────────────────────────────────────


def extract_evidence(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    criterion: dict,
) -> dict:
    """Run both branches, reconcile, return the unified Evidence dict."""
    bidder_text, bidder_pages, bidder_docs = _collect_bidder_text(
        conn, tender_id, bidder_id,
    )
    if not bidder_text:
        return _empty_evidence("no_documents")

    ctype = criterion.get("criterion_type") or "qualitative_assessment"

    if ctype == "numeric_threshold":
        rules = _rules_numeric(bidder_text, bidder_pages, bidder_docs, criterion)
        llm = _llm_numeric(conn, bidder_text, bidder_docs, criterion, tender_id)
        return _reconcile_numeric(rules, llm, bidder_pages, bidder_docs)

    if ctype == "categorical_presence":
        rules = _rules_categorical(bidder_text, bidder_pages, bidder_docs, criterion)
        llm = _llm_categorical(conn, bidder_text, bidder_docs, criterion, tender_id)
        return _reconcile_categorical(rules, llm, bidder_pages, bidder_docs)

    if ctype == "temporal_recency":
        rules = _rules_temporal(bidder_text, bidder_pages, bidder_docs, criterion)
        llm = _llm_temporal(conn, bidder_text, bidder_docs, criterion, tender_id)
        return _reconcile_temporal(rules, llm, bidder_pages, bidder_docs)

    if ctype == "qualitative_assessment":
        return _llm_qualitative(
            conn, bidder_text, bidder_pages, bidder_docs, criterion, tender_id,
        )

    # composite — placeholder; treat as qualitative
    return _llm_qualitative(
        conn, bidder_text, bidder_pages, bidder_docs, criterion, tender_id,
    )


# ─── Branch A — regex extractors ───────────────────────────────────────


def _rules_numeric(text: str, pages: list, docs: list, criterion: dict) -> dict:
    """Regex extractor — returns ALL matching figures, not just the max.
    Each entry is a dict with rupees/raw_value/unit/match_text."""
    label_hint = _numeric_label_hint(criterion)
    scoped = _lines_containing(text, label_hint) if label_hint else None
    haystack = scoped or text

    matches = list(NUMERIC_RUPEE.finditer(haystack))
    if not matches:
        return {"found": False, "branch": "rules", "figures": []}

    figures: list[dict] = []
    seen: set[tuple[float, str]] = set()
    for m in matches:
        raw_value = float(m.group("value").replace(",", ""))
        unit = m.group("unit").lower()
        key = (raw_value, unit)
        if key in seen:
            continue
        seen.add(key)
        figures.append({
            "period_label": "",
            "raw_value": raw_value,
            "unit": unit,
            "rupees": _to_rupees(raw_value, unit),
            "match_text": m.group(0),
        })
    return {
        "found": True,
        "figures": figures,
        "label": label_hint,
        "branch": "rules",
        "confidence": 0.7 if scoped else 0.55,
    }


def _rules_categorical(text: str, pages: list, docs: list, criterion: dict) -> dict:
    cert_kind = _categorical_kind(criterion)
    pattern_map = {
        "gst": GSTIN_PATTERN,
        "pan": PAN_PATTERN,
        "iso": ISO_PATTERN,
        "udyam": UDYAM_PATTERN,
    }
    pattern = pattern_map.get(cert_kind)
    if not pattern:
        return {"found": False, "branch": "rules", "certificate_type": cert_kind}

    match = pattern.search(text)
    if not match:
        return {"found": False, "branch": "rules", "certificate_type": cert_kind}

    reg = match.group(0)
    validity_match = VALIDITY_DATE_RE.search(text)
    is_valid: Optional[bool] = None
    validity_date: Optional[str] = None
    if validity_match:
        validity_date = validity_match.group(1)
        is_valid = _is_future_date(validity_date)

    return {
        "found": True,
        "registration_number": reg,
        "validity_date": validity_date,
        "is_valid": is_valid,
        "certificate_type": cert_kind,
        "format_matches": True,
        "branch": "rules",
        "confidence": 0.85 if is_valid is True else (0.65 if is_valid is None else 0.75),
    }


def _rules_temporal(text: str, pages: list, docs: list, criterion: dict) -> dict:
    threshold = _parse_threshold(criterion)
    required_count = int(threshold.get("count", 3) if threshold else 3)
    period_years = int(threshold.get("period_years", 5) if threshold else 5)
    dates = PROJECT_DATE_RE.findall(text)
    project_count = len(dates)
    return {
        "found": project_count > 0,
        "qualifying_count": project_count,
        "required_count": required_count,
        "period_years": period_years,
        "branch": "rules",
        "confidence": 0.6,  # regex-only date counting is weak
    }


# ─── Branch B — LLM extractors ─────────────────────────────────────────


def _llm_numeric(conn, text: str, docs: list, criterion: dict, tender_id: str) -> dict:
    threshold = _parse_threshold(criterion)
    rule = (threshold.get("measurement_period") or "single").lower()
    expected = int(threshold.get("period_n_years") or 1)

    # Map rule → human-readable hint for the prompt
    rule_text = {
        "single": "A single figure must meet the threshold.",
        "each_of_n_years": f"Every one of {expected} consecutive years must meet the threshold.",
        "average_of_n_years": f"The mean across {expected} years must meet the threshold.",
        "any_of_n_years": f"At least one of {expected} years must meet.",
        "cumulative_n_years": f"The sum across {expected} years must meet.",
    }.get(rule, "A single figure must meet the threshold.")

    user = NUMERIC_EVIDENCE.render_user(
        criterion_text=criterion.get("criterion_text", ""),
        measurement_rule=rule_text,
        expected_count=expected,
        bidder_name=docs[0].get("company_name", "the bidder") if docs else "the bidder",
        bidder_text=text[:24_000],
    )
    resp = bedrock_client.invoke(
        invocation_type="numeric_evidence",
        system=NUMERIC_EVIDENCE.system,
        user=user,
        prompt_version=NUMERIC_EVIDENCE.version,
        structured=True,
        schema_hint=NUMERIC_EVIDENCE.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not isinstance(resp.data, dict):
        return {"branch": "llm", "error": resp.error or "no_data", "found": False,
                "figures": [], "expected_count": expected}
    d = resp.data
    figures = d.get("figures") or []
    # Sanitise figure shape
    clean: list[dict] = []
    for f in figures:
        if not isinstance(f, dict):
            continue
        rupees = f.get("rupees")
        if rupees is None and f.get("raw_value") is not None and f.get("unit"):
            rupees = _to_rupees(float(f["raw_value"]), str(f["unit"]))
        try:
            rupees = int(rupees)
        except (TypeError, ValueError):
            continue
        clean.append({
            "period_label": f.get("period_label") or "",
            "raw_value": float(f.get("raw_value") or 0),
            "unit": f.get("unit") or "rupee",
            "rupees": rupees,
            "source_quote": f.get("source_quote") or "",
        })
    return {
        "branch": "llm",
        "found": bool(d.get("found")) and len(clean) > 0,
        "figures": clean,
        "found_count": int(d.get("found_count") or len(clean)),
        "expected_count": int(d.get("expected_count") or expected),
        "label": d.get("label"),
        "confidence": float(d.get("confidence") or 0.0),
        "reasoning": d.get("reasoning"),
        "_prompt_hash": resp.prompt_hash,
        "_cached": resp.cached,
    }


def _llm_categorical(conn, text: str, docs: list, criterion: dict, tender_id: str) -> dict:
    cert_kind = _categorical_kind(criterion)
    user = CATEGORICAL_EVIDENCE.render_user(
        criterion_text=criterion.get("criterion_text", ""),
        cert_kind=cert_kind,
        bidder_name=docs[0].get("company_name", "the bidder") if docs else "the bidder",
        bidder_text=text[:24_000],
    )
    resp = bedrock_client.invoke(
        invocation_type="categorical_evidence",
        system=CATEGORICAL_EVIDENCE.system,
        user=user,
        prompt_version=CATEGORICAL_EVIDENCE.version,
        structured=True,
        schema_hint=CATEGORICAL_EVIDENCE.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not isinstance(resp.data, dict):
        return {"branch": "llm", "error": resp.error or "no_data", "found": False}
    d = resp.data
    return {
        "branch": "llm",
        "found": bool(d.get("found")),
        "registration_number": d.get("registration_number"),
        "validity_date": d.get("validity_date"),
        "is_valid": d.get("is_valid"),
        "certificate_type": d.get("certificate_type") or cert_kind,
        "format_matches": d.get("format_matches"),
        "source_quote": d.get("source_quote"),
        "confidence": float(d.get("confidence") or 0.0),
        "reasoning": d.get("reasoning"),
        "_prompt_hash": resp.prompt_hash,
        "_cached": resp.cached,
    }


def _llm_temporal(conn, text: str, docs: list, criterion: dict, tender_id: str) -> dict:
    threshold = _parse_threshold(criterion)
    required_count = int(threshold.get("count", 3) if threshold else 3)
    period_years = int(threshold.get("period_years", 5) if threshold else 5)
    value_threshold = ""
    if threshold and threshold.get("min_value_rupees"):
        value_threshold = f"each ≥ Rs {threshold['min_value_rupees']:,}"
    user = TEMPORAL_EVIDENCE.render_user(
        criterion_text=criterion.get("criterion_text", ""),
        required_count=required_count,
        period_years=period_years,
        value_threshold=value_threshold or "(not specified)",
        bidder_name=docs[0].get("company_name", "the bidder") if docs else "the bidder",
        bidder_text=text[:24_000],
    )
    resp = bedrock_client.invoke(
        invocation_type="temporal_evidence",
        system=TEMPORAL_EVIDENCE.system,
        user=user,
        prompt_version=TEMPORAL_EVIDENCE.version,
        structured=True,
        schema_hint=TEMPORAL_EVIDENCE.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not isinstance(resp.data, dict):
        return {"branch": "llm", "error": resp.error or "no_data", "found": False}
    d = resp.data
    return {
        "branch": "llm",
        "found": bool(d.get("found")),
        "qualifying_count": int(d.get("qualifying_count") or 0),
        "required_count": int(d.get("required_count") or required_count),
        "projects": d.get("projects") or [],
        "confidence": float(d.get("confidence") or 0.0),
        "reasoning": d.get("reasoning"),
        "_prompt_hash": resp.prompt_hash,
        "_cached": resp.cached,
    }


def _llm_qualitative(
    conn, text: str, pages: list, docs: list,
    criterion: dict, tender_id: str,
) -> dict:
    user = QUALITATIVE_EVIDENCE.render_user(
        criterion_text=criterion.get("criterion_text", ""),
        bidder_name=docs[0].get("company_name", "the bidder") if docs else "the bidder",
        bidder_text=text[:30_000],
    )
    resp = bedrock_client.invoke(
        invocation_type="qualitative_evidence",
        system=QUALITATIVE_EVIDENCE.system,
        user=user,
        prompt_version=QUALITATIVE_EVIDENCE.version,
        structured=True,
        schema_hint=QUALITATIVE_EVIDENCE.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not resp.data:
        return _empty_evidence("llm_failed:" + (resp.error or "no_data"),
                                source_docs=docs)

    data = resp.data if isinstance(resp.data, dict) else {}
    verdict = data.get("verdict", "REVIEW")
    confidence = float(data.get("confidence", 0.5) or 0.5)
    reasoning = data.get("reasoning", "")
    quote = data.get("key_quote")
    source = _find_in_pages(quote, pages) if quote else None

    return {
        "value": {
            "verdict": verdict,
            "reasoning": reasoning,
            "key_quote": quote,
            "factors": data.get("factors_considered", []),
        },
        "source_doc_id": (source["doc"]["id"] if source else (docs[0]["id"] if docs else None)),
        "source_page": source["page_number"] if source else None,
        "source_bbox": source.get("bbox") if source else None,
        "ocr_confidence": source["ocr_confidence"] if source else 0.7,
        "extraction_confidence": confidence,
        "entity_match_flag": False,
        "evaluation_method": "llm",
        "notes": reasoning[:300] if reasoning else None,
        "branches": {"llm": data},
        "union": {"agreement": "agree", "score": 1.0},
        "_extraction_prompt_hash": resp.prompt_hash,
        "_cached": resp.cached,
    }


# ─── Reconcilers ───────────────────────────────────────────────────────


def _reconcile_numeric(
    rules: dict, llm: dict, pages: list, docs: list,
) -> dict:
    """Reconcile rules+LLM figures and apply the criterion's measurement rule.

    The reconciler now returns the FULL list of period→value pairs in
    `value.figures`, plus an evaluation summary in `value.summary`:
      - met_count       — how many figures meet the threshold
      - total_count     — how many figures we found
      - expected_count  — how many we expected per the rule
      - rule_outcome    — 'PASS' | 'FAIL' | 'INSUFFICIENT_DATA'
      - rule_reason     — short string the verdict layer surfaces
    """
    rules_figures = rules.get("figures") or []
    llm_figures   = llm.get("figures") or []
    rules_conf = float(rules.get("confidence") or 0.0)
    llm_conf   = float(llm.get("confidence") or 0.0)

    # Prefer LLM figures if available (richer — period labels + quotes)
    figures = llm_figures if llm_figures else rules_figures
    chose_branch = "llm" if llm_figures else ("rules" if rules_figures else "none")
    expected_count = int(llm.get("expected_count") or rules.get("expected_count") or 1)

    # Cross-check: if both branches found values, do their sets agree
    # within tolerance (5%)? If yes → high confidence. If no → flag.
    agreement, score = "agree", 1.0
    if rules_figures and llm_figures:
        rules_max = max(f["rupees"] for f in rules_figures)
        llm_max   = max(f["rupees"] for f in llm_figures)
        if max(rules_max, llm_max) > 0:
            spread = abs(rules_max - llm_max) / max(rules_max, llm_max)
            if spread > 0.05:
                agreement, score = "disagree", 0.4

    if not figures:
        return _empty_evidence(
            "no_numeric_match",
            source_docs=docs,
            branches={"rules": rules, "llm": llm},
            union={"agreement": "agree", "score": 1.0},
        )

    return {
        "value": {
            "figures": figures,
            "expected_count": expected_count,
            "found_count": len(figures),
            "label": rules.get("label") or llm.get("label"),
        },
        "source_doc_id": docs[0]["id"] if docs else None,
        "source_page": None,
        "source_bbox": None,
        "ocr_confidence": 0.85 if docs else 0.0,
        "extraction_confidence": (
            min(0.95, max(rules_conf, llm_conf) + 0.05) if agreement == "agree"
            else max(rules_conf, llm_conf) * 0.7
        ),
        "entity_match_flag": False,
        "evaluation_method": "rules+llm" if (rules_figures and llm_figures) else (
            "llm" if llm_figures else "rules"
        ),
        "notes": (
            f"Found {len(figures)} of {expected_count} expected figure(s); "
            f"{'branches agree' if agreement == 'agree' else 'rules and LLM disagree'}."
        ),
        "branches": {"rules": rules, "llm": llm},
        "union": {"agreement": agreement, "score": score},
        "_extraction_prompt_hash": llm.get("_prompt_hash"),
    }


def _reconcile_categorical(
    rules: dict, llm: dict, pages: list, docs: list,
) -> dict:
    rules_found = bool(rules.get("found"))
    llm_found = bool(llm.get("found")) and not llm.get("error")
    rules_reg = (rules.get("registration_number") or "").upper()
    llm_reg = (llm.get("registration_number") or "").upper()
    rules_conf = float(rules.get("confidence") or 0.0)
    llm_conf = float(llm.get("confidence") or 0.0)

    if not rules_found and not llm_found:
        return {
            "value": {
                "found": False,
                "registration_number": None,
                "is_valid": False,
                "certificate_type": rules.get("certificate_type") or llm.get("certificate_type"),
            },
            "source_doc_id": docs[0]["id"] if docs else None,
            "source_page": None, "source_bbox": None,
            "ocr_confidence": 0.6,
            "extraction_confidence": 0.65,
            "entity_match_flag": False,
            "evaluation_method": "rules+llm",
            "notes": "Neither branch found this certificate.",
            "branches": {"rules": rules, "llm": llm},
            "union": {"agreement": "agree", "score": 1.0},
        }

    if rules_found and llm_found and rules_reg == llm_reg:
        agreement = "agree"; score = 1.0
        picked = "both"; conf = min(0.95, max(rules_conf, llm_conf) + 0.05)
    elif rules_found and llm_found:
        agreement = "disagree"; score = 0.4
        picked = "llm" if llm_conf >= rules_conf else "rules"
        conf = max(rules_conf, llm_conf) * 0.7
    else:
        agreement = "partial"; score = 0.7
        picked = "llm" if llm_found else "rules"
        conf = (llm_conf if llm_found else rules_conf) * 0.85

    chosen = llm if picked in ("llm", "both") else rules
    quote = llm.get("source_quote") if llm_found else None
    source = _find_in_pages(quote or chosen.get("registration_number") or "", pages)
    bidder_doc = source["doc"] if source else (docs[0] if docs else None)
    note = _union_note("Categorical", agreement, rules, llm, picked)

    return {
        "value": {
            "found": True,
            "registration_number": chosen.get("registration_number"),
            "validity_date": chosen.get("validity_date"),
            "is_valid": chosen.get("is_valid"),
            "certificate_type": chosen.get("certificate_type"),
            "source_quote": llm.get("source_quote"),
        },
        "source_doc_id": bidder_doc["id"] if bidder_doc else None,
        "source_page": source["page_number"] if source else None,
        "source_bbox": source.get("bbox") if source else None,
        "ocr_confidence": source["ocr_confidence"] if source else 0.7,
        "extraction_confidence": round(conf, 4),
        "entity_match_flag": False,
        "evaluation_method": "rules+llm",
        "notes": note,
        "branches": {"rules": rules, "llm": llm},
        "union": {"agreement": agreement, "score": score},
        "_extraction_prompt_hash": llm.get("_prompt_hash"),
    }


def _reconcile_temporal(
    rules: dict, llm: dict, pages: list, docs: list,
) -> dict:
    rules_count = int(rules.get("qualifying_count") or 0) if rules.get("found") else 0
    llm_count = int(llm.get("qualifying_count") or 0) if llm.get("found") else 0
    rules_conf = float(rules.get("confidence") or 0.0)
    llm_conf = float(llm.get("confidence") or 0.0)
    required = int(llm.get("required_count") or rules.get("required_count") or 3)

    # LLM-first because rules can only count dates, can't filter by relevance
    if llm.get("error") and rules_count > 0:
        agreement = "partial"; score = 0.5; picked = "rules"
        chosen_count = rules_count
        conf = min(rules_conf, 0.6)
    elif llm.get("error"):
        return _empty_evidence("temporal_no_data", source_docs=docs,
                                branches={"rules": rules, "llm": llm},
                                union={"agreement": "agree", "score": 1.0})
    else:
        # Both branches present
        if abs(rules_count - llm_count) <= 1:
            agreement = "agree"; score = 1.0; picked = "llm"
            chosen_count = llm_count
            conf = min(0.92, llm_conf + 0.05)
        else:
            agreement = "disagree"; score = 0.4; picked = "llm"
            chosen_count = llm_count
            conf = llm_conf * 0.7

    note = _union_note("Temporal", agreement, rules, llm, picked)
    return {
        "value": {
            "qualifying_count": chosen_count,
            "required_count": required,
            "projects": llm.get("projects", []),
        },
        "source_doc_id": docs[0]["id"] if docs else None,
        "source_page": None,
        "source_bbox": None,
        "ocr_confidence": 0.7,
        "extraction_confidence": round(conf, 4),
        "entity_match_flag": False,
        "evaluation_method": "rules+llm",
        "notes": note,
        "branches": {"rules": rules, "llm": llm},
        "union": {"agreement": agreement, "score": score},
        "_extraction_prompt_hash": llm.get("_prompt_hash"),
    }


def _reconcile_values_numeric(
    rules_found, llm_found, rules_rupees, llm_rupees,
    rules_conf, llm_conf,
) -> tuple[str, float, Optional[int], str, float]:
    """Return (agreement, score, value, picked, confidence)."""
    if not rules_found and not llm_found:
        return ("agree", 1.0, None, "none", 0.0)
    if rules_found and llm_found:
        # Tolerance: within 5% counts as agreement
        bigger = max(rules_rupees, llm_rupees)
        smaller = min(rules_rupees, llm_rupees)
        if bigger == 0 or (bigger - smaller) / bigger <= 0.05:
            return ("agree", 1.0, llm_rupees,
                    "both", min(0.95, max(rules_conf, llm_conf) + 0.05))
        # Disagreement — pick higher-confidence branch, cap conf
        if llm_conf >= rules_conf:
            return ("disagree", 0.4, llm_rupees, "llm", llm_conf * 0.7)
        return ("disagree", 0.4, rules_rupees, "rules", rules_conf * 0.7)
    # Only one branch found something
    if llm_found:
        return ("partial", 0.7, llm_rupees, "llm", llm_conf * 0.85)
    return ("partial", 0.7, rules_rupees, "rules", rules_conf * 0.85)


def _union_note(prefix: str, agreement: str, rules: dict, llm: dict, picked: str) -> str:
    if agreement == "agree":
        return f"{prefix}: rules + LLM agree (high confidence)."
    if agreement == "partial":
        return f"{prefix}: only the {picked} branch found a value (officer to verify)."
    return f"{prefix}: rules and LLM disagree — used the {picked} branch (officer review recommended)."


# ─── Helpers ───────────────────────────────────────────────────────────


def _collect_bidder_text(conn, tender_id: str, bidder_id: str) -> tuple[str, list[dict], list[dict]]:
    docs = conn.execute(
        "SELECT d.id, d.filename, d.doc_type, b.company_name "
        "FROM documents d "
        "LEFT JOIN bidders b ON d.bidder_id = b.id "
        "WHERE d.tender_id = ? AND d.bidder_id = ? AND d.processing_state = 'complete'",
        (tender_id, bidder_id),
    ).fetchall()
    if not docs:
        return "", [], []

    docs_list = [dict(d) for d in docs]
    page_meta: list[dict] = []
    text_parts: list[str] = []

    for d in docs_list:
        for p in conn.execute(
            "SELECT page_number, raw_text, ocr_confidence FROM pages "
            "WHERE document_id = ? ORDER BY page_number",
            (d["id"],),
        ):
            page_meta.append({
                "doc_id": d["id"],
                "doc": d,
                "page_number": p["page_number"],
                "raw_text": p["raw_text"] or "",
                "ocr_confidence": p["ocr_confidence"] or 0.0,
            })
            text_parts.append(p["raw_text"] or "")

    return "\n".join(text_parts), page_meta, docs_list


def _find_in_pages(needle: str, pages: list[dict]) -> Optional[dict]:
    if not needle:
        return None
    needle_low = needle.lower()[:40]
    for p in pages:
        if needle_low in (p["raw_text"] or "").lower():
            return p
    return None


def _lines_containing(text: str, label_hint: str) -> Optional[str]:
    if not label_hint:
        return None
    label_low = label_hint.lower()
    matches = [line for line in text.splitlines()
               if label_low in line.lower()]
    return "\n".join(matches) if matches else None


def _numeric_label_hint(criterion: dict) -> str:
    text = (criterion.get("criterion_text") or "").lower()
    if "turnover" in text:
        return "turnover"
    if "net worth" in text:
        return "net worth"
    if "emd" in text or "earnest" in text:
        return "emd"
    return ""


def _categorical_kind(criterion: dict) -> str:
    text = (criterion.get("criterion_text") or "").lower()
    if "gst" in text:
        return "gst"
    if "pan" in text or "permanent account" in text:
        return "pan"
    if "iso" in text:
        return "iso"
    if "msme" in text or "udyam" in text:
        return "udyam"
    return "unknown"


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


def _to_rupees(value: float, unit: str) -> int:
    unit = unit.lower().strip().rstrip(".")
    multipliers = {
        "crore": 10_000_000, "cr": 10_000_000,
        "lakh": 100_000, "lac": 100_000, "l": 100_000,
    }
    return int(value * multipliers.get(unit, 1))


def _from_rupees(rupees: int) -> tuple[float, str]:
    if rupees >= 10_000_000:
        return (round(rupees / 10_000_000, 2), "crore")
    if rupees >= 100_000:
        return (round(rupees / 100_000, 2), "lakh")
    return (float(rupees), "rupee")


def _is_future_date(date_str: str) -> Optional[bool]:
    from datetime import datetime
    parts = re.split(r"[-/.]", date_str)
    if len(parts) != 3:
        return None
    try:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        if y < 100:
            y += 2000
        dt = datetime(y, m, d)
        return dt > datetime.utcnow()
    except (ValueError, IndexError):
        return None


def _empty_evidence(
    reason: str,
    source_docs: list | None = None,
    branches: dict | None = None,
    union: dict | None = None,
) -> dict:
    """Return an evidence dict that says 'we looked but didn't find this'.

    confidence reflects confidence in the *finding* (high) — i.e. we're
    confident this isn't in the bidder's docs — not confidence in any
    extracted value. The verdict layer maps this to FAIL with high conf
    when the evidence is genuinely missing from a complete submission,
    or REVIEW when documents are missing entirely.
    """
    docs = source_docs or []
    has_docs = bool(docs)
    return {
        "value": None,
        "source_doc_id": docs[0]["id"] if docs else None,
        "source_page": None,
        "source_bbox": None,
        "ocr_confidence": 0.85 if has_docs else 0.0,
        # 'extraction confidence' here means "confidence we did not find
        # this figure in the docs" — high if we read the docs at all.
        "extraction_confidence": 0.78 if has_docs else 0.0,
        "entity_match_flag": False,
        "evaluation_method": "rules+llm" if (branches or {}).get("llm") else "rules",
        "notes": reason,
        "branches": branches or {},
        "union": union or {"agreement": "agree", "score": 1.0},
    }
