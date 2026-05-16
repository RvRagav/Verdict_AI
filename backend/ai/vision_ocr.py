"""Bedrock-vision OCR.

We use Claude Sonnet 4.5 (multimodal) on Bedrock to read scanned and
photographed pages. This is the same model that does our reasoning,
which gives us a unique property the competition cannot match:

    No OCR/LLM gap. The text the officer reads is verbatim what the
    reasoning model already understands. Every word the AI quotes
    can be highlighted on the same page it was lifted from.

Pipeline:
    1. Open the page image, base64-encode it
    2. Single Bedrock invoke with a structured-output prompt:
       - lines[]: { text, bbox_norm, confidence }
       - page_confidence: float
       - notes: anything the model wants to flag (faint stamp, tear,
         handwriting, second language, etc.)
    3. Cached on prompt_hash like every other call
    4. On failure → caller falls back to Tesseract

Bbox returned by Claude is approximate (LLM vision is not a layout-
extraction model). We use it for line-level source highlighting,
which is sufficient for the click-through trust pattern. Word-level
boxes can be added by Tesseract as a backup layer.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from backend.ai import bedrock_client
from backend.config import settings


logger = logging.getLogger(__name__)


VISION_OCR_PROMPT_VERSION = "1.0.0"


VISION_OCR_SYSTEM = (
    "You are an OCR engine for Indian government tender documents. "
    "You read scanned, printed, and photographed pages and return "
    "their text exactly as it appears. You preserve layout in the "
    "order a human reads (top-down, left-right). You preserve table "
    "rows as tab-separated lines. You read English, Hindi, and "
    "common Indian financial notation (Rs., ₹, lakh, crore). You "
    "never paraphrase, summarise, correct spelling, or fabricate. "
    "If a region is too faint or torn to read, you mark that line "
    "as '[illegible]' and lower its confidence. "
    "\n\n"
    "For each text line you return its approximate bounding box in "
    "the source image, normalised to the [0, 1] range with origin "
    "at the top-left corner. Bounding boxes do not need to be exact "
    "— line-level granularity is enough."
)


VISION_OCR_USER = (
    "Read every word on this page. Return JSON only.\n\n"
    "Schema:\n"
    "{\n"
    '  "page_confidence": 0.0-1.0,\n'
    '  "language_detected": "en" | "hi" | "mixed" | "other",\n'
    '  "has_tables": bool,\n'
    '  "has_stamp_or_seal": bool,\n'
    '  "has_signature": bool,\n'
    '  "lines": [\n'
    '    {\n'
    '      "text": "<verbatim line>",\n'
    '      "bbox_norm": {"x_min": 0.0-1.0, "y_min": 0.0-1.0, '
    '"x_max": 0.0-1.0, "y_max": 0.0-1.0},\n'
    '      "confidence": 0.0-1.0\n'
    '    }\n'
    '  ],\n'
    '  "notes": "<anything to flag, e.g. faint stamp, torn corner>"\n'
    "}"
)


@dataclass
class VisionOcrResult:
    raw_text: str
    words: list[dict] = field(default_factory=list)
    page_confidence: float = 0.0
    has_tables: bool = False
    has_stamp_or_seal: bool = False
    has_signature: bool = False
    language: str = "en"
    notes: str = ""
    cached: bool = False
    error: Optional[str] = None
    invocation_id: Optional[str] = None
    prompt_hash: Optional[str] = None


def ocr_image(
    image_path: str,
    *,
    conn=None,
    tender_id: Optional[str] = None,
) -> VisionOcrResult:
    """Run Bedrock-vision OCR on a page image. Cached on the image hash."""
    if not os.path.exists(image_path):
        return VisionOcrResult(raw_text="", error=f"file not found: {image_path}")

    try:
        b64, media_type = _encode_image(image_path)
    except Exception as exc:
        return VisionOcrResult(raw_text="", error=f"image_encode_failed: {exc}")

    # We pre-hash the image bytes so the cache key is stable.
    # The bedrock_client computes its own prompt_hash too; ours is
    # included in the user-prompt envelope so identical images +
    # identical schema = identical hash = cache hit.
    image_hash = _hash_b64(b64)
    user_prompt = f"{VISION_OCR_USER}\n\n[image_sha256={image_hash[:16]}]"

    # Build the multimodal message body manually (the shared
    # bedrock_client.invoke is text-only). We still go through
    # the cache + log layer.
    cfg = settings.bedrock
    final_system = (
        VISION_OCR_SYSTEM
        + "\n\nIMPORTANT: Respond with valid JSON only. "
        "No markdown fences, no commentary."
    )

    prompt_hash = bedrock_client.compute_prompt_hash(
        system=final_system,
        user=user_prompt,
        prompt_version=VISION_OCR_PROMPT_VERSION,
        structured=True,
        schema_hint="vision_ocr",
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        model_id=cfg.model_id,
    )

    # Cache lookup
    if conn is not None:
        cached = bedrock_client.lookup_cached(conn, prompt_hash)
        if cached is not None:
            data = _safe_json(cached["response_content"])
            return _build_result(
                data, cached_text=cached["response_content"],
                cached=True, invocation_id=cached["id"],
                prompt_hash=prompt_hash,
            )

    if cfg.disabled:
        return VisionOcrResult(raw_text="", error="LLM_DISABLED",
                                prompt_hash=prompt_hash)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "system": final_system,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    }

    start = time.perf_counter()
    text = ""
    error: Optional[str] = None
    tokens_in = 0
    tokens_out = 0
    try:
        client = bedrock_client._client()
        response = client.invoke_model(
            modelId=cfg.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        usage = result.get("usage", {})
        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))
    except Exception as exc:
        logger.error("Bedrock vision OCR failed: %s", exc)
        error = f"{type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - start) * 1000)

    invocation_id: Optional[str] = None
    if conn is not None:
        invocation_id = bedrock_client.log_invocation(
            conn,
            invocation_type="vision_ocr",
            tender_id=tender_id,
            prompt_hash=prompt_hash,
            prompt_content=json.dumps({
                "system": final_system,
                "user": user_prompt,
                "image_hash": image_hash,
            }),
            response_content=text,
            model_id=cfg.model_id,
            region=cfg.region,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            error=error,
        )

    if error or not text:
        return VisionOcrResult(
            raw_text="", error=error or "empty_response",
            invocation_id=invocation_id, prompt_hash=prompt_hash,
        )

    data = _safe_json(text)
    return _build_result(
        data, cached_text=text, cached=False,
        invocation_id=invocation_id, prompt_hash=prompt_hash,
    )


# ─── Helpers ────────────────────────────────────────────────────────


def _build_result(
    data: Optional[dict],
    *,
    cached_text: str,
    cached: bool,
    invocation_id: Optional[str],
    prompt_hash: str,
) -> VisionOcrResult:
    """Convert a parsed Claude response to our internal shape."""
    if not isinstance(data, dict):
        return VisionOcrResult(
            raw_text="", error="non_dict_response",
            cached=cached, invocation_id=invocation_id,
            prompt_hash=prompt_hash,
        )

    lines = data.get("lines") or []
    if not isinstance(lines, list):
        lines = []

    text_parts: list[str] = []
    words: list[dict] = []
    confidences: list[float] = []

    for line in lines:
        if not isinstance(line, dict):
            continue
        t = (line.get("text") or "").strip()
        if not t:
            continue
        text_parts.append(t)

        bbox = line.get("bbox_norm") or {}
        if not isinstance(bbox, dict):
            bbox = {}
        x_min = _clamp01(bbox.get("x_min", 0.05))
        y_min = _clamp01(bbox.get("y_min", 0.05))
        x_max = _clamp01(bbox.get("x_max", 0.95))
        y_max = _clamp01(bbox.get("y_max", min(0.95, y_min + 0.025)))
        conf = float(line.get("confidence") or 0.9)
        confidences.append(conf)

        # Spread the line text across word-level synthesised boxes
        # so the existing bbox-based highlighter still works at word
        # granularity (it just snaps to the line's vertical band).
        tokens = t.split()
        if not tokens:
            continue
        line_width = max(0.01, x_max - x_min)
        # naive proportional layout — character count weighted
        total_chars = sum(len(tok) for tok in tokens) + (len(tokens) - 1)
        if total_chars <= 0:
            total_chars = 1
        cursor = x_min
        for tok in tokens:
            tok_share = (len(tok) + 1) / total_chars
            w = line_width * tok_share
            words.append({
                "text_content": tok,
                "x_min": round(cursor, 4),
                "y_min": round(y_min, 4),
                "x_max": round(min(x_max, cursor + w), 4),
                "y_max": round(y_max, 4),
                "confidence": conf,
                "source_engine": "bedrock_vision",
            })
            cursor += w

    page_conf = float(data.get("page_confidence") or 0.0)
    if page_conf <= 0 and confidences:
        page_conf = sum(confidences) / len(confidences)

    return VisionOcrResult(
        raw_text="\n".join(text_parts),
        words=words,
        page_confidence=round(page_conf, 4),
        has_tables=bool(data.get("has_tables")),
        has_stamp_or_seal=bool(data.get("has_stamp_or_seal")),
        has_signature=bool(data.get("has_signature")),
        language=str(data.get("language_detected") or "en"),
        notes=str(data.get("notes") or ""),
        cached=cached,
        invocation_id=invocation_id,
        prompt_hash=prompt_hash,
    )


def _safe_json(text: str) -> Optional[dict]:
    """Reuse bedrock_client's JSON parser (handles fences, stray prose)."""
    return bedrock_client._parse_json(text)


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_string, media_type) for a Bedrock image content block.

    Claude only accepts jpeg / png / gif / webp. We normalise to JPEG
    to keep payloads small (the OCR doesn't need lossless).
    """
    from PIL import Image
    import io

    with Image.open(image_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Cap longest side at 2048 — Claude charges per pixel
        # and 2048 is more than enough for OCR on A4 at 200 DPI.
        max_side = max(img.size)
        if max_side > 2048:
            scale = 2048 / max_side
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        b = buf.getvalue()
    return base64.standard_b64encode(b).decode("ascii"), "image/jpeg"


def _hash_b64(b64: str) -> str:
    import hashlib
    return hashlib.sha256(b64.encode("ascii")).hexdigest()


def _clamp01(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x
