import { useMemo } from "react";

import type { CandidateResult, ObjectiveDefinition, SuggestionRow } from "../types";

interface OptimizationResultsProps {
  candidates: CandidateResult[];
  objectives: ObjectiveDefinition[];
  rows: SuggestionRow[];
}

export function OptimizationResults({ candidates, objectives, rows }: OptimizationResultsProps) {
  const feasible = candidates.filter((candidate) => candidate.feasible);
  const recommendations = rows.filter((row) => row.source === "advisor" && row.status !== "submitted");
  const summary = useMemo(() => summarizeResults(feasible, objectives), [feasible, objectives]);

  return (
    <section className="panel results-summary-panel" aria-labelledby="result-summary-title">
      <div className="section-heading">
        <div>
          <h2 id="result-summary-title">Result Summary</h2>
          <p>Pareto front, objective coverage, and best observed values from saved observations.</p>
        </div>
      </div>

      <div className="metric-grid result-metrics">
        <Metric label="Saved" value={`${candidates.length} saved`} />
        <Metric label="Feasible" value={`${feasible.length} feasible`} />
        <Metric label="Pareto" value={`${summary.front.length} Pareto`} />
        <Metric label="Coverage min" value={formatNumber(summary.coverageMin)} />
      </div>

      {candidates.length === 0 ? (
        <div className="summary-empty">Save completed rows to compute optimization results.</div>
      ) : feasible.length === 0 ? (
        <div className="summary-empty">No feasible saved rows are available for Pareto analysis.</div>
      ) : (
        <div className="result-sections">
          <div>
            <h3>Best Per Objective</h3>
            <div className="mini-table-wrap">
              <table aria-label="Best objective values">
                <thead>
                  <tr>
                    <th>Objective</th>
                    <th>Best</th>
                    <th>Candidate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.best.map((item) => (
                    <tr key={item.name}>
                      <td>{item.name}</td>
                      <td className="tabular">{formatNumber(item.value)}</td>
                      <td>{item.candidateId}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3>Pareto Front Preview</h3>
            <div className="mini-table-wrap">
              <table aria-label="Pareto front results">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    {objectives.slice(0, 4).map((objective) => (
                      <th key={objective.name}>{objective.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summary.front.slice(0, 8).map((candidate) => (
                    <tr key={candidate.candidateId}>
                      <td>{candidate.candidateId}</td>
                      {objectives.slice(0, 4).map((objective) => (
                        <td className="tabular" key={`${candidate.candidateId}-${objective.name}`}>
                          {formatNumber(candidate.objectives[objective.name])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {recommendations.length > 0 ? (
        <div className="recommendation-strip">
          <h3>Recommended active advisor candidates</h3>
          <div className="recommendation-list">
            {recommendations.map((row) => (
              <div className="recommendation-item" key={row.candidateId}>
                <strong>{row.candidateId}</strong>
                <span>{row.reason}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function summarizeResults(candidates: CandidateResult[], objectives: ObjectiveDefinition[]) {
  return {
    best: objectives.map((objective) => bestForObjective(candidates, objective)),
    coverageMin: objectiveCoverageMin(candidates, objectives),
    front: paretoFront(candidates, objectives),
  };
}

function bestForObjective(candidates: CandidateResult[], objective: ObjectiveDefinition) {
  const direction = objective.direction ?? "min";
  let best: CandidateResult | undefined = candidates[0];
  for (const candidate of candidates) {
    const value = candidate.objectives[objective.name];
    const bestValue = best?.objectives[objective.name];
    if (best === undefined || bestValue === undefined || isBetter(value, bestValue, direction)) {
      best = candidate;
    }
  }
  return {
    candidateId: best?.candidateId ?? "-",
    name: objective.name,
    value: best?.objectives[objective.name],
  };
}

function paretoFront(candidates: CandidateResult[], objectives: ObjectiveDefinition[]) {
  return candidates.filter((candidate, index) =>
    !candidates.some((other, otherIndex) => otherIndex !== index && dominates(other, candidate, objectives)),
  );
}

function dominates(left: CandidateResult, right: CandidateResult, objectives: ObjectiveDefinition[]) {
  let strictlyBetter = false;
  for (const objective of objectives) {
    const leftValue = left.objectives[objective.name];
    const rightValue = right.objectives[objective.name];
    if (leftValue === undefined || rightValue === undefined) {
      return false;
    }
    if (isBetter(rightValue, leftValue, objective.direction)) {
      return false;
    }
    strictlyBetter = strictlyBetter || isBetter(leftValue, rightValue, objective.direction);
  }
  return strictlyBetter;
}

function objectiveCoverageMin(candidates: CandidateResult[], objectives: ObjectiveDefinition[]) {
  if (candidates.length === 0 || objectives.length === 0) {
    return 0;
  }
  const ranges = objectives.map((objective) => {
    const values = candidates
      .map((candidate) => candidate.objectives[objective.name])
      .filter((value): value is number => Number.isFinite(value));
    if (values.length === 0) {
      return 0;
    }
    return Math.max(...values) - Math.min(...values);
  });
  return Math.min(...ranges);
}

function isBetter(left: number | undefined, right: number | undefined, direction: "min" | "max") {
  if (left === undefined || right === undefined) {
    return false;
  }
  return direction === "max" ? left > right : left < right;
}

function formatNumber(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) {
    return "-";
  }
  if (value === 0) {
    return "0";
  }
  const formatted = Math.abs(value) >= 1000 || Math.abs(value) < 0.001 ? value.toExponential(3) : value.toPrecision(4);
  return formatted.replace(/(\.\d*?[1-9])0+(e|$)/, "$1$2").replace(/\.0+(e|$)/, "$1");
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
