"""A bundled sample skill so the product can be explored without any API key.

This skill is also used as a fixture in tests.
"""

from __future__ import annotations

from ..schemas import Skill, SkillFile
from . import frontmatter as fm

SAMPLE_SKILL_NAME = "release-notes-writer"

_BODY = """# Release Notes Writer

Turn a raw git commit log or changelog fragment into clear, user-facing release notes.

## When to use

Use this skill when the user asks to draft, summarize, or format release notes,
changelogs, or "what changed" summaries from commits, PR titles, or issue lists.

## Instructions

1. Ask for the target audience and the version number if they are not provided.
2. Classify each change into one of: **Added**, **Changed**, **Fixed**, **Removed**, **Security**.
3. Rewrite terse commit messages into benefit-focused, present-tense sentences.
4. Drop internal-only churn (formatting, dependency bumps with no user impact) unless asked to keep it.
5. Group entries by category, most impactful first, and keep each entry to one line.
6. Flag breaking changes explicitly and put them at the top under **Breaking Changes**.
7. Never invent changes that are not present in the input.

## Output format

```markdown
## [version] - YYYY-MM-DD

### Breaking Changes
- ...

### Added
- ...

### Fixed
- ...
```

## Edge cases

- If the input has no version, omit the heading version and ask for it.
- If a commit is ambiguous, keep its original wording and mark it `[needs review]`.
- If there are zero user-facing changes, say so plainly instead of padding the list.

See [references/examples.md](references/examples.md) for worked examples.
"""

_REFERENCES = """# Examples

## Input

```
fix: crash when token expires
feat: add dark mode
chore: bump eslint
```

## Output

```markdown
### Added
- Added a dark mode theme.

### Fixed
- Fixed a crash that occurred when the session token expired.
```
"""

_SCRIPT = '''"""Validate a release notes draft (no network, deterministic)."""

from __future__ import annotations

import sys

REQUIRED = ("Breaking Changes", "Added", "Fixed")


def main(text: str) -> int:
    missing = [section for section in REQUIRED if section not in text]
    if missing:
        print("Missing sections: " + ", ".join(missing))
        return 1
    print("Release notes draft looks structurally complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
'''


def get_sample_skill() -> Skill:
    data = {
        "name": SAMPLE_SKILL_NAME,
        "description": (
            "Turn commit logs and changelog fragments into clear, categorized user-facing release notes. "
            "Use when the user asks to draft, summarize, or format release notes or changelogs."
        ),
        "license": "Apache-2.0",
        "metadata": {"author": "SkillForge", "version": "1.0"},
        "compatibility": "No runtime requirements beyond a text environment.",
    }
    files = [
        SkillFile(path="SKILL.md", content=fm.render_skill_md(data, _BODY)),
        SkillFile(path="references/examples.md", content=_REFERENCES),
        SkillFile(path="scripts/check_sections.py", content=_SCRIPT),
    ]
    return Skill(files=files)
