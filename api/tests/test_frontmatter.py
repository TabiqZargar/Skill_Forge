from __future__ import annotations

from app.services import frontmatter as fm


def test_split_frontmatter_ok():
    text = "---\nname: demo\ndescription: hi\n---\n\n# Body\n"
    fm_text, body, state = fm.split_frontmatter(text)
    assert state == "ok"
    assert "name: demo" in fm_text
    assert body.strip() == "# Body"


def test_split_frontmatter_none():
    _, body, state = fm.split_frontmatter("# Just markdown\n")
    assert state == "none"
    assert body.startswith("# Just")


def test_split_frontmatter_unterminated():
    _, _, state = fm.split_frontmatter("---\nname: demo\n")
    assert state == "unterminated"


def test_parse_frontmatter_missing():
    data, _, errors = fm.parse_frontmatter("# no frontmatter\n")
    assert data is None
    assert "missing_frontmatter" in errors


def test_parse_frontmatter_not_mapping():
    data, _, errors = fm.parse_frontmatter("---\n- a\n- b\n---\n")
    assert data is None
    assert errors


def test_parse_frontmatter_valid():
    data, body, errors = fm.parse_frontmatter("---\nname: demo\ndescription: x\n---\nBody\n")
    assert errors == []
    assert data == {"name": "demo", "description": "x"}
    assert body.strip() == "Body"


def test_render_round_trip():
    data = {"name": "demo", "description": "Does a thing.", "metadata": {"author": "me"}, "license": "Apache-2.0"}
    rendered = fm.render_skill_md(data, "# Body\n\nUse when the user asks.")
    parsed, body, errors = fm.parse_frontmatter(rendered)
    assert errors == []
    assert parsed["name"] == "demo"
    assert parsed["metadata"] == {"author": "me"}
    assert "Use when the user asks." in body


def test_render_orders_known_keys_first():
    rendered = fm.render_skill_md({"metadata": {"a": "b"}, "name": "x", "description": "d"}, "body")
    assert rendered.index("name:") < rendered.index("description:") < rendered.index("metadata:")
