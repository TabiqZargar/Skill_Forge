"""Skill evaluation.

Two clearly separated layers:

* Deterministic structural checks (keyword/coverage/file-reference heuristics)
  that are genuinely executed and reproducible.
* Optional model-based judgment via DigitalOcean Inference, labelled as such and
  reported with confidence and evidence.

Skills are never *executed* and their instructions are never treated as trusted
code. Every result states its method so nothing is presented as a passed test
unless a check actually ran.
"""

from __future__ import annotations

import re

from ..errors import InferenceUnavailable
from ..schemas import (
    EvalCheck,
    EvaluateRequest,
    EvaluationReport,
    ModelUsage,
    Scenario,
    ScenarioResult,
    Skill,
)
from . import frontmatter as fm
from .generator import extract_json_object
from .inference import InferenceClient
from .validator import MARKDOWN_LINK_RE, RESOURCE_REF_RE

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "than", "them",
    "they", "will", "should", "must", "your", "youa", "you", "are", "not", "but", "can", "all",
    "any", "use", "using", "used", "does", "how", "what", "which", "where", "who", "why", "its",
    "our", "their", "there", "these", "those", "over", "under", "each", "also", "such", "only",
    "more", "most", "some", "very", "make", "made", "have", "has", "had", "been", "being", "was",
    "were", "get", "got", "onto", "about", "above", "below", "after", "before",
}

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]{2,}")

MODEL_JUDGE_SYSTEM = """You are a careful evaluator of Agent Skills.
Given a skill and a test scenario, judge whether the skill's instructions would
plausibly satisfy the scenario. Judge only from the provided skill text. Do not
assume capabilities the skill does not describe.
Respond with a SINGLE JSON object and nothing else:
{"satisfied": true|false, "confidence": 0.0-1.0, "rationale": "<short reason>", "evidence": ["<quote>", ...]}"""


def keywords(text: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(text or "") if w.lower() not in STOPWORDS}


def _skill_text(skill: Skill) -> tuple[str, str, dict[str, str]]:
    file_map = skill.file_map()
    data, body, _ = fm.parse_frontmatter(file_map.get("SKILL.md", ""))
    description = ""
    if isinstance(data, dict) and isinstance(data.get("description"), str):
        description = data["description"]
    return description, body, file_map


def _ratio(found: set[str], wanted: set[str]) -> float:
    if not wanted:
        return 0.0
    return len(found & wanted) / len(wanted)


def deterministic_checks(scenario: Scenario, skill: Skill) -> list[EvalCheck]:
    description, body, file_map = _skill_text(skill)
    combined_body = body.lower()
    desc_lower = description.lower()

    scenario_kw = keywords(scenario.input) | keywords(scenario.expected_behavior)
    checks: list[EvalCheck] = []

    # 1. Description coverage
    desc_hits = {k for k in scenario_kw if k in desc_lower}
    desc_ratio = _ratio(desc_hits, scenario_kw)
    checks.append(
        EvalCheck(
            id="description-covers-scenario",
            label="Description mentions the scenario's key terms",
            status="passed" if desc_hits else "failed",
            method="deterministic",
            evidence=sorted(desc_hits)[:8],
            notes=f"Matched {len(desc_hits)}/{len(scenario_kw)} key terms (ratio {desc_ratio:.2f}).",
        )
    )

    # 2. Instructions coverage
    body_hits = {k for k in scenario_kw if k in combined_body}
    checks.append(
        EvalCheck(
            id="instructions-cover-scenario",
            label="Instructions mention the scenario's key terms",
            status="passed" if len(body_hits) >= max(1, len(scenario_kw) // 3) else "failed",
            method="deterministic",
            evidence=sorted(body_hits)[:10],
            notes=f"Matched {len(body_hits)}/{len(scenario_kw)} key terms in the body.",
        )
    )

    # 3. Constraints referenced
    for index, constraint in enumerate(scenario.constraints):
        ckw = keywords(constraint)
        hits = {k for k in ckw if k in combined_body}
        checks.append(
            EvalCheck(
                id=f"constraint-{index + 1}",
                label=f"Constraint addressed: {constraint[:70]}",
                status="passed" if hits else "failed",
                method="deterministic",
                evidence=sorted(hits)[:6],
                notes=f"Matched {len(hits)}/{len(ckw)} constraint terms.",
            )
        )

    # 4. File references resolve
    refs: set[str] = set()
    for match in MARKDOWN_LINK_RE.finditer(body):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        refs.add(target.split("#", 1)[0].lstrip("./"))
    for match in RESOURCE_REF_RE.finditer(body):
        refs.add(match.group(1).lstrip("./"))
    missing = sorted(r for r in refs if r and r not in file_map)
    checks.append(
        EvalCheck(
            id="file-references-resolve",
            label="Referenced skill files exist",
            status="passed" if not missing else "failed",
            method="deterministic",
            evidence=missing,
            notes="All internal references resolve." if not missing else f"Missing: {', '.join(missing)}",
        )
    )

    # 5. Scope/trigger stated
    scope_ok = any(k in desc_lower for k in ("use when", "when the user", "when you", "trigger"))
    checks.append(
        EvalCheck(
            id="scope-stated",
            label="Description states when to use the skill",
            status="passed" if scope_ok else "failed",
            method="deterministic",
            evidence=[],
            notes=(
                "Description contains trigger language."
                if scope_ok
                else "No trigger language (e.g. 'Use when ...')."
            ),
        )
    )

    return checks


async def model_checks(scenario: Scenario, skill: Skill, client: InferenceClient) -> list[EvalCheck]:
    file_map = skill.file_map()
    skill_md = file_map.get("SKILL.md", "")
    constraint_text = "\n".join(f"- {c}" for c in scenario.constraints) or "(none)"
    user = (
        f"# Skill\n{skill_md[:12000]}\n\n"
        f"# Scenario\nName: {scenario.name}\nInput/trigger: {scenario.input}\n"
        f"Expected behavior: {scenario.expected_behavior}\nConstraints:\n{constraint_text}"
    )
    result = await client.chat(
        [
            {"role": "system", "content": MODEL_JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        max_completion_tokens=700,
    )
    payload = extract_json_object(result.content)
    satisfied = bool(payload.get("satisfied"))
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    rationale = payload.get("rationale")
    if not isinstance(rationale, str):
        rationale = ""
    evidence_raw = payload.get("evidence")
    evidence = [str(e) for e in evidence_raw][:6] if isinstance(evidence_raw, list) else []

    if confidence < 0.4:
        status = "uncertain"
    else:
        status = "passed" if satisfied else "failed"

    return [
        EvalCheck(
            id="model-judgment",
            label="Model judgment: skill would satisfy the scenario",
            status=status,
            method="model",
            evidence=evidence,
            notes=f"{rationale} (confidence {confidence:.2f})".strip(),
        )
    ]


def _scenario_status(checks: list[EvalCheck]) -> str:
    if any(c.status == "failed" for c in checks):
        return "failed"
    if any(c.status == "uncertain" for c in checks):
        return "uncertain"
    if all(c.status == "passed" for c in checks) and checks:
        return "passed"
    return "uncertain"


def _score(checks: list[EvalCheck]) -> float:
    total = sum(c.weight for c in checks)
    if total <= 0:
        return 0.0
    earned = sum(c.weight for c in checks if c.status == "passed")
    return round(earned / total, 4)


def _usage_from(result_usage: dict[str, int] | None) -> ModelUsage | None:
    if not result_usage:
        return None
    return ModelUsage(
        prompt_tokens=result_usage.get("prompt_tokens"),
        completion_tokens=result_usage.get("completion_tokens"),
        total_tokens=result_usage.get("total_tokens"),
    )


async def evaluate_skill(request: EvaluateRequest, client: InferenceClient | None) -> EvaluationReport:
    mode = request.mode
    limitations: list[str] = []
    use_model = mode in ("auto", "model")

    if mode == "model" and client is None:
        raise InferenceUnavailable(
            "Evaluation mode 'model' requires DIGITALOCEAN_INFERENCE_KEY to be configured."
        )
    if mode == "auto" and client is None:
        use_model = False
        limitations.append(
            "DIGITALOCEAN_INFERENCE_KEY is not configured, so only deterministic structural checks ran. "
            "Model-based judgment was skipped rather than faked."
        )

    results: list[ScenarioResult] = []
    model_used = False
    model_name: str | None = None

    for scenario in request.scenarios:
        checks = deterministic_checks(scenario, request.skill)
        method: str = "deterministic"
        if use_model and client is not None:
            checks = checks + await model_checks(scenario, request.skill, client)
            model_used = True
            model_name = client.model
            method = "hybrid"

        status = _scenario_status(checks)
        results.append(
            ScenarioResult(
                scenario_id=scenario.id,
                name=scenario.name,
                status=status,  # type: ignore[arg-type]
                score=_score(checks),
                method=method,  # type: ignore[arg-type]
                checks=checks,
            )
        )

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    uncertain = sum(1 for r in results if r.status == "uncertain")
    avg_score = round(sum(r.score for r in results) / len(results), 4) if results else 0.0

    limitations.append(
        "Deterministic checks are keyword/structure heuristics over the skill text; they verify that the skill "
        "addresses a scenario's terms and constraints, not runtime correctness."
    )
    limitations.append(
        "Skills are never executed and their instructions are treated as untrusted text, so no check "
        "proves behavior at runtime."
    )
    if model_used:
        limitations.append(
            "Model-based judgments are non-deterministic, may be wrong, and are reported with confidence and evidence."
        )

    effective_mode = "hybrid" if model_used else "deterministic"
    if mode == "model" and model_used:
        effective_mode = "model"

    return EvaluationReport(
        mode=mode,
        effective_mode=effective_mode,  # type: ignore[arg-type]
        model=model_name,
        results=results,
        summary={
            "scenarios": len(results),
            "passed": passed,
            "failed": failed,
            "uncertain": uncertain,
            "average_score": avg_score,
        },
        limitations=limitations,
    )
