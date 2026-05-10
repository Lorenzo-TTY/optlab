export type VariableType = "float" | "int" | "categorical" | "bool";
export type ScaleType = "linear" | "log";
export type ObjectiveDirection = "min" | "max";
export type AdvisorStatus = "idle" | "asking" | "ready" | "error";

export interface VariableDefinition {
  name: string;
  type: VariableType;
  lower?: number;
  upper?: number;
  choices?: Array<string | number | boolean>;
  scale: ScaleType;
  default?: string | number | boolean;
}

export interface ObjectiveDefinition {
  name: string;
  direction: ObjectiveDirection;
  unit?: string;
  weight?: number;
  threshold?: number;
}

export interface ProblemDraft {
  variables: VariableDefinition[];
  objectives: ObjectiveDefinition[];
  evaluator: { type: "builtin"; name: string };
  budget: { max_evals: number; seed: number };
  algorithm: "auto" | "random" | "ga" | "nsga2" | "nsga3" | "rvea";
  batchSize: number;
}

export interface ProblemPayload {
  variables: VariableDefinition[];
  objectives: ObjectiveDefinition[];
  constraints: [];
  evaluator: { type: "builtin"; name: string };
  budget: { max_evals: number; seed: number };
  algorithm: ProblemDraft["algorithm"];
}

export interface CandidateResult {
  candidateId: string;
  generation: number;
  variables: Record<string, string | number | boolean>;
  objectives: Record<string, number>;
  constraints?: Record<string, number>;
  feasible: boolean;
  metadata?: Record<string, unknown>;
}

export interface SuggestionRow {
  candidateId: string;
  variables: Record<string, string | number | boolean>;
  objectives: Record<string, string>;
  status: "suggested" | "complete" | "submitted" | "invalid";
  reason: string;
}

export interface AdvisorSuggestion {
  candidateId: string;
  variables: Record<string, string | number | boolean>;
  reason: string;
}

export interface AdvisorVisualization {
  recommendedView: "scatter2d" | "scatter3d" | "parallel-coordinates";
  supportingViews: string[];
  objectiveNames: string[];
}

export interface AdvisorSuggestResponse {
  phase: "initial" | "surrogate";
  algorithm: "lhs" | "parego-idw";
  suggestions: AdvisorSuggestion[];
  visualization: AdvisorVisualization;
}

export interface AdvisorSuggestRequest {
  problem: ProblemPayload;
  observations: CandidateResult[];
  batchSize: number;
  seed: number;
}

export interface JobMetrics {
  generation: number;
  paretoCount: number;
  hypervolume?: number;
  feasibleRatio?: number;
}

export type JobStatus =
  | "idle"
  | "validating"
  | "queued"
  | "running"
  | "stopping"
  | "completed"
  | "failed"
  | "cancelled";

export interface StartJobResponse {
  jobId: string;
  status: JobStatus;
}

export interface ConfigValidationResponse {
  valid: boolean;
  summary?: {
    variables?: number;
    objectives?: number;
  };
}
