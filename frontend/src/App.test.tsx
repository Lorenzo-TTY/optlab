import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("react-plotly.js/factory", () => ({
  default: () => () => <div aria-label="plotly-chart" />,
}));

vi.mock("plotly.js/lib/core", () => ({
  default: { register: () => undefined },
}));

vi.mock("plotly.js/lib/scatter", () => ({ default: {} }));
vi.mock("plotly.js/lib/scatter3d", () => ({ default: {} }));
vi.mock("plotly.js/lib/parcoords", () => ({ default: {} }));

const firstAdvisorResponse = {
  phase: "initial",
  algorithm: "lhs",
  suggestions: [
    {
      candidateId: "suggest_000001",
      variables: { x1: 0.25, x2: 0.75 },
      reason: "Latin hypercube initial design",
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
  algorithm: "parego-idw",
  suggestions: [
    {
      candidateId: "suggest_000002",
      variables: { x1: 0.45, x2: 0.35 },
      reason: "ParEGO scalarization with IDW uncertainty search",
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
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(JSON.stringify(firstAdvisorResponse)))
        .mockResolvedValueOnce(new Response(JSON.stringify(secondAdvisorResponse))),
    );
  });

  afterEach(() => {
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

    expect(await screen.findByText("manual_000001")).toBeInTheDocument();
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

    expect(await screen.findByText("suggest_000001")).toBeInTheDocument();
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

  it("saves advisor-suggested rows without automatically asking for the next suggestion", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Get optional algorithm suggestion" }));

    expect(await screen.findByText("suggest_000001")).toBeInTheDocument();
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

    await userEvent.clear(screen.getByLabelText("Objective dimensions"));
    await userEvent.type(screen.getByLabelText("Objective dimensions"), "5");

    expect(screen.getByText("Parallel coordinates primary")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Objective definition table" })).toBeInTheDocument();
  });
});

async function fillCandidateRow(
  candidateId: string,
  values: { x1: string; x2: string; f1: string; f2: string },
) {
  await userEvent.type(screen.getByLabelText(`x1 for ${candidateId}`), values.x1);
  await userEvent.type(screen.getByLabelText(`x2 for ${candidateId}`), values.x2);
  await userEvent.type(screen.getByLabelText(`f1 for ${candidateId}`), values.f1);
  await userEvent.type(screen.getByLabelText(`f2 for ${candidateId}`), values.f2);
}

function candidateRow(candidateId: string) {
  const row = screen.getByText(candidateId).closest("tr");
  if (!row) {
    throw new Error(`Could not find row for ${candidateId}`);
  }
  return row;
}

function expectSavedObservations(count: number) {
  const strip = screen.getByText("Saved observations").closest(".observation-strip");
  expect(strip).not.toBeNull();
  expect(within(strip as HTMLElement).getByText(String(count))).toBeInTheDocument();
}
