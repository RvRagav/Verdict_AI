"""External-source verification module.

Architecture
------------
Every external authority is a *Verifier* — a class with a stable
interface but two implementations:

  - Stub mode  (default): deterministic, derived from the bidder's
                          claim text. Each result carries a
                          `verified_via='stub'` flag so the UI can
                          honestly badge it.
  - Live mode  (env-flagged): hits the real authority's portal/API.

The driver-stub pattern lets us:

  1. Demo without depending on flaky external sites
  2. Show the panel that the integration architecture is real
  3. Switch to live by setting env vars at deployment

Verifiers
---------
  - GST              gst.gov.in/services/searchtp
  - PAN              tin-nsdl PAN verification
  - UDIN             udin.icai.org
  - FRN              icai.org chartered-accountant search
  - Udyam            udyamregistration.gov.in
  - MCA              mca.gov.in (CIN existence + entity status)
  - Debarment        local registry (CVC + GeM blacklist seedable)

Each verifier returns a `VerificationResult` with:
  status         verified | mismatch | not_found | unreachable | unknown
  confidence     0.0..1.0
  source_url     authority portal URL
  verified_via   "stub" | "live"
  source_snapshot raw response from the authority (for audit)
  verified_at    ISO timestamp
  notes          human-readable summary
"""

from .base import Verifier, VerificationResult
from .gst import GSTVerifier
from .pan import PANVerifier
from .udin import UDINVerifier
from .frn import FRNVerifier
from .udyam import UdyamVerifier
from .mca import MCAVerifier
from .debarment_verifier import DebarmentVerifier
from .registry import VerifierRegistry, get_registry


__all__ = [
    "Verifier",
    "VerificationResult",
    "GSTVerifier",
    "PANVerifier",
    "UDINVerifier",
    "FRNVerifier",
    "UdyamVerifier",
    "MCAVerifier",
    "DebarmentVerifier",
    "VerifierRegistry",
    "get_registry",
]
