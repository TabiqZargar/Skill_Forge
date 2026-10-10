from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.errors import InferenceFailed, InferenceUnavailable, MalformedModelResponse
from app.services.inference import InferenceClient, _parse_chat_response, build_client


def settings(**overrides) -> Settings:
    base = dict(
        inference_key="test-key",
        model="openai-gpt-oss-120b",
        base_url="https://inference.do-ai.run/v1",
        timeout_seconds=5.0,
        web_origins=["http://localhost:3000"],
    )
    base.update(overrides)
    return Settings(**base)


def client_with(handler) -> InferenceClient:
    return InferenceClient(settings(), transport=httpx.MockTransport(handler))


async def test_successful_chat():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "openai-gpt-oss-120b",
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    result = await client_with(handler).chat([{"role": "user", "content": "hi"}])
    assert result.content == "hello"
    assert result.usage == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


async def test_missing_key_raises_unavailable():
    client = InferenceClient(settings(inference_key=None))
    with pytest.raises(InferenceUnavailable):
        await client.chat([{"role": "user", "content": "hi"}])


async def test_unauthorized_raises_inference_failed():
    client = client_with(lambda request: httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(InferenceFailed) as exc:
        await client.chat([{"role": "user", "content": "hi"}])
    assert exc.value.details.get("status") == 401


async def test_rate_limit_raises():
    client = client_with(lambda request: httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(InferenceFailed) as exc:
        await client.chat([{"role": "user", "content": "hi"}])
    assert exc.value.details.get("status") == 429


async def test_server_error_raises():
    client = client_with(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(InferenceFailed) as exc:
        await client.chat([{"role": "user", "content": "hi"}])
    assert exc.value.details.get("status") == 500


async def test_timeout_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    with pytest.raises(InferenceFailed) as exc:
        await client_with(handler).chat([{"role": "user", "content": "hi"}])
    assert exc.value.details.get("reason") == "timeout"


async def test_non_json_body_raises_malformed():
    client = client_with(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(MalformedModelResponse):
        await client.chat([{"role": "user", "content": "hi"}])


def test_parse_no_choices_raises():
    with pytest.raises(MalformedModelResponse):
        _parse_chat_response({"choices": []}, fallback_model="m")


def test_parse_empty_content_raises():
    with pytest.raises(MalformedModelResponse):
        _parse_chat_response({"choices": [{"message": {"content": "  "}}]}, fallback_model="m")


def test_parse_not_object_raises():
    with pytest.raises(MalformedModelResponse):
        _parse_chat_response(["nope"], fallback_model="m")


def test_build_client_none_without_key():
    assert build_client(settings(inference_key=None)) is None
    assert build_client(settings()) is not None
