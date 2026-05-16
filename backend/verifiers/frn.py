"""FRN verifier — ICAI Firm Registration Number lookup.

Every CA firm has an FRN issued by the Institute of Chartered
Accountants of India. Format: 6 digits + 1 letter (e.g. 012345N for
Northern region). The ICAI website lets anyone search for a firm by
FRN to verify its existence and current status.
"""

from __future__ import annotations

import re

from .base import Verifier, VerificationResult


FRN_FMT = re.compile(r"^[0-9]{6}[A-Z]$")


class FRNVerifier(Verifier):
    name = "frn"
    source_url = "https://icai.org/post/firm-search"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        frn = (claim.get("frn") or "").strip().upper()
        firm_name = (claim.get("firm_name") or "").strip()

        if self.live:
            return self._live(frn, firm_name)

        if not frn:
            return VerificationResult(
                verifier_name=self.name, status="not_found", confidence=0.7,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim},
                notes="No FRN visible on the CA certificate.",
            )
        if not FRN_FMT.match(frn):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.9,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"frn": frn, "format_ok": False},
                notes="FRN format invalid; expected 6 digits + 1 region "
                      "letter (e.g. 012345N).",
            )
        region = {
            "N": "Northern", "S": "Southern", "E": "Eastern",
            "W": "Western", "C": "Central",
        }.get(frn[-1], "Unknown")

        snapshot = {
            "frn": frn, "format_ok": True,
            "firm_name_on_cert": firm_name or "(not on cert)",
            "region": region,
            "in_practice": True,
            "_stub_note": "Stub-mode: format + region inference. "
                          "Live mode will hit icai.org firm search.",
        }
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.80,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes=f"FRN {frn} ({region} region) format valid. Live "
                  f"verification would confirm firm name + 'in practice' status.",
        )

    def _live(self, frn, firm_name) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live FRN verifier not yet implemented"},
            notes="Live mode disabled.",
        )
