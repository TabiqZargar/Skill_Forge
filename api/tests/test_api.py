from __future__ import annotations

import io
import json
import zipfile

from app.services import frontmatter as fm


def skill_payload(name: str = "demo-skill") -> dict:
    body = "# Demo\n\nUse when the user asks.\n\n1. Read.\n2. Write."
    content = fm.render_skill_md({"name": name, "description": "A demo. Use when the user wants a demo."}, body)
    return {"files": [{"path": "SKILL.md", "content": content}]}


def test_health(api_client):
    response = api_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["inference_configured"] is False
    assert body["model"]


def test_sample_skill_is_valid(api_client):
    response = api_client.get("/api/skills/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["valid"] is True
    assert body["model"] == "sample"
    assert any(f["path"] == "SKILL.md" for f in body["skill"]["files"])


def test_validate_valid(api_client):
    response = api_client.post("/api/skills/validate", json={"skill": skill_payload(), "expected_root": "demo-skill"})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_invalid(api_client):
    payload = skill_payload(name="Bad Name")
    response = api_client.post("/api/skills/validate", json={"skill": payload})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any(c["id"] == "name-format" for c in body["errors"])


def test_generate_without_credentials_returns_503(api_client):
    response = api_client.post("/api/skills/generate", json={"task": "Summarize articles"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "inference_unavailable"


def test_generate_rejects_short_task(api_client):
    response = api_client.post("/api/skills/generate", json={"task": "hi"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


def test_generate_success(api_client_factory, fake_client_factory):
    model_payload = {
        "name": "article-summarizer",
        "description": "Summarizes articles. Use when the user wants a summary.",
        "instructions": "# Steps\n\nUse when the user wants a summary.\n\n1. Read.\n2. Summarize.",
    }
    fake = fake_client_factory(json.dumps(model_payload))
    client = api_client_factory(fake)
    response = client.post("/api/skills/generate", json={"task": "Summarize long articles"})
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "fake-model"
    assert body["validation"]["valid"] is True


def test_generate_malformed_model_response(api_client_factory, fake_client_factory):
    fake = fake_client_factory("no json here")
    client = api_client_factory(fake)
    response = client.post("/api/skills/generate", json={"task": "Summarize long articles"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "malformed_model_response"


def test_export_valid_skill(api_client, sample_skill):
    response = api_client.post("/api/skills/export", json={"skill": sample_skill.model_dump()})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "release-notes-writer.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "release-notes-writer/SKILL.md" in archive.namelist()


def test_export_invalid_skill_blocked(api_client):
    payload = {"files": [{"path": "SKILL.md", "content": "# no frontmatter"}]}
    response = api_client.post("/api/skills/export", json={"skill": payload})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "export_blocked"


def test_evaluate_deterministic(api_client, sample_skill):
    payload = {
        "skill": sample_skill.model_dump(),
        "scenarios": [
            {
                "id": "s1",
                "name": "Release notes",
                "input": "Draft release notes from commits",
                "expected_behavior": "Categorized notes with Added and Fixed",
                "constraints": ["never invent changes"],
            }
        ],
        "mode": "auto",
    }
    response = api_client.post("/api/skills/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["effective_mode"] == "deterministic"
    assert body["results"][0]["checks"]


def test_evaluate_model_mode_without_credentials_503(api_client, sample_skill):
    payload = {
        "skill": sample_skill.model_dump(),
        "scenarios": [
            {"id": "s1", "name": "x", "input": "a task", "expected_behavior": "does something", "constraints": []}
        ],
        "mode": "model",
    }
    response = api_client.post("/api/skills/evaluate", json=payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inference_unavailable"


def test_import_zip_round_trip(api_client, sample_skill):
    export = api_client.post("/api/skills/export", json={"skill": sample_skill.model_dump()})
    response = api_client.post(
        "/api/skills/import", content=export.content, headers={"content-type": "application/zip"}
    )
    assert response.status_code == 200
    assert set(f["path"] for f in response.json()["files"]) == set(sample_skill.paths())
