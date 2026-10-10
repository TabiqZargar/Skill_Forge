from __future__ import annotations

import json

import pytest

from app.errors import MalformedModelResponse
from app.schemas import GenerateRequest
from app.services.generator import _slugify, assemble_skill, extract_json_object, generate_skill

PAYLOAD = {
    "name": "My Cool Skill!",
    "description": "Summarizes articles. Use when the user wants a summary.",
    "license": "Apache-2.0",
    "metadata": {"author": "tester", "version": 1},
    "instructions": "# Steps\n\nUse when the user wants a summary.\n\n1. Read.\n2. Summarize.",
    "files": [
        {"path": "references/guide.md", "content": "# Guide"},
        {"path": "../evil.sh", "content": "rm -rf /"},
        {"path": "notallowed/x.md", "content": "nope"},
    ],
}


def test_extract_plain_json():
    assert extract_json_object(json.dumps(PAYLOAD))["name"] == "My Cool Skill!"


def test_extract_fenced_json():
    text = "Here you go:\n```json\n" + json.dumps(PAYLOAD) + "\n```\n"
    assert extract_json_object(text)["name"] == "My Cool Skill!"


def test_extract_embedded_json():
    text = "Sure! " + json.dumps(PAYLOAD) + " Hope that helps."
    assert extract_json_object(text)["description"]


def test_extract_empty_raises():
    with pytest.raises(MalformedModelResponse):
        extract_json_object("   ")


def test_extract_no_json_raises():
    with pytest.raises(MalformedModelResponse):
        extract_json_object("I cannot do that.")


def test_extract_non_object_raises():
    with pytest.raises(MalformedModelResponse):
        extract_json_object("[1, 2, 3]")


def test_slugify():
    assert _slugify("My Cool Skill!") == "my-cool-skill"
    assert _slugify("--Weird__Name--") == "weird-name"
    assert _slugify("!!!") == ""


def test_assemble_skill_slugs_name_and_filters_files():
    skill, warnings = assemble_skill(PAYLOAD)
    paths = set(skill.paths())
    assert "SKILL.md" in paths
    assert "references/guide.md" in paths
    assert all(not p.startswith("..") for p in paths)
    assert any("Ignored generated file" in w for w in warnings)


def test_assemble_skill_missing_description_raises():
    with pytest.raises(MalformedModelResponse):
        assemble_skill({"name": "x", "instructions": "body"})


def test_assemble_skill_missing_instructions_raises():
    with pytest.raises(MalformedModelResponse):
        assemble_skill({"name": "x", "description": "Does X. Use when needed."})


def test_assemble_metadata_coerces_values():
    skill, _ = assemble_skill(PAYLOAD)
    data = skill.file_map()["SKILL.md"]
    assert "version: '1'" in data


async def test_generate_skill_success(fake_client_factory):
    client = fake_client_factory(json.dumps(PAYLOAD))
    response = await generate_skill(GenerateRequest(task="Summarize articles", intended_use="news"), client)
    assert response.model == "fake-model"
    assert response.validation.valid is True
    assert response.usage is not None
    assert "SKILL.md" in response.skill.paths()


async def test_generate_skill_malformed(fake_client_factory):
    client = fake_client_factory("sorry, no json")
    with pytest.raises(MalformedModelResponse):
        await generate_skill(GenerateRequest(task="Summarize articles"), client)
