from __future__ import annotations

from optlab.core.models import BudgetSpec, EvaluatorSpec, ObjectiveSpec, ProblemSpec, VariableSpec
from optlab.core.runner import run_problem


def benchmark_spec(name: str, objective_count: int, variable_count: int, seed: int) -> ProblemSpec:
    return ProblemSpec(
        variables=[
            VariableSpec(name=f"x{i + 1}", type="float", lower=0.0, upper=1.0)
            for i in range(variable_count)
        ],
        objectives=[ObjectiveSpec(name=f"f{i + 1}") for i in range(objective_count)],
        evaluator=EvaluatorSpec(type="builtin", name=name),
        budget=BudgetSpec(max_evals=48, seed=seed),
        algorithm="auto",
    )


def test_fixed_seed_reproduces_candidate_sequence_and_archive() -> None:
    spec = benchmark_spec("zdt1", objective_count=2, variable_count=10, seed=101)

    first = run_problem(spec)
    second = run_problem(spec)

    assert [record.variables for record in first.archive.records] == [
        record.variables for record in second.archive.records
    ]
    assert [record.minimized for record in first.archive.rank_zero()] == [
        record.minimized for record in second.archive.rank_zero()
    ]


def test_auto_algorithm_selects_nsga2_for_two_or_three_objectives() -> None:
    result = run_problem(benchmark_spec("dtlz2", objective_count=3, variable_count=10, seed=2))

    assert result.algorithm == "nsga2"
    assert result.metrics[-1].pareto_count > 0
    assert result.metrics[-1].feasible_ratio == 1.0


def test_auto_algorithm_selects_nsga3_for_four_to_six_objectives() -> None:
    result = run_problem(benchmark_spec("dtlz2", objective_count=6, variable_count=20, seed=3))

    assert result.algorithm == "nsga3"
    assert result.metrics[-1].pareto_count > 0
    assert result.metrics[-1].approximate_hypervolume is not None


def test_explicit_rvea_many_objective_run_is_available() -> None:
    spec = ProblemSpec(
        variables=[
            VariableSpec(name=f"x{i + 1}", type="float", lower=0.0, upper=1.0)
            for i in range(12)
        ],
        objectives=[ObjectiveSpec(name=f"f{i + 1}") for i in range(5)],
        evaluator=EvaluatorSpec(type="builtin", name="dtlz2"),
        budget=BudgetSpec(max_evals=48, seed=13),
        algorithm="rvea",
    )

    result = run_problem(spec)

    assert result.algorithm == "rvea"
    assert result.metrics[-1].pareto_count > 0


def test_benchmark_suite_includes_zdt2_and_dtlz7() -> None:
    zdt2 = run_problem(benchmark_spec("zdt2", objective_count=2, variable_count=10, seed=4))
    dtlz7 = run_problem(benchmark_spec("dtlz7", objective_count=4, variable_count=10, seed=5))

    assert zdt2.summary["evaluations"] == 48
    assert dtlz7.summary["evaluations"] >= 48
    assert zdt2.metrics[-1].pareto_count > 0
    assert dtlz7.metrics[-1].pareto_count > 0
