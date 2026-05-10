"""Notebook-friendly helpers for running OptLab problems."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_SEED = 11


def run_builtin_zdt1(
    max_evals: int = 64,
    *,
    seed: int = DEFAULT_SEED,
    variable_count: int = 10,
    algorithm: str = "random",
) -> Any:
    """Run the built-in ZDT1 benchmark with float variables in [0, 1]."""

    evaluator = _make_evaluator({"type": "builtin", "name": "zdt1"})
    problem = _make_problem(
        variables=_default_variables(variable_count),
        objectives=_default_objectives(2),
        evaluator=evaluator,
        max_evals=max_evals,
        seed=seed,
        algorithm=algorithm,
    )
    return _run_problem(problem)


def run_python_plugin_problem(
    module_path: str | Path,
    *,
    function_name: str = "evaluate",
    variables: Iterable[Mapping[str, Any] | Any] | None = None,
    objectives: Iterable[Mapping[str, Any] | Any] | None = None,
    max_evals: int = 64,
    seed: int = DEFAULT_SEED,
    algorithm: str = "random",
) -> Any:
    """Run a trusted local Python evaluator module from a notebook."""

    evaluator = _make_evaluator(
        {
            "type": "python",
            "module_path": str(module_path),
            "function_name": function_name,
        }
    )
    problem = _make_problem(
        variables=variables or _default_variables(2),
        objectives=objectives or _default_objectives(2),
        evaluator=evaluator,
        max_evals=max_evals,
        seed=seed,
        algorithm=algorithm,
    )
    return _run_problem(problem)


def run_http_problem(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
    variables: Iterable[Mapping[str, Any] | Any] | None = None,
    objectives: Iterable[Mapping[str, Any] | Any] | None = None,
    max_evals: int = 64,
    seed: int = DEFAULT_SEED,
    algorithm: str = "random",
) -> Any:
    """Run an optimization against an HTTP evaluator endpoint."""

    evaluator = _make_evaluator(
        {
            "type": "http",
            "url": url,
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
        }
    )
    problem = _make_problem(
        variables=variables or _default_variables(2),
        objectives=objectives or _default_objectives(2),
        evaluator=evaluator,
        max_evals=max_evals,
        seed=seed,
        algorithm=algorithm,
    )
    return _run_problem(problem)


def _default_variables(count: int) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("variable_count must be at least 1")
    return [
        {"name": f"x{i + 1}", "type": "float", "lower": 0.0, "upper": 1.0}
        for i in range(count)
    ]


def _default_objectives(count: int) -> list[dict[str, str]]:
    return [{"name": f"f{i + 1}", "direction": "min"} for i in range(count)]


def _make_problem(
    *,
    variables: Iterable[Mapping[str, Any] | Any],
    objectives: Iterable[Mapping[str, Any] | Any],
    evaluator: Any,
    max_evals: int,
    seed: int,
    algorithm: str,
) -> Any:
    if max_evals < 1:
        raise ValueError("max_evals must be at least 1")

    BudgetSpec, _, _, ProblemSpec, VariableSpec = _model_classes()
    objective_spec = _model_classes()[2]
    return ProblemSpec(
        variables=[_coerce_model(VariableSpec, item) for item in variables],
        objectives=[_coerce_model(objective_spec, item) for item in objectives],
        evaluator=evaluator,
        budget=BudgetSpec(max_evals=max_evals, seed=seed),
        algorithm=algorithm,
    )


def _make_evaluator(payload: Mapping[str, Any]) -> Any:
    _, EvaluatorSpec, _, _, _ = _model_classes()
    return EvaluatorSpec(**dict(payload))


def _coerce_model(model_class: type, item: Mapping[str, Any] | Any) -> Any:
    if isinstance(item, Mapping):
        return model_class(**dict(item))
    return item


def _model_classes() -> tuple[type, type, type, type, type]:
    from optlab.core.models import BudgetSpec, EvaluatorSpec, ObjectiveSpec, ProblemSpec, VariableSpec

    return BudgetSpec, EvaluatorSpec, ObjectiveSpec, ProblemSpec, VariableSpec


def _run_problem(problem: Any) -> Any:
    from optlab.core.runner import run_problem

    return run_problem(problem)


__all__ = [
    "run_builtin_zdt1",
    "run_http_problem",
    "run_python_plugin_problem",
]
