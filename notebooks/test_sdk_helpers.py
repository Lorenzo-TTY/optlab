from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VariableSpec:
    name: str
    type: str
    lower: float | None = None
    upper: float | None = None
    choices: list[str] | None = None


@dataclass
class ObjectiveSpec:
    name: str
    direction: str = "min"


@dataclass
class BudgetSpec:
    max_evals: int
    seed: int


@dataclass
class EvaluatorSpec:
    type: str
    name: str | None = None
    module_path: str | None = None
    function_name: str | None = None
    url: str | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None


@dataclass
class ProblemSpec:
    variables: list[VariableSpec]
    objectives: list[ObjectiveSpec]
    evaluator: EvaluatorSpec
    budget: BudgetSpec
    algorithm: str = "auto"


def install_fake_core(monkeypatch):
    captured = {}

    def run_problem(problem):
        captured["problem"] = problem
        return types.SimpleNamespace(summary={"evaluations": problem.budget.max_evals})

    models = types.ModuleType("optlab.core.models")
    models.VariableSpec = VariableSpec
    models.ObjectiveSpec = ObjectiveSpec
    models.BudgetSpec = BudgetSpec
    models.EvaluatorSpec = EvaluatorSpec
    models.ProblemSpec = ProblemSpec

    runner = types.ModuleType("optlab.core.runner")
    runner.run_problem = run_problem

    monkeypatch.setitem(sys.modules, "optlab.core.models", models)
    monkeypatch.setitem(sys.modules, "optlab.core.runner", runner)
    return captured


def load_sdk():
    sys.modules.pop("optlab.sdk", None)
    return importlib.import_module("optlab.sdk")


def test_run_builtin_zdt1_builds_standard_problem_and_runs(monkeypatch):
    captured = install_fake_core(monkeypatch)
    sdk = load_sdk()

    result = sdk.run_builtin_zdt1(max_evals=16, seed=99)

    problem = captured["problem"]
    assert result.summary == {"evaluations": 16}
    assert problem.evaluator == EvaluatorSpec(type="builtin", name="zdt1")
    assert problem.budget == BudgetSpec(max_evals=16, seed=99)
    assert problem.algorithm == "random"
    assert [variable.name for variable in problem.variables] == [f"x{i + 1}" for i in range(10)]
    assert [objective.name for objective in problem.objectives] == ["f1", "f2"]


def test_run_python_plugin_problem_accepts_notebook_defaults(monkeypatch, tmp_path: Path):
    captured = install_fake_core(monkeypatch)
    sdk = load_sdk()
    plugin = tmp_path / "plugin.py"

    sdk.run_python_plugin_problem(plugin, function_name="score", max_evals=8)

    problem = captured["problem"]
    assert problem.evaluator == EvaluatorSpec(
        type="python",
        module_path=str(plugin),
        function_name="score",
    )
    assert problem.budget.max_evals == 8
    assert [variable.name for variable in problem.variables] == ["x1", "x2"]


def test_run_http_problem_accepts_url_timeout_and_retries(monkeypatch):
    captured = install_fake_core(monkeypatch)
    sdk = load_sdk()

    sdk.run_http_problem("http://127.0.0.1:8000/evaluate", timeout_seconds=3.5, max_retries=1)

    assert captured["problem"].evaluator == EvaluatorSpec(
        type="http",
        url="http://127.0.0.1:8000/evaluate",
        timeout_seconds=3.5,
        max_retries=1,
    )
