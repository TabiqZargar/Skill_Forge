# SkillForge

**Build, validate, and evaluate Agent Skills — powered by DigitalOcean Inference.**

SkillForge turns a plain-language task into a portable [Agent Skills](https://agentskills.io/specification)
package: a `SKILL.md` file with standards-compliant YAML frontmatter, a step-by-step Markdown
body, and optional `scripts/` and `references/` support files. It then checks the result and
lets you export a clean ZIP that any Agent Skills runtime can load.

> Built for the Hacktoberfest Hack Day Srinagar × BUILDFEST-KASHMIR "Best Open-Source AI Project"
> challenge. Open source under Apache-2.0.

---

## Features

- **AI generation** — describe a task and DigitalOcean Inference drafts the skill.
- **Deterministic validation** — naming rules, required frontmatter, character limits,
  progressive-disclosure budget, safe file references, and more. No AI needed.
- **Scenario-based evaluation** — define expected behavior; get a transparent, weighted
  report that uses deterministic checks first and model judgment where it helps.
- **Round-trip export/import** — download or upload a ZIP with the correct
  `<name>/SKILL.md` directory structure.
- **Safe by design** — skills are never executed; uploaded archives are size-limited and
  path-traversal protected; credentials stay server-side.

## Architecture

```
Skill_Forge/
├── api/                 FastAPI backend (Python 3.11+)
│   ├── app/
│   │   ├── config.py    env-driven settings (secrets never sent to clients)
│   │   ├── schemas.py   typed request/response models
│   │   ├── deps.py      settings + inference client injection
│   │   ├── services/    frontmatter, validator, inference, generator,
│   │   │                evaluator, exporter, samples
│   │   └── routers/     /api/skills/* routes
│   └── tests/           pytest suite (deterministic + mocked inference)
├── web/                 Next.js 16 (App Router, TypeScript, Tailwind v4)
│   └── src/
│       ├── app/         layout, page, global styles
│       ├── components/  SPA views + UI primitives
│       └── lib/         API client, types, frontmatter helper
└── .do/app.yaml         DigitalOcean App Platform spec
```

The web app is a client-side single-page app at `/`. The Next.js server proxies `/api/*`
to the FastAPI backend (`API_ORIGIN`), so the browser never sees backend credentials.

## DigitalOcean integration

SkillForge uses two DigitalOcean products for real work:

1. **DigitalOcean Inference** — the backend calls the OpenAI-compatible
   `POST {base}/chat/completions` endpoint at `https://inference.do-ai.run/v1` with a
   server-side API key. The default model is `openai-gpt-oss-120b`, an open-weight
   Apache-2.0 model hosted by DigitalOcean. The key is read from
   `DIGITALOCEAN_INFERENCE_KEY` and is **never** exposed to the browser.
2. **DigitalOcean App Platform** — `.do/app.yaml` deploys the `api` and `web` services,
   wires the frontend's `API_ORIGIN` to the backend's private URL, runs a health check on
   `/api/health`, and injects the inference key as an encrypted secret.

If no key is configured, generation returns an actionable `503` and the UI explains how to
enable it; every other feature (sample, edit, validate, deterministic evaluate, export) still works.

## Getting started (local)

### 1. Backend

```bash
cd api
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then set DIGITALOCEAN_INFERENCE_KEY (optional for non-AI features)
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are served at <http://localhost:8000/docs>.

### 2. Frontend

```bash
cd web
npm install
cp .env.example .env.local   # API_ORIGIN defaults to http://localhost:8000
npm run dev
```

Open <http://localhost:3000>.

## Configuration

| Variable                          | Where | Default                          | Purpose                                             |
| --------------------------------- | ----- | -------------------------------- | --------------------------------------------------- |
| `DIGITALOCEAN_INFERENCE_KEY`      | api   | _(none)_                         | Inference API key. Required for AI generation/eval. |
| `DIGITALOCEAN_MODEL`              | api   | `openai-gpt-oss-120b`            | Model ID.                                           |
| `DIGITALOCEAN_INFERENCE_BASE_URL` | api   | `https://inference.do-ai.run/v1` | Inference base URL.                                 |
| `DIGITALOCEAN_INFERENCE_TIMEOUT`  | api   | `60`                             | Request timeout (seconds).                          |
| `WEB_ORIGIN`                      | api   | `http://localhost:3000,...`      | Comma-separated CORS origins.                       |
| `SKILLFORGE_MAX_FILES`            | api   | `40`                             | Max files per skill.                                |
| `SKILLFORGE_MAX_FILE_BYTES`       | api   | `131072`                         | Max bytes per file.                                 |
| `SKILLFORGE_MAX_TOTAL_BYTES`      | api   | `524288`                         | Max total skill bytes / upload size.                |
| `API_ORIGIN`                      | web   | `http://localhost:8000`          | Backend origin for the `/api/*` proxy.              |

## API

Base path: `/api`.

| Method | Path                   | Description                                                      |
| ------ | ---------------------- | ---------------------------------------------------------------- |
| `GET`  | `/api/health`          | Service status, whether inference is configured, model, version. |
| `GET`  | `/api/skills/sample`   | Bundled sample skill (no credentials needed).                    |
| `POST` | `/api/skills/validate` | Deterministic validation report for a skill.                     |
| `POST` | `/api/skills/generate` | Generate a skill via DigitalOcean Inference.                     |
| `POST` | `/api/skills/evaluate` | Evaluate a skill against scenarios.                              |
| `POST` | `/api/skills/export`   | Download a skill as a ZIP.                                       |
| `POST` | `/api/skills/import`   | Safely import a skill from a ZIP body.                           |

## The Agent Skills standard

A skill is a folder whose name matches the `name` field and contains a `SKILL.md`:

```markdown
---
name: release-notes-writer
description: Draft release notes from merged PRs. Use when the user asks for a changelog.
license: Apache-2.0
metadata:
  audience: maintainers
---

# Release Notes Writer

1. Gather the merged pull requests.
2. Group them by Conventional Commit type.
   ...
```

Supported frontmatter fields: `name` (required), `description` (required), `license`,
`compatibility`, `metadata`, and the experimental `allowed-tools`. Optional directories:
`scripts/`, `references/`, `assets/`.

## Testing

```bash
cd api
pytest -q          # 86 tests, no network required (inference is mocked)
ruff check app tests
```

```bash
cd web
npm run lint
npx tsc --noEmit
npm run build
```

## Deployment (DigitalOcean App Platform)

1. Push this repository to GitHub.
2. Edit `.do/app.yaml`: set `github.repo`/`branch` for both services.
3. Set `DIGITALOCEAN_INFERENCE_KEY` (use an App Platform encrypted/secret value).
4. Deploy: `doctl apps create --spec .do/app.yaml` (or paste the spec in the App Platform UI).

App Platform builds the Python service (FastAPI/uvicorn) and the Node service
(`npm ci && npm run build` → `npm start`), then routes `/` to the frontend and `/api/*`
through the frontend's proxy to the backend.

## Security notes

- Credentials are read from the environment and are never returned by the API or embedded
  in the client bundle.
- Generated and uploaded content is treated as untrusted text; skills are never executed.
- ZIP import enforces file-count and total-size limits and rejects absolute paths,
  `..` traversal, symlinks, and duplicate entries.

## License

[Apache-2.0](LICENSE).
