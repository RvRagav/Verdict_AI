"""Debarment verifier — wraps `services.debarment_service.check_bidder`
in the Verifier interface so the Verifiers tab shows it in the same
matrix as GST/PAN/UDIN/etc.
"""

from __future__ import annotations

from .base import Verifier, VerificationResult


class DebarmentVerifier(Verifier):
    name = "debarment"
    source_url = (
        "https://cvc.gov.in/punitive-information + "
        "https://gem.gov.in/blacklisting-of-bidders"
    )

    def __init__(self, *, conn) -> None:
        self.conn = conn
        self.live = False  # registry IS the source; "live" not meaningful here

    def verify(self, claim: dict) -> VerificationResult:
        from backend.services import debarment_service
        result = debarment_service.check_bidder(
            self.conn,
            pan_number=claim.get("pan_number"),
            gstin=claim.get("gstin"),
            company_name=claim.get("company_name"),
        )
        if result["flagged"]:
            sev = result["confidence"]
            status = "mismatch" if sev == "high" else "verified"  # inverse semantics
            notes = (
                f"Bidder matches a debarment registry entry "
                f"({len(result['matches'])} match(es), confidence={sev})."
            )
        else:
            status = "verified"
            notes = "Bidder does not appear in CVC / GeM / departmental debarment registry."

        return VerificationResult(
            verifier_name=self.name,
            status="mismatch" if result["flagged"] and result["confidence"] == "high" else "verified",
            confidence=0.95 if not result["flagged"] else 0.92,
            source_url=self.source_url,
            verified_via="local-registry",
            source_snapshot={
                "flagged": result["flagged"],
                "match_count": len(result["matches"]),
                "matches_summary": [
                    {"source": m["source"], "match_type": m["match_type"],
                     "reason": m["reason"]}
                    for m in result["matches"][:5]
                ],
                "registry_size": _count(self.conn),
            },
            notes=notes,
        )


def _count(conn) -> int:
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM debarment_registry").fetchone()["c"]
    except Exception:
        return -1
