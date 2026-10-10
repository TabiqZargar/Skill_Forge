"""Parsing and rendering of ``SKILL.md`` YAML frontmatter + Markdown body.

Implements the format from the Agent Skills specification:
https://agentskills.io/specification
"""

from __future__ import annotations

from typing import Any

import yaml

FRONTMATTER_ORDER = ("name", "description", "license", "compatibility", "metadata", "allowed-tools")

State = str  # "none" | "ok" | "unterminated"


def split_frontmatter(text: str) -> tuple[str | None, str, State]:
    """Split raw file text into (frontmatter_yaml, body, state)."""

    if text.startswith("\ufeff"):
        text = text[1:]

    if not text.startswith("---"):
        return None, text, "none"

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text, "none"

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            return frontmatter, body, "ok"

    return None, text, "unterminated"


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Return (data, body, errors). ``data`` is None when frontmatter is absent/invalid."""

    frontmatter, body, state = split_frontmatter(text)
    if state == "none":
        return None, body, ["missing_frontmatter"]
    if state == "unterminated":
        return None, body, ["unterminated_frontmatter"]

    try:
        data = yaml.safe_load(frontmatter) if frontmatter is not None else None
    except yaml.YAMLError as exc:  # pragma: no cover - message varies by version
        return None, body, [f"invalid_yaml: {exc.__class__.__name__}"]

    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, body, ["frontmatter_not_mapping"]
    return data, body, []


def render_skill_md(data: dict[str, Any], body: str) -> str:
    """Render frontmatter + body back into a canonical ``SKILL.md`` string."""

    ordered: dict[str, Any] = {}
    for key in FRONTMATTER_ORDER:
        if key in data and data[key] is not None:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered and value is not None:
            ordered[key] = value

    frontmatter = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    clean_body = body.strip("\n")
    return f"---\n{frontmatter}\n---\n\n{clean_body}\n"
