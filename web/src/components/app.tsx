"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  EvalMode,
  EvaluationReport,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
  Scenario,
  Skill,
  ValidationReport,
} from "@/lib/types";
import {
  downloadBlob,
  evaluateSkill,
  exportSkill,
  generateSkill,
  getHealth,
  getSampleSkill,
  importSkillZip,
  validateSkill,
} from "@/lib/api";
import { readFrontmatterName } from "@/lib/frontmatter";
import { HomeView } from "./home-view";
import { CreateView } from "./create-view";
import { EditorView, type GenerationMeta } from "./editor-view";
import { EvaluateView } from "./evaluate-view";
import { Alert, Button, cx } from "./ui";

type View = "home" | "create" | "editor" | "evaluate";

const tabs: Array<{ id: View; label: string }> = [
  { id: "home", label: "Home" },
  { id: "create", label: "Create" },
  { id: "editor", label: "Editor" },
  { id: "evaluate", label: "Evaluate" },
];

export function App() {
  const [view, setView] = useState<View>("home");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [skill, setSkill] = useState<Skill | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [meta, setMeta] = useState<GenerationMeta | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);

  const inferenceConfigured = health?.inference_configured ?? false;

  useEffect(() => {
    let active = true;
    getHealth()
      .then((data) => {
        if (active) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err: Error) => {
        if (active) setHealthError(err.message);
      });
    return () => {
      active = false;
    };
  }, []);

  const applyGenerated = useCallback((data: GenerateResponse) => {
    setSkill(data.skill);
    setValidation(data.validation);
    setMeta({ model: data.model, usage: data.usage, warnings: data.warnings });
  }, []);

  const runValidation = useCallback(
    async (target: Skill) => {
      const report = await validateSkill({
        skill: target,
        expected_root: readFrontmatterName(target) ?? undefined,
      });
      setValidation(report);
      return report;
    },
    [],
  );

  const handleLoadSample = useCallback(async () => {
    setLoadingSample(true);
    try {
      const data = await getSampleSkill();
      applyGenerated(data);
      setEvaluation(null);
      setView("editor");
      setNotice("Sample skill loaded. Explore, validate, and export it.");
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Could not load the sample skill.");
    } finally {
      setLoadingSample(false);
    }
  }, [applyGenerated]);

  const handleGenerate = useCallback(
    async (payload: GenerateRequest) => {
      const data = await generateSkill(payload);
      applyGenerated(data);
      setEvaluation(null);
      setView("editor");
      setNotice(`Generated "${payload.name_hint || "skill"}" with ${data.model}.`);
    },
    [applyGenerated],
  );

  const handleValidate = useCallback(async () => {
    if (!skill) return;
    await runValidation(skill);
    setNotice("Re-validated against the Agent Skills standard.");
  }, [skill, runValidation]);

  const handleExport = useCallback(async () => {
    if (!skill) return;
    const blob = await exportSkill(skill);
    const name = readFrontmatterName(skill) || "skill";
    downloadBlob(blob, `${name}.zip`);
    setNotice(`Exported ${name}.zip`);
  }, [skill]);

  const handleImport = useCallback(
    async (file: File) => {
      const imported = await importSkillZip(file);
      setSkill(imported);
      setMeta(null);
      setEvaluation(null);
      setView("editor");
      await runValidation(imported);
      setNotice(`Imported ${imported.files.length} file(s) from ${file.name}.`);
    },
    [runValidation],
  );

  const handleUpdateFile = useCallback((path: string, content: string) => {
    setSkill((prev) =>
      prev ? { files: prev.files.map((f) => (f.path === path ? { ...f, content } : f)) } : prev,
    );
  }, []);

  const handleAddFile = useCallback((path: string) => {
    setSkill((prev) => {
      if (!prev || prev.files.some((f) => f.path === path)) return prev;
      return { files: [...prev.files, { path, content: "" }] };
    });
  }, []);

  const handleRemoveFile = useCallback((path: string) => {
    setSkill((prev) => (prev ? { files: prev.files.filter((f) => f.path !== path) } : prev));
  }, []);

  const handleEvaluate = useCallback(
    async (scenarios: Scenario[], mode: EvalMode) => {
      if (!skill) return;
      const report = await evaluateSkill({ skill, scenarios, mode });
      setEvaluation(report);
      setNotice("Evaluation complete.");
    },
    [skill],
  );

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-6 sm:px-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => setView("home")}
          className="flex items-center gap-2 text-left"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            SF
          </span>
          <span>
            <span className="block text-base font-bold leading-tight text-slate-900 dark:text-slate-50">
              SkillForge
            </span>
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Agent Skills builder
            </span>
          </span>
        </button>

        <nav className="flex items-center gap-1 rounded-lg border border-slate-200 p-1 dark:border-slate-800">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={cx(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                view === tab.id
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {notice ? (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex-1">
            <Alert tone="success">{notice}</Alert>
          </div>
          <Button variant="ghost" onClick={() => setNotice(null)} aria-label="Dismiss">
            ×
          </Button>
        </div>
      ) : null}

      <main className="flex-1">
        {view === "home" ? (
          <HomeView
            health={health}
            healthError={healthError}
            inferenceConfigured={inferenceConfigured}
            hasSkill={Boolean(skill)}
            onGenerate={() => setView("create")}
            onLoadSample={handleLoadSample}
            onOpenEditor={() => setView("editor")}
            loadingSample={loadingSample}
          />
        ) : null}

        {view === "create" ? (
          <CreateView
            inferenceConfigured={inferenceConfigured}
            onGenerate={handleGenerate}
            onLoadSample={handleLoadSample}
          />
        ) : null}

        {view === "editor" ? (
          <EditorView
            skill={skill}
            validation={validation}
            meta={meta}
            onUpdate={handleUpdateFile}
            onAddFile={handleAddFile}
            onRemoveFile={handleRemoveFile}
            onValidate={handleValidate}
            onExport={handleExport}
            onImport={handleImport}
          />
        ) : null}

        {view === "evaluate" ? (
          <EvaluateView
            skill={skill}
            report={evaluation}
            onEvaluate={handleEvaluate}
            onOpenCreate={() => setView("create")}
          />
        ) : null}
      </main>

      <footer className="mt-8 border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        SkillForge · open source (Apache-2.0) · powered by DigitalOcean Inference ·{" "}
        {health?.model ? `model: ${health.model}` : healthError ? "backend offline" : "connecting…"}
      </footer>
    </div>
  );
}
