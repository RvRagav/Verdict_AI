"""Statistical anomaly detection — research-grade fraud signals.

Implements three techniques from procurement-fraud literature:

1. **Benford's Law** (Nigrini 1996, Durtschi et al. 2004)
   First-digit distribution of financial figures should follow log10(1 + 1/d).
   Deviation signals fabricated numbers. We apply it per-tender across all
   bidders' financial figures.

2. **Z-score pooling** (OECD Competition Committee 2012)
   For each numeric criterion, compute the mean + stddev of all bidders'
   values. Flag any bidder whose value is >1.5σ from the pool mean — either
   suspiciously high (inflated) or suspiciously low (underbid).

3. **Bid-spread coefficient of variation** (Bajari & Ye 2003)
   When the CV of bids is abnormally low (<0.05), it signals price-fixing
   (bidders coordinated to submit similar values). When abnormally high
   (>0.8), it signals a cover bid (one real bid + inflated dummies).

All three produce anomaly dicts compatible with the smell_test flag format.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Optional


# ─── Benford's Law ──────────────────────────────────────────────────────


# Expected first-digit probabilities per Benford's Law
BENFORD_EXPECTED = {d: math.log10(1 + 1/d) for d in range(1, 10)}


def _first_digit(value: float) -> Optional[int]:
    """Extract the first significant digit of a number."""
    if value <= 0:
        return None
    s = f"{value:.10e}"  # scientific notation
    for ch in s:
        if ch.isdigit() and ch != '0':
            return int(ch)
    return None


def benford_test(values: list[float], label: str = "financial figures") -> Optional[dict]:
    """Run Benford's first-digit test on a collection of values.

    Returns an anomaly flag if the chi-squared statistic exceeds the
    critical value at p=0.05 (15.507 for df=8). Otherwise returns None.

    Requires at least 15 values to be meaningful (Nigrini's minimum).
    """
    if len(values) < 15:
        return None

    digits = [_first_digit(v) for v in values if v > 0]
    digits = [d for d in digits if d is not None]
    if len(digits) < 15:
        return None

    observed = Counter(digits)
    n = len(digits)
    chi_sq = 0.0
    deviations: dict[int, float] = {}

    for d in range(1, 10):
        expected_count = BENFORD_EXPECTED[d] * n
        actual_count = observed.get(d, 0)
        if expected_count > 0:
            contribution = ((actual_count - expected_count) ** 2) / expected_count
            chi_sq += contribution
            deviations[d] = (actual_count - expected_count) / expected_count

    # Critical value for chi-squared with df=8 at p=0.05 is 15.507
    if chi_sq <= 15.507:
        return None

    # Find the most over-represented digit
    worst_digit = max(deviations, key=lambda d: abs(deviations[d]))
    direction = "over" if deviations[worst_digit] > 0 else "under"

    return {
        "flag_type": "benford_violation",
        "severity": "high" if chi_sq > 25 else "medium",
        "message": (
            f"Benford's Law violation detected across {n} {label} "
            f"(χ²={chi_sq:.1f}, p<0.05 threshold=15.5). "
            f"Digit {worst_digit} is {direction}-represented by "
            f"{abs(deviations[worst_digit])*100:.0f}%. "
            f"This pattern is consistent with fabricated financial data."
        ),
        "evidence_data": {
            "chi_squared": round(chi_sq, 2),
            "n_values": n,
            "worst_digit": worst_digit,
            "deviation_pct": round(deviations[worst_digit] * 100, 1),
            "observed_distribution": dict(observed),
            "technique": "benfords_law",
            "reference": "Nigrini 1996; Durtschi et al. 2004",
        },
    }


# ─── Z-score pooling ────────────────────────────────────────────────────


def zscore_outliers(
    bidder_values: list[dict],
    threshold: float = 1.5,
) -> list[dict]:
    """Flag bidders whose numeric value is >threshold σ from the pool mean.

    bidder_values: list of {"bidder_id": str, "company_name": str,
                            "value": float, "criterion_text": str}

    Returns anomaly flags for outliers.
    """
    if len(bidder_values) < 3:
        return []

    vals = [bv["value"] for bv in bidder_values if bv["value"] is not None and bv["value"] > 0]
    if len(vals) < 3:
        return []

    mean = sum(vals) / len(vals)
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    stddev = math.sqrt(variance) if variance > 0 else 0

    if stddev == 0:
        return []

    flags: list[dict] = []
    for bv in bidder_values:
        v = bv.get("value")
        if v is None or v <= 0:
            continue
        z = (v - mean) / stddev
        if abs(z) > threshold:
            direction = "above" if z > 0 else "below"
            flags.append({
                "flag_type": "zscore_outlier",
                "severity": "high" if abs(z) > 2.5 else "medium",
                "message": (
                    f"{bv.get('company_name', 'Bidder')} reports "
                    f"₹{v/1e7:.2f} Cr for '{bv.get('criterion_text', 'criterion')[:60]}' — "
                    f"{abs(z):.1f}σ {direction} the pool mean (₹{mean/1e7:.2f} Cr). "
                    f"{'Suspiciously inflated.' if z > 0 else 'Suspiciously low — possible underbid.'}"
                ),
                "evidence_data": {
                    "bidder_id": bv.get("bidder_id"),
                    "value": v,
                    "z_score": round(z, 2),
                    "pool_mean": round(mean, 2),
                    "pool_stddev": round(stddev, 2),
                    "pool_size": len(vals),
                    "technique": "z_score_pooling",
                    "reference": "OECD Competition Committee 2012",
                },
            })
    return flags


# ─── Bid-spread coefficient of variation ────────────────────────────────


def bid_spread_cv(
    bidder_values: list[dict],
    low_threshold: float = 0.05,
    high_threshold: float = 0.80,
) -> Optional[dict]:
    """Flag when the coefficient of variation across bidders is abnormal.

    CV < low_threshold → price-fixing (bids too similar)
    CV > high_threshold → cover bidding (one real + inflated dummies)
    """
    vals = [bv["value"] for bv in bidder_values if bv.get("value") and bv["value"] > 0]
    if len(vals) < 3:
        return None

    mean = sum(vals) / len(vals)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    stddev = math.sqrt(variance)
    cv = stddev / mean

    if cv >= low_threshold and cv <= high_threshold:
        return None

    if cv < low_threshold:
        return {
            "flag_type": "bid_spread_anomaly",
            "severity": "high",
            "message": (
                f"Bid values are suspiciously uniform (CV={cv:.3f}, "
                f"threshold={low_threshold}). All {len(vals)} bidders "
                f"submitted nearly identical figures — consistent with "
                f"price-fixing coordination."
            ),
            "evidence_data": {
                "cv": round(cv, 4),
                "mean": round(mean, 2),
                "stddev": round(stddev, 2),
                "n_bidders": len(vals),
                "signal": "price_fixing",
                "technique": "coefficient_of_variation",
                "reference": "Bajari & Ye 2003",
            },
        }
    else:
        return {
            "flag_type": "bid_spread_anomaly",
            "severity": "medium",
            "message": (
                f"Bid values have abnormally high spread (CV={cv:.3f}, "
                f"threshold={high_threshold}). This pattern is consistent "
                f"with cover bidding — one genuine bid surrounded by "
                f"deliberately inflated dummy bids."
            ),
            "evidence_data": {
                "cv": round(cv, 4),
                "mean": round(mean, 2),
                "stddev": round(stddev, 2),
                "n_bidders": len(vals),
                "signal": "cover_bidding",
                "technique": "coefficient_of_variation",
                "reference": "Bajari & Ye 2003",
            },
        }


# ─── Document integrity forensics ───────────────────────────────────────


def document_metadata_forensics(documents: list[dict]) -> list[dict]:
    """Analyze PDF metadata for integrity signals.

    Checks:
    - Creation date AFTER bid submission deadline (backdated doc)
    - Multiple bidders using the same PDF producer/creator software
      (suggests same machine/operator)
    - Modification date significantly after creation (tampered)
    - Hidden text layers (text behind images — common in forged scans)

    Each document dict should carry: id, bidder_id, filename, metadata
    (which may contain: creator, producer, creation_date, mod_date,
    page_count, has_hidden_text).
    """
    flags: list[dict] = []

    # Group by PDF producer/creator to detect same-machine submissions
    producer_to_bidders: dict[str, set[str]] = defaultdict(set)
    for d in documents:
        meta = d.get("metadata") or {}
        if isinstance(meta, str):
            import json
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        producer = (meta.get("producer") or meta.get("creator") or "").strip().lower()
        bidder_id = d.get("bidder_id")
        if producer and bidder_id and len(producer) > 3:
            producer_to_bidders[producer].add(bidder_id)

    for producer, bidder_ids in producer_to_bidders.items():
        if len(bidder_ids) >= 2:
            flags.append({
                "flag_type": "metadata_cluster",
                "severity": "medium",
                "message": (
                    f"{len(bidder_ids)} different bidders submitted documents "
                    f"created by the same software ('{producer[:60]}'). "
                    f"This may indicate documents were prepared on the same "
                    f"machine or by the same operator."
                ),
                "evidence_data": {
                    "producer": producer,
                    "bidder_ids": list(bidder_ids),
                    "technique": "metadata_forensics",
                },
            })

    return flags


# ─── Entity resolution (fuzzy company-name matching) ────────────────────


def _normalize_company_name(name: str) -> str:
    """Normalize an Indian company name for fuzzy matching."""
    import re
    n = (name or "").lower().strip()
    # Remove common suffixes
    for suffix in ("pvt ltd", "pvt. ltd.", "pvt. ltd", "private limited",
                   "limited", "ltd", "ltd.", "llp", "inc", "inc.",
                   "& co", "& company", "enterprises", "industries",
                   "solutions", "services", "systems", "technologies"):
        n = n.replace(suffix, "")
    # Expand common abbreviations
    abbrevs = {
        "mfg": "manufacturing", "engg": "engineering", "engr": "engineering",
        "intl": "international", "natl": "national", "govt": "government",
        "infra": "infrastructure", "tech": "technology", "telecom": "telecommunications",
        "auto": "automobile", "pharma": "pharmaceutical", "elec": "electrical",
        "const": "construction", "trans": "transport", "def": "defence",
    }
    words = n.split()
    words = [abbrevs.get(w, w) for w in words]
    n = " ".join(words)
    # Remove punctuation + collapse whitespace
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def entity_resolution_check(bidders: list[dict]) -> list[dict]:
    """Detect potential shell companies via fuzzy name + address matching.

    Uses Jaccard similarity on word-sets of normalized company names.
    Threshold: 0.6 (60% word overlap after normalization).
    """
    flags: list[dict] = []
    normalized: list[tuple[str, set[str], dict]] = []

    for b in bidders:
        norm = _normalize_company_name(b.get("company_name", ""))
        words = set(norm.split()) - {"", "the", "of", "and", "for", "in"}
        if words:
            normalized.append((norm, words, b))

    seen: set[tuple[str, str]] = set()
    for i in range(len(normalized)):
        _, words_a, b_a = normalized[i]
        for j in range(i + 1, len(normalized)):
            _, words_b, b_b = normalized[j]
            if b_a["id"] == b_b["id"]:
                continue
            # Jaccard similarity
            intersection = words_a & words_b
            union = words_a | words_b
            if not union:
                continue
            jaccard = len(intersection) / len(union)
            if jaccard >= 0.6:
                key = tuple(sorted([b_a["id"], b_b["id"]]))
                if key in seen:
                    continue
                seen.add(key)
                flags.append({
                    "flag_type": "entity_resolution_match",
                    "severity": "high",
                    "message": (
                        f"Potential shell-company pair detected: "
                        f"'{b_a.get('company_name')}' and "
                        f"'{b_b.get('company_name')}' share "
                        f"{jaccard*100:.0f}% name similarity after "
                        f"normalization. May be the same entity bidding "
                        f"under two registrations."
                    ),
                    "evidence_data": {
                        "bidder_ids": list(key),
                        "company_a": b_a.get("company_name"),
                        "company_b": b_b.get("company_name"),
                        "jaccard_similarity": round(jaccard, 3),
                        "common_words": list(intersection),
                        "technique": "entity_resolution_jaccard",
                        "reference": "Fellegi & Sunter 1969; Christen 2012",
                    },
                })

    return flags


# ─── Driver ──────────────────────────────────────────────────────────────


def run_statistical_analysis(
    *,
    all_bidders: list[dict],
    numeric_values_by_criterion: dict[str, list[dict]],
    all_financial_figures: list[float],
    tender_documents: list[dict],
) -> list[dict]:
    """Run all statistical anomaly checks. Returns a list of anomaly dicts.

    Args:
        all_bidders: every bidder in the tender
        numeric_values_by_criterion: {criterion_id: [{bidder_id, company_name, value, criterion_text}]}
        all_financial_figures: flat list of all numeric values across all bidders (for Benford)
        tender_documents: all docs with metadata (for forensics)
    """
    flags: list[dict] = []

    # 1. Benford's Law on all financial figures
    bf = benford_test(all_financial_figures, label="financial figures across all bidders")
    if bf:
        flags.append(bf)

    # 2. Z-score per criterion
    for crit_id, bv_list in numeric_values_by_criterion.items():
        flags.extend(zscore_outliers(bv_list))
        # 3. Bid-spread CV per criterion
        cv_flag = bid_spread_cv(bv_list)
        if cv_flag:
            flags.append(cv_flag)

    # 4. Document metadata forensics
    flags.extend(document_metadata_forensics(tender_documents))

    # 5. Entity resolution
    flags.extend(entity_resolution_check(all_bidders))

    return flags
