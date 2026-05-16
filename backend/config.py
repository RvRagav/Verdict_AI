"""Centralised configuration for VerdictAI.

Reads from environment variables, with sensible defaults for local development.
The .env file (if present) is loaded by main.py at startup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    val = _env(name, "1" if default else "0").lower()
    return val in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class BedrockConfig:
    """AWS Bedrock configuration."""

    region: str = _env("AWS_REGION", "us-east-1")
    model_id: str = _env(
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    )
    max_tokens: int = _env_int("BEDROCK_MAX_TOKENS", 8192)
    temperature: float = _env_float("BEDROCK_TEMPERATURE", 0.0)
    timeout_s: int = _env_int("BEDROCK_TIMEOUT_S", 60)
    max_retries: int = _env_int("BEDROCK_MAX_RETRIES", 3)
    disabled: bool = _env_bool("LLM_DISABLED", False)


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Routing thresholds. Confidence Veil: deliberately conservative."""

    auto_commit: float = 0.92
    review_floor: float = 0.50
    cold_start_auto_commit: float = 0.95
    cold_start_review_floor: float = 0.60


@dataclass(frozen=True)
class Settings:
    """Application-wide settings."""

    db_path: str = _env("DB_PATH", "verdict_ai.db")
    upload_dir: str = _env("UPLOAD_DIR", "uploads")
    reports_dir: str = _env("REPORTS_DIR", "reports")
    pages_dir: str = _env("PAGES_DIR", "pages")
    vaults_dir: str = _env("VAULTS_DIR", "vaults")
    bedrock: BedrockConfig = BedrockConfig()
    confidence: ConfidenceThresholds = ConfidenceThresholds()
    cpm_calibration_threshold: int = _env_int("CPM_CALIBRATION_THRESHOLD", 50)
    pipeline_version: str = "1.0.0"


settings = Settings()
