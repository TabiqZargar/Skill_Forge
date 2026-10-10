from __future__ import annotations

import io
import zipfile

import pytest

from app.errors import ExportBlocked, PayloadTooLarge
from app.schemas import Skill, SkillFile
from app.services import frontmatter as fm
from app.services.exporter import build_zip, safe_extract_zip


def skill_md(name: str = "demo-skill") -> str:
    return fm.render_skill_md(
        {"name": name, "description": "A demo. Use when the user wants a demo."},
        "# Demo\n\nUse when the user asks.",
    )


def zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_build_zip_structure(sample_skill):
    data, root = build_zip(sample_skill)
    assert root == "release-notes-writer"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert "release-notes-writer/SKILL.md" in names
    assert "release-notes-writer/references/examples.md" in names
    assert "release-notes-writer/scripts/check_sections.py" in names


def test_build_zip_blocks_invalid_skill():
    invalid = Skill(files=[SkillFile(path="SKILL.md", content="# no frontmatter")])
    with pytest.raises(ExportBlocked):
        build_zip(invalid)


def test_build_zip_rejects_unsafe_path_when_not_requiring_valid():
    skill = Skill(
        files=[
            SkillFile(path="SKILL.md", content=skill_md()),
            SkillFile(path="../evil.sh", content="rm -rf /"),
        ]
    )
    with pytest.raises(ExportBlocked):
        build_zip(skill, require_valid=False)


def test_build_zip_enforces_file_limit(sample_skill):
    with pytest.raises(PayloadTooLarge):
        build_zip(sample_skill, max_files=1)


def test_extract_round_trip(sample_skill):
    data, _ = build_zip(sample_skill)
    extracted = safe_extract_zip(data)
    assert set(extracted.paths()) == set(sample_skill.paths())


def test_extract_rejects_zip_slip():
    data = zip_bytes({"skill/../../etc/evil": "x"})
    with pytest.raises(ExportBlocked):
        safe_extract_zip(data)


def test_extract_rejects_absolute_path():
    data = zip_bytes({"/etc/passwd": "x"})
    with pytest.raises(ExportBlocked):
        safe_extract_zip(data)


def test_extract_rejects_symlink():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("skill/link")
        info.external_attr = (0o120777 << 16)
        archive.writestr(info, "target")
    with pytest.raises(ExportBlocked):
        safe_extract_zip(buffer.getvalue())


def test_extract_rejects_duplicates():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("skill/SKILL.md", skill_md())
        archive.writestr("skill/SKILL.md", skill_md())
    with pytest.raises(ExportBlocked):
        safe_extract_zip(buffer.getvalue())


def test_extract_rejects_bad_zip():
    with pytest.raises(PayloadTooLarge):
        safe_extract_zip(b"not a zip")


def test_extract_enforces_file_limit():
    data = zip_bytes({"skill/a.txt": "a", "skill/b.txt": "b"})
    with pytest.raises(PayloadTooLarge):
        safe_extract_zip(data, max_files=1)
