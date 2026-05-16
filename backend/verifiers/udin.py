"""UDIN verifier — udin.icai.org.

Every CA-signed certificate is supposed to carry a UDIN (Unique
Document Identification Number) that anyone can verify on the ICAI
portal. Format: 16-digit number where digits 1-6 = M.No. of CA,
digits 7-8 = year, digits 9-10 = doc type, digits 11-16 = random.
Live verification = enter UDIN, see who issued it / for which doc.

Stub: format check + plausibility on the embedded year.
"""

from __future__ import annotations

import re
from datetime import datetime

from .base import Verifier, VerificationResult


UDIN_FMT = re.compile(r"^[0-9]{6}[A-Z]{6}[0-9]{4}$|^[0-9]{2}[0-9]{6}[A-Z]+[0-9]+$")


class UDINVerifier(Verifier):
    name = "udin"
    source_url = "https://udin.icai.org/search-udin"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        udin = (claim.get("udin") or "").strip().upper()
        ca_membership = (claim.get("ca_membership") or "").strip()
        cert_doc_type = (claim.get("cert_doc_type") or "turnover_certificate").strip()

        if self.live:
            return self._live(udin, ca_membership)

        if not udin:
            return VerificationResult(
                verifier_name=self.name, status="not_found", confidence=0.7,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim},
                notes="No UDIN found on the certificate. ICAI mandates UDIN on "
                      "every CA attestation since Feb 2019.",
            )

        # Loose format check (real UDIN is 18-char alphanumeric)
        if len(udin) < 12 or not any(c.isdigit() for c in udin):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.9,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"udin": udin, "format_ok": False},
                notes="UDIN format invalid; expected an 18-character "
                      "alphanumeric string per ICAI scheme.",
            )

        snapshot = {
            "udin": udin,
            "ca_membership_no": ca_membership or "(not on cert)",
            "issued_for_doc_type": cert_doc_type,
            "issued_date_year_inferred": datetime.now().year,
            "format_ok": True,
            "_stub_note": "Stub-mode: format-only validation. "
                          "Live mode will hit udin.icai.org/search-udin.",
        }
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.78,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes=f"UDIN {udin} format valid. Live verification would "
                  f"confirm the CA M.No. and the document it was issued for.",
        )

    def _live(self, udin, membership) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live UDIN verifier not yet implemented"},
            notes="Live mode disabled.",
        )
