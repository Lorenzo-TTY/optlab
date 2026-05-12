import { useEffect, useMemo, useState } from "react";

import { suggestCandidates } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { OptimizationResults } from "./components/OptimizationResults";
import { ParetoView } from "./components/ParetoView";
import { ProjectSidebar } from "./components/ProjectSidebar";
import { ResultsTable } from "./components/ResultsTable";
import { StatusPanel } from "./components/StatusPanel";
import {
  createProject,
  loadActiveProjectId,
  loadProjects,
  saveActiveProjectId,
  saveProjects,
  touchProject,
  type OptimizationProject,
} from "./projectStorage";
import type {
  AdvisorStatus,
  AdvisorSuggestResponse,
  AdvisorSuggestion,
  CandidateResult,
  ProblemDraft,
  SuggestionRow,
  VariableDefinition,
} from "./types";
import "./styles.css";

const initialProblem: ProblemDraft = {
  variables: [
    { name: "x1", type: "float", lower: 0, upper: 1, scale: "linear" },
    { name: "x2", type: "float", lower: 0, upper: 1, scale: "linear" },
  ],
  objectives: [
    { name: "f1", direction: "min" },
    { name: "f2", direction: "min" },
  ],
  evaluator: { type: "builtin", name: "manual" },
  budget: { max_evals: 200, seed: 11 },
  algorithm: "auto",
  batchSize: 1,
};

export default function App() {
  const [projects, setProjects] = useState<OptimizationProject[]>(() => loadProjects(initialProblem));
  const [activeProjectId, setActiveProjectId] = useState(() => loadActiveProjectId(projects));
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? projects[0];
  const [problem, setProblem] = useState<ProblemDraft>(activeProject.problem);
  const [status, setStatus] = useState<AdvisorStatus>("idle");
  const [advisor, setAdvisor] = useState<AdvisorSuggestResponse | null>(activeProject.advisor);
  const [rows, setRows] = useState<SuggestionRow[]>(activeProject.rows);
  const [observations, setObservations] = useState<CandidateResult[]>(activeProject.observations);
  const [message, setMessage] = useState("Define dimensions, then add your own data rows or request optional algorithm suggestions.");

  const completedRows = useMemo(() => rows.filter((row) => row.status === "complete"), [rows]);
  const editableRows = rows.filter((row) => row.status !== "submitted").length;

  useEffect(() => {
    if (!saveProjects(projects)) {
      setMessage("Local project save failed. Current work remains in memory, but this browser did not persist it.");
    }
  }, [projects]);

  useEffect(() => {
    if (!saveActiveProjectId(activeProjectId)) {
      setMessage("Local project save failed. Current work remains in memory, but this browser did not persist it.");
    }
  }, [activeProjectId]);

  useEffect(() => {
    updateActiveProject({ problem, rows, observations, advisor });
  }, [problem, rows, observations, advisor]);

  const selectProject = (projectId: string) => {
    const nextProject = projects.find((project) => project.id === projectId);
    if (!nextProject) {
      return;
    }
    setActiveProjectId(projectId);
    setProblem(nextProject.problem);
    setRows(nextProject.rows);
    setObservations(nextProject.observations);
    setAdvisor(nextProject.advisor);
    setStatus("idle");
    setMessage(`Loaded ${nextProject.name}. Continue entering data or request optional suggestions.`);
  };

  const updateActiveProject = (patch: Partial<OptimizationProject>) => {
    setProjects((current) => updateProjectList(current, activeProjectId, patch));
  };

  const handleCreateProject = () => {
    const nextProject = createProject(initialProblem, `Project ${projects.length + 1}`);
    setProjects((current) => [...current, nextProject]);
    setActiveProjectId(nextProject.id);
    setProblem(nextProject.problem);
    setRows([]);
    setObservations([]);
    setAdvisor(null);
    setStatus("idle");
    setMessage("New optimization project created. Define the problem, then add rows or request optional suggestions.");
  };

  const handleRenameProject = (projectId: string, name: string) => {
    setProjects((current) =>
      current.map((project) => (project.id === projectId ? touchProject({ ...project, name }) : project)),
    );
  };

  const handleSaveProject = () => {
    const updatedProjects = updateProjectList(projects, activeProjectId, { problem, rows, observations, advisor });
    setProjects(updatedProjects);
    if (saveProjects(updatedProjects) && saveActiveProjectId(activeProjectId)) {
      setMessage(`${activeProject.name || "Untitled project"} saved locally. It will be restored when you reopen this browser.`);
      return;
    }
    setMessage("Local project save failed. Current work remains in memory, but this browser did not persist it.");
  };

  const askWithObservations = async (nextObservations: CandidateResult[], baseRows: SuggestionRow[]) => {
    setStatus("asking");
    try {
      const response = await suggestCandidates(problem, nextObservations);
      setAdvisor(response);
      setRows((current) => {
        const activeRows = current.length >= baseRows.length ? current : baseRows;
        const usedIds = new Set([
          ...nextObservations.map((observation) => observation.candidateId),
          ...activeRows.map((row) => row.candidateId),
        ]);
        const suggestionRows = response.suggestions.map((suggestion) => createSuggestionRow(suggestion, problem, usedIds));
        return [...activeRows, ...suggestionRows];
      });
      setStatus("ready");
      setMessage(`${response.phase} phase via ${response.algorithm}; ${response.suggestions.length} optional candidate(s) proposed.`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to get advisor suggestion.");
    }
  };

  const handleAsk = async () => {
    await askWithObservations(observations, rows);
  };

  const handleVariableChange = (candidateId: string, variableName: string, value: string) => {
    setRows((current) =>
      current.map((row) => {
        if (row.candidateId !== candidateId || row.status === "submitted") {
          return row;
        }
        const variables = { ...row.variables, [variableName]: value };
        return { ...row, variables, status: rowStatus(variables, row.objectives, problem.variables, problem.objectives.map((objective) => objective.name), row.source) };
      }),
    );
  };

  const handleObjectiveChange = (candidateId: string, objectiveName: string, value: string) => {
    setRows((current) =>
      current.map((row) => {
        if (row.candidateId !== candidateId || row.status === "submitted") {
          return row;
        }
        const objectives = { ...row.objectives, [objectiveName]: value };
        return { ...row, objectives, status: rowStatus(row.variables, objectives, problem.variables, problem.objectives.map((objective) => objective.name), row.source) };
      }),
    );
  };

  const handleSaveRows = () => {
    const committed = commitRows(rows, observations, problem);
    if (committed.count === 0) {
      return;
    }
    setObservations(committed.observations);
    setRows(committed.rows);
    setMessage(`${committed.count} data row(s) saved. You can keep entering data or request an algorithm suggestion when useful.`);
    if (status !== "error") {
      setStatus("ready");
    }
  };

  const handleAddManualRows = (count: number) => {
    const safeCount = Math.max(1, Number.isFinite(count) ? Math.trunc(count) : 1);
    const startIndex = nextManualIndex(rows, observations);
    const newRows = Array.from({ length: safeCount }, (_, offset) => createManualRow(problem, startIndex + offset));
    setRows((current) => [...current, ...newRows]);
    setMessage(`${safeCount} manual data row(s) added. Fill parameter and objective values, then save completed rows.`);
  };

  const handlePasteRows = (startRowIndex: number, startColumnIndex: number, values: string[][]) => {
    const pastedRows = values.filter((row) => row.some((cell) => cell.trim() !== ""));
    if (pastedRows.length === 0) {
      return;
    }
    setRows((current) => {
      const nextRows = [...current];
      const rowsNeeded = Math.max(0, startRowIndex + pastedRows.length - nextRows.length);
      if (rowsNeeded > 0) {
        const startIndex = nextManualIndex(nextRows, observations);
        nextRows.push(...Array.from({ length: rowsNeeded }, (_, offset) => createManualRow(problem, startIndex + offset)));
      }

      const columns = [
        ...problem.variables.map((variable) => ({ kind: "variable" as const, name: variable.name })),
        ...problem.objectives.map((objective) => ({ kind: "objective" as const, name: objective.name })),
      ];
      const objectiveNames = problem.objectives.map((objective) => objective.name);

      pastedRows.forEach((rowValues, rowOffset) => {
        const rowIndex = startRowIndex + rowOffset;
        const row = nextRows[rowIndex];
        if (!row || row.status === "submitted") {
          return;
        }
        const variables = { ...row.variables };
        const objectives = { ...row.objectives };
        rowValues.forEach((rawValue, columnOffset) => {
          const column = columns[startColumnIndex + columnOffset];
          if (!column) {
            return;
          }
          const value = rawValue.trim();
          if (column.kind === "variable") {
            variables[column.name] = value;
          } else {
            objectives[column.name] = value;
          }
        });
        nextRows[rowIndex] = {
          ...row,
          variables,
          objectives,
          status: rowStatus(variables, objectives, problem.variables, objectiveNames, row.source),
        };
      });

      return nextRows;
    });
    setMessage(`${pastedRows.length} spreadsheet row(s) pasted. Review row status, then save completed rows.`);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>OptLab</h1>
          <p>Interactive multi-objective ask/tell optimization for engineering experiments.</p>
        </div>
      </header>

      <div className="workspace-layout">
        <ProjectSidebar
          activeProjectId={activeProjectId}
          projects={projects}
          onCreate={handleCreateProject}
          onRename={handleRenameProject}
          onSave={handleSaveProject}
          onSelect={selectProject}
        />
        <div className="dashboard-grid">
          <ConfigPanel
            disabled={status === "asking"}
            message={message}
            problem={problem}
            onAsk={handleAsk}
            onChange={(nextProblem) => {
              setProblem(nextProblem);
              setAdvisor(null);
              setRows([]);
              setObservations([]);
              setStatus("idle");
              setMessage("Problem definition changed; add fresh data rows or request optional suggestions.");
            }}
          />
          <StatusPanel
            advisor={advisor}
            completedRows={completedRows.length}
            observations={observations.length}
            pending={editableRows}
            status={status}
          />
          <ParetoView candidates={observations} objectives={problem.objectives} policy={advisor?.visualization ?? null} />
          <OptimizationResults candidates={observations} objectives={problem.objectives} rows={rows} />
          <ResultsTable
            objectives={problem.objectives}
            observations={observations}
            rows={rows}
            variables={problem.variables}
            disabled={status === "asking"}
            onAddManualRows={handleAddManualRows}
            onObjectiveChange={handleObjectiveChange}
            onPasteRows={handlePasteRows}
            onSaveRows={handleSaveRows}
            onVariableChange={handleVariableChange}
          />
        </div>
      </div>
    </main>
  );
}

function rowStatus(
  variables: Record<string, string | number | boolean>,
  objectives: Record<string, string>,
  variableDefinitions: VariableDefinition[],
  objectiveNames: string[],
  source: SuggestionRow["source"],
): SuggestionRow["status"] {
  const variableValues = variableDefinitions.map((variable) => variables[variable.name] ?? "");
  if (variableValues.some((value, index) => !isBlank(value) && !isValidVariable(variableDefinitions[index], value))) {
    return "invalid";
  }
  if (variableValues.some((value) => isBlank(value))) {
    return source === "advisor" ? "suggested" : "draft";
  }
  const values = objectiveNames.map((name) => objectives[name] ?? "");
  if (values.every((value) => !isBlank(value) && Number.isFinite(Number(String(value).trim())))) {
    return "complete";
  }
  if (values.some((value) => !isBlank(value) && !Number.isFinite(Number(String(value).trim())))) {
    return "invalid";
  }
  return source === "advisor" ? "suggested" : "draft";
}

function updateProjectList(
  projects: OptimizationProject[],
  activeProjectId: string,
  patch: Partial<OptimizationProject>,
) {
  return projects.map((project) =>
    project.id === activeProjectId
      ? touchProject({
          ...project,
          ...patch,
        })
      : project,
  );
}

function commitRows(rows: SuggestionRow[], observations: CandidateResult[], problem: ProblemDraft) {
  const completedRows = rows.filter((row) => row.status === "complete");
  const nextResults = completedRows.map((row, index) => rowToObservation(row, observations.length + index, problem));
  return {
    count: nextResults.length,
    observations: [...observations, ...nextResults],
    rows: rows.map((row) => (row.status === "complete" ? { ...row, status: "submitted" as const } : row)),
  };
}

function rowToObservation(row: SuggestionRow, generation: number, problem: ProblemDraft): CandidateResult {
  return {
    candidateId: row.candidateId,
    generation,
    variables: Object.fromEntries(problem.variables.map((variable) => [variable.name, parseVariableValue(variable, row.variables[variable.name])])),
    objectives: Object.fromEntries(Object.entries(row.objectives).map(([name, value]) => [name, Number(value)])),
    constraints: {},
    feasible: true,
    metadata: { source: row.source === "advisor" ? "advisor-edited-ask-tell" : "manual-dataset" },
  };
}

function createSuggestionRow(suggestion: AdvisorSuggestion, problem: ProblemDraft, usedIds: Set<string>): SuggestionRow {
  const candidateId = uniqueCandidateId(suggestion.candidateId, usedIds);
  return {
    candidateId,
    source: "advisor",
    variables: Object.fromEntries(
      problem.variables.map((variable) => [variable.name, stringifyVariableValue(suggestion.variables[variable.name])]),
    ),
    objectives: Object.fromEntries(problem.objectives.map((objective) => [objective.name, ""])),
    status: "suggested",
    reason: suggestion.reason,
  };
}

function createManualRow(problem: ProblemDraft, index: number): SuggestionRow {
  return {
    candidateId: `manual_${index.toString().padStart(6, "0")}`,
    source: "manual",
    variables: Object.fromEntries(problem.variables.map((variable) => [variable.name, variable.default ?? ""])),
    objectives: Object.fromEntries(problem.objectives.map((objective) => [objective.name, ""])),
    status: "draft",
    reason: "User-entered candidate; algorithm suggestions are optional references.",
  };
}

function nextManualIndex(rows: SuggestionRow[], observations: CandidateResult[]) {
  const indexes = [...rows.map((row) => row.candidateId), ...observations.map((observation) => observation.candidateId)]
    .map((id) => /^manual_(\d+)$/.exec(id)?.[1])
    .filter((value): value is string => Boolean(value))
    .map((value) => Number(value));
  return indexes.length === 0 ? 1 : Math.max(...indexes) + 1;
}

function uniqueCandidateId(baseId: string, usedIds: Set<string>) {
  if (!usedIds.has(baseId)) {
    usedIds.add(baseId);
    return baseId;
  }
  let suffix = 2;
  let candidateId = `${baseId}_${suffix}`;
  while (usedIds.has(candidateId)) {
    suffix += 1;
    candidateId = `${baseId}_${suffix}`;
  }
  usedIds.add(candidateId);
  return candidateId;
}

function isValidVariable(variable: VariableDefinition, value: string | number | boolean) {
  if (variable.type === "bool") {
    return value === true || value === false || value === "true" || value === "false";
  }
  const text = String(value).trim();
  if (variable.type === "categorical") {
    return text.length > 0 && ((variable.choices?.length ?? 0) === 0 || variable.choices?.some((choice) => String(choice) === text));
  }
  const number = Number(text);
  if (!Number.isFinite(number)) {
    return false;
  }
  if (variable.type === "int" && !Number.isInteger(number)) {
    return false;
  }
  const lower = Number(variable.lower ?? Number.NEGATIVE_INFINITY);
  const upper = Number(variable.upper ?? Number.POSITIVE_INFINITY);
  return number >= lower && number <= upper;
}

function parseVariableValue(variable: VariableDefinition, value: string | number | boolean): string | number | boolean {
  if (variable.type === "bool") {
    return value === true || value === "true";
  }
  if (variable.type === "int") {
    return Number(String(value).trim());
  }
  if (variable.type === "float") {
    return Number(String(value).trim());
  }
  return String(value).trim();
}

function stringifyVariableValue(value: string | number | boolean | undefined) {
  return value === undefined ? "" : String(value);
}

function isBlank(value: string | number | boolean) {
  return typeof value === "string" ? value.trim() === "" : false;
}
