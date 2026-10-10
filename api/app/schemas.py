"""Typed request/response schemas shared across routers and services."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Level = Literal["error", "warning", "info", "pass"]
Method = Literal["deterministic", "model", "hybrid"]
EvalStatus = Literal["passed", "failed", "uncertain", "skipped"]


class SkillFile(BaseModel):
    path: str = Field(..., min_length=1, max_length=512, description="Relative path inside the skill root.")
    content: str = Field(default="", max_length=400_000)


class Skill(BaseModel):
    """A skill is a set of relative-path files. ``SKILL.md`` lives at the root."""

    files: list[SkillFile] = Field(default_factory=list, max_length=200)

    def file_map(self) -> dict[str, str]:
        return {f.path: f.content for f in self.files}

    def paths(self) -> list[str]:
        return [f.path for f in self.files]


class Check(BaseModel):
    id: str
    level: Level
    message: str
    path: str | None = None
    spec: str | None = Field(default=None, description="Reference to the relevant part of the Agent Skills spec.")
    detail: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    errors: list[Check] = Field(default_factory=list)
    warnings: list[Check] = Field(default_factory=list)
    passed: list[Check] = Field(default_factory=list)
    info: list[Check] = Field(default_factory=list)
    checks_run: int = 0
    stats: dict[str, int | float | str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=4, max_length=4000, description="What the skill should accomplish.")
    intended_use: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)
    name_hint: str | None = Field(default=None, max_length=64)
    include_references: bool = True
    include_scripts: bool = False

    @field_validator("task")
    @classmethod
    def _task_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task must not be blank")
        return value.strip()


class ModelUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GenerateResponse(BaseModel):
    skill: Skill
    validation: ValidationReport
    model: str
    usage: ModelUsage | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidateRequest(BaseModel):
    skill: Skill
    expected_root: str | None = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class Scenario(BaseModel):
    id: str = Field(default="scenario", max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    input: str = Field(..., min_length=1, max_length=4000)
    expected_behavior: str = Field(..., min_length=1, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("constraints")
    @classmethod
    def _trim_constraints(cls, value: list[str]) -> list[str]:
        return [c.strip() for c in value if c and c.strip()]


class EvaluateRequest(BaseModel):
    skill: Skill
    scenarios: list[Scenario] = Field(..., min_length=1, max_length=20)
    mode: Literal["auto", "deterministic", "model"] = "auto"


class EvalCheck(BaseModel):
    id: str
    label: str
    status: EvalStatus
    method: Method
    weight: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    notes: str | None = None


class ScenarioResult(BaseModel):
    scenario_id: str
    name: str
    status: EvalStatus
    score: float = Field(ge=0.0, le=1.0)
    method: Method
    checks: list[EvalCheck] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    mode: Literal["auto", "deterministic", "model"]
    effective_mode: Literal["deterministic", "model", "hybrid"]
    model: str | None = None
    results: list[ScenarioResult] = Field(default_factory=list)
    summary: dict[str, float | int | str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    usage: ModelUsage | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | list | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"]
    inference_configured: bool
    model: str
    version: str
