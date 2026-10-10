"use client";

import type { HealthResponse } from "@/lib/types";
import { Alert, Badge, Button, Card } from "./ui";

const features = [
  {
    title: "Generate with DigitalOcean Inference",
    body: "Describe a task and SkillForge drafts a spec-compliant SKILL.md with frontmatter, instructions, and supporting files.",
  },
  {
    title: "Validate against the standard",
    body: "Deterministic checks cover naming, frontmatter fields, progressive disclosure, and safe file references.",
  },
  {
    title: "Evaluate with scenarios",
    body: "Define expected behavior and get a transparent, weighted report — deterministic checks first, model judgment where useful.",
  },
  {
    title: "Export a portable package",
    body: "Download a ZIP with the correct <name>/SKILL.md directory structure, ready for any Agent Skills runtime.",
  },
];

export function HomeView({
  health,
  healthError,
  inferenceConfigured,
  hasSkill,
  onGenerate,
  onLoadSample,
  onOpenEditor,
  loadingSample,
}: {
  health: HealthResponse | null;
  healthError: string | null;
  inferenceConfigured: boolean;
  hasSkill: boolean;
  onGenerate: () => void;
  onLoadSample: () => void;
  onOpenEditor: () => void;
  loadingSample: boolean;
}) {
  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-indigo-50 to-white p-8 dark:border-slate-800 dark:from-slate-900 dark:to-slate-950">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="info">Open Source</Badge>
          <Badge tone="neutral">Agent Skills standard</Badge>
          {health ? <Badge tone="success">API v{health.version}</Badge> : null}
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50 sm:text-4xl">
          Build, validate, and evaluate Agent Skills
        </h1>
        <p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-300">
          SkillForge turns an idea into a portable Agent Skill folder — <code className="rounded bg-slate-200/70 px-1 py-0.5 text-sm dark:bg-slate-800">SKILL.md</code> with
          standard frontmatter plus optional scripts and references — then checks it before you ship.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button onClick={onGenerate} disabled={!inferenceConfigured}>
            Create a skill with AI
          </Button>
          <Button variant="secondary" onClick={onLoadSample} loading={loadingSample}>
            Load sample skill
          </Button>
          {hasSkill ? (
            <Button variant="ghost" onClick={onOpenEditor}>
              Open editor
            </Button>
          ) : null}
        </div>
      </div>

      {healthError ? (
        <Alert tone="error">
          <span className="font-medium">Backend unreachable.</span> {healthError} Start the FastAPI
          service (`uvicorn app.main:app --reload` in <code>api/</code>) and reload.
        </Alert>
      ) : null}

      {!inferenceConfigured && !healthError ? (
        <Alert tone="warning">
          <span className="font-medium">AI generation is disabled.</span> The backend has no{" "}
          <code>DIGITALOCEAN_INFERENCE_KEY</code> configured. You can still load the sample skill,
          edit, validate, evaluate deterministically, and export.
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {features.map((feature) => (
          <Card key={feature.title} title={feature.title}>
            <p className="text-sm text-slate-600 dark:text-slate-300">{feature.body}</p>
          </Card>
        ))}
      </div>

      <Card title="How it works">
        <ol className="grid gap-3 text-sm text-slate-600 dark:text-slate-300 sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950/50">
            <span className="font-semibold text-slate-800 dark:text-slate-100">1. Describe</span>
            <p className="mt-1">Tell SkillForge what the skill should do and when to use it.</p>
          </li>
          <li className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950/50">
            <span className="font-semibold text-slate-800 dark:text-slate-100">2. Generate</span>
            <p className="mt-1">DigitalOcean Inference drafts the skill; you keep full control.</p>
          </li>
          <li className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950/50">
            <span className="font-semibold text-slate-800 dark:text-slate-100">3. Validate</span>
            <p className="mt-1">Fix errors and warnings against the Agent Skills specification.</p>
          </li>
          <li className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950/50">
            <span className="font-semibold text-slate-800 dark:text-slate-100">4. Export</span>
            <p className="mt-1">Ship a clean, portable ZIP package.</p>
          </li>
        </ol>
      </Card>
    </div>
  );
}
