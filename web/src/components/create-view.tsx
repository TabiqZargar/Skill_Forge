"use client";

import { useState } from "react";
import type { GenerateRequest } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { Alert, Button, Card, Switch, TextInput, Textarea } from "./ui";

export function CreateView({
  inferenceConfigured,
  onGenerate,
  onLoadSample,
}: {
  inferenceConfigured: boolean;
  onGenerate: (payload: GenerateRequest) => Promise<void>;
  onLoadSample: () => void;
}) {
  const [task, setTask] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [constraints, setConstraints] = useState("");
  const [nameHint, setNameHint] = useState("");
  const [includeReferences, setIncludeReferences] = useState(true);
  const [includeScripts, setIncludeScripts] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await onGenerate({
        task: task.trim(),
        intended_use: intendedUse.trim(),
        constraints: constraints.trim(),
        name_hint: nameHint.trim() || null,
        include_references: includeReferences,
        include_scripts: includeScripts,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Generation failed unexpectedly.");
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = task.trim().length >= 4 && inferenceConfigured && !busy;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <form onSubmit={submit} className="lg:col-span-2">
        <Card title="Describe the skill">
          <div className="space-y-4">
            {!inferenceConfigured ? (
              <Alert tone="warning">
                AI generation needs <code>DIGITALOCEAN_INFERENCE_KEY</code> on the backend. You can
                still{" "}
                <button type="button" onClick={onLoadSample} className="underline">
                  load the sample skill
                </button>{" "}
                to explore the editor.
              </Alert>
            ) : null}

            <Textarea
              id="task"
              label="Task"
              rows={3}
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="e.g. Draft release notes from a list of merged pull requests"
              hint="Required — what should this skill accomplish?"
            />
            <TextInput
              id="intended-use"
              label="Intended use (optional)"
              value={intendedUse}
              onChange={(e) => setIntendedUse(e.target.value)}
              placeholder="When should an agent reach for this skill?"
            />
            <Textarea
              id="constraints"
              label="Constraints (optional)"
              rows={2}
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="e.g. Keep output under 200 words, use Conventional Commits grouping"
            />
            <TextInput
              id="name-hint"
              label="Name hint (optional)"
              value={nameHint}
              onChange={(e) => setNameHint(e.target.value)}
              placeholder="release-notes-writer"
              hint="Lowercase letters, numbers, and hyphens. Must match the folder name."
            />
            <div className="flex flex-wrap gap-6 border-t border-slate-200 pt-4 dark:border-slate-800">
              <Switch
                checked={includeReferences}
                onChange={setIncludeReferences}
                label="Include references/"
              />
              <Switch checked={includeScripts} onChange={setIncludeScripts} label="Include scripts/" />
            </div>

            {error ? <Alert tone="error">{error}</Alert> : null}

            <div className="flex items-center gap-3">
              <Button type="submit" loading={busy} disabled={!canSubmit}>
                {busy ? "Generating…" : "Generate skill"}
              </Button>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Generation can take a few seconds.
              </span>
            </div>
          </div>
        </Card>
      </form>

      <Card title="What you'll get" className="h-fit">
        <ul className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
          <li>
            <span className="font-medium text-slate-800 dark:text-slate-100">SKILL.md</span> with
            validated frontmatter and step-by-step instructions.
          </li>
          <li>
            Optional <span className="font-medium text-slate-800 dark:text-slate-100">references/</span>{" "}
            documents for progressive disclosure.
          </li>
          <li>
            A deterministic validation report so you catch problems immediately.
          </li>
          <li>
            An editable draft you can refine, evaluate, and export as a ZIP.
          </li>
        </ul>
      </Card>
    </div>
  );
}
