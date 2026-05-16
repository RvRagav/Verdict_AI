"""Document security scanner — runs on every uploaded file.

Inspired by resistant.ai's multi-layer document verification approach.
Checks for:
1. Hidden text layers (text behind images — common in forged scans)
2. Prompt injection attempts (adversarial text targeting LLM extraction)
3. Metadata inconsistencies (creation date after modification, impossible timestamps)
4. Suspicious PDF structure (JavaScript, embedded executables, form actions)

Returns a list of security findings that get stored on the document row
and surfaced in the File Vault + Verifiers tabs.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


# ─── Prompt injection detection ─────────────────────────────────────────

# Patterns that indicate adversarial text targeting LLM extraction
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a",
    r"disregard\s+(the\s+)?(above|previous)",
    r"system\s*:\s*you\s+are",
    r"<\|im_start\|>",
    r"\[INST\]",
    r"<<SYS>>",
    r"forget\s+(everything|all)\s+(you|that)",
    r"new\s+instructions?\s*:",
    r"override\s+(the\s+)?system",
    r"act\s+as\s+(if|though)\s+you",
    r"pretend\s+(you\s+are|to\s+be)",
]

_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def scan_for_injection(text: str) -> Optional[dict]:
    """Scan extracted text for prompt injection attempts."""
    if not text:
        return None
    m = _INJECTION_RE.search(text)
    if m:
        # Find the surrounding context (±50 chars)
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 50)
        context = text[start:end]
        return {
            "finding_type": "prompt_injection",
            "severity": "critical",
            "message": (
                f"Potential prompt injection detected in document text: "
                f"'{m.group(0)}'. This may be an adversarial attempt to "
                f"manipulate the AI extraction pipeline."
            ),
            "evidence": {
                "matched_pattern": m.group(0),
                "context": context,
                "position": m.start(),
            },
        }
    return None


# ─── Hidden text detection ──────────────────────────────────────────────


def scan_for_hidden_text(
    *,
    native_text: str,
    ocr_text: str,
    page_number: int,
) -> Optional[dict]:
    """Detect hidden text layers by comparing native PDF text extraction
    with OCR output. If native text contains significantly more content
    than what's visually rendered (OCR), there may be hidden text behind
    images — a common forgery technique.

    Heuristic: if native text is >3x longer than OCR text AND OCR text
    is non-empty (meaning the page has visual content), flag it.
    """
    if not native_text or not ocr_text:
        return None

    native_words = len(native_text.split())
    ocr_words = len(ocr_text.split())

    if ocr_words < 5:
        return None  # page is mostly blank/image — can't compare

    ratio = native_words / max(ocr_words, 1)
    if ratio > 3.0:
        return {
            "finding_type": "hidden_text_layer",
            "severity": "high",
            "message": (
                f"Page {page_number}: native text extraction found "
                f"{native_words} words but OCR only sees {ocr_words} words. "
                f"Ratio {ratio:.1f}x suggests hidden text behind images — "
                f"common in forged scanned documents."
            ),
            "evidence": {
                "page_number": page_number,
                "native_word_count": native_words,
                "ocr_word_count": ocr_words,
                "ratio": round(ratio, 2),
            },
        }
    return None


# ─── Metadata consistency ───────────────────────────────────────────────


def scan_metadata_consistency(metadata: dict) -> list[dict]:
    """Check PDF metadata for impossible or suspicious values."""
    findings: list[dict] = []
    if not metadata:
        return findings

    creation = metadata.get("creation_date")
    modification = metadata.get("mod_date") or metadata.get("modification_date")

    # Creation date in the future
    if creation:
        try:
            cd = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            if cd > datetime.now(cd.tzinfo):
                findings.append({
                    "finding_type": "future_creation_date",
                    "severity": "high",
                    "message": (
                        f"Document creation date ({creation}) is in the future. "
                        f"This is physically impossible and indicates metadata tampering."
                    ),
                    "evidence": {"creation_date": creation},
                })
        except (ValueError, TypeError):
            pass

    # Modification date before creation date
    if creation and modification:
        try:
            cd = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            md = datetime.fromisoformat(modification.replace("Z", "+00:00"))
            if md < cd:
                findings.append({
                    "finding_type": "modification_before_creation",
                    "severity": "medium",
                    "message": (
                        f"Document was modified ({modification}) before it was "
                        f"created ({creation}). Metadata has been tampered."
                    ),
                    "evidence": {
                        "creation_date": creation,
                        "modification_date": modification,
                    },
                })
        except (ValueError, TypeError):
            pass

    return findings


# ─── PDF structure checks ───────────────────────────────────────────────


def scan_pdf_structure(raw_bytes: bytes) -> list[dict]:
    """Scan raw PDF bytes for dangerous structures.

    Checks for:
    - JavaScript (/JS, /JavaScript)
    - Embedded files (/EmbeddedFile)
    - Form submit actions (/SubmitForm)
    - Launch actions (/Launch)
    """
    findings: list[dict] = []
    if not raw_bytes:
        return findings

    # Only check first 100KB to avoid scanning huge files
    sample = raw_bytes[:102400]
    text = sample.decode("latin-1", errors="ignore")

    dangerous_patterns = [
        (r"/JavaScript|/JS\s", "javascript", "critical",
         "PDF contains JavaScript — potential malware vector."),
        (r"/Launch", "launch_action", "critical",
         "PDF contains a Launch action — can execute external programs."),
        (r"/SubmitForm", "form_submit", "high",
         "PDF contains a form-submit action — may exfiltrate data."),
        (r"/EmbeddedFile", "embedded_file", "medium",
         "PDF contains embedded files — inspect manually."),
    ]

    for pattern, finding_type, severity, message in dangerous_patterns:
        if re.search(pattern, text):
            findings.append({
                "finding_type": finding_type,
                "severity": severity,
                "message": message,
                "evidence": {"pattern": pattern},
            })

    return findings


# ─── Driver ──────────────────────────────────────────────────────────────


def scan_document(
    *,
    text: str = "",
    metadata: Optional[dict] = None,
    raw_bytes: Optional[bytes] = None,
    native_text: str = "",
    ocr_text: str = "",
    page_number: int = 1,
) -> list[dict]:
    """Run all security checks on a document. Returns findings list."""
    findings: list[dict] = []

    # Prompt injection
    inj = scan_for_injection(text)
    if inj:
        findings.append(inj)

    # Hidden text
    ht = scan_for_hidden_text(
        native_text=native_text, ocr_text=ocr_text, page_number=page_number,
    )
    if ht:
        findings.append(ht)

    # Metadata
    if metadata:
        findings.extend(scan_metadata_consistency(metadata))

    # PDF structure
    if raw_bytes:
        findings.extend(scan_pdf_structure(raw_bytes))

    return findings
