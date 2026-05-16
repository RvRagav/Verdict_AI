"""PAN verifier — Income Tax Department's NSDL/Protean.

The 4th character of a PAN encodes entity type:
  P = Person (individual)
  C = Company
  H = Hindu Undivided Family
  F = Firm/Partnership
  A = Association of Persons
  T = Trust
  B = Body of Individuals
  L = Local Authority
  J = Artificial Juridical Person
  G = Government

Stub: validates format + entity-type alignment with declared
constitution. Live (TODO): hits the NSDL PAN verification API.
"""

from __future__ import annotations

import re

from .base import Verifier, VerificationResult


PAN_FMT = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
ENTITY_CODE = {
    "P": "Person", "C": "Company", "H": "HUF", "F": "Firm",
    "A": "Association", "T": "Trust", "B": "BOI",
    "L": "Local Authority", "J": "Artificial Juridical", "G": "Government",
}


class PANVerifier(Verifier):
    name = "pan"
    source_url = "https://www.tin-nsdl.com/services/pan/pan-verification.html"

    def __init__(self, *, live: bool = False) -> None:
        self.live = live

    def verify(self, claim: dict) -> VerificationResult:
        pan = (claim.get("pan_number") or "").strip().upper()
        declared_constitution = (claim.get("constitution") or "").strip().lower()

        if self.live:
            return self._live(pan, declared_constitution)

        if not pan:
            return VerificationResult(
                verifier_name=self.name, status="unknown", confidence=0.0,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"requested": claim}, notes="No PAN supplied.",
            )
        if not PAN_FMT.match(pan):
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.95,
                source_url=self.source_url, verified_via="stub",
                source_snapshot={"pan": pan, "format_ok": False},
                notes="PAN format invalid (expected AAAAA9999A).",
            )

        entity_char = pan[3]
        entity_label = ENTITY_CODE.get(entity_char, "Unknown")

        # Heuristic constitution check
        decl = declared_constitution
        ok = True
        why = ""
        if "private limited" in decl or "pvt ltd" in decl or "limited" in decl or "ltd" in decl:
            if entity_char != "C":
                ok = False
                why = (f"PAN 4th char is '{entity_char}' ({entity_label}); "
                       f"bidder declares as a Limited Company — expected 'C'.")
        elif "partnership" in decl or "llp" in decl:
            if entity_char != "F":
                ok = False
                why = f"Partnership/LLP — expected 'F', got '{entity_char}'."
        elif "trust" in decl and entity_char != "T":
            ok = False
            why = f"Trust — expected 'T', got '{entity_char}'."

        snapshot = {
            "pan": pan, "format_ok": True,
            "entity_char": entity_char, "entity_label": entity_label,
            "declared_constitution": declared_constitution,
            "_stub_note": "Stub-mode: derived from PAN structure. "
                          "Live mode will hit NSDL PAN verification.",
        }

        if not ok:
            return VerificationResult(
                verifier_name=self.name, status="mismatch", confidence=0.90,
                source_url=self.source_url, verified_via="stub",
                source_snapshot=snapshot, notes=why,
            )
        return VerificationResult(
            verifier_name=self.name, status="verified", confidence=0.93,
            source_url=self.source_url, verified_via="stub",
            source_snapshot=snapshot,
            notes=f"PAN format valid; entity-type code '{entity_char}' "
                  f"({entity_label}) consistent with declared constitution.",
        )

    def _live(self, pan, constitution) -> VerificationResult:
        return VerificationResult(
            verifier_name=self.name, status="unreachable", confidence=0.0,
            source_url=self.source_url, verified_via="live",
            source_snapshot={"error": "Live PAN verifier needs NSDL API key"},
            notes="Live mode not configured. Use stub.",
        )
