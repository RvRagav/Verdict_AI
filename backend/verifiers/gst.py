"""GST verifier — gst.gov.in / Form GST REG-06.

Stub: derives status from format + a simulated 'active on bid date'
check. Live (TODO): hits the GST search-taxpayer endpoint.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from .base import Verifier, VerificationResult


GSTIN_FMT = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class GSTVerifier(Verifier):
    name = "gst"
    source_url = "https://services.gst.gov.in/services/searchtp"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        gstin = (claim.get("gstin") or "").strip().upper()
        bid_submission_date = claim.get("bid_submission_date")
        valid_until = claim.get("valid_until")  # from the cert
        legal_name = (claim.get("legal_name") or "").strip()

        if self.live:
            return self._live_verify(gstin, bid_submission_date, valid_until)

        # ── Stub mode ──
        if not gstin:
            return VerificationResult(
                verifier_name=self.name, status="unknown", confidence=0.0,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim},
                notes="No GSTIN supplied for verification.",
            )
        if not GSTIN_FMT.match(gstin):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.95,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"gstin": gstin, "format_ok": False},
                notes="GSTIN does not match the standard format "
                      "(99XXXXX9999X1Z9).",
            )

        # Bid-date anchored check
        bid_dt = _parse_iso(bid_submission_date)
        valid_dt = _parse_iso(valid_until)
        active_on_bid_date = True
        active_today = True
        today = date.today()

        if valid_dt:
            active_on_bid_date = (bid_dt is None) or (valid_dt >= bid_dt)
            active_today = valid_dt >= today

        snapshot = {
            "gstin": gstin,
            "format_ok": True,
            "legal_name": legal_name or "(not provided)",
            "registration_status": "Active" if active_today else "Cancelled/Expired",
            "valid_until": valid_until,
            "bid_submission_date": bid_submission_date,
            "active_on_bid_date": active_on_bid_date,
            "active_today": active_today,
            "_stub_note": (
                "Stub-mode: response synthesised from supplied claim. "
                "Live mode will hit gst.gov.in search-taxpayer."
            ),
        }
        if not active_on_bid_date:
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.92,
                source_url=self.source_url, verified_via="stub",
                source_snapshot=snapshot,
                notes=f"GSTIN was not active on bid submission date "
                      f"({bid_submission_date}); validity ended {valid_until}.",
            )
        if not active_today:
            return VerificationResult(
                verifier_name=self.name, status="verified", confidence=0.85,
                source_url=self.source_url, verified_via="stub",
                source_snapshot=snapshot,
                notes="GSTIN was active on bid submission date but has since "
                      "expired. Officer to confirm impact.",
            )
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.95,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes="GSTIN format valid and active.",
        )

    def _live_verify(self, gstin: str, bid_date, valid_until) -> VerificationResult:
        # Real implementation hits services.gst.gov.in. Stubbed for now
        # to fail gracefully if env-flagged on without a working network.
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live GST verifier not yet implemented"},
            notes="Live mode requires GST portal API credentials. "
                  "Switch back to stub mode for the demo.",
        )


def _parse_iso(s) -> Optional[date]:
    if not s:
        return None
    try:
        if isinstance(s, datetime):
            return s.date()
        s = str(s).strip()
        # Handle DD/MM/YYYY too
        if "/" in s and "-" not in s:
            d, m, y = s.split("/")
            return date(int(y), int(m), int(d))
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None
