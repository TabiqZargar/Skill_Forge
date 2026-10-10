"""ZIP export (and a zip-slip-safe extraction helper).

Exports produce ``<skill-name>/SKILL.md`` plus any supporting files. Paths are
validated before writing and reads are rejected if they escape the archive root.
"""

from __future__ import annotations

import io
import posixpath
import zipfile

from ..errors import ExportBlocked, PayloadTooLarge
from ..schemas import Skill, SkillFile
from . import frontmatter as fm
from .validator import NAME_RE, _is_safe_path, validate_skill


def _skill_root(skill: Skill) -> str:
    data, _, _ = fm.parse_frontmatter(skill.file_map().get("SKILL.md", ""))
    name = data.get("name") if isinstance(data, dict) else None
    if isinstance(name, str) and NAME_RE.match(name):
        return name
    return "skill"


def build_zip(
    skill: Skill,
    *,
    require_valid: bool = True,
    max_files: int = 40,
    max_total_bytes: int = 512 * 1024,
) -> tuple[bytes, str]:
    """Return (zip_bytes, root_directory_name). Raises on invalid/unsafe input."""

    report = validate_skill(skill)
    if require_valid and report.errors:
        raise ExportBlocked(
            "Skill does not satisfy the Agent Skills standard and cannot be exported.",
            details={"validation": report.model_dump()},
        )

    root = _skill_root(skill)
    file_map = skill.file_map()
    if "SKILL.md" not in file_map:
        raise ExportBlocked("Skill is missing SKILL.md.")

    if len(file_map) > max_files:
        raise PayloadTooLarge(f"Skill has {len(file_map)} files; the limit is {max_files}.")
    total = sum(len(c.encode("utf-8")) for c in file_map.values())
    if total > max_total_bytes:
        raise PayloadTooLarge(f"Skill is {total} bytes; the limit is {max_total_bytes}.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(file_map):
            safe, reason = _is_safe_path(path)
            if not safe:
                raise ExportBlocked(f"Refusing to export unsafe path '{path}': {reason}.")
            arcname = posixpath.join(root, path)
            archive.writestr(arcname, file_map[path])
    return buffer.getvalue(), root


def safe_extract_zip(
    data: bytes,
    *,
    max_files: int = 40,
    max_total_bytes: int = 512 * 1024,
    max_compression_ratio: int = 200,
) -> Skill:
    """Extract a skill from zip bytes while defending against zip-slip and zip bombs."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PayloadTooLarge("Uploaded file was not a valid ZIP archive.") from exc

    infos = [i for i in archive.infolist() if not i.is_dir()]
    if len(infos) > max_files:
        raise PayloadTooLarge(f"Archive contains {len(infos)} files; the limit is {max_files}.")

    total_uncompressed = sum(i.file_size for i in infos)
    if total_uncompressed > max_total_bytes:
        raise PayloadTooLarge(f"Archive is {total_uncompressed} bytes uncompressed; the limit is {max_total_bytes}.")
    total_compressed = sum(max(i.compress_size, 1) for i in infos)
    if total_compressed and (total_uncompressed / total_compressed) > max_compression_ratio:
        raise PayloadTooLarge("Archive compression ratio is suspiciously high; refusing to extract.")

    names = [i.filename.replace("\\", "/") for i in infos]
    root = _common_root(names)

    files: list[SkillFile] = []
    seen: set[str] = set()
    for info in infos:
        raw_name = info.filename.replace("\\", "/")
        if raw_name.startswith("/"):
            raise ExportBlocked(f"Refusing absolute path in archive: '{raw_name}'.")
        relative = raw_name[len(root) :].lstrip("/") if root and raw_name.startswith(root) else raw_name
        relative = relative.lstrip("/")
        if not relative:
            continue

        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise ExportBlocked(f"Refusing symlink entry '{relative}'.")

        safe, reason = _is_safe_path(relative)
        if not safe:
            raise ExportBlocked(f"Refusing unsafe archive path '{relative}': {reason}.")
        if relative in seen:
            raise ExportBlocked(f"Duplicate path in archive: '{relative}'.")
        seen.add(relative)

        try:
            content = archive.read(info).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExportBlocked(f"File '{relative}' is not valid UTF-8 text.") from exc
        files.append(SkillFile(path=relative, content=content))

    return Skill(files=files)


def _common_root(names: list[str]) -> str:
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(roots) == 1 and all("/" in name for name in names):
        return roots.pop()
    return ""
