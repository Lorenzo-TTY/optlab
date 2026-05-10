import type { CandidateResult, ObjectiveDefinition, SuggestionRow, VariableDefinition } from "../types";

interface ResultsTableProps {
  rows: SuggestionRow[];
  variables: VariableDefinition[];
  objectives: ObjectiveDefinition[];
  observations: CandidateResult[];
  onObjectiveChange: (candidateId: string, objectiveName: string, value: string) => void;
  onSubmitAndAsk: () => void;
}

export function ResultsTable({
  rows,
  variables,
  objectives,
  observations,
  onObjectiveChange,
  onSubmitAndAsk,
}: ResultsTableProps) {
  const canSubmit = rows.some((row) => row.status === "complete");

  return (
    <section className="panel results-panel" aria-labelledby="results-title">
      <div className="section-heading">
        <div>
          <h2 id="results-title">Ask / Tell Workbench</h2>
          <p>Variable columns are suggested by the algorithm; objective columns are filled after engineering evaluation.</p>
        </div>
        <button className="secondary-button" disabled={!canSubmit} type="button" onClick={onSubmitAndAsk}>
          Save objectives and ask next
        </button>
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
                  No suggestions yet
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.candidateId}>
                  <td>
                    <strong>{row.candidateId}</strong>
                    <span className="row-reason">{row.reason}</span>
                  </td>
                  {variables.map((variable) => (
                    <td className="tabular" key={`${row.candidateId}-${variable.name}`}>
                      {formatCell(row.variables[variable.name])}
                    </td>
                  ))}
                  {objectives.map((objective) => (
                    <td key={`${row.candidateId}-${objective.name}`}>
                      <input
                        aria-label={`${objective.name} for ${row.candidateId}`}
                        disabled={row.status === "submitted"}
                        inputMode="decimal"
                        type="text"
                        value={row.objectives[objective.name] ?? ""}
                        onChange={(event) => onObjectiveChange(row.candidateId, objective.name, event.target.value)}
                      />
                    </td>
                  ))}
                  <td>
                    <span className={`tag ${row.status === "complete" || row.status === "submitted" ? "success" : "warning"}`}>
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
        <span className="metric-label">Submitted observations</span>
        <strong>{observations.length}</strong>
      </div>
    </section>
  );
}

function formatCell(value: string | number | boolean | undefined) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : value.toPrecision(5);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return value ?? "-";
}
