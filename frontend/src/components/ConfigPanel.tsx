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

  return (
    <section className="panel config-panel" aria-labelledby="config-title">
      <div className="section-heading">
        <div>
          <h2 id="config-title">Problem Setup</h2>
          <p>Set dimensions first, then define every parameter and objective row explicitly.</p>
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
            type="text"
            value={problem.budget.seed}
            onChange={(event) =>
              onChange({ ...problem, budget: { ...problem.budget, seed: clampInteger(Number(event.target.value), 0, 999999) } })
            }
          />
        </label>
      </div>

      <div className="definition-stack">
        <VariableDefinitionTable variables={problem.variables} onChange={updateVariable} />
        <ObjectiveDefinitionTable objectives={problem.objectives} onChange={updateObjective} />
      </div>

      <div className="action-row">
        <button className="primary-button" disabled={disabled} type="button" onClick={onAsk}>
          Get algorithm suggestion
        </button>
      </div>

      <p className="validation-note">{message}</p>
    </section>
  );
}

function VariableDefinitionTable({
  variables,
  onChange,
}: {
  variables: VariableDefinition[];
  onChange: (index: number, patch: Partial<VariableDefinition>) => void;
}) {
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
                    value={variable.name}
                    onChange={(event) => onChange(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`Parameter ${index + 1} type`}
                    value={variable.type}
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
                    disabled={variable.type === "bool" || variable.type === "categorical"}
                    type="number"
                    value={variable.lower ?? 0}
                    onChange={(event) => onChange(index, { lower: Number(event.target.value) })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`${variable.name} upper`}
                    disabled={variable.type === "bool" || variable.type === "categorical"}
                    type="number"
                    value={variable.upper ?? 1}
                    onChange={(event) => onChange(index, { upper: Number(event.target.value) })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`${variable.name} scale`}
                    disabled={variable.type === "bool" || variable.type === "categorical"}
                    value={variable.scale}
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
  objectives,
  onChange,
}: {
  objectives: ObjectiveDefinition[];
  onChange: (index: number, patch: Partial<ObjectiveDefinition>) => void;
}) {
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
                    value={objective.name}
                    onChange={(event) => onChange(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`${objective.name} direction`}
                    value={objective.direction}
                    onChange={(event) => onChange(index, { direction: event.target.value as "min" | "max" })}
                  >
                    <option value="min">min</option>
                    <option value="max">max</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`${objective.name} unit`}
                    value={objective.unit ?? ""}
                    onChange={(event) => onChange(index, { unit: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={`${objective.name} threshold`}
                    type="number"
                    value={objective.threshold ?? ""}
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

function clampInteger(value: number, lower: number, upper: number): number {
  const integer = Number.isFinite(value) ? Math.trunc(value) : lower;
  return Math.max(lower, Math.min(upper, integer));
}
