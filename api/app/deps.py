"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from .config import Settings, get_settings
from .services.inference import InferenceClient, build_client


def get_settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_inference_client(settings: SettingsDep) -> InferenceClient | None:
    """Return the configured DigitalOcean client, or ``None`` when no key is set.

    Returning ``None`` (instead of raising) lets endpoints decide between a hard
    failure (generation) and a graceful deterministic fallback (evaluation).
    """

    return build_client(settings)


InferenceDep = Annotated[InferenceClient | None, Depends(get_inference_client)]
