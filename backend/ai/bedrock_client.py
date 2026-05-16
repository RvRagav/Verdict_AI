"""AWS Bedrock client for Claude 3.5 Sonnet.

Uses boto3 invoke_model and invoke_model_with_response_stream.
Region: us-east-1 (default; override via AWS_REGION).
Auth: default credential chain — for local development that means ADA
credentials from the terminal.

Critical design choices that make this trustworthy:

1. **Persistent cache.** Every successful call is logged to llm_invocations
   keyed by prompt_hash. Subsequent calls with the same hash short-circuit
   to the cached response. This is the foundation of byte-identical
   reproducibility and the only thing standing between us and a
   prohibitive demo bill.

2. **Robust prompt hash.** We hash a canonical envelope containing
   *every* input that can change the response: model_id, region,
   temperature, max_tokens, the JSON-mode flag, and the prompt template
   version (caller-supplied).

3. **Temperature=0 by default.** Caller can override but the default
   is deterministic. Reproducibility relies on cache-or-equivalent;
   determinism makes equivalence safer.

4. **Adaptive retries.** botocore Config with retries={mode: adaptive,
   max_attempts: 3} so a throttle doesn't kill the demo.

5. **Streaming separates from caching.** Stream responses are fully
   accumulated server-side and persisted on completion. A client
   disconnect mid-stream still produces an audited llm_invocations
   row (with error="client_disconnected" and the partial text).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from botocore.config import Config as BotoConfig

from backend.config import settings


logger = logging.getLogger(__name__)


# ─── Response shape ──────────────────────────────────────────────────────


@dataclass
class BedrockResponse:
    """Result of a single Bedrock invocation."""

    text: str
    data: Any = None  # parsed JSON when structured=True
    model_id: str = ""
    prompt_hash: str = ""
    cached: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    error: Optional[str] = None
    invocation_id: Optional[str] = None  # row id in llm_invocations


# ─── boto3 client (lazy, cached) ─────────────────────────────────────────


_boto_client = None
_caller_identity_cache: Optional[dict] = None
_caller_identity_at: float = 0.0
_CALLER_IDENTITY_TTL_S = 60.0   # re-check every 60s so token expiry is noticed quickly


def _client():
    """Lazy-init the bedrock-runtime client with adaptive retries.

    Uses a fresh boto3.Session() each time it rebuilds so that
    credential refreshes (ada credentials update) are picked up
    without restarting the process.
    """
    global _boto_client
    if _boto_client is None:
        import boto3
        # Fresh session re-reads ~/.aws/credentials from disk
        session = boto3.Session()
        cfg = BotoConfig(
            region_name=settings.bedrock.region,
            retries={"max_attempts": settings.bedrock.max_retries, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=settings.bedrock.timeout_s,
        )
        _boto_client = session.client("bedrock-runtime", config=cfg)
    return _boto_client


def _reset_client() -> None:
    """Drop the cached boto3 client. Forces the next call to rebuild it
    so freshly-refreshed credentials are picked up."""
    global _boto_client, _caller_identity_cache, _caller_identity_at
    _boto_client = None
    _caller_identity_cache = None
    _caller_identity_at = 0.0


def _is_expired_token(exc: Exception) -> bool:
    """Detect AWS expired-token errors regardless of how they surface."""
    s = f"{type(exc).__name__}: {exc}"
    return ("ExpiredToken" in s) or ("expired" in s.lower() and "token" in s.lower())


def get_caller_identity() -> Optional[dict]:
    """Return AWS caller identity (cached for 60s on success).

    On failure we DO NOT cache — every subsequent call retries until it
    succeeds. This is so the 'AI not configured' state in the UI clears
    automatically when ADA refreshes the token, without needing a server
    restart.
    """
    import time
    global _caller_identity_cache, _caller_identity_at
    now = time.time()
    if _caller_identity_cache is not None and (now - _caller_identity_at) < _CALLER_IDENTITY_TTL_S:
        return _caller_identity_cache
    try:
        import boto3
        import botocore.session
        # Force a FRESH session that re-reads ~/.aws/credentials from disk.
        # The default boto3 session caches credentials at import time and
        # won't pick up ADA refreshes without this.
        fresh_session = boto3.Session()
        sts = fresh_session.client("sts", region_name=settings.bedrock.region)
        ident = sts.get_caller_identity()
        _caller_identity_cache = {
            "account": ident.get("Account"),
            "arn": ident.get("Arn"),
            "user_id": ident.get("UserId"),
        }
        _caller_identity_at = now
        return _caller_identity_cache
    except Exception as exc:
        logger.warning("STS get_caller_identity failed: %s", exc)
        _caller_identity_cache = None
        _caller_identity_at = 0.0
        return None


def is_configured() -> bool:
    """True iff Bedrock can be called right now."""
    if settings.bedrock.disabled:
        return False
    return get_caller_identity() is not None


# ─── Prompt hash ─────────────────────────────────────────────────────────


def compute_prompt_hash(
    *,
    system: str,
    user: str,
    prompt_version: str,
    structured: bool,
    schema_hint: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model_id: Optional[str] = None,
) -> str:
    """Deterministic SHA-256 over every input that can change the response.

    Anything we leave out here will silently break reproducibility on the
    next change. So we include it all.
    """
    envelope = {
        "model_id": model_id or settings.bedrock.model_id,
        "region": settings.bedrock.region,
        "temperature": temperature if temperature is not None else settings.bedrock.temperature,
        "max_tokens": max_tokens if max_tokens is not None else settings.bedrock.max_tokens,
        "prompt_version": prompt_version,
        "structured": bool(structured),
        "schema_hint": schema_hint or "",
        "system": system,
        "user": user,
    }
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── Cache ───────────────────────────────────────────────────────────────


def lookup_cached(conn: sqlite3.Connection, prompt_hash: str) -> Optional[dict]:
    """Return the most recent cached response for a prompt hash, or None."""
    row = conn.execute(
        """SELECT id, response_content, model_id, tokens_in, tokens_out, latency_ms, error
           FROM llm_invocations
           WHERE prompt_hash = ? AND error IS NULL
           ORDER BY timestamp DESC LIMIT 1""",
        (prompt_hash,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def log_invocation(
    conn: sqlite3.Connection,
    *,
    invocation_type: str,
    tender_id: Optional[str],
    prompt_hash: str,
    prompt_content: str,
    response_content: str,
    model_id: str,
    region: str,
    temperature: float,
    max_tokens: int,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    error: Optional[str] = None,
) -> str:
    """Insert a row into llm_invocations and return its id.

    If tender_id doesn't exist in the tenders table (e.g. unit tests,
    cache priming), we fall back to NULL rather than violating the FK.
    """
    invocation_id = str(uuid.uuid4())
    if tender_id is not None:
        exists = conn.execute(
            "SELECT 1 FROM tenders WHERE id = ?", (tender_id,)
        ).fetchone()
        if not exists:
            tender_id = None
    conn.execute(
        """INSERT INTO llm_invocations
           (id, tender_id, invocation_type, prompt_hash, prompt_content,
            response_content, model_id, region, temperature, max_tokens,
            tokens_in, tokens_out, latency_ms, error, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            invocation_id, tender_id, invocation_type, prompt_hash,
            prompt_content, response_content, model_id, region,
            temperature, max_tokens, tokens_in, tokens_out, latency_ms,
            error, datetime.now(timezone.utc).isoformat(),
        ),
    )
    return invocation_id


# ─── Core invoke ─────────────────────────────────────────────────────────


def invoke(
    *,
    invocation_type: str,
    system: str,
    user: str,
    prompt_version: str,
    structured: bool = False,
    schema_hint: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tender_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    use_cache: bool = True,
) -> BedrockResponse:
    """Invoke Claude on Bedrock, with cache-first lookup and full logging.

    Args:
        invocation_type: tag for the audit log
            (e.g. 'criterion_extraction', 'verdict', 'dissent', 'chat').
        system: system prompt.
        user: user prompt.
        prompt_version: caller-supplied version of the prompt template
            (bump this when you edit the template — it changes the hash).
        structured: parse the response as JSON.
        schema_hint: optional JSON schema hint appended to the system prompt.
        temperature, max_tokens: overrides for this call.
        tender_id: stamped onto the log row for tender-scoped audit.
        conn: SQLite connection for cache + logging. If None, no cache.
        use_cache: set False to force a live call.

    Returns:
        BedrockResponse with .text, .data (if structured), .cached, etc.
    """
    cfg = settings.bedrock
    temp = cfg.temperature if temperature is None else temperature
    mtok = cfg.max_tokens if max_tokens is None else max_tokens

    final_system = system
    if structured:
        final_system = (
            system + "\n\nIMPORTANT: Respond with valid JSON only. "
            "No markdown, no code fences, no commentary."
        )
        if schema_hint:
            final_system += f"\nSchema hint: {schema_hint}"

    prompt_hash = compute_prompt_hash(
        system=final_system,
        user=user,
        prompt_version=prompt_version,
        structured=structured,
        schema_hint=schema_hint,
        temperature=temp,
        max_tokens=mtok,
        model_id=cfg.model_id,
    )

    # ── Cache lookup ─────────────────────────────────────────────────
    if use_cache and conn is not None:
        cached = lookup_cached(conn, prompt_hash)
        if cached is not None:
            text = cached["response_content"]
            data = _parse_json(text) if structured else None
            return BedrockResponse(
                text=text,
                data=data,
                model_id=cached["model_id"],
                prompt_hash=prompt_hash,
                cached=True,
                tokens_in=cached["tokens_in"] or 0,
                tokens_out=cached["tokens_out"] or 0,
                latency_ms=cached["latency_ms"] or 0,
                invocation_id=cached["id"],
            )

    # ── Disabled? short-circuit ──────────────────────────────────────
    if cfg.disabled:
        return BedrockResponse(
            text="",
            model_id=cfg.model_id,
            prompt_hash=prompt_hash,
            error="LLM_DISABLED",
        )

    # ── Live call ────────────────────────────────────────────────────
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": mtok,
        "temperature": temp,
        "system": final_system,
        "messages": [{"role": "user", "content": user}],
    }

    start = time.perf_counter()
    error: Optional[str] = None
    text = ""
    tokens_in = 0
    tokens_out = 0
    model_id_used = cfg.model_id

    try:
        response = _client().invoke_model(
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
        model_id_used = result.get("model", cfg.model_id)
    except Exception as exc:
        # Expired-token? rebuild the client once and retry, so a fresh
        # `ada credentials update` is picked up without a process restart.
        if _is_expired_token(exc):
            logger.warning("Bedrock token expired — resetting client and retrying once.")
            _reset_client()
            try:
                response = _client().invoke_model(
                    modelId=cfg.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                result = json.loads(response["body"].read())
                text = ""
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]
                usage = result.get("usage", {})
                tokens_in = int(usage.get("input_tokens", 0))
                tokens_out = int(usage.get("output_tokens", 0))
                model_id_used = result.get("model", cfg.model_id)
                error = None
            except Exception as exc2:
                logger.error("Bedrock retry also failed: %s", exc2)
                error = f"{type(exc2).__name__}: {exc2}"
        else:
            logger.error("Bedrock invoke_model failed: %s", exc)
            error = f"{type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - start) * 1000)

    # ── Persist to llm_invocations ───────────────────────────────────
    invocation_id: Optional[str] = None
    if conn is not None:
        invocation_id = log_invocation(
            conn,
            invocation_type=invocation_type,
            tender_id=tender_id,
            prompt_hash=prompt_hash,
            prompt_content=json.dumps({"system": final_system, "user": user}),
            response_content=text,
            model_id=model_id_used,
            region=cfg.region,
            temperature=temp,
            max_tokens=mtok,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            error=error,
        )

    data = _parse_json(text) if (structured and text) else None

    return BedrockResponse(
        text=text,
        data=data,
        model_id=model_id_used,
        prompt_hash=prompt_hash,
        cached=False,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        error=error,
        invocation_id=invocation_id,
    )


# ─── Streaming (for the Copilot chat) ────────────────────────────────────


def invoke_stream(
    *,
    invocation_type: str,
    system: str,
    user: str,
    prompt_version: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tender_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    use_cache: bool = True,
) -> Iterator[dict]:
    """Stream tokens from Claude. Yields dicts:

        {"type": "delta", "text": "..."}
        {"type": "done",  "text": "<full>", "cached": bool, "invocation_id": str}
        {"type": "error", "error": "..."}

    Cache hits replay tokens as a single delta-then-done sequence so the
    client UX is identical regardless of cache state.

    Caller (the FastAPI endpoint) wraps the generator in a StreamingResponse
    using server-sent events.
    """
    cfg = settings.bedrock
    temp = cfg.temperature if temperature is None else temperature
    mtok = cfg.max_tokens if max_tokens is None else max_tokens

    prompt_hash = compute_prompt_hash(
        system=system, user=user,
        prompt_version=prompt_version,
        structured=False,
        temperature=temp,
        max_tokens=mtok,
    )

    # Cache replay
    if use_cache and conn is not None:
        cached = lookup_cached(conn, prompt_hash)
        if cached is not None:
            yield {"type": "delta", "text": cached["response_content"]}
            yield {
                "type": "done",
                "text": cached["response_content"],
                "cached": True,
                "invocation_id": cached["id"],
                "prompt_hash": prompt_hash,
            }
            return

    if cfg.disabled:
        yield {"type": "error", "error": "LLM_DISABLED"}
        return

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": mtok,
        "temperature": temp,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    start = time.perf_counter()
    accumulated = []
    tokens_in = 0
    tokens_out = 0
    error_msg: Optional[str] = None

    try:
        response = _client().invoke_model_with_response_stream(
            modelId=cfg.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        for event in response.get("body", []):
            chunk = event.get("chunk", {})
            payload_bytes = chunk.get("bytes")
            if not payload_bytes:
                continue
            payload = json.loads(payload_bytes.decode("utf-8"))

            etype = payload.get("type")
            if etype == "content_block_delta":
                delta = payload.get("delta", {})
                if delta.get("type") == "text_delta":
                    text_chunk = delta.get("text", "")
                    accumulated.append(text_chunk)
                    yield {"type": "delta", "text": text_chunk}
            elif etype == "message_delta":
                usage = payload.get("usage", {})
                tokens_out = int(usage.get("output_tokens", tokens_out))
            elif etype == "message_start":
                usage = payload.get("message", {}).get("usage", {})
                tokens_in = int(usage.get("input_tokens", 0))
    except Exception as exc:
        # Expired token mid-stream? Reset + retry once.
        if _is_expired_token(exc):
            logger.warning("Bedrock streaming token expired — resetting + retrying.")
            _reset_client()
            try:
                accumulated.clear()
                response = _client().invoke_model_with_response_stream(
                    modelId=cfg.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                for event in response.get("body", []):
                    chunk = event.get("chunk", {})
                    payload_bytes = chunk.get("bytes")
                    if not payload_bytes:
                        continue
                    payload = json.loads(payload_bytes.decode("utf-8"))
                    etype = payload.get("type")
                    if etype == "content_block_delta":
                        delta = payload.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text_chunk = delta.get("text", "")
                            accumulated.append(text_chunk)
                            yield {"type": "delta", "text": text_chunk}
                    elif etype == "message_delta":
                        usage = payload.get("usage", {})
                        tokens_out = int(usage.get("output_tokens", tokens_out))
                    elif etype == "message_start":
                        usage = payload.get("message", {}).get("usage", {})
                        tokens_in = int(usage.get("input_tokens", 0))
                error_msg = None
            except Exception as exc2:
                logger.error("Bedrock stream retry failed: %s", exc2)
                error_msg = f"{type(exc2).__name__}: {exc2}"
        else:
            logger.error("Bedrock stream failed: %s", exc)
            error_msg = f"{type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - start) * 1000)
    full_text = "".join(accumulated)

    invocation_id: Optional[str] = None
    if conn is not None:
        invocation_id = log_invocation(
            conn,
            invocation_type=invocation_type,
            tender_id=tender_id,
            prompt_hash=prompt_hash,
            prompt_content=json.dumps({"system": system, "user": user}),
            response_content=full_text,
            model_id=cfg.model_id,
            region=cfg.region,
            temperature=temp,
            max_tokens=mtok,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            error=error_msg,
        )

    if error_msg:
        yield {"type": "error", "error": error_msg}
    else:
        yield {
            "type": "done",
            "text": full_text,
            "cached": False,
            "invocation_id": invocation_id,
            "prompt_hash": prompt_hash,
        }


# ─── JSON parser with recovery ───────────────────────────────────────────


def _parse_json(text: str) -> Optional[Any]:
    """Parse text as JSON; recover from common LLM quirks.

    Handles:
    - markdown code fences (```json ... ```)
    - leading/trailing prose around the JSON
    - top-level objects OR arrays
    """
    if not text:
        return None
    s = text.strip()

    # Strip markdown fences
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

    # Direct parse
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        pass

    # Find JSON object or array boundaries
    obj_start = s.find("{")
    obj_end = s.rfind("}")
    arr_start = s.find("[")
    arr_end = s.rfind("]")

    candidates: list[tuple[int, str]] = []
    if obj_start != -1 and obj_end > obj_start:
        candidates.append((obj_start, s[obj_start : obj_end + 1]))
    if arr_start != -1 and arr_end > arr_start:
        candidates.append((arr_start, s[arr_start : arr_end + 1]))

    # Try whichever appears first in the text
    candidates.sort(key=lambda c: c[0])
    for _, candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None
