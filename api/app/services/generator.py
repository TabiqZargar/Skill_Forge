"""AI skill generation via DigitalOcean Inference.

Builds a strict prompt that asks the model for a single JSON object describing a
skill, then assembles a spec-compliant skill directory. All model output is
treated as untrusted text and is parsed defensively.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..errors import MalformedModelResponse, PayloadTooLarge
from ..schemas import (
    GenerateRequest,
    GenerateResponse,
    ModelUsage,
    Skill,
    SkillFile,
)
from . import frontmatter as fm
from .inference import ChatResult, InferenceClient
from .validator import _is_safe_path, validate_skill

ALLOWED_EXTRA_PREFIXES = ("scripts/", "references/", "assets/")

SYSTEM_PROMPT = """You are SkillForge, an expert author of Agent Skills.

An Agent Skill is a directory containing a SKILL.md file with YAML frontmatter
and a Markdown body. The frontmatter fields are:
- name (required): 1-64 chars, lowercase letters, numbers and single hyphens only,
  no leading/trailing hyphen, no consecutive hyphens, and it MUST match the folder name.
- description (required): 1-1024 chars. State BOTH what the skill does AND when to use it.
- license (optional): short string.
- compatibility (optional): 1-500 chars describing environment requirements.
- metadata (optional): flat mapping of string keys to string values.
- allowed-tools (optional): space-separated string (experimental).

The Markdown body holds step-by-step instructions and should stay under 500 lines.
Optional supporting files live under scripts/, references/, or assets/.

Respond with a SINGLE JSON object and NOTHING else. No prose, no code fences.
Schema:
{
  "name": "<lowercase-hyphen-name>",
  "description": "<what it does and when to use it>",
  "license": "<optional, e.g. Apache-2.0>",
  "compatibility": "<optional>",
  "metadata": {"<key>": "<value>"},
  "instructions": "<the full Markdown body of SKILL.md>",
  "files": [{"path": "references/REFERENCE.md", "content": "..."}]
}
Only include "files" entries whose path starts with scripts/, references/, or assets/.
Do not include SKILL.md in "files"; it is generated from the fields above."""


def _build_user_prompt(request: GenerateRequest) -> str:
    lines = [f"Task: {request.task.strip()}"]
    if request.intended_use.strip():
        lines.append(f"Intended use: {request.intended_use.strip()}")
    if request.constraints.strip():
        lines.append(f"Constraints: {request.constraints.strip()}")
    if request.name_hint:
        hint = _slugify(request.name_hint)
        if hint:
            lines.append(f"Preferred skill name: {hint}")
    search_dirs = ["values"]
    if request.include_scripts:
        search_dirs.append("scripts/")
    if request.include_references:
        search_dirs.append("references/")
    lines.append("Supporting directories to consider: " + ", ".join(search_dirs))
    lines.append("Return only the JSON object described in the system prompt.")
    return "\n".join(lines)


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:64].strip("-")


def extract_json_object(text: str) -> dict[str, Any]:
    """Defensively extract a JSON object from raw model output."""

    if not text or not text.strip():
        raise MalformedModelResponse("Model returned an empty response.")

    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise MalformedModelResponse(
                "Model response did not contain a JSON object.",
                details={"excerpt": text[:400]},
            ) from None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MalformedModelResponse(
                "Model response was not valid JSON.",
                details={"excerpt": text[:400], "error": str(exc)},
            ) from exc

    if not isinstance(parsed, dict):
        raise MalformedModelResponse("Model response JSON was not an object.")
    return parsed


def assemble_skill(payload: dict[str, Any], *, fallback_name: str | None = None) -> tuple[Skill, list[str]]:
    """Turn a parsed model payload into a Skill plus non-fatal warnings."""

    warnings: list[str] = []

    raw_name = payload.get("name")
    name = _slugify(raw_name if isinstance(raw_name, str) else "")
    if not name:
        name = _slugify(fallback_name or "") or "generated-skill"

    description = payload.get("description")
    if not isinstance(description, str) or not description.strip():
        raise MalformedModelResponse("Model response was missing a usable 'description'.")

    instructions = payload.get("instructions") or payload.get("body")
    if not isinstance(instructions, str) or not instructions.strip():
        raise MalformedModelResponse("Model response was missing usable skill instructions.")

    frontmatter_data: dict[str, Any] = {
        "name": name,
        "description": description.strip(),
    }
    license_value = payload.get("license")
    if isinstance(license_value, str) and license_value.strip():
        frontmatter_data["license"] = license_value.strip()
    compatibility = payload.get("compatibility")
    if isinstance(compatibility, str) and compatibility.strip():
        frontmatter_data["compatibility"] = compatibility.strip()[:500]

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        clean_meta = {
            str(k): str(v)
            for k, v in metadata.items()
            if isinstance(k, (str, int, float)) and isinstance(v, (str, int, float, bool))
        }
        if clean_meta:
            frontmatter_data["metadata"] = clean_meta

    files: list[SkillFile] = [
        SkillFile(path="SKILL.md", content=fm.render_skill_md(frontmatter_data, instructions))
    ]

    raw_files = payload.get("files")
    if isinstance(raw_files, list):
        for entry in raw_files:
            if not isinstance(entry, dict):
                warnings.append("Ignored a non-object entry in generated 'files'.")
                continue
            path = str(entry.get("path", "")).strip().lstrip("./")
            content = entry.get("content", "")
            if not isinstance(content, str):
                warnings.append(f"Ignored generated file '{path}': content was not a string.")
                continue
            safe, reason = _is_safe_path(path)
            if not safe or not path.startswith(ALLOWED_EXTRA_PREFIXES):
                reason_text = reason or "must live under scripts/, references/, or assets/"
                warnings.append(f"Ignored generated file '{path}': {reason_text}.")
                continue
            files.append(SkillFile(path=path, content=content))

    return Skill(files=files), warnings


def _usage_from(result: ChatResult) -> ModelUsage | None:
    if not result.usage:
        return None
    return ModelUsage(
        prompt_tokens=result.usage.get("prompt_tokens"),
        completion_tokens=result.usage.get("completion_tokens"),
        total_tokens=result.usage.get("total_tokens"),
    )


def _enforce_limits(skill: Skill, *, max_files: int, max_total_bytes: int) -> None:
    if len(skill.files) > max_files:
        raise PayloadTooLarge(f"Generated skill has {len(skill.files)} files; the limit is {max_files}.")
    total = sum(len(f.content.encode("utf-8")) for f in skill.files)
    if total > max_total_bytes:
        raise PayloadTooLarge(f"Generated skill is {total} bytes; the limit is {max_total_bytes}.")


async def generate_skill(
    request: GenerateRequest,
    client: InferenceClient,
    *,
    max_files: int = 40,
    max_total_bytes: int = 512 * 1024,
    temperature: float = 0.3,
) -> GenerateResponse:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(request)},
    ]
    result = await client.chat(messages, temperature=temperature, max_completion_tokens=3072)
    payload = extract_json_object(result.content)
    skill, warnings = assemble_skill(payload, fallback_name=request.name_hint)
    _enforce_limits(skill, max_files=max_files, max_total_bytes=max_total_bytes)

    # Validate against the actual directory name (the skill name).
    data, _, _ = fm.parse_frontmatter(skill.file_map()["SKILL.md"])
    directory = data.get("name") if isinstance(data, dict) else None
    report = validate_skill(skill, expected_root=directory if isinstance(directory, str) else None)

    return GenerateResponse(
        skill=skill,
        validation=report,
        model=result.model,
        usage=_usage_from(result),
        warnings=warnings,
    )
