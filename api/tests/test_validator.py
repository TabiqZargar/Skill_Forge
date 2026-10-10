from __future__ import annotations

from app.schemas import Skill, SkillFile
from app.services import frontmatter as fm
from app.services.validator import validate_skill


def skill_md(
    name: str = "demo-skill",
    description: str = "A demo. Use when the user wants a demo.",
    body: str = "# Demo\n\nUse when the user asks.",
) -> str:
    return fm.render_skill_md({"name": name, "description": description}, body)


def build(files: list[tuple[str, str]]) -> Skill:
    return Skill(files=[SkillFile(path=p, content=c) for p, c in files])


def error_ids(report) -> set[str]:
    return {c.id for c in report.errors}


def warning_ids(report) -> set[str]:
    return {c.id for c in report.warnings}


def test_valid_skill_passes(valid_skill):
    report = validate_skill(valid_skill, expected_root="demo-skill")
    assert report.valid is True
    assert report.errors == []
    assert report.checks_run > 0
    assert report.stats["files"] == 2


def test_missing_skill_md():
    report = validate_skill(build([("references/x.md", "hi")]))
    assert "skill-md-present" in error_ids(report)
    assert report.valid is False


def test_missing_frontmatter():
    report = validate_skill(build([("SKILL.md", "# no frontmatter\n")]))
    assert "frontmatter-present" in error_ids(report)


def test_unterminated_frontmatter():
    report = validate_skill(build([("SKILL.md", "---\nname: demo\n")]))
    assert "frontmatter-terminated" in error_ids(report)


def test_missing_name():
    report = validate_skill(build([("SKILL.md", "---\ndescription: hi\n---\nbody")]))
    assert "name-required" in error_ids(report)


def test_name_uppercase_rejected():
    report = validate_skill(build([("SKILL.md", skill_md(name="PDF-Processing"))]))
    assert "name-format" in error_ids(report)


def test_name_consecutive_hyphens_rejected():
    report = validate_skill(build([("SKILL.md", skill_md(name="pdf--processing"))]))
    assert "name-format" in error_ids(report)


def test_name_leading_hyphen_rejected():
    report = validate_skill(build([("SKILL.md", skill_md(name="-pdf"))]))
    assert "name-format" in error_ids(report)


def test_name_too_long_rejected():
    report = validate_skill(build([("SKILL.md", skill_md(name="a" * 65))]))
    assert "name-length" in error_ids(report)


def test_name_mismatch_directory():
    report = validate_skill(build([("SKILL.md", skill_md(name="demo-skill"))]), expected_root="other-name")
    assert "name-matches-directory" in error_ids(report)


def test_missing_description():
    report = validate_skill(build([("SKILL.md", "---\nname: demo-skill\n---\nbody")]))
    assert "description-required" in error_ids(report)


def test_description_too_long():
    long_desc = "word " * 300
    report = validate_skill(build([("SKILL.md", skill_md(description=long_desc))]))
    assert "description-length" in error_ids(report)


def test_compatibility_too_long():
    text = fm.render_skill_md(
        {"name": "demo-skill", "description": "A demo. Use when the user wants a demo.", "compatibility": "x" * 501},
        "body",
    )
    report = validate_skill(build([("SKILL.md", text)]))
    assert "compatibility-length" in error_ids(report)


def test_metadata_non_string_value():
    text = fm.render_skill_md(
        {"name": "demo-skill", "description": "A demo. Use when the user wants a demo.", "metadata": {"count": 3}},
        "body",
    )
    report = validate_skill(build([("SKILL.md", text)]))
    assert "metadata-values" in error_ids(report)


def test_allowed_tools_must_be_string():
    text = fm.render_skill_md(
        {"name": "demo-skill", "description": "A demo. Use when the user wants a demo.", "allowed-tools": ["Read"]},
        "body",
    )
    report = validate_skill(build([("SKILL.md", text)]))
    assert "allowed-tools-type" in error_ids(report)


def test_unknown_frontmatter_key_warns():
    text = fm.render_skill_md(
        {"name": "demo-skill", "description": "A demo. Use when the user wants a demo.", "foo": "bar"},
        "body",
    )
    report = validate_skill(build([("SKILL.md", text)]))
    assert "frontmatter-unknown-keys" in warning_ids(report)


def test_path_traversal_rejected():
    report = validate_skill(build([("SKILL.md", skill_md()), ("../evil.sh", "rm -rf /")]))
    assert "path-safety" in error_ids(report)


def test_absolute_path_rejected():
    report = validate_skill(build([("SKILL.md", skill_md()), ("/etc/passwd", "x")]))
    assert "path-safety" in error_ids(report)


def test_duplicate_paths_rejected():
    report = validate_skill(build([("SKILL.md", skill_md()), ("references/x.md", "a"), ("references/x.md", "b")]))
    assert "path-unique" in error_ids(report)


def test_missing_file_reference_warns():
    body = "# Demo\n\nUse when asked. See [missing](references/missing.md)."
    report = validate_skill(build([("SKILL.md", skill_md(body=body))]))
    assert "file-references-missing" in warning_ids(report)


def test_empty_body_warns():
    report = validate_skill(build([("SKILL.md", fm.render_skill_md({"name": "demo-skill", "description": "x"}, ""))]))
    assert "body-empty" in warning_ids(report)


def test_description_without_trigger_warns():
    report = validate_skill(build([("SKILL.md", skill_md(description="Processes PDFs."))]))
    assert "description-trigger" in warning_ids(report)


def test_sample_skill_is_valid(sample_skill):
    report = validate_skill(sample_skill, expected_root="release-notes-writer")
    assert report.valid is True
