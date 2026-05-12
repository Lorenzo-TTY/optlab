import type { ClipboardEvent } from "react";

import { parseSpreadsheetGrid } from "../spreadsheet";
import type { ObjectiveDefinition, ProblemDraft, VariableDefinition, VariableType } from "../types";

interface ConfigPanelProps {
  problem: ProblemDraft;
  disabled: boolean;
  message: string;
  onChange: (problem: ProblemDraft) => void;
  onAsk: () => void;
}

export function ConfigPanel({ problem, disabled, message, onChange, onAsk }: ConfigPanelProps) {
  const setVariableCount = (count: number) => {
    onChange({ ...problem, variables: resizeVariables(problem.variables, clampInteger(count, 1, 30)) });
  };
  const setObjectiveCount = (count: number) => {
    onChange({ ...problem, objectives: resizeObjectives(problem.objectives, clampInteger(count, 1, 6)) });
  };

  const updateVariable = (index: number, patch: Partial<VariableDefinition>) => {
    const variables = problem.variables.map((variable, current) =>
      current === index ? { ...variable, ...patch } : variable,
    );
    onChange({ ...problem, variables });
  };

  const updateObjective = (index: number, patch: Partial<ObjectiveDefinition>) => {
    const objectives = problem.objectives.map((objective, current) =>
      current === index ? { ...objective, ...patch } : objective,
    );
    onChange({ ...problem, objectives });
  };

  const pasteVariables = (startRow: number, startColumn: number, text: string) => {
    const grid = parseSpreadsheetGrid(text);
    if (grid.length === 0) {
      return false;
    }
    const nextCount = clampInteger(Math.max(problem.variables.length, startRow + grid.length), 1, 30);
    const variables = resizeVariables(problem.variables, nextCount);
    grid.slice(0, nextCount - startRow).forEach((row, rowOffset) => {
      const index = startRow + rowOffset;
      variables[index] = applyVariablePaste(variables[index], startColumn, row);
    });
    onChange({ ...problem, variables });
    return true;
  };

  const pasteObjectives = (startRow: number, startColumn: number, text: string) => {
    const grid = parseSpreadsheetGrid(text);
    if (grid.length === 0) {
      return false;
    }
    const nextCount = clampInteger(Math.max(problem.objectives.length, startRow + grid.length), 1, 6);
    const objectives = resizeObjectives(problem.objectives, nextCount);
    grid.slice(0, nextCount - startRow).forEach((row, rowOffset) => {
      const index = startRow + rowOffset;
      objectives[index] = applyObjectivePaste(objectives[index], startColumn, row);
    });
    onChange({ ...problem, objectives });
    return true;
  };

  return (
    <section className="panel config-panel" aria-labelledby="config-title">
      <div className="section-heading">
        <div>
          <h2 id="config-title">Problem Setup</h2>
          <p>Set dimensions first, then define every parameter and objective before entering or importing data rows.</p>
        </div>
      </div>

      <div className="field-grid shape-grid">
        <label className="field">
          <span>Parameter dimensions</span>
          <input
            aria-label="Parameter dimensions"
            autoComplete="off"
            inputMode="numeric"
            max={30}
            min={1}
            disabled={disabled}
            type="text"
            value={problem.variables.length}
            onChange={(event) => setVariableCount(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Objective dimensions</span>
          <input
            aria-label="Objective dimensions"
            autoComplete="off"
            inputMode="numeric"
            max={6}
            min={1}
            disabled={disabled}
            type="text"
            value={problem.objectives.length}
            onChange={(event) => setObjectiveCount(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Batch size</span>
          <input
            autoComplete="off"
            inputMode="numeric"
            max={16}
            min={1}
            disabled={disabled}
            type="text"
            value={problem.batchSize}
            onChange={(event) =>
              onChange({ ...problem, batchSize: clampInteger(Number(event.target.value), 1, 16) })
            }
          />
        </label>
        <label className="field">
          <span>Seed</span>
          <input
            autoComplete="off"
            inputMode="numeric"
            min={0}
            disabled={disabled}
            type="text"
            value={problem.budget.seed}
            onChange={(event) =>
              onChange({ ...problem, budget: { ...problem.budget, seed: clampInteger(Number(event.target.value), 0, 999999) } })
            }
          />
        </label>
      </div>

      <div className="definition-stack">
        <VariableDefinitionTable disabled={disabled} variables={problem.variables} onChange={updateVariable} onPaste={pasteVariables} />
        <ObjectiveDefinitionTable disabled={disabled} objectives={problem.objectives} onChange={updateObjective} onPaste={pasteObjectives} />
      </div>

      <div className="action-row">
        <button className="primary-button" disabled={disabled} type="button" onClick={onAsk}>
          Get optional algorithm suggestion
        </button>
      </div>

      <p className="validation-note" aria-live="polite">{message}</p>
    </section>
  );
}

function VariableDefinitionTable({
  disabled,
  variables,
  onChange,
  onPaste,
}: {
  disabled: boolean;
  variables: VariableDefinition[];
  onChange: (index: number, patch: Partial<VariableDefinition>) => void;
  onPaste: (startRow: number, startColumn: number, text: string) => boolean;
}) {
  const handlePaste = (event: ClipboardEvent, row: number, column: number) => {
    const text = event.clipboardData.getData("text");
    if (text.includes("\t") || text.includes("\n") || text.includes(",")) {
      if (onPaste(row, column, text)) {
        event.preventDefault();
      }
    }
  };

  return (
    <div className="definition-block">
      <h3>Parameters</h3>
      <div className="table-wrap compact-table">
        <table aria-label="Parameter definition table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Lower</th>
              <th>Upper</th>
              <th>Scale</th>
            </tr>
          </thead>
          <tbody>
            {variables.map((variable, index) => (
              <tr key={`variable-${index}`}>
                <td>
                  <input
                    aria-label={`Parameter ${index + 1} name`}
                    disabled={disabled}
                    value={variable.name}
                    onPaste={(event) => handlePaste(event, index, 0)}
                    onChange={(event) => onChange(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`Parameter ${index + 1} type`}
                    disabled={disabled}
                    value={variable.type}
                    onPaste={(event) => handlePaste(event, index, 1)}
                    onChange={(event) => onChange(index, { type: event.target.value as VariableType })}
                  >
                    <option value="float">float</option>
                    <option value="int">int</option>
                    <option value="bool">bool</option>
                    <option value="categorical">categorical</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`${variable.name} lower`}
                    disabled={disabled || variable.type === "bool" || variable.type === "categorical"}
                    type="number"
                    value={variable.lower ?? 0}
                    onPaste={(event) => handlePaste(event, index, 2)}
                    onChange={(event) => onChange(index, { lower: Number(event.target.value) })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`${variable.name} upper`}
                    disabled={disabled || variable.type === "bool" || variable.type === "categorical"}
                    type="number"
                    value={variable.upper ?? 1}
                    onPaste={(event) => handlePaste(event, index, 3)}
                    onChange={(event) => onChange(index, { upper: Number(event.target.value) })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`${variable.name} scale`}
                    disabled={disabled || variable.type === "bool" || variable.type === "categorical"}
                    value={variable.scale}
                    onPaste={(event) => handlePaste(event, index, 4)}
                    onChange={(event) => onChange(index, { scale: event.target.value as "linear" | "log" })}
                  >
                    <option value="linear">linear</option>
                    <option value="log">log</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ObjectiveDefinitionTable({
  disabled,
  objectives,
  onChange,
  onPaste,
}: {
  disabled: boolean;
  objectives: ObjectiveDefinition[];
  onChange: (index: number, patch: Partial<ObjectiveDefinition>) => void;
  onPaste: (startRow: number, startColumn: number, text: string) => boolean;
}) {
  const handlePaste = (event: ClipboardEvent, row: number, column: number) => {
    const text = event.clipboardData.getData("text");
    if (text.includes("\t") || text.includes("\n") || text.includes(",")) {
      if (onPaste(row, column, text)) {
        event.preventDefault();
      }
    }
  };

  return (
    <div className="definition-block">
      <h3>Objectives</h3>
      <div className="table-wrap compact-table">
        <table aria-label="Objective definition table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Direction</th>
              <th>Unit</th>
              <th>Threshold</th>
            </tr>
          </thead>
          <tbody>
            {objectives.map((objective, index) => (
              <tr key={`objective-${index}`}>
                <td>
                  <input
                    aria-label={`Objective ${index + 1} name`}
                    disabled={disabled}
                    value={objective.name}
                    onPaste={(event) => handlePaste(event, index, 0)}
                    onChange={(event) => onChange(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`${objective.name} direction`}
                    disabled={disabled}
                    value={objective.direction}
                    onPaste={(event) => handlePaste(event, index, 1)}
                    onChange={(event) => onChange(index, { direction: event.target.value as "min" | "max" })}
                  >
                    <option value="min">min</option>
                    <option value="max">max</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`${objective.name} unit`}
                    disabled={disabled}
                    value={objective.unit ?? ""}
                    onPaste={(event) => handlePaste(event, index, 2)}
                    onChange={(event) => onChange(index, { unit: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`${objective.name} threshold`}
                    disabled={disabled}
                    type="number"
                    value={objective.threshold ?? ""}
                    onPaste={(event) => handlePaste(event, index, 3)}
                    onChange={(event) =>
                      onChange(index, {
                        threshold: event.target.value === "" ? undefined : Number(event.target.value),
                      })
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function resizeVariables(current: VariableDefinition[], count: number): VariableDefinition[] {
  return Array.from({ length: count }, (_, index) => current[index] ?? defaultVariable(index));
}

function resizeObjectives(current: ObjectiveDefinition[], count: number): ObjectiveDefinition[] {
  return Array.from({ length: count }, (_, index) => current[index] ?? defaultObjective(index));
}

function defaultVariable(index: number): VariableDefinition {
  return { name: `x${index + 1}`, type: "float", lower: 0, upper: 1, scale: "linear" };
}

function defaultObjective(index: number): ObjectiveDefinition {
  return { name: `f${index + 1}`, direction: "min" };
}

function applyVariablePaste(variable: VariableDefinition, startColumn: number, row: string[]): VariableDefinition {
  return row.reduce((current, rawValue, offset) => {
    const value = rawValue.trim();
    const column = startColumn + offset;
    if (column === 0) {
      return value === "" ? current : { ...current, name: value };
    }
    if (column === 1) {
      return isVariableType(value) ? { ...current, type: value } : current;
    }
    if (column === 2) {
      const lower = optionalNumber(value);
      return lower.valid ? { ...current, lower: lower.value } : current;
    }
    if (column === 3) {
      const upper = optionalNumber(value);
      return upper.valid ? { ...current, upper: upper.value } : current;
    }
    if (column === 4) {
      return value === "linear" || value === "log" ? { ...current, scale: value } : current;
    }
    return current;
  }, variable);
}

function applyObjectivePaste(objective: ObjectiveDefinition, startColumn: number, row: string[]): ObjectiveDefinition {
  return row.reduce((current, rawValue, offset) => {
    const value = rawValue.trim();
    const column = startColumn + offset;
    if (column === 0) {
      return value === "" ? current : { ...current, name: value };
    }
    if (column === 1) {
      return value === "min" || value === "max" ? { ...current, direction: value } : current;
    }
    if (column === 2) {
      return { ...current, unit: value };
    }
    if (column === 3) {
      const threshold = optionalNumber(value);
      return threshold.valid ? { ...current, threshold: threshold.value } : current;
    }
    return current;
  }, objective);
}

function isVariableType(value: string): value is VariableType {
  return value === "float" || value === "int" || value === "bool" || value === "categorical";
}

function optionalNumber(value: string): { valid: true; value: number | undefined } | { valid: false } {
  if (value === "") {
    return { valid: true, value: undefined };
  }
  const number = Number(value);
  return Number.isFinite(number) ? { valid: true, value: number } : { valid: false };
}

function clampInteger(value: number, lower: number, upper: number): number {
  const integer = Number.isFinite(value) ? Math.trunc(value) : lower;
  return Math.max(lower, Math.min(upper, integer));
}
