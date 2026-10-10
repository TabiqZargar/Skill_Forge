import type {
  ApiErrorBody,
  EvaluateRequest,
  EvaluationReport,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
  Skill,
  ValidateRequest,
  ValidationReport,
} from "./types";

export class ApiError extends Error {
  code: string;
  details?: unknown;

  constructor(message: string, code = "error", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

async function readError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON; fall through to a generic message.
  }

  const structured = body as ApiErrorBody | undefined;
  if (structured?.error?.message) {
    return new ApiError(structured.error.message, structured.error.code, structured.error.details);
  }

  // FastAPI's HTTPException uses { detail: string }.
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") {
    return new ApiError(detail, `http_${response.status}`);
  }

  return new ApiError(`Request failed with status ${response.status}.`, `http_${response.status}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(
      "Could not reach the SkillForge API. Is the backend running?",
      "network_error",
    );
  }

  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", { cache: "no-store" });
}

export function getSampleSkill(): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/skills/sample", { cache: "no-store" });
}

export function validateSkill(payload: ValidateRequest): Promise<ValidationReport> {
  return request<ValidationReport>("/api/skills/validate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateSkill(payload: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/skills/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function evaluateSkill(payload: EvaluateRequest): Promise<EvaluationReport> {
  return request<EvaluationReport>("/api/skills/evaluate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function exportSkill(skill: Skill): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch("/api/skills/export", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ skill }),
    });
  } catch {
    throw new ApiError("Could not reach the SkillForge API. Is the backend running?", "network_error");
  }
  if (!response.ok) {
    throw await readError(response);
  }
  return response.blob();
}

export async function importSkillZip(file: File): Promise<Skill> {
  let response: Response;
  try {
    response = await fetch("/api/skills/import", {
      method: "POST",
      headers: { "content-type": "application/zip" },
      body: file,
    });
  } catch {
    throw new ApiError("Could not reach the SkillForge API. Is the backend running?", "network_error");
  }
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Skill;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
