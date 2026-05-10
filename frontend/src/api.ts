import type {
  AdvisorSuggestRequest,
  AdvisorSuggestResponse,
  CandidateResult,
  ConfigValidationResponse,
  ProblemDraft,
  ProblemPayload,
  StartJobResponse,
} from "./types";

export async function validateProblem(problem: ProblemDraft): Promise<ConfigValidationResponse> {
  const response = await fetch("/api/configs/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toProblemPayload(problem)),
  });

  if (!response.ok) {
    throw new Error("Configuration validation failed");
  }

  return response.json() as Promise<ConfigValidationResponse>;
}

export async function suggestCandidates(
  problem: ProblemDraft,
  observations: CandidateResult[],
): Promise<AdvisorSuggestResponse> {
  const request: AdvisorSuggestRequest = {
    problem: toProblemPayload(problem),
    observations: observations.map((observation) => ({
      candidateId: observation.candidateId,
      variables: observation.variables,
      objectives: observation.objectives,
      constraints: observation.constraints,
      feasible: observation.feasible,
      generation: observation.generation,
      metadata: observation.metadata,
    })),
    batchSize: problem.batchSize,
    seed: problem.budget.seed,
  };
  const response = await fetch("/api/advisor/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("Unable to get advisor suggestion");
  }

  return response.json() as Promise<AdvisorSuggestResponse>;
}

export function toProblemPayload(problem: ProblemDraft): ProblemPayload {
  return {
    variables: problem.variables.map((variable) => ({
      name: variable.name.trim(),
      type: variable.type,
      lower: variable.type === "float" || variable.type === "int" ? Number(variable.lower ?? 0) : undefined,
      upper: variable.type === "float" || variable.type === "int" ? Number(variable.upper ?? 1) : undefined,
      choices: variable.type === "categorical" ? variable.choices ?? [] : undefined,
      scale: variable.scale,
      default: variable.default,
    })),
    objectives: problem.objectives.map((objective) => ({
      name: objective.name.trim(),
      direction: objective.direction,
      unit: objective.unit,
      weight: objective.weight,
      threshold: objective.threshold,
    })),
    constraints: [],
    evaluator: problem.evaluator,
    budget: {
      max_evals: clampInteger(problem.budget.max_evals, 1, 5000),
      seed: clampInteger(problem.budget.seed, 0, Number.MAX_SAFE_INTEGER),
    },
    algorithm: problem.algorithm,
  };
}

export async function startJob(problem: ProblemDraft): Promise<StartJobResponse> {
  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toProblemPayload(problem)),
  });

  if (!response.ok) {
    throw new Error("Unable to start optimization job");
  }

  return response.json() as Promise<StartJobResponse>;
}

export async function cancelJob(jobId: string): Promise<StartJobResponse> {
  const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to stop optimization job");
  }

  const payload = (await response.json()) as Partial<StartJobResponse>;
  return { jobId, status: payload.status ?? "stopping" };
}

export function createJobSocket(jobId: string): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host || "127.0.0.1:5173";
  return new WebSocket(`${protocol}//${host}/ws/jobs/${jobId}`);
}

function clampInteger(value: number, lower: number, upper: number): number {
  const integer = Number.isFinite(value) ? Math.trunc(value) : lower;
  return Math.max(lower, Math.min(upper, integer));
}
