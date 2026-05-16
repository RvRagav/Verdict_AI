"""Verifier base class + result dataclass."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


VerificationStatus = str  # 'verified' | 'mismatch' | 'not_found' | 'unreachable' | 'unknown'


@dataclass
class VerificationResult:
    """Result of one external-source verification."""

    verifier_name: str
    status: VerificationStatus
    confidence: float
    source_url: str
    verified_via: str            # 'stub' | 'live'
    source_snapshot: dict        # raw response from the authority
    notes: str
    verified_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def snapshot_sha256(self) -> str:
        """Hash of the source_snapshot — anchors the audit chain."""
        canonical = json.dumps(
            self.source_snapshot, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["snapshot_sha256"] = self.snapshot_sha256()
        return d


class Verifier:
    """Abstract base. Subclasses implement either stub or live verify()."""

    name: str = "unknown"
    source_url: str = ""
    live: bool = False

    def verify(self, claim: dict) -> VerificationResult:
        raise NotImplementedError

    def __repr__(self) -> str:
        mode = "live" if self.live else "stub"
        return f"<{type(self).__name__} {self.name} mode={mode}>"
