// Types mirroring api/app/schemas.py.

export type CheckLevel = "error" | "warning" | "info" | "pass";
export type EvalMethod = "deterministic" | "model" | "hybrid";
export type EvalStatus = "passed" | "failed" | "uncertain" | "skipped";
export type EvalMode = "auto" | "deterministic" | "model";
export type EffectiveMode = "deterministic" | "model" | "hybrid";

export interface SkillFile {
  path: string;
  content: string;
}

export interface Skill {
  files: SkillFile[];
}

export interface Check {
  id: string;
  level: CheckLevel;
  message: string;
  path: string | null;
  spec: string | null;
  detail: string | null;
}

export interface ValidationReport {
  valid: boolean;
  errors: Check[];
  warnings: Check[];
  passed: Check[];
  info: Check[];
  checks_run: number;
  stats: Record<string, number | string>;
}

export interface ValidateRequest {
  skill: Skill;
  expected_root?: string | null;
}

export interface ModelUsage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface GenerateRequest {
  task: string;
  intended_use?: string;
  constraints?: string;
  name_hint?: string | null;
  include_references?: boolean;
  include_scripts?: boolean;
}

export interface GenerateResponse {
  skill: Skill;
  validation: ValidationReport;
  model: string;
  usage: ModelUsage | null;
  warnings: string[];
}

export interface Scenario {
  id: string;
  name: string;
  input: string;
  expected_behavior: string;
  constraints: string[];
}

export interface EvaluateRequest {
  skill: Skill;
  scenarios: Scenario[];
  mode: EvalMode;
}

export interface EvalCheck {
  id: string;
  label: string;
  status: EvalStatus;
  method: EvalMethod;
  weight: number;
  evidence: string[];
  notes: string | null;
}

export interface ScenarioResult {
  scenario_id: string;
  name: string;
  status: EvalStatus;
  score: number;
  method: EvalMethod;
  checks: EvalCheck[];
}

export interface EvaluationReport {
  mode: EvalMode;
  effective_mode: EffectiveMode;
  model: string | null;
  results: ScenarioResult[];
  summary: Record<string, number | string>;
  limitations: string[];
  usage: ModelUsage | null;
}

export interface HealthResponse {
  status: "ok";
  inference_configured: boolean;
  model: string;
  version: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
