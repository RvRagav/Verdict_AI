"""Udyam (MSME) verifier — udyamregistration.gov.in.

Format: UDYAM-XX-99-9999999  (XX = state code, 99 = district code,
9999999 = registration number).
"""

from __future__ import annotations

import re

from .base import Verifier, VerificationResult


UDYAM_FMT = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]+$")


class UdyamVerifier(Verifier):
    name = "udyam"
    source_url = "https://udyamregistration.gov.in/Udyam_Verify.aspx"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        udyam = (claim.get("udyam") or "").strip().upper()

        if self.live:
            return self._live(udyam)

        if not udyam:
            return VerificationResult(
                verifier_name=self.name, status="not_found", confidence=0.7,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim},
                notes="No Udyam Registration Number provided.",
            )
        if not UDYAM_FMT.match(udyam):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.92,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"udyam": udyam, "format_ok": False},
                notes="Udyam format invalid; expected UDYAM-XX-99-9999999.",
            )

        snapshot = {
            "udyam_no": udyam, "format_ok": True,
            "category": "Medium",  # MSME category (would come from portal in live)
            "active": True,
            "_stub_note": "Stub-mode: format check only. "
                          "Live mode will hit udyamregistration.gov.in.",
        }
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.78,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes=f"Udyam {udyam} format valid. Live verification would "
                  f"confirm enterprise category + active status.",
        )

    def _live(self, udyam) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live Udyam verifier not yet implemented"},
            notes="Live mode disabled.",
        )
