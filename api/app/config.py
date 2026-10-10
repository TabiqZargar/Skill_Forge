"""Server-side configuration for SkillForge.

All secrets are read from environment variables at call time so that tests can
monkeypatch them and so that nothing is captured at import time. Credentials are
never returned to clients.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Verified open-weight default model hosted by DigitalOcean Inference.
# Model ID verified against https://docs.digitalocean.com/products/inference/details/models/
# License: Apache-2.0 (https://huggingface.co/openai/gpt-oss-120b).
DEFAULT_MODEL = "openai-gpt-oss-120b"
DEFAULT_BASE_URL = "https://inference.do-ai.run/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0

# Guardrails for generated/uploaded content.
DEFAULT_MAX_FILES = 40
DEFAULT_MAX_FILE_BYTES = 128 * 1024
DEFAULT_MAX_TOTAL_BYTES = 512 * 1024


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _list_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return list(default)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or list(default)


@dataclass(frozen=True)
class Settings:
    inference_key: str | None
    model: str
    base_url: str
    timeout_seconds: float
    web_origins: list[str] = field(default_factory=list)
    max_files: int = DEFAULT_MAX_FILES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES

    @property
    def inference_configured(self) -> bool:
        return bool(self.inference_key)


def get_settings() -> Settings:
    """Read settings from the environment.

    ``DIGITALOCEAN_INFERENCE_KEY`` and ``DIGITALOCEAN_MODEL`` are the documented
    server-side variables. A missing key is represented explicitly (``None``) so
    callers can surface an actionable error instead of silently degrading.
    """

    key = os.environ.get("DIGITALOCEAN_INFERENCE_KEY")
    key = key.strip() if key and key.strip() else None
    model = (os.environ.get("DIGITALOCEAN_MODEL") or "").strip() or DEFAULT_MODEL
    base_url = (
        os.environ.get("DIGITALOCEAN_INFERENCE_BASE_URL") or ""
    ).strip().rstrip("/") or DEFAULT_BASE_URL

    return Settings(
        inference_key=key,
        model=model,
        base_url=base_url,
        timeout_seconds=_float_env("DIGITALOCEAN_INFERENCE_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
        web_origins=_list_env("WEB_ORIGIN", ["http://localhost:3000", "http://127.0.0.1:3000"]),
        max_files=_int_env("SKILLFORGE_MAX_FILES", DEFAULT_MAX_FILES),
        max_file_bytes=_int_env("SKILLFORGE_MAX_FILE_BYTES", DEFAULT_MAX_FILE_BYTES),
        max_total_bytes=_int_env("SKILLFORGE_MAX_TOTAL_BYTES", DEFAULT_MAX_TOTAL_BYTES),
    )
