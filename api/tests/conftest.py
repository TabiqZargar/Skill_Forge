"""Shared pytest fixtures. The inference provider is always mocked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import get_inference_client
from app.main import app
from app.schemas import Skill, SkillFile
from app.services import frontmatter as fm
from app.services.inference import ChatResult


def make_skill_md(name: str, description: str, body: str, extra_fm: dict | None = None) -> str:
    data = {"name": name, "description": description}
    if extra_fm:
        data.update(extra_fm)
    return fm.render_skill_md(data, body)


@pytest.fixture
def valid_skill() -> Skill:
    body = (
        "# Demo Skill\n\n"
        "Use when the user asks for a demo.\n\n"
        "1. Read the input.\n"
        "2. Produce output.\n\n"
        "See [references/guide.md](references/guide.md).\n"
    )
    files = [
        SkillFile(
            path="SKILL.md",
            content=make_skill_md("demo-skill", "A demo skill. Use when the user wants a demo.", body),
        ),
        SkillFile(path="references/guide.md", content="# Guide\n"),
    ]
    return Skill(files=files)


@pytest.fixture
def sample_skill() -> Skill:
    from app.services import samples

    return samples.get_sample_skill()


class FakeInferenceClient:
    """Deterministic stand-in for the DigitalOcean client."""

    def __init__(self, content: str = "", *, error: Exception | None = None, model: str = "fake-model") -> None:
        self._content = content
        self._error = error
        self._model = model
        self.calls: list[list[dict[str, str]]] = []

    @property
    def model(self) -> str:
        return self._model

    async def chat(self, messages, *, temperature: float = 0.2, max_completion_tokens: int = 2048) -> ChatResult:
        self.calls.append(messages)
        if self._error is not None:
            raise self._error
        return ChatResult(
            content=self._content,
            model=self._model,
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
        )


@pytest.fixture
def fake_client_factory():
    def _factory(
        content: str = "",
        *,
        error: Exception | None = None,
        model: str = "fake-model",
    ) -> FakeInferenceClient:
        return FakeInferenceClient(content, error=error, model=model)

    return _factory


def make_settings(**overrides) -> Settings:
    base = dict(
        inference_key=None,
        model="openai-gpt-oss-120b",
        base_url="https://inference.do-ai.run/v1",
        timeout_seconds=30.0,
        web_origins=["http://localhost:3000"],
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def api_client():
    """TestClient with the inference dependency overridden to an unconfigured state."""

    app.dependency_overrides[get_inference_client] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def api_client_factory():
    def _factory(client_obj) -> TestClient:
        app.dependency_overrides[get_inference_client] = lambda: client_obj
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
