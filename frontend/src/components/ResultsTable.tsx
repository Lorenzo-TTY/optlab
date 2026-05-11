import { useState } from "react";

import type { CandidateResult, ObjectiveDefinition, SuggestionRow, VariableDefinition } from "../types";

interface ResultsTableProps {
  rows: SuggestionRow[];
  variables: VariableDefinition[];
  objectives: ObjectiveDefinition[];
  observations: CandidateResult[];
  disabled?: boolean;
  onAddManualRows: (count: number) => void;
  onObjectiveChange: (candidateId: string, objectiveName: string, value: string) => void;
  onSaveRows: () => void;
  onVariableChange: (candidateId: string, variableName: string, value: string) => void;
}

export function ResultsTable({
  rows,
  variables,
  objectives,
  observations,
  disabled = false,
  onAddManualRows,
  onObjectiveChange,
  onSaveRows,
  onVariableChange,
}: ResultsTableProps) {
  const [rowsToAdd, setRowsToAdd] = useState("1");
  const canSubmit = rows.some((row) => row.status === "complete");
  const addCount = Math.max(1, Math.trunc(Number(rowsToAdd) || 1));

  return (
    <section className="panel results-panel" aria-labelledby="results-title">
      <div className="section-heading">
        <div>
          <h2 id="results-title">Ask / Tell Workbench</h2>
          <p>Enter candidate variables and objective values directly; advisor suggestions are optional editable references.</p>
        </div>
        <div className="table-actions">
          <label className="inline-field">
            <span>Rows to add</span>
            <input
              aria-label="Rows to add"
              autoComplete="off"
              disabled={disabled}
              inputMode="numeric"
              type="text"
              value={rowsToAdd}
              onChange={(event) => setRowsToAdd(event.target.value)}
            />
          </label>
          <button className="secondary-button" disabled={disabled} type="button" onClick={() => onAddManualRows(addCount)}>
            Add manual rows
          </button>
          <button className="primary-button" disabled={disabled || !canSubmit} type="button" onClick={onSaveRows}>
            Save completed rows
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table aria-label="Suggestion and objective entry table">
          <thead>
            <tr>
              <th>Candidate</th>
              {variables.map((variable) => (
                <th key={variable.name}>{variable.name}</th>
              ))}
              {objectives.map((objective) => (
                <th key={objective.name}>{objective.name}</th>
              ))}
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={variables.length + objectives.length + 2} className="empty-cell">
                  No data rows yet. Add manual rows or request optional algorithm suggestions.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.candidateId}>
                  <td>
                    <strong>{row.candidateId}</strong>
                    <span className="row-source">{row.source}</span>
                    <span className="row-reason">{row.reason}</span>
                  </td>
                  {variables.map((variable) => (
                    <td key={`${row.candidateId}-${variable.name}`}>
                      <VariableValueInput
                        candidateId={row.candidateId}
                        disabled={disabled || row.status === "submitted"}
                        value={row.variables[variable.name] ?? ""}
                        variable={variable}
                        onChange={onVariableChange}
                      />
                    </td>
                  ))}
                  {objectives.map((objective) => (
                    <td key={`${row.candidateId}-${objective.name}`}>
                      <input
                        aria-label={`${objective.name} for ${row.candidateId}`}
                        disabled={disabled || row.status === "submitted"}
                        inputMode="decimal"
                        type="text"
                        value={row.objectives[objective.name] ?? ""}
                        onChange={(event) => onObjectiveChange(row.candidateId, objective.name, event.target.value)}
                      />
                    </td>
                  ))}
                  <td>
                    <span className={`tag ${statusTone(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="observation-strip">
        <span className="metric-label">Saved observations</span>
        <strong>{observations.length}</strong>
      </div>
    </section>
  );
}

function VariableValueInput({
  candidateId,
  disabled,
  value,
  variable,
  onChange,
}: {
  candidateId: string;
  disabled: boolean;
  value: string | number | boolean;
  variable: VariableDefinition;
  onChange: (candidateId: string, variableName: string, value: string) => void;
}) {
  const label = `${variable.name} for ${candidateId}`;
  if (variable.type === "bool") {
    return (
      <select
        aria-label={label}
        disabled={disabled}
        value={String(value)}
        onChange={(event) => onChange(candidateId, variable.name, event.target.value)}
      >
        <option value="">-</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }
  if (variable.type === "categorical" && (variable.choices?.length ?? 0) > 0) {
    return (
      <select
        aria-label={label}
        disabled={disabled}
        value={String(value)}
        onChange={(event) => onChange(candidateId, variable.name, event.target.value)}
      >
        <option value="">-</option>
        {variable.choices?.map((choice) => (
          <option key={String(choice)} value={String(choice)}>
            {String(choice)}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      aria-label={label}
      disabled={disabled}
      inputMode={variable.type === "int" ? "numeric" : "decimal"}
      type="text"
      value={String(value)}
      onChange={(event) => onChange(candidateId, variable.name, event.target.value)}
    />
  );
}

function statusTone(status: SuggestionRow["status"]) {
  if (status === "complete" || status === "submitted") {
    return "success";
  }
  if (status === "invalid") {
    return "danger";
  }
  return "warning";
}
