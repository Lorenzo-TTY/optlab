import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { ACTIVE_PROJECT_STORAGE_KEY, PROJECT_STORAGE_KEY } from "./projectStorage";

vi.mock("react-plotly.js/factory", () => ({
  default: () =>
    ({ data }: { data?: Array<{ dimensions?: Array<{ label: string }> }> }) => (
      <div aria-label="plotly-chart">
        {data?.[0]?.dimensions?.map((dimension) => dimension.label).join("|") ?? ""}
      </div>
    ),
}));

vi.mock("plotly.js/lib/core", () => ({
  default: { register: () => undefined },
}));

vi.mock("plotly.js/lib/scatter", () => ({ default: {} }));
vi.mock("plotly.js/lib/scatter3d", () => ({ default: {} }));
vi.mock("plotly.js/lib/parcoords", () => ({ default: {} }));

const firstAdvisorResponse = {
  phase: "initial",
  algorithm: "sobol-lhs-maximin",
  suggestions: [
    {
      candidateId: "suggest_000001",
      variables: { x1: 0.25, x2: 0.75 },
      reason: "Sobol/LHS/maximin space-filling initial design",
    },
  ],
  visualization: {
    recommendedView: "scatter2d",
    supportingViews: ["parallel-coordinates"],
    objectiveNames: ["f1", "f2"],
  },
};

const secondAdvisorResponse = {
  phase: "surrogate",
  algorithm: "ensemble-mobo",
  suggestions: [
    {
      candidateId: "suggest_000002",
      variables: { x1: 0.45, x2: 0.35 },
      reason: "Ensemble MOBO surrogate balances objective improvement and diversity",
    },
  ],
  visualization: {
    recommendedView: "scatter2d",
    supportingViews: ["parallel-coordinates"],
    objectiveNames: ["f1", "f2"],
  },
};

describe("OptLab ask/tell UI", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(JSON.stringify(firstAdvisorResponse)))
        .mockResolvedValueOnce(new Response(JSON.stringify(secondAdvisorResponse))),
    );
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("starts from dimensions and renders editable variable/objective tables", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "OptLab" })).toBeInTheDocument();
    expect(screen.getByLabelText("Parameter dimensions")).toHaveValue("2");
    expect(screen.getByLabelText("Objective dimensions")).toHaveValue("2");

    const variableTable = screen.getByRole("table", { name: "Parameter definition table" });
    expect(within(variableTable).getByDisplayValue("x1")).toBeInTheDocument();
    expect(within(variableTable).getByDisplayValue("x2")).toBeInTheDocument();

    const objectiveTable = screen.getByRole("table", { name: "Objective definition table" });
    expect(within(objectiveTable).getByDisplayValue("f1")).toBeInTheDocument();
    expect(within(objectiveTable).getByDisplayValue("f2")).toBeInTheDocument();
  });

  it("adds and saves a completed manual row without requesting the advisor", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));

    expect(await within(resultsEntryTable()).findByText("manual_000001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save completed rows" })).toBeDisabled();

    await fillCandidateRow("manual_000001", {
      x1: "0.2",
      x2: "0.8",
      f1: "0.12",
      f2: "0.88",
    });
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));

    expectSavedObservations(1);
    expect(within(candidateRow("manual_000001")).getByText("submitted")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("keeps incomplete or out-of-range manual rows from being saved", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRow("manual_000001", {
      x1: "2",
      x2: "0.8",
      f1: " ",
      f2: "0.88",
    });

    expect(within(candidateRow("manual_000001")).getByText("invalid")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save completed rows" })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("includes saved manual observations when requesting an optional advisor suggestion", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRow("manual_000001", {
      x1: "0.2",
      x2: "0.8",
      f1: "0.12",
      f2: "0.88",
    });
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));
    await userEvent.click(screen.getByRole("button", { name: "Get optional algorithm suggestion" }));

    expect(await within(resultsEntryTable()).findByText("suggest_000001")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body));
    expect(body.observations).toEqual([
      expect.objectContaining({
        candidateId: "manual_000001",
        variables: { x1: 0.2, x2: 0.8 },
        objectives: { f1: 0.12, f2: 0.88 },
        metadata: { source: "manual-dataset" },
      }),
    ]);
  });

  it("does not send completed but unsaved draft rows to the advisor", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRow("manual_000001", {
      x1: "0.2",
      x2: "0.8",
      f1: "0.12",
      f2: "0.88",
    });
    expect(within(candidateRow("manual_000001")).getByText("complete")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Get optional algorithm suggestion" }));

    expect(await within(resultsEntryTable()).findByText("suggest_000001")).toBeInTheDocument();
    expectSavedObservations(0);
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body));
    expect(body.observations).toEqual([]);
    expect(within(candidateRow("manual_000001")).getByText("complete")).toBeInTheDocument();
  });

  it("creates separate optimization projects and restores the selected project after reload", async () => {
    const { unmount } = render(<App />);

    await userEvent.clear(screen.getByLabelText("Project name"));
    await userEvent.type(screen.getByLabelText("Project name"), "Wing sweep");
    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRow("manual_000001", {
      x1: "0.2",
      x2: "0.8",
      f1: "0.12",
      f2: "0.88",
    });
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));
    expectSavedObservations(1);

    await userEvent.click(screen.getByRole("button", { name: "New project" }));
    expect(screen.getByLabelText("Project name")).toHaveValue("Project 2");
    expectSavedObservations(0);
    expect(screen.queryByText("manual_000001")).not.toBeInTheDocument();

    await userEvent.click(projectButton("Wing sweep"));
    expectSavedObservations(1);
    expect(within(candidateRow("manual_000001")).getByText("submitted")).toBeInTheDocument();

    await userEvent.click(projectButton("Project 2"));
    await userEvent.clear(screen.getByLabelText("Project name"));
    await userEvent.type(screen.getByLabelText("Project name"), "Thermal sweep");
    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await userEvent.type(screen.getByLabelText("x1 for manual_000001"), "0.4");
    await userEvent.type(screen.getByLabelText("x2 for manual_000001"), "0.6");

    await waitFor(() => expect(window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY)).toBeTruthy());
    unmount();
    render(<App />);

    expect(screen.getByLabelText("Project name")).toHaveValue("Thermal sweep");
    expectSavedObservations(0);
    expect(screen.getByLabelText("x1 for manual_000001")).toHaveValue("0.4");
    expect(screen.getByLabelText("x2 for manual_000001")).toHaveValue("0.6");
    expect(within(candidateRow("manual_000001")).getByText("draft")).toBeInTheDocument();
  });

  it("falls back to a fresh project when stored project data is corrupt", () => {
    window.localStorage.setItem(PROJECT_STORAGE_KEY, "{not valid json");
    window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, "missing_project");

    render(<App />);

    expect(screen.getByLabelText("Project name")).toHaveValue("Project 1");
    expectSavedObservations(0);
    expect(screen.getByText("No data rows yet. Add manual rows or request optional algorithm suggestions.")).toBeInTheDocument();
  });

  it("keeps the workbench usable when browser project storage fails", async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    render(<App />);

    expect(await screen.findByText("Local project save failed. Current work remains in memory, but this browser did not persist it.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    expect(await within(resultsEntryTable()).findByText("manual_000001")).toBeInTheDocument();
    expect(screen.getByLabelText("x1 for manual_000001")).toBeEnabled();

    setItemSpy.mockRestore();
  });

  it("displays optimization result summary for saved manual rows and active advisor recommendations", async () => {
    render(<App />);

    await userEvent.clear(screen.getByLabelText("Rows to add"));
    await userEvent.type(screen.getByLabelText("Rows to add"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRow("manual_000001", {
      x1: "0.2",
      x2: "0.8",
      f1: "0.12",
      f2: "0.88",
    });
    await fillCandidateRow("manual_000002", {
      x1: "0.6",
      x2: "0.4",
      f1: "0.2",
      f2: "0.2",
    });
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));

    const summary = resultSummary();
    expect(within(summary).getByRole("heading", { name: "Result Summary" })).toBeInTheDocument();
    expect(within(summary).getByText("Saved")).toBeInTheDocument();
    expect(within(summary).getByText("Feasible")).toBeInTheDocument();
    expect(within(summary).getByText("Pareto")).toBeInTheDocument();
    expect(within(summary).getByText("2 saved")).toBeInTheDocument();
    expect(within(summary).getByText("2 feasible")).toBeInTheDocument();
    expect(within(summary).getByText("2 Pareto")).toBeInTheDocument();
    const bestValues = within(summary).getByRole("table", { name: "Best objective values" });
    const bestScope = within(bestValues);
    expect(bestScope.getByRole("row", { name: "f1 0.12 manual_000001" })).toBeInTheDocument();
    expect(bestScope.getByRole("row", { name: "f2 0.2 manual_000002" })).toBeInTheDocument();

    const paretoPreview = within(summary).getByRole("table", { name: "Pareto front results" });
    const paretoScope = within(paretoPreview);
    expect(paretoScope.getByRole("row", { name: "manual_000001 0.12 0.88" })).toBeInTheDocument();
    expect(paretoScope.getByRole("row", { name: "manual_000002 0.2 0.2" })).toBeInTheDocument();
    expect(within(summary).queryByText("suggest_000001")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Get optional algorithm suggestion" }));

    const updatedSummary = resultSummary();
    expect(await within(updatedSummary).findByText("suggest_000001")).toBeInTheDocument();
    const recommendations = recommendationStrip(updatedSummary);
    expect(within(recommendations).getByText("Recommended active advisor candidates")).toBeInTheDocument();
    expect(within(recommendations).getByText("Sobol/LHS/maximin space-filling initial design")).toBeInTheDocument();
  });

  it("saves advisor-suggested rows without automatically asking for the next suggestion", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Get optional algorithm suggestion" }));

    expect(await within(resultsEntryTable()).findByText("suggest_000001")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/advisor/suggest",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"batchSize":1'),
      }),
    );

    await userEvent.type(screen.getByLabelText("f1 for suggest_000001"), "0.12");
    await userEvent.type(screen.getByLabelText("f2 for suggest_000001"), "0.88");
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expectSavedObservations(1);
    expect(within(candidateRow("suggest_000001")).getByText("submitted")).toBeInTheDocument();
    expect(screen.queryByText("suggest_000002")).not.toBeInTheDocument();
  });

  it("switches the visualization guidance to high-dimensional mode", async () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Objective dimensions"), { target: { value: "5" } });

    expect(screen.getByText("Parallel coordinates primary")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Objective definition table" })).toBeInTheDocument();
  });

  it("keeps user-defined objective order in high-dimensional results and parallel coordinates", async () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText("Objective dimensions"), { target: { value: "5" } });
    const orderedNames = ["drag", "lift", "cost", "noise", "mass"];
    for (const [index, name] of orderedNames.entries()) {
      await userEvent.clear(screen.getByLabelText(`Objective ${index + 1} name`));
      await userEvent.type(screen.getByLabelText(`Objective ${index + 1} name`), name);
    }

    await userEvent.click(screen.getByRole("button", { name: "Add manual rows" }));
    await fillCandidateRowFields("manual_000001", {
      x1: "0.1",
      x2: "0.9",
      drag: "0.11",
      lift: "0.22",
      cost: "0.33",
      noise: "0.44",
      mass: "0.55",
    });
    expect(within(candidateRow("manual_000001")).getByText("complete")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save completed rows" }));

    const paretoPreview = within(resultSummary()).getByRole("table", { name: "Pareto front results" });
    expect(within(paretoPreview).getByRole("row", { name: "Candidate drag lift cost noise" })).toBeInTheDocument();
    expect(screen.getByLabelText("plotly-chart")).toHaveTextContent("drag|lift|cost|noise|mass");
  });
});

async function fillCandidateRow(
  candidateId: string,
  values: { x1: string; x2: string; f1: string; f2: string },
) {
  await fillCandidateRowFields(candidateId, values);
}

async function fillCandidateRowFields(candidateId: string, values: Record<string, string>) {
  await userEvent.type(screen.getByLabelText(`x1 for ${candidateId}`), values.x1);
  await userEvent.type(screen.getByLabelText(`x2 for ${candidateId}`), values.x2);
  for (const [name, value] of Object.entries(values)) {
    if (name === "x1" || name === "x2") {
      continue;
    }
    await userEvent.type(screen.getByLabelText(`${name} for ${candidateId}`), value);
  }
}

function candidateRow(candidateId: string) {
  const row = within(resultsEntryTable()).getByText(candidateId).closest("tr");
  if (!row) {
    throw new Error(`Could not find row for ${candidateId}`);
  }
  return row;
}

function resultsEntryTable() {
  return screen.getByRole("table", { name: "Suggestion and objective entry table" });
}

function expectSavedObservations(count: number) {
  const strip = screen.getByText("Saved observations").closest(".observation-strip");
  expect(strip).not.toBeNull();
  expect(within(strip as HTMLElement).getByText(String(count))).toBeInTheDocument();
}

function resultSummary() {
  const summary = screen.getByRole("heading", { name: "Result Summary" }).closest("section");
  if (!summary) {
    throw new Error("Could not find Result Summary section");
  }
  return summary;
}

function recommendationStrip(summary: HTMLElement) {
  const strip = within(summary).getByRole("heading", { name: "Recommended active advisor candidates" }).closest("div");
  if (!strip) {
    throw new Error("Could not find recommendation strip");
  }
  return strip;
}

function projectButton(name: string) {
  const label = screen.getByText(name);
  const button = label.closest("button");
  if (!button) {
    throw new Error(`Could not find project button for ${name}`);
  }
  return button;
}
