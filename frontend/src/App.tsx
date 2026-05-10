import { useMemo, useState } from "react";

import { suggestCandidates } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { ParetoView } from "./components/ParetoView";
import { ResultsTable } from "./components/ResultsTable";
import { StatusPanel } from "./components/StatusPanel";
import type {
  AdvisorStatus,
  AdvisorSuggestResponse,
  CandidateResult,
  ProblemDraft,
  SuggestionRow,
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
  const [problem, setProblem] = useState<ProblemDraft>(initialProblem);
  const [status, setStatus] = useState<AdvisorStatus>("idle");
  const [advisor, setAdvisor] = useState<AdvisorSuggestResponse | null>(null);
  const [rows, setRows] = useState<SuggestionRow[]>([]);
  const [observations, setObservations] = useState<CandidateResult[]>([]);
  const [message, setMessage] = useState("Define dimensions and request the first algorithm suggestion.");

  const completedRows = useMemo(() => rows.filter((row) => row.status === "complete"), [rows]);
  const pendingRows = rows.filter((row) => row.status !== "submitted").length;

  const askWithObservations = async (nextObservations: CandidateResult[]) => {
    setStatus("asking");
    try {
      const response = await suggestCandidates(problem, nextObservations);
      setAdvisor(response);
      setRows((current) => [
        ...current,
        ...response.suggestions.map((suggestion) => ({
          candidateId: suggestion.candidateId,
          variables: suggestion.variables,
          objectives: Object.fromEntries(problem.objectives.map((objective) => [objective.name, ""])),
          status: "suggested" as const,
          reason: suggestion.reason,
        })),
      ]);
      setStatus("ready");
      setMessage(`${response.phase} phase via ${response.algorithm}; ${response.suggestions.length} candidate(s) proposed.`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to get advisor suggestion.");
    }
  };

  const handleAsk = async () => {
    await askWithObservations(observations);
  };

  const handleObjectiveChange = (candidateId: string, objectiveName: string, value: string) => {
    setRows((current) =>
      current.map((row) => {
        if (row.candidateId !== candidateId || row.status === "submitted") {
          return row;
        }
        const objectives = { ...row.objectives, [objectiveName]: value };
        return { ...row, objectives, status: rowStatus(objectives, problem.objectives.map((objective) => objective.name)) };
      }),
    );
  };

  const handleSubmitAndAsk = async () => {
    const nextResults = rows.filter((row) => row.status === "complete").map((row, index) => rowToObservation(row, observations.length + index));
    if (nextResults.length === 0) {
      return;
    }
    const nextObservations = [...observations, ...nextResults];
    setObservations(nextObservations);
    setRows((current) =>
      current.map((row) => (row.status === "complete" ? { ...row, status: "submitted" } : row)),
    );
    await askWithObservations(nextObservations);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>OptLab</h1>
          <p>Interactive multi-objective ask/tell optimization for engineering experiments.</p>
        </div>
      </header>

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
            setMessage("Problem definition changed; request fresh suggestions.");
          }}
        />
        <StatusPanel
          advisor={advisor}
          completedRows={completedRows.length}
          observations={observations.length}
          pending={pendingRows}
          status={status}
        />
        <ParetoView candidates={observations} objectives={problem.objectives} policy={advisor?.visualization ?? null} />
        <ResultsTable
          objectives={problem.objectives}
          observations={observations}
          rows={rows}
          variables={problem.variables}
          onObjectiveChange={handleObjectiveChange}
          onSubmitAndAsk={handleSubmitAndAsk}
        />
      </div>
    </main>
  );
}

function rowStatus(objectives: Record<string, string>, objectiveNames: string[]): SuggestionRow["status"] {
  const values = objectiveNames.map((name) => objectives[name] ?? "");
  if (values.every((value) => value !== "" && Number.isFinite(Number(value)))) {
    return "complete";
  }
  if (values.some((value) => value !== "" && !Number.isFinite(Number(value)))) {
    return "invalid";
  }
  return "suggested";
}

function rowToObservation(row: SuggestionRow, generation: number): CandidateResult {
  return {
    candidateId: row.candidateId,
    generation,
    variables: row.variables,
    objectives: Object.fromEntries(Object.entries(row.objectives).map(([name, value]) => [name, Number(value)])),
    constraints: {},
    feasible: true,
    metadata: { source: "manual-ask-tell" },
  };
}
