"use client";

import { useState } from "react";
import type { EvalMode, EvaluationReport, Scenario, Skill } from "@/lib/types";
import { ApiError } from "@/lib/api";
import { EvaluationReportView } from "./report";
import { Alert, Button, Card, EmptyState, Label, TextInput, Textarea } from "./ui";

function newScenario(index: number): Scenario {
  return {
    id: `scenario-${Date.now()}-${index}`,
    name: "",
    input: "",
    expected_behavior: "",
    constraints: [],
  };
}

function constraintsToText(list: string[]): string {
  return list.join("\n");
}

export function EvaluateView({
  skill,
  report,
  onEvaluate,
  onOpenCreate,
}: {
  skill: Skill | null;
  report: EvaluationReport | null;
  onEvaluate: (scenarios: Scenario[], mode: EvalMode) => Promise<void>;
  onOpenCreate: () => void;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([newScenario(0)]);
  const [mode, setMode] = useState<EvalMode>("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patch(id: string, changes: Partial<Scenario>) {
    setScenarios((prev) => prev.map((s) => (s.id === id ? { ...s, ...changes } : s)));
  }

  function remove(id: string) {
    setScenarios((prev) => (prev.length > 1 ? prev.filter((s) => s.id !== id) : prev));
  }

  async function run() {
    setError(null);
    setBusy(true);
    try {
      await onEvaluate(scenarios, mode);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!skill) {
    return (
      <EmptyState
        title="No skill to evaluate"
        description="Generate, import, or load a skill before running evaluation scenarios."
        action={<Button onClick={onOpenCreate}>Create a skill</Button>}
      />
    );
  }

  const ready = scenarios.every((s) => s.name.trim() && s.input.trim() && s.expected_behavior.trim());

  return (
    <div className="space-y-6">
      <Card
        title="Scenarios"
        actions={
          <Button variant="secondary" onClick={() => setScenarios((prev) => [...prev, newScenario(prev.length)])}>
            Add scenario
          </Button>
        }
      >
        <div className="space-y-4">
          {scenarios.map((scenario, index) => (
            <div
              key={scenario.id}
              className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Scenario {index + 1}
                </span>
                <Button
                  variant="ghost"
                  onClick={() => remove(scenario.id)}
                  disabled={scenarios.length === 1}
                >
                  Remove
                </Button>
              </div>
              <div className="space-y-3">
                <TextInput
                  label="Name"
                  value={scenario.name}
                  onChange={(e) => patch(scenario.id, { name: e.target.value })}
                  placeholder="Missing release date"
                />
                <Textarea
                  label="Input"
                  rows={2}
                  value={scenario.input}
                  onChange={(e) => patch(scenario.id, { input: e.target.value })}
                  placeholder="The user provides a list of PRs without dates…"
                />
                <Textarea
                  label="Expected behavior"
                  rows={2}
                  value={scenario.expected_behavior}
                  onChange={(e) => patch(scenario.id, { expected_behavior: e.target.value })}
                  placeholder="The skill asks for the missing dates before producing notes."
                />
                <Textarea
                  label="Constraints (one per line, optional)"
                  rows={2}
                  value={constraintsToText(scenario.constraints)}
                  onChange={(e) =>
                    patch(scenario.id, {
                      constraints: e.target.value
                        .split("\n")
                        .map((line) => line.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap items-end justify-between gap-4 border-t border-slate-200 pt-4 dark:border-slate-800">
          <div>
            <Label htmlFor="mode">Evaluation mode</Label>
            <select
              id="mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as EvalMode)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="auto">Auto (deterministic first, model if available)</option>
              <option value="deterministic">Deterministic only</option>
              <option value="model">Model only</option>
            </select>
          </div>
          <Button onClick={run} loading={busy} disabled={!ready || busy}>
            Run evaluation
          </Button>
        </div>
      </Card>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {report ? (
        <div>
          <h2 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">
            Evaluation report
          </h2>
          <EvaluationReportView report={report} />
        </div>
      ) : null}
    </div>
  );
}
