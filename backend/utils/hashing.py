"""Hashing helpers — file SHA-256 + canonical JSON hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path, chunk_size: int = 65536) -> str:
    """Return the SHA-256 of the file at `path` as a 64-char hex string."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_canonical(obj: Any) -> str:
    """SHA-256 of a JSON-serialisable object's canonical form."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
