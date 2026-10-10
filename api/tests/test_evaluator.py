from __future__ import annotations

import json

import pytest

from app.errors import InferenceUnavailable
from app.schemas import EvaluateRequest, Scenario
from app.services.evaluator import deterministic_checks, evaluate_skill

RELEASE_SCENARIO = Scenario(
    id="s1",
    name="Draft release notes",
    input="Draft release notes from a list of commits",
    expected_behavior="Produces categorized release notes with Added and Fixed sections",
    constraints=["never invent changes", "group by category"],
)

OFF_TOPIC_SCENARIO = Scenario(
    id="s2",
    name="Compile Rust",
    input="Compile a Rust program and fix borrow checker errors",
    expected_behavior="Explains ownership and resolves lifetime errors",
    constraints=["explain the borrow checker"],
)


def test_deterministic_checks_on_relevant_scenario(sample_skill):
    checks = deterministic_checks(RELEASE_SCENARIO, sample_skill)
    by_id = {c.id: c for c in checks}
    assert by_id["description-covers-scenario"].status == "passed"
    assert by_id["instructions-cover-scenario"].status == "passed"
    assert by_id["file-references-resolve"].status == "passed"
    assert by_id["scope-stated"].status == "passed"
    assert all(c.method == "deterministic" for c in checks)


def test_deterministic_checks_on_off_topic_scenario(sample_skill):
    checks = deterministic_checks(OFF_TOPIC_SCENARIO, sample_skill)
    assert any(c.status == "failed" for c in checks)


async def test_evaluate_auto_without_client_falls_back(sample_skill):
    report = await evaluate_skill(EvaluateRequest(skill=sample_skill, scenarios=[RELEASE_SCENARIO]), None)
    assert report.effective_mode == "deterministic"
    assert report.model is None
    assert any("not configured" in lim for lim in report.limitations)
    assert report.results[0].method == "deterministic"


async def test_evaluate_model_mode_requires_client(sample_skill):
    with pytest.raises(InferenceUnavailable):
        await evaluate_skill(
            EvaluateRequest(skill=sample_skill, scenarios=[RELEASE_SCENARIO], mode="model"), None
        )


async def test_evaluate_model_mode_with_fake(sample_skill, fake_client_factory):
    judge = json.dumps(
        {"satisfied": True, "confidence": 0.9, "rationale": "covers it", "evidence": ["Added", "Fixed"]}
    )
    client = fake_client_factory(judge)
    report = await evaluate_skill(
        EvaluateRequest(skill=sample_skill, scenarios=[RELEASE_SCENARIO], mode="model"), client
    )
    assert report.effective_mode == "model"
    assert report.model == "fake-model"
    model_check = next(c for c in report.results[0].checks if c.id == "model-judgment")
    assert model_check.status == "passed"
    assert model_check.method == "model"


async def test_evaluate_auto_with_fake_is_hybrid(sample_skill, fake_client_factory):
    judge = json.dumps({"satisfied": False, "confidence": 0.8, "rationale": "nope", "evidence": []})
    client = fake_client_factory(judge)
    report = await evaluate_skill(
        EvaluateRequest(skill=sample_skill, scenarios=[RELEASE_SCENARIO], mode="auto"), client
    )
    assert report.effective_mode == "hybrid"
    assert report.results[0].status == "failed"


async def test_evaluate_low_confidence_is_uncertain(sample_skill, fake_client_factory):
    judge = json.dumps({"satisfied": True, "confidence": 0.1, "rationale": "unsure", "evidence": []})
    client = fake_client_factory(judge)
    report = await evaluate_skill(
        EvaluateRequest(skill=sample_skill, scenarios=[RELEASE_SCENARIO], mode="model"), client
    )
    model_check = next(c for c in report.results[0].checks if c.id == "model-judgment")
    assert model_check.status == "uncertain"
