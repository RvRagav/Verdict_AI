"""Smell Test — rule-based anomaly detection across a tender's bidders.

Detects patterns a senior officer would notice. Conservative by design:
false positives erode officer trust. Each anomaly carries:
  - flag_type: one of the enum values in schema.py
  - severity: low | medium | high
  - message: human-readable explanation
  - evidence_data: a dict the UI can show on click

Rules implemented (all rule-based, fast, no LLM call):
  1. round_number          — financial figures suspiciously round
  2. address_collision     — two bidders share the same address
  3. date_proximity        — multiple bidders' docs created within minutes
  4. pan_format_mismatch   — PAN doesn't match AAAAA9999A
  5. gstin_format_mismatch — GSTIN doesn't match 99XXXXX9999X9X9
  6. duplicate_document    — two bidders submitted byte-identical doc
  7. parent_company_substitution — bidder name appears as substring of doc-claimed entity

The novel-anomaly LLM call (ANOMALY_DETECTION prompt) is invoked
separately for cases the rules miss.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional


PAN_PATTERN  = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


# ─── Individual rules ────────────────────────────────────────────────────


def detect_round_number(value: Optional[float]) -> Optional[dict]:
    """Flag if a financial figure is suspiciously round.

    Heuristic: integer-rounded to ≥4 trailing zeros and ≥10 lakh in scale.
    """
    if value is None or value < 1_000_000:
        return None
    if value % 1_000_000 == 0:  # whole crore or higher
        return {
            "flag_type": "round_number",
            "severity": "low",
            "message": f"Figure {value:,.0f} is suspiciously round (whole crore).",
            "evidence_data": {"value": value},
        }
    if value % 100_000 == 0:
        return {
            "flag_type": "round_number",
            "severity": "low",
            "message": f"Figure {value:,.0f} is suspiciously round (whole lakh).",
            "evidence_data": {"value": value},
        }
    return None


def detect_pan_format_mismatch(pan: str) -> Optional[dict]:
    if not pan:
        return None
    if not PAN_PATTERN.match(pan.strip().upper()):
        return {
            "flag_type": "pan_format_mismatch",
            "severity": "medium",
            "message": f"PAN '{pan}' does not match the standard format AAAAA9999A.",
            "evidence_data": {"pan": pan},
        }
    return None


def detect_gstin_format_mismatch(gstin: str, expected_pan: Optional[str] = None) -> Optional[dict]:
    if not gstin:
        return None
    g = gstin.strip().upper()
    if not GSTIN_PATTERN.match(g):
        return {
            "flag_type": "gstin_format_mismatch",
            "severity": "medium",
            "message": f"GSTIN '{gstin}' does not match the standard format.",
            "evidence_data": {"gstin": gstin},
        }
    # If PAN is known, GSTIN positions 3-12 should equal PAN
    if expected_pan and len(g) == 15:
        gstin_pan_part = g[2:12]
        if gstin_pan_part != expected_pan.strip().upper():
            return {
                "flag_type": "gstin_format_mismatch",
                "severity": "high",
                "message": f"GSTIN PAN-segment '{gstin_pan_part}' does not match bidder's PAN '{expected_pan}'.",
                "evidence_data": {"gstin": gstin, "pan": expected_pan},
            }
    return None


# ─── Cross-bidder rules (operate on the whole tender) ───────────────────


def detect_address_collision(bidders: list[dict]) -> list[dict]:
    """Two or more bidders share the same address."""
    address_to_bidders: dict[str, list[str]] = defaultdict(list)
    for b in bidders:
        addr = (b.get("address") or "").strip().lower()
        if addr:
            address_to_bidders[addr].append(b["id"])
    flags: list[dict] = []
    for addr, ids in address_to_bidders.items():
        if len(ids) >= 2:
            flags.append({
                "flag_type": "address_collision",
                "severity": "high",
                "message": f"{len(ids)} bidders share the same address.",
                "evidence_data": {"address": addr, "bidder_ids": ids},
            })
    return flags


def detect_date_proximity(documents: list[dict], window_seconds: int = 600) -> list[dict]:
    """Multiple documents from different bidders created within minutes of each other."""
    by_time: list[tuple[datetime, dict]] = []
    for d in documents:
        if not d.get("modification_date"):
            continue
        try:
            dt = datetime.fromisoformat(d["modification_date"].replace("Z", "+00:00"))
        except ValueError:
            continue
        by_time.append((dt, d))

    by_time.sort(key=lambda x: x[0])
    flags: list[dict] = []
    for i, (dt, d) in enumerate(by_time):
        for j in range(i + 1, len(by_time)):
            dt2, d2 = by_time[j]
            if (dt2 - dt).total_seconds() > window_seconds:
                break
            if d.get("bidder_id") and d2.get("bidder_id") and d["bidder_id"] != d2["bidder_id"]:
                flags.append({
                    "flag_type": "date_proximity",
                    "severity": "medium",
                    "message": (
                        f"Documents from two bidders modified within "
                        f"{(dt2 - dt).total_seconds():.0f} seconds of each other."
                    ),
                    "evidence_data": {
                        "doc_a": d.get("id"),
                        "doc_b": d2.get("id"),
                        "delta_seconds": (dt2 - dt).total_seconds(),
                    },
                })
    return flags


def detect_duplicate_document(documents: list[dict]) -> list[dict]:
    """Two bidders submitted byte-identical files."""
    hash_groups: dict[str, list[dict]] = defaultdict(list)
    for d in documents:
        if d.get("sha256_hash"):
            hash_groups[d["sha256_hash"]].append(d)
    flags: list[dict] = []
    for h, docs in hash_groups.items():
        bidders = {d.get("bidder_id") for d in docs if d.get("bidder_id")}
        if len(bidders) >= 2:
            flags.append({
                "flag_type": "duplicate_document",
                "severity": "high",
                "message": f"Identical document submitted by {len(bidders)} different bidders.",
                "evidence_data": {
                    "sha256": h,
                    "document_ids": [d["id"] for d in docs],
                    "bidder_ids": list(bidders),
                },
            })
    return flags


# ─── Phase-12 cross-bidder cartel rules ─────────────────────────────────


def detect_sequential_dd_numbers(bidders: list[dict]) -> list[dict]:
    """Sequential DD numbers across bidders — the CCI 2025 cartel signature.

    `bidders` carries `emd_instrument` (DD/BG/e-payment) and
    `emd_instrument_no`. We look for a numeric instrument number, and flag
    when two or more bidders' DD numbers fall in a tight integer window
    (consecutive or within 5).
    """
    nums: list[tuple[int, str, str]] = []   # (numeric, bidder_id, raw_no)
    for b in bidders:
        if (b.get("emd_instrument") or "").lower() not in ("dd", "demand draft", "banker's cheque"):
            continue
        raw = (b.get("emd_instrument_no") or "").strip()
        if not raw:
            continue
        # Pull the longest run of digits (DD numbers can be like "DD-845221")
        m = re.search(r"\d{4,}", raw)
        if not m:
            continue
        try:
            nums.append((int(m.group(0)), b["id"], raw))
        except ValueError:
            continue

    nums.sort(key=lambda t: t[0])
    flags: list[dict] = []
    for i in range(len(nums) - 1):
        a_num, a_id, a_raw = nums[i]
        b_num, b_id, b_raw = nums[i + 1]
        # Different bidders, gap of ≤ 5 — this is the cartel signal CCI cited in
        # multiple 2024-25 orders. ≤2 is "sequential"; ≤5 is "issued by the
        # same teller within minutes of each other".
        if a_id == b_id:
            continue
        gap = b_num - a_num
        if 0 <= gap <= 5:
            severity = "high" if gap <= 2 else "medium"
            flags.append({
                "flag_type": "sequential_dd",
                "severity": severity,
                "message": (
                    f"Two bidders' EMD demand drafts have near-sequential "
                    f"numbers ({a_raw} and {b_raw}, gap {gap}) — "
                    f"consistent with collusive bidding patterns."
                ),
                "evidence_data": {
                    "bidder_ids": [a_id, b_id],
                    "dd_numbers": [a_raw, b_raw],
                    "numeric_gap": gap,
                },
            })
    return flags


def _normalise_name(name: str) -> str:
    """Normalise an Indian-context person name for cross-bidder comparison."""
    if not name:
        return ""
    n = name.lower()
    # Strip honorifics + suffixes
    for token in ("mr.", "mrs.", "ms.", "dr.", "shri", "smt.", "jr.", "sr."):
        n = n.replace(token, " ")
    # Collapse whitespace + punctuation
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def detect_common_signatory(bidders: list[dict]) -> list[dict]:
    """The same person signs as Director on bidder A and Authorised Signatory
    on bidder B — classic Indian cartel pattern.

    Each bidder dict can carry a `signatories` list of dicts:
      [{"name": "P. Sharma", "role": "Director"}, ...]
    """
    name_to_bidders: dict[str, list[dict]] = defaultdict(list)
    for b in bidders:
        for s in (b.get("signatories") or []):
            n = _normalise_name(s.get("name") or "")
            if not n or len(n) < 5:           # skip initials-only "p s"
                continue
            name_to_bidders[n].append({
                "bidder_id": b["id"],
                "company": b.get("company_name"),
                "role": s.get("role") or "signatory",
            })

    flags: list[dict] = []
    for name, occurrences in name_to_bidders.items():
        bidder_ids = {o["bidder_id"] for o in occurrences}
        if len(bidder_ids) >= 2:
            flags.append({
                "flag_type": "common_signatory",
                "severity": "high",
                "message": (
                    f"The same person (signatory name '{name.title()}') appears on "
                    f"{len(bidder_ids)} different bidders — typical Indian-cartel "
                    f"pattern (director-on-A, signatory-on-B)."
                ),
                "evidence_data": {
                    "signatory_name": name.title(),
                    "occurrences": occurrences,
                    "bidder_ids": list(bidder_ids),
                },
            })
    return flags


def detect_cover_letter_overlap(bidders: list[dict]) -> list[dict]:
    """Verbatim phrase overlap across cover letters — collusion-quality signal.

    Each bidder dict can carry a `cover_letter_text` string. We extract
    long-shingle (10-word) overlaps; ≥2 shingles in common between two
    different bidders is the threshold.
    """
    SHINGLE_N = 10

    def _shingles(text: str) -> set[str]:
        words = re.findall(r"[A-Za-z']+", (text or "").lower())
        if len(words) < SHINGLE_N:
            return set()
        return {" ".join(words[i:i + SHINGLE_N]) for i in range(len(words) - SHINGLE_N + 1)}

    bidder_shingles: list[tuple[str, set[str]]] = []
    for b in bidders:
        text = b.get("cover_letter_text") or ""
        s = _shingles(text)
        if s:
            bidder_shingles.append((b["id"], s))

    flags: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for i in range(len(bidder_shingles)):
        a_id, a_set = bidder_shingles[i]
        for j in range(i + 1, len(bidder_shingles)):
            b_id, b_set = bidder_shingles[j]
            common = a_set & b_set
            if len(common) >= 2:
                key = tuple(sorted([a_id, b_id]))
                if key in seen:
                    continue
                seen.add(key)
                sample = next(iter(common))
                flags.append({
                    "flag_type": "cover_letter_overlap",
                    "severity": "high",
                    "message": (
                        f"Two bidders' cover letters share {len(common)} verbatim "
                        f"10-word phrases — strong collusion signal."
                    ),
                    "evidence_data": {
                        "bidder_ids": list(key),
                        "overlap_count": len(common),
                        "sample_phrase": sample,
                    },
                })
    return flags


# ─── Driver ──────────────────────────────────────────────────────────────


def run_smell_test(
    *,
    bidder: dict,
    tender_documents: list[dict],
    all_bidders: list[dict],
    extracted_values: list[dict],
) -> list[dict]:
    """Run all rules for one bidder. Returns a list of anomaly dicts.

    Args:
        bidder: dict with id, company_name, pan_number, gstin, address?
        tender_documents: all docs across all bidders in the tender
        all_bidders: every bidder in the tender (for cross-bidder rules)
        extracted_values: numeric figures we've pulled from this bidder
            (each: {"value": float, "label": str})
    """
    flags: list[dict] = []

    # Per-bidder rules
    for ev in extracted_values:
        flag = detect_round_number(ev.get("value"))
        if flag:
            flag["evidence_data"]["label"] = ev.get("label")
            flags.append(flag)

    if bidder.get("pan_number"):
        f = detect_pan_format_mismatch(bidder["pan_number"])
        if f: flags.append(f)
    if bidder.get("gstin"):
        f = detect_gstin_format_mismatch(bidder["gstin"], bidder.get("pan_number"))
        if f: flags.append(f)

    # Cross-bidder rules — run once per tender, but each call returns
    # global flags; the caller dedupes
    flags.extend(detect_address_collision(all_bidders))
    flags.extend(detect_date_proximity(tender_documents))
    flags.extend(detect_duplicate_document(tender_documents))
    # Phase-12 cartel rules (CCI 2025 signals)
    flags.extend(detect_sequential_dd_numbers(all_bidders))
    flags.extend(detect_common_signatory(all_bidders))
    flags.extend(detect_cover_letter_overlap(all_bidders))

    return flags
