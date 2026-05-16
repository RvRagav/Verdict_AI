"""MCA verifier — mca.gov.in CIN search.

Indian companies have a Corporate Identification Number (CIN). Format:
LXXXXXXXXXXXXXXXXX (21 chars). The MCA portal lets you look up a
company by CIN and confirm its status (Active / Strike Off / Under
Liquidation).
"""

from __future__ import annotations

import re

from .base import Verifier, VerificationResult


CIN_FMT = re.compile(r"^[ULP][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")


class MCAVerifier(Verifier):
    name = "mca"
    source_url = "https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        cin = (claim.get("cin") or "").strip().upper()
        company_name = (claim.get("company_name") or "").strip()

        if self.live:
            return self._live(cin, company_name)

        if not cin:
            return VerificationResult(
                verifier_name=self.name, status="not_found", confidence=0.6,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim},
                notes="No CIN provided. (CIN is mandatory for incorporated "
                      "bidders only.)",
            )
        if not CIN_FMT.match(cin):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.9,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"cin": cin, "format_ok": False},
                notes="CIN format invalid; expected LXXXXXXXXXXXXXXXXX (21 chars).",
            )

        listing_status = "Listed" if cin[0] == "L" else "Unlisted"
        state_code = cin[6:8]
        year_of_incorp = cin[8:12]

        snapshot = {
            "cin": cin, "format_ok": True,
            "listing_status": listing_status,
            "state_code": state_code,
            "year_of_incorporation": year_of_incorp,
            "company_status": "Active",
            "_stub_note": "Stub-mode: derived from CIN structure. "
                          "Live mode will hit mca.gov.in master-data lookup.",
        }
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.82,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes=f"CIN {cin}: {listing_status} company incorporated in "
                  f"{year_of_incorp} (state code {state_code}). Live mode "
                  f"would confirm 'Active' / 'Strike Off' status.",
        )

    def _live(self, cin, name) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live MCA verifier not yet implemented"},
            notes="Live mode disabled.",
        )
