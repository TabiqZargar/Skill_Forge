"""Server-side DigitalOcean Inference adapter.

Uses the documented OpenAI-compatible Serverless Inference endpoint:

    POST https://inference.do-ai.run/v1/chat/completions
    Authorization: Bearer $DIGITALOCEAN_INFERENCE_KEY

Docs: https://docs.digitalocean.com/products/inference/how-to/use-chat-completions-api/

The adapter never mutates the configured model: if a call fails, that failure is
surfaced to the caller. It never substitutes another model or fabricates output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..errors import InferenceFailed, InferenceUnavailable, MalformedModelResponse


@dataclass
class ChatResult:
    content: str
    model: str
    usage: dict[str, int] | None = None
    finish_reason: str | None = None


class InferenceClient:
    """Thin async wrapper around the DigitalOcean chat completions endpoint."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def model(self) -> str:
        return self._settings.model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_completion_tokens: int = 2048,
    ) -> ChatResult:
        key = self._settings.inference_key
        if not key:
            raise InferenceUnavailable(
                "DIGITALOCEAN_INFERENCE_KEY is not set on the server. Configure it to enable AI generation."
            )

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": messages,
            "temperature": max(0.0, min(1.0, temperature)),
            "max_completion_tokens": max_completion_tokens,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self._settings.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.timeout_seconds),
                transport=self._transport,
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise InferenceFailed(
                f"DigitalOcean Inference request timed out after {self._settings.timeout_seconds:.0f}s.",
                details={"reason": "timeout"},
            ) from exc
        except httpx.HTTPError as exc:
            raise InferenceFailed(
                "Could not reach DigitalOcean Inference.",
                details={"reason": "connection_error", "error": exc.__class__.__name__},
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise InferenceFailed(
                "DigitalOcean Inference rejected the credentials. Check DIGITALOCEAN_INFERENCE_KEY.",
                details={"status": response.status_code, "provider_message": _safe_text(response)},
            )
        if response.status_code == 429:
            raise InferenceFailed(
                "DigitalOcean Inference rate limit reached. Retry shortly.",
                details={"status": 429, "provider_message": _safe_text(response)},
            )
        if response.status_code >= 400:
            raise InferenceFailed(
                f"DigitalOcean Inference returned HTTP {response.status_code}.",
                details={"status": response.status_code, "provider_message": _safe_text(response)},
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise MalformedModelResponse("Provider response was not valid JSON.") from exc

        return _parse_chat_response(body, fallback_model=self._settings.model)


def _safe_text(response: httpx.Response, limit: int = 500) -> str:
    try:
        return response.text[:limit]
    except Exception:  # pragma: no cover - defensive
        return ""


def _parse_chat_response(body: Any, *, fallback_model: str) -> ChatResult:
    if not isinstance(body, dict):
        raise MalformedModelResponse("Provider response was not a JSON object.")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise MalformedModelResponse("Provider response did not contain any choices.")

    first = choices[0]
    if not isinstance(first, dict):
        raise MalformedModelResponse("Provider choice was malformed.")

    message = first.get("message")
    content: Any = None
    if isinstance(message, dict):
        content = message.get("content")
    if content is None:
        content = first.get("text")

    if not isinstance(content, str) or not content.strip():
        raise MalformedModelResponse("Provider response contained no text content.")

    usage_raw = body.get("usage")
    usage: dict[str, int] | None = None
    if isinstance(usage_raw, dict):
        usage = {k: v for k, v in usage_raw.items() if isinstance(v, int)}

    model = body.get("model")
    if not isinstance(model, str) or not model:
        model = fallback_model

    finish_reason = first.get("finish_reason")
    if not isinstance(finish_reason, str):
        finish_reason = None

    return ChatResult(content=content, model=model, usage=usage, finish_reason=finish_reason)


def build_client(settings: Settings) -> InferenceClient | None:
    """Return a client when configured, otherwise ``None`` (never a fake)."""

    if not settings.inference_configured:
        return None
    return InferenceClient(settings)
