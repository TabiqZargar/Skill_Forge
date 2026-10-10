"use client";

import { useMemo, useRef, useState } from "react";
import type { ModelUsage, Skill, ValidationReport } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { ValidationReportView } from "./report";
import { Alert, Badge, Button, Card, EmptyState, TextInput, Textarea } from "./ui";

export interface GenerationMeta {
  model: string;
  usage: ModelUsage | null;
  warnings: string[];
}

export function EditorView({
  skill,
  validation,
  meta,
  onUpdate,
  onAddFile,
  onRemoveFile,
  onValidate,
  onExport,
  onImport,
}: {
  skill: Skill | null;
  validation: ValidationReport | null;
  meta: GenerationMeta | null;
  onUpdate: (path: string, content: string) => void;
  onAddFile: (path: string) => void;
  onRemoveFile: (path: string) => void;
  onValidate: () => Promise<void>;
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [newPath, setNewPath] = useState("");
  const [busy, setBusy] = useState<null | "validate" | "export" | "import">(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const activePath = useMemo(() => {
    if (!skill) return null;
    if (selected && skill.files.some((f) => f.path === selected)) return selected;
    return skill.files[0]?.path ?? null;
  }, [skill, selected]);

  const activeFile = skill?.files.find((f) => f.path === activePath) ?? null;

  async function run(action: "validate" | "export", fn: () => Promise<void>) {
    setError(null);
    setBusy(action);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  async function handleImport(file: File) {
    setError(null);
    setBusy("import");
    try {
      await onImport(file);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed.");
    } finally {
      setBusy(null);
    }
  }

  function addFile() {
    const path = newPath.trim().replace(/^\.?\//, "");
    if (!path) return;
    onAddFile(path);
    setSelected(path);
    setNewPath("");
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {validation ? (
            <Badge tone={validation.valid ? "success" : "error"}>
              {validation.valid ? "Valid" : `${validation.errors.length} error(s)`}
            </Badge>
          ) : null}
          {validation && validation.warnings.length > 0 ? (
            <Badge tone="warning">{validation.warnings.length} warning(s)</Badge>
          ) : null}
          {meta ? <Badge tone="info">draft: {meta.model}</Badge> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImport(file);
              e.target.value = "";
            }}
          />
          <Button
            variant="secondary"
            onClick={() => fileInput.current?.click()}
            loading={busy === "import"}
          >
            Import ZIP
          </Button>
          {skill ? (
            <Button
              variant="secondary"
              onClick={() => run("validate", onValidate)}
              loading={busy === "validate"}
            >
              Re-validate
            </Button>
          ) : null}
          {skill ? (
            <Button onClick={() => run("export", onExport)} loading={busy === "export"}>
              Export ZIP
            </Button>
          ) : null}
        </div>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {meta && meta.warnings.length > 0 ? (
        <Alert tone="warning">
          <p className="font-medium">Generation notes</p>
          <ul className="mt-1 list-disc pl-5">
            {meta.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {meta ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <div className="text-xs uppercase text-slate-500 dark:text-slate-400">Model</div>
            <div className="font-medium text-slate-800 dark:text-slate-100">{meta.model}</div>
          </div>
          <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <div className="text-xs uppercase text-slate-500 dark:text-slate-400">Prompt tokens</div>
            <div className="font-medium text-slate-800 dark:text-slate-100">
              {meta.usage?.prompt_tokens ?? "—"}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <div className="text-xs uppercase text-slate-500 dark:text-slate-400">Completion tokens</div>
            <div className="font-medium text-slate-800 dark:text-slate-100">
              {meta.usage?.completion_tokens ?? "—"}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800">
            <div className="text-xs uppercase text-slate-500 dark:text-slate-400">Total tokens</div>
            <div className="font-medium text-slate-800 dark:text-slate-100">
              {meta.usage?.total_tokens ?? "—"}
            </div>
          </div>
        </div>
      ) : null}

      {!skill ? (
        <EmptyState
          title="No skill loaded"
          description="Generate a skill, load the sample, or import a ZIP to start editing."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <Card title="Files" className="h-fit">
            <ul className="space-y-1">
              {skill.files.map((file) => (
                <li key={file.path}>
                  <button
                    type="button"
                    onClick={() => setSelected(file.path)}
                    className={
                      "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left font-mono text-xs " +
                      (file.path === activePath
                        ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800")
                    }
                  >
                    <span className="truncate">{file.path}</span>
                    {file.path !== "SKILL.md" ? (
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveFile(file.path);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            onRemoveFile(file.path);
                          }
                        }}
                        className="text-slate-400 hover:text-rose-500"
                        aria-label={`Remove ${file.path}`}
                      >
                        ×
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-3 space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
              <TextInput
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addFile();
                  }
                }}
                placeholder="references/new.md"
                className="font-mono text-xs"
              />
              <Button variant="secondary" className="w-full" onClick={addFile} disabled={!newPath.trim()}>
                Add file
              </Button>
            </div>
          </Card>

          <Card
            title={activeFile ? activeFile.path : "Editor"}
            actions={
              activeFile ? (
                <span className="text-xs text-slate-400">
                  {activeFile.content.length.toLocaleString()} chars
                </span>
              ) : null
            }
          >
            {activeFile ? (
              <Textarea
                value={activeFile.content}
                onChange={(e) => onUpdate(activeFile.path, e.target.value)}
                spellCheck={false}
                className="min-h-[360px] w-full resize-y font-mono text-xs leading-relaxed"
              />
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">Select a file to edit.</p>
            )}
          </Card>
        </div>
      )}

      {validation ? (
        <div>
          <h2 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">
            Validation report
          </h2>
          <ValidationReportView report={validation} />
        </div>
      ) : null}
    </div>
  );
}
