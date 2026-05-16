"""Verifier registry — single point to fetch all configured verifiers.

Reads `VERIFIER_LIVE_*` env vars to decide stub vs live per verifier.
Default: every verifier is in stub mode for local demo.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import Verifier
from .debarment_verifier import DebarmentVerifier
from .frn import FRNVerifier
from .gst import GSTVerifier
from .mca import MCAVerifier
from .pan import PANVerifier
from .udin import UDINVerifier
from .udyam import UdyamVerifier


def _live(name: str) -> bool:
    """Read VERIFIER_LIVE_<NAME>=1 to enable live mode for one verifier."""
    return os.environ.get(f"VERIFIER_LIVE_{name.upper()}", "0") == "1"


class VerifierRegistry:
    """Build all verifiers for a given DB connection."""

    def __init__(self, conn):
        self.gst = GSTVerifier(live=_live("gst"))
        self.pan = PANVerifier(live=_live("pan"))
        self.udin = UDINVerifier(live=_live("udin"))
        self.frn = FRNVerifier(live=_live("frn"))
        self.udyam = UdyamVerifier(live=_live("udyam"))
        self.mca = MCAVerifier(live=_live("mca"))
        self.debarment = DebarmentVerifier(conn=conn)

    def all(self) -> dict[str, Verifier]:
        return {
            "gst": self.gst, "pan": self.pan, "udin": self.udin,
            "frn": self.frn, "udyam": self.udyam, "mca": self.mca,
            "debarment": self.debarment,
        }


def get_registry(conn) -> VerifierRegistry:
    return VerifierRegistry(conn)
