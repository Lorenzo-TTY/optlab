# OptLab API Contract

This v1 contract is shared by the core runner, evaluators, HTTP API, and the
notebook SDK in `optlab.sdk`. The executable contract lives in backend tests;
this document records the stable payload shape expected by examples and clients.

## Unified Evaluator Return

Every evaluator type returns the same logical object:

```json
{
  "objectives": {"f1": 0.25, "f2": 0.75},
  "constraints": {},
  "metadata": {"source": "example"}
}
```

- `objectives` is required and maps objective names to numeric values.
- `constraints` is optional for callers but normalized to `{}` by evaluators.
  Values less than or equal to zero are feasible; positive values are violations.
- `metadata` is optional for callers and normalized to `{}`. It is for diagnostic
  data only and must not be used as an optimization objective.
- Evaluator failures are normalized by the evaluator layer before they reach
  callers of `run_problem`.

## HTTP Evaluator Request

HTTP evaluators receive a `POST` request at the configured URL. The request body
uses camelCase identifiers for wire compatibility:

```json
{
  "jobId": "job_123",
  "candidateId": "cand_1",
  "variables": {"x1": 0.2, "x2": 0.8},
  "context": {"seed": 11}
}
```

The endpoint must respond with the unified evaluator return shape above. SDK
helpers expose `timeout_seconds` and `max_retries`; timeout and transport
failures are reported as normalized evaluator errors by the backend evaluator.

## Core Python API

The notebook SDK builds `ProblemSpec` instances from `optlab.core.models` and
runs them with `optlab.core.runner.run_problem`.

Primary helper functions:

```python
from optlab.sdk import run_builtin_zdt1, run_http_problem, run_python_plugin_problem

result = run_builtin_zdt1(max_evals=64)

plugin_result = run_python_plugin_problem(
    "my_plugin.py",
    function_name="evaluate",
    max_evals=64,
)

http_result = run_http_problem(
    "http://127.0.0.1:8000/evaluate",
    timeout_seconds=10.0,
    max_retries=2,
    max_evals=64,
)
```

Default SDK assumptions:

- `run_builtin_zdt1` uses evaluator `{type: "builtin", name: "zdt1"}`, two
  minimization objectives named `f1` and `f2`, and ten float variables `x1..x10`
  in `[0, 1]`.
- `run_python_plugin_problem` and `run_http_problem` default to two float
  variables `x1`, `x2` and two minimization objectives `f1`, `f2`.
- All helpers accept `max_evals`, `seed`, and `algorithm`; `algorithm` defaults
  to `"random"` so notebook examples honor small `max_evals` values exactly.
  Pass `algorithm="auto"` to use core algorithm selection.

## HTTP API

The backend API is expected to expose these main endpoints:

- `POST /api/configs/validate`: validate a problem config and return
  `{valid: true, summary: ...}` for accepted configs.
- `POST /api/advisor/suggest`: ask the interactive advisor for the next
  candidate variables. The request is stateless and includes `{problem,
  observations, batchSize, seed}`. The response contains `{phase, algorithm,
  suggestions, visualization}`.
- `POST /api/jobs`: create and start an optimization job. Returns `{jobId: ...}`.
- `GET /api/jobs/{job_id}`: return job status, evaluation count, and Pareto
  count. Terminal statuses are `completed`, `failed`, and `cancelled`.
- `POST /api/jobs/{job_id}/cancel`: request cancellation for a running job.
- `GET /api/jobs/{job_id}/results`: return all evaluations and the Pareto front.
- `GET /api/jobs/{job_id}/export.csv`: export job results as CSV.
- `GET /api/jobs/{job_id}/export.json`: export job results as JSON.
- `WS /ws/jobs/{job_id}`: stream or replay job events such as `job.started` and
  `evaluation.completed`.

Advisor request example:

```json
{
  "problem": {
    "variables": [{"name": "x1", "type": "float", "lower": 0, "upper": 1}],
    "objectives": [{"name": "f1", "direction": "min"}, {"name": "f2", "direction": "min"}],
    "constraints": [],
    "evaluator": {"type": "builtin", "name": "manual"},
    "budget": {"max_evals": 200, "seed": 11},
    "algorithm": "auto"
  },
  "observations": [
    {
      "candidateId": "suggest_000001",
      "variables": {"x1": 0.42},
      "objectives": {"f1": 0.12, "f2": 0.88},
      "constraints": {},
      "metadata": {}
    }
  ],
  "batchSize": 1,
  "seed": 11
}
```

## Stability Notes

Core modules are the source of truth for validation limits and algorithm
selection. At the time this SDK contract was written, the expected public imports
were:

- `optlab.core.models.BudgetSpec`
- `optlab.core.models.EvaluatorSpec`
- `optlab.core.models.ObjectiveSpec`
- `optlab.core.models.ProblemSpec`
- `optlab.core.models.VariableSpec`
- `optlab.core.runner.run_problem`

If those core modules are still in progress, the SDK assumes their constructor
fields match the backend tests already present in the repository.
