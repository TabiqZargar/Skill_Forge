"""Deterministic validation of skills against the Agent Skills Open Standard.

Spec: https://agentskills.io/specification

This module contains *no* AI calls. It is pure and independently testable so
that standard compliance can be reasoned about and trusted.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ..schemas import Check, Skill, ValidationReport
from . import frontmatter as fm

# 1-64 chars, lowercase alphanumerics and single hyphens, no leading/trailing hyphen.
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RESOURCE_REF_RE = re.compile(r"`?((?:scripts|references|assets)/[A-Za-z0-9._/-]+)`?")

MAX_BODY_LINES = 500
RECOMMENDED_TOKEN_BUDGET = 5000

UNKNOWN_KEY_LEVEL = "warning"


def _is_safe_path(path: str) -> tuple[bool, str | None]:
    if not path or not path.strip():
        return False, "empty path"
    if path.startswith("/") or path.startswith("\\"):
        return False, "absolute path is not allowed"
    if re.match(r"^[A-Za-z]:", path):
        return False, "drive-qualified path is not allowed"
    if "\\" in path:
        return False, "backslashes are not allowed; use forward slashes"
    parts = path.split("/")
    if any(part in ("..", ".") or part == "" for part in parts):
        return False, "path traversal segments are not allowed"
    return True, None


def validate_skill(skill: Skill, expected_root: str | None = None) -> ValidationReport:
    errors: list[Check] = []
    warnings: list[Check] = []
    passed: list[Check] = []
    info: list[Check] = []

    def err(cid: str, message: str, **kw: str | None) -> None:
        errors.append(Check(id=cid, level="error", message=message, **kw))

    def warn(cid: str, message: str, **kw: str | None) -> None:
        warnings.append(Check(id=cid, level="warning", message=message, **kw))

    def ok(cid: str, message: str, **kw: str | None) -> None:
        passed.append(Check(id=cid, level="pass", message=message, **kw))

    def note(cid: str, message: str, **kw: str | None) -> None:
        info.append(Check(id=cid, level="info", message=message, **kw))

    file_map = skill.file_map()
    paths = skill.paths()

    # --- Path safety and uniqueness ---------------------------------------
    bad_paths = False
    for path in paths:
        safe, reason = _is_safe_path(path)
        if not safe:
            bad_paths = True
            err("path-safety", f"Unsafe file path '{path}': {reason}.", path=path, spec="directory-structure")
    if not bad_paths:
        ok("path-safety", "All file paths are relative and traversal-safe.")

    duplicates = {p for p in paths if paths.count(p) > 1}
    if duplicates:
        err("path-unique", f"Duplicate file paths: {', '.join(sorted(duplicates))}.")
    else:
        ok("path-unique", "All file paths are unique.")

    # --- SKILL.md presence -------------------------------------------------
    if "SKILL.md" not in file_map:
        err("skill-md-present", "Missing required 'SKILL.md' at the skill root.", spec="directory-structure")
        return _finalize(errors, warnings, passed, info, file_map)

    ok("skill-md-present", "'SKILL.md' exists at the skill root.")

    skill_md = file_map["SKILL.md"]
    data, body, parse_errors = fm.parse_frontmatter(skill_md)

    if "missing_frontmatter" in parse_errors:
        err(
            "frontmatter-present",
            "'SKILL.md' must begin with YAML frontmatter delimited by '---'.",
            path="SKILL.md",
            spec="skill.md-format",
        )
    elif "unterminated_frontmatter" in parse_errors:
        err(
            "frontmatter-terminated",
            "Frontmatter was opened with '---' but never closed.",
            path="SKILL.md",
            spec="skill.md-format",
        )
    elif "frontmatter_not_mapping" in parse_errors:
        err("frontmatter-mapping", "Frontmatter must be a YAML mapping.", path="SKILL.md", spec="skill.md-format")
    elif parse_errors:
        err("frontmatter-yaml", f"Frontmatter is not valid YAML ({parse_errors[0]}).", path="SKILL.md")
    else:
        ok("frontmatter-present", "Frontmatter is present and parses as a YAML mapping.")

    if data is not None:
        _validate_frontmatter(data, expected_root, err, warn, ok, note)
        _validate_body(body, err, warn, ok, note)
        _validate_file_references(body, file_map, warn, ok)

    return _finalize(errors, warnings, passed, info, file_map, body)


def _validate_frontmatter(data, expected_root, err, warn, ok, note) -> None:
    # name
    name = data.get("name")
    if name is None:
        err("name-required", "Required field 'name' is missing.", spec="name-field")
    elif not isinstance(name, str):
        err("name-type", "'name' must be a string.", spec="name-field")
    else:
        ok("name-present", f"Name present: '{name}'.")
        if not (1 <= len(name) <= 64):
            err("name-length", f"'name' must be 1-64 characters (got {len(name)}).", spec="name-field")
        else:
            ok("name-length", "Name length is within 1-64 characters.")
        if not NAME_RE.match(name):
            detail = []
            if name != name.lower():
                detail.append("uppercase characters")
            if name.startswith("-") or name.endswith("-"):
                detail.append("leading/trailing hyphen")
            if "--" in name:
                detail.append("consecutive hyphens")
            if re.search(r"[^a-z0-9-]", name):
                detail.append("characters outside [a-z0-9-]")
            reason = ", ".join(detail) if detail else "invalid format"
            err(
                "name-format",
                f"'name' may only contain lowercase letters, numbers and single hyphens ({reason}).",
                spec="name-field",
            )
        else:
            ok("name-format", "Name uses lowercase alphanumerics and single hyphens only.")
        if expected_root is not None and name != expected_root:
            err(
                "name-matches-directory",
                f"'name' ('{name}') must match the parent directory name ('{expected_root}').",
                spec="name-field",
            )
        elif expected_root is not None:
            ok("name-matches-directory", "Name matches the parent directory name.")

    # description
    description = data.get("description")
    if description is None:
        err("description-required", "Required field 'description' is missing.", spec="description-field")
    elif not isinstance(description, str) or not description.strip():
        err("description-type", "'description' must be a non-empty string.", spec="description-field")
    else:
        ok("description-present", "Description is present.")
        if len(description) > 1024:
            err(
                "description-length",
                f"'description' must be at most 1024 characters (got {len(description)}).",
                spec="description-field",
            )
        else:
            ok("description-length", "Description length is within 1024 characters.")
        lowered = description.lower()
        trigger_markers = ("use when", "when the user", "when you", "uses when", "should be used", "trigger")
        if not any(k in lowered for k in trigger_markers):
            warn(
                "description-trigger",
                "Description does not state when the skill should be used; agents rely on this to trigger the skill.",
                spec="description-field",
            )
        else:
            ok("description-trigger", "Description indicates when to use the skill.")

    # license
    license_value = data.get("license")
    if license_value is not None:
        if not isinstance(license_value, str) or not license_value.strip():
            warn(
                "license-type",
                "'license' should be a short non-empty string or a bundled license file name.",
                spec="license-field",
            )
        else:
            ok("license-valid", "License is a valid short string.")

    # compatibility
    compatibility = data.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str) or not compatibility.strip():
            err(
                "compatibility-type",
                "'compatibility' must be a non-empty string when provided.",
                spec="compatibility-field",
            )
        elif len(compatibility) > 500:
            err(
                "compatibility-length",
                f"'compatibility' must be at most 500 characters (got {len(compatibility)}).",
                spec="compatibility-field",
            )
        else:
            ok("compatibility-valid", "Compatibility is within 500 characters.")

    # metadata
    metadata = data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            err("metadata-type", "'metadata' must be a mapping of string keys to string values.", spec="metadata-field")
        else:
            bad = [k for k, v in metadata.items() if not isinstance(k, str) or not isinstance(v, str)]
            if bad:
                err(
                    "metadata-values",
                    "'metadata' values must all be strings; non-string keys/values: " + ", ".join(map(str, bad)),
                    spec="metadata-field",
                )
            else:
                ok("metadata-valid", "Metadata is a mapping of string keys to string values.")

    # allowed-tools
    allowed_tools = data.get("allowed-tools")
    if allowed_tools is not None:
        if not isinstance(allowed_tools, str):
            err(
                "allowed-tools-type",
                "'allowed-tools' must be a single space-separated string.",
                spec="allowed-tools-field",
            )
        else:
            ok("allowed-tools-valid", "Allowed-tools is a string.")
            note(
                "allowed-tools-experimental",
                "'allowed-tools' is experimental and support varies between agent implementations.",
                spec="allowed-tools-field",
            )

    # unknown keys
    known = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    unknown = [k for k in data if k not in known]
    if unknown:
        warn(
            "frontmatter-unknown-keys",
            f"Unknown frontmatter keys (ignored by the standard): {', '.join(sorted(unknown))}.",
            spec="skill.md-format",
        )


def _validate_body(body, err, warn, ok, note) -> None:
    if not body or not body.strip():
        warn("body-empty", "Skill body is empty; add step-by-step instructions for the agent.", spec="body-content")
        return
    ok("body-present", "Skill body contains instructions.")
    line_count = body.count("\n") + 1
    if line_count > MAX_BODY_LINES:
        warn(
            "body-length",
            f"Body is {line_count} lines; keep SKILL.md under {MAX_BODY_LINES} lines and move detail to references/.",
            spec="progressive-disclosure",
        )
    else:
        ok("body-length", f"Body length ({line_count} lines) is within the recommended limit.")
    estimated_tokens = max(1, len(body) // 4)
    if estimated_tokens > RECOMMENDED_TOKEN_BUDGET:
        warn(
            "body-token-budget",
            f"Body is ~{estimated_tokens} tokens; the standard recommends < {RECOMMENDED_TOKEN_BUDGET} "
            "tokens for the main file.",
            spec="progressive-disclosure",
        )
    else:
        ok("body-token-budget", f"Body is ~{estimated_tokens} tokens, within the recommended budget.")


def _validate_file_references(body: str, file_map: dict[str, str], warn, ok) -> None:
    references: set[str] = set()
    for match in MARKDOWN_LINK_RE.finditer(body):
        target = match.group(1).strip()
        parsed = urlparse(target)
        if parsed.scheme in ("http", "https", "mailto"):
            continue
        target = target.split("#", 1)[0].strip()
        if target:
            references.add(target.lstrip("./"))
    for match in RESOURCE_REF_RE.finditer(body):
        references.add(match.group(1).lstrip("./"))

    if not references:
        ok("file-references", "No internal file references to verify.")
        return

    missing = sorted(r for r in references if r not in file_map)
    if missing:
        warn(
            "file-references-missing",
            "Referenced files not found in the skill: " + ", ".join(missing),
            spec="file-references",
        )
    else:
        ok("file-references", "All referenced internal files exist.")


def _finalize(errors, warnings, passed, info, file_map, body: str = "") -> ValidationReport:
    total_bytes = sum(len(content.encode("utf-8")) for content in file_map.values())
    stats: dict[str, int | float | str] = {
        "files": len(file_map),
        "total_bytes": total_bytes,
        "body_lines": (body.count("\n") + 1) if body else 0,
        "body_chars": len(body),
        "estimated_body_tokens": max(0, len(body) // 4),
    }
    return ValidationReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        passed=passed,
        info=info,
        checks_run=len(errors) + len(warnings) + len(passed) + len(info),
        stats=stats,
    )
