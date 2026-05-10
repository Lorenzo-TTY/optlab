import { useMemo } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import type { Data } from "plotly.js";
import Plotly from "plotly.js/lib/core";
import parcoords from "plotly.js/lib/parcoords";
import scatter from "plotly.js/lib/scatter";
import scatter3d from "plotly.js/lib/scatter3d";

import type { AdvisorVisualization, CandidateResult, ObjectiveDefinition } from "../types";

Plotly.register([scatter, scatter3d, parcoords]);
const Plot = createPlotlyComponent(Plotly);

interface ParetoViewProps {
  candidates: CandidateResult[];
  objectives: ObjectiveDefinition[];
  policy: AdvisorVisualization | null;
}

export function ParetoView({ candidates, objectives, policy }: ParetoViewProps) {
  const feasible = candidates.filter((candidate) => candidate.feasible);
  const declaredNames = objectives.map((objective) => objective.name);
  const objectiveNames = useMemo(
    () => collectObjectiveNames(feasible, declaredNames),
    [feasible, declaredNames.join("|")],
  );
  const plotData = useMemo(() => buildObjectiveTrace(feasible, objectiveNames), [feasible, objectiveNames]);
  const parallelData = useMemo(() => buildParallelTrace(feasible, objectiveNames), [feasible, objectiveNames]);
  const recommendedView = policy?.recommendedView ?? inferRecommendedView(objectiveNames.length);
  const primaryLabel =
    recommendedView === "parallel-coordinates"
      ? "Parallel coordinates primary"
      : recommendedView === "scatter3d"
        ? "3D objective scatter"
        : "2D objective scatter";
  const showParallel = objectiveNames.length > 2;
  const showScatter = recommendedView !== "parallel-coordinates" || objectiveNames.length <= 3;

  return (
    <section className="panel pareto-panel" aria-labelledby="pareto-title">
      <div className="section-heading">
        <div>
          <h2 id="pareto-title">Objective Explorer</h2>
          <p>{primaryLabel}</p>
        </div>
      </div>

      {feasible.length === 0 ? (
        <div className="pareto-canvas" aria-label="Pareto frontier preview">
          <div className="axis x-axis" />
          <div className="axis y-axis" />
          <span className="empty-state">No candidates yet</span>
        </div>
      ) : (
        <div className="plot-stack" aria-label="Pareto frontier preview">
          {showParallel ? (
            <Plot
              config={{ displayModeBar: false, responsive: true }}
              data={parallelData}
              layout={{
                autosize: true,
                height: recommendedView === "parallel-coordinates" ? 320 : 220,
                margin: { b: 24, l: 24, r: 24, t: 16 },
                paper_bgcolor: "rgba(0,0,0,0)",
              }}
              style={{ height: recommendedView === "parallel-coordinates" ? "320px" : "220px", width: "100%" }}
              useResizeHandler
            />
          ) : null}
          {showScatter ? (
            <Plot
              config={{ displayModeBar: false, responsive: true }}
              data={plotData}
              layout={{
                autosize: true,
                height: 280,
                margin: { b: 40, l: 48, r: 16, t: 16 },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                xaxis: { title: { text: objectiveNames[0] ?? "f1" }, zeroline: false },
                yaxis: { title: { text: objectiveNames[1] ?? objectiveNames[0] ?? "f2" }, zeroline: false },
                scene: {
                  xaxis: { title: { text: objectiveNames[0] } },
                  yaxis: { title: { text: objectiveNames[1] } },
                  zaxis: { title: { text: objectiveNames[2] } },
                },
                showlegend: false,
              }}
              style={{ height: "280px", width: "100%" }}
              useResizeHandler
            />
          ) : null}
        </div>
      )}
    </section>
  );
}

function collectObjectiveNames(candidates: CandidateResult[], fallback: string[]): string[] {
  const names = new Set<string>();
  for (const candidate of candidates) {
    Object.keys(candidate.objectives).forEach((name) => names.add(name));
  }
  return names.size > 0 ? [...names].sort() : fallback;
}

function buildObjectiveTrace(candidates: CandidateResult[], objectiveNames: string[]): Data[] {
  const xName = objectiveNames[0] ?? "f1";
  const yName = objectiveNames[1] ?? xName;
  const zName = objectiveNames[2];
  const common = {
    marker: {
      color: candidates.map((candidate) => candidate.generation),
      colorscale: "Viridis",
      line: { color: "#0f172a", width: 0.5 },
      size: 8,
    },
    mode: "markers",
    text: candidates.map((candidate) => candidate.candidateId),
    type: zName ? ("scatter3d" as const) : ("scatter" as const),
  };

  if (zName) {
    return [
      {
        ...common,
        x: candidates.map((candidate) => candidate.objectives[xName] ?? 0),
        y: candidates.map((candidate) => candidate.objectives[yName] ?? 0),
        z: candidates.map((candidate) => candidate.objectives[zName] ?? 0),
      },
    ] as Data[];
  }

  return [
    {
      ...common,
      x: candidates.map((candidate) => candidate.objectives[xName] ?? 0),
      y: candidates.map((candidate) => candidate.objectives[yName] ?? 0),
    },
  ] as unknown as Data[];
}

function inferRecommendedView(objectiveCount: number): AdvisorVisualization["recommendedView"] {
  if (objectiveCount <= 2) {
    return "scatter2d";
  }
  if (objectiveCount === 3) {
    return "scatter3d";
  }
  return "parallel-coordinates";
}

function buildParallelTrace(candidates: CandidateResult[], objectiveNames: string[]): Data[] {
  return [
    {
      dimensions: objectiveNames.map((name) => ({
        label: name,
        values: candidates.map((candidate) => candidate.objectives[name] ?? 0),
      })),
      line: {
        color: candidates.map((candidate) => candidate.generation),
        colorscale: "Viridis",
      },
      type: "parcoords" as const,
    },
  ] as unknown as Data[];
}
