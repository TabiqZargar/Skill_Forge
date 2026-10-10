"use client";

import type {
  Check,
  CheckLevel,
  EvalStatus,
  EvaluationReport,
  ScenarioResult,
  ValidationReport,
} from "@/lib/types";
import { Badge, Card, Stat, cx } from "./ui";

const levelTone: Record<CheckLevel, "error" | "warning" | "info" | "success"> = {
  error: "error",
  warning: "warning",
  info: "info",
  pass: "success",
};

function CheckList({ checks }: { checks: Check[] }) {
  if (checks.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">None.</p>;
  }
  return (
    <ul className="space-y-2">
      {checks.map((check, index) => (
        <li key={`${check.id}-${index}`} className="flex items-start gap-3">
          <Badge tone={levelTone[check.level]} className="mt-0.5 shrink-0">
            {check.level}
          </Badge>
          <div className="min-w-0">
            <p className="text-sm text-slate-800 dark:text-slate-100">{check.message}</p>
            <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-slate-400">
              <span className="font-mono">{check.id}</span>
              {check.path ? <span className="font-mono">{check.path}</span> : null}
              {check.spec ? <span className="font-mono">spec: {check.spec}</span> : null}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ValidationReportView({ report }: { report: ValidationReport }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Status" value={report.valid ? "Valid" : "Invalid"} />
        <Stat label="Errors" value={report.errors.length} />
        <Stat label="Warnings" value={report.warnings.length} />
        <Stat label="Checks run" value={report.checks_run} />
      </div>

      {report.errors.length > 0 ? (
        <Card title={`Errors (${report.errors.length})`}>
          <CheckList checks={report.errors} />
        </Card>
      ) : null}

      {report.warnings.length > 0 ? (
        <Card title={`Warnings (${report.warnings.length})`}>
          <CheckList checks={report.warnings} />
        </Card>
      ) : null}

      <Card title={`Passed (${report.passed.length})`}>
        <CheckList checks={report.passed} />
      </Card>

      {report.info.length > 0 ? (
        <Card title={`Info (${report.info.length})`}>
          <CheckList checks={report.info} />
        </Card>
      ) : null}
    </div>
  );
}

const evalStatusTone: Record<EvalStatus, "success" | "error" | "warning" | "neutral"> = {
  passed: "success",
  failed: "error",
  uncertain: "warning",
  skipped: "neutral",
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-40 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div
          className={cx(
            "h-full rounded-full",
            pct >= 75 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{pct}%</span>
    </div>
  );
}

function ScenarioCard({ result }: { result: ScenarioResult }) {
  return (
    <Card
      title={result.name}
      actions={
        <div className="flex items-center gap-2">
          <Badge tone={evalStatusTone[result.status]}>{result.status}</Badge>
          <Badge tone="neutral">{result.method}</Badge>
        </div>
      }
    >
      <div className="mb-4">
        <ScoreBar score={result.score} />
      </div>
      <ul className="space-y-3">
        {result.checks.map((check, index) => (
          <li key={`${check.id}-${index}`} className="border-t border-slate-100 pt-3 dark:border-slate-800">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{check.label}</span>
              <div className="flex items-center gap-2">
                <Badge tone={evalStatusTone[check.status]}>{check.status}</Badge>
                <Badge tone="neutral">{check.method}</Badge>
              </div>
            </div>
            {check.notes ? (
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{check.notes}</p>
            ) : null}
            {check.evidence.length > 0 ? (
              <ul className="mt-1 list-disc pl-5 text-xs text-slate-500 dark:text-slate-400">
                {check.evidence.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function EvaluationReportView({ report }: { report: EvaluationReport }) {
  const average =
    typeof report.summary.average_score === "number"
      ? Math.round((report.summary.average_score as number) * 100)
      : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Effective mode" value={report.effective_mode} />
        <Stat label="Average score" value={average === null ? "—" : `${average}%`} />
        <Stat label="Scenarios" value={report.results.length} />
        <Stat label="Model" value={report.model ?? "—"} />
      </div>

      {report.limitations.length > 0 ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
          <p className="font-medium">Limitations</p>
          <ul className="mt-1 list-disc pl-5">
            {report.limitations.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.results.map((result) => (
        <ScenarioCard key={result.scenario_id} result={result} />
      ))}
    </div>
  );
}
