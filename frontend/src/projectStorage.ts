import type { AdvisorSuggestResponse, CandidateResult, ProblemDraft, SuggestionRow } from "./types";

export const PROJECT_STORAGE_KEY = "optlab.projects.v1";
export const ACTIVE_PROJECT_STORAGE_KEY = "optlab.activeProjectId.v1";
export const PROJECT_SCHEMA_VERSION = 1;

export interface OptimizationProject {
  schemaVersion: 1;
  id: string;
  name: string;
  problem: ProblemDraft;
  rows: SuggestionRow[];
  observations: CandidateResult[];
  advisor: AdvisorSuggestResponse | null;
  createdAt: string;
  updatedAt: string;
}

export function createProject(problem: ProblemDraft, name: string, now = new Date()): OptimizationProject {
  const timestamp = now.toISOString();
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    id: createProjectId(),
    name,
    problem: structuredCloneFallback(problem),
    rows: [],
    observations: [],
    advisor: null,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

export function loadProjects(fallbackProblem: ProblemDraft): OptimizationProject[] {
  if (typeof window === "undefined") {
    return [createProject(fallbackProblem, "Project 1")];
  }
  try {
    const raw = window.localStorage.getItem(PROJECT_STORAGE_KEY);
    if (!raw) {
      return [createProject(fallbackProblem, "Project 1")];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [createProject(fallbackProblem, "Project 1")];
    }
    const projects = parsed.map((item) => coerceProject(item, fallbackProblem)).filter(Boolean) as OptimizationProject[];
    return projects.length > 0 ? projects : [createProject(fallbackProblem, "Project 1")];
  } catch {
    return [createProject(fallbackProblem, "Project 1")];
  }
}

export function saveProjects(projects: OptimizationProject[]) {
  if (typeof window === "undefined") {
    return true;
  }
  try {
    window.localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(projects));
    return true;
  } catch {
    return false;
  }
}

export function loadActiveProjectId(projects: OptimizationProject[]) {
  if (typeof window === "undefined") {
    return projects[0]?.id ?? "";
  }
  try {
    const stored = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
    return projects.some((project) => project.id === stored) ? String(stored) : projects[0]?.id ?? "";
  } catch {
    return projects[0]?.id ?? "";
  }
}

export function saveActiveProjectId(projectId: string) {
  if (typeof window === "undefined") {
    return true;
  }
  try {
    window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, projectId);
    return true;
  } catch {
    return false;
  }
}

export function touchProject(project: OptimizationProject, now = new Date()): OptimizationProject {
  return { ...project, updatedAt: now.toISOString() };
}

function coerceProject(item: unknown, fallbackProblem: ProblemDraft): OptimizationProject | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const candidate = item as Partial<OptimizationProject>;
  if (candidate.schemaVersion !== PROJECT_SCHEMA_VERSION || !candidate.id || !candidate.name) {
    return null;
  }
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    id: String(candidate.id),
    name: String(candidate.name).trim() || "Untitled project",
    problem: candidate.problem ? structuredCloneFallback(candidate.problem) : structuredCloneFallback(fallbackProblem),
    rows: Array.isArray(candidate.rows) ? candidate.rows : [],
    observations: Array.isArray(candidate.observations) ? candidate.observations : [],
    advisor: candidate.advisor ?? null,
    createdAt: candidate.createdAt ?? new Date().toISOString(),
    updatedAt: candidate.updatedAt ?? new Date().toISOString(),
  };
}

function createProjectId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `project_${crypto.randomUUID()}`;
  }
  return `project_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function structuredCloneFallback<T>(value: T): T {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
}
