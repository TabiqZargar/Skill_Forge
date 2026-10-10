"""Typed application errors mapped to HTTP responses."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for errors that map to a structured JSON response."""

    code = "app_error"
    status_code = 400

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details if details is not None else {}


class PayloadTooLarge(AppError):
    code = "payload_too_large"
    status_code = 413


class RequestInvalid(AppError):
    code = "request_invalid"
    status_code = 422


class ValidationFailed(AppError):
    code = "validation_failed"
    status_code = 422


class ExportBlocked(AppError):
    code = "export_blocked"
    status_code = 422


class InferenceUnavailable(AppError):
    """Raised when the inference provider is not configured (missing key)."""

    code = "inference_unavailable"
    status_code = 503


class InferenceFailed(AppError):
    """Raised when the provider call fails or returns an unusable response."""

    code = "inference_failed"
    status_code = 502


class MalformedModelResponse(AppError):
    """Raised when the model response cannot be parsed into a skill."""

    code = "malformed_model_response"
    status_code = 502
