from __future__ import annotations

import math

import pytest

from optlab.core.archive import CandidateRecord, ParetoArchive, dominates
from optlab.core.encoding import decode_vector, encode_variables
from optlab.core.metrics import compute_metric_snapshot
from optlab.core.models import (
    BudgetSpec,
    EvaluatorSpec,
    ObjectiveSpec,
    ProblemSpec,
    VariableSpec,
)


def make_problem(objective_count: int = 2) -> ProblemSpec:
    return ProblemSpec(
        variables=[
            VariableSpec(name="x", type="float", lower=0.0, upper=10.0),
            VariableSpec(name="n", type="int", lower=1, upper=5),
            VariableSpec(name="mode", type="categorical", choices=["a", "b", "c"]),
            VariableSpec(name="flag", type="bool"),
        ],
        objectives=[
            ObjectiveSpec(name=f"f{i + 1}", direction="min" if i % 2 == 0 else "max")
            for i in range(objective_count)
        ],
        evaluator=EvaluatorSpec(type="builtin", name="dtlz2"),
        budget=BudgetSpec(max_evals=64, seed=123),
    )


def test_variable_encoding_round_trips_numeric_and_discrete_values() -> None:
    problem = make_problem()
    raw = {"x": 2.5, "n": 4, "mode": "b", "flag": True}

    encoded = encode_variables(problem.variables, raw)
    decoded = decode_vector(problem.variables, encoded)

    assert encoded == pytest.approx([0.25, 0.75, 0.5, 1.0])
    assert decoded == raw


def test_max_objectives_are_converted_to_internal_minimization() -> None:
    problem = make_problem(objective_count=3)

    values = problem.to_minimized_objectives({"f1": 1.0, "f2": 5.0, "f3": -2.0})

    assert values == pytest.approx([1.0, -5.0, -2.0])


def test_archive_rank_zero_records_are_feasible_and_non_dominated() -> None:
    archive = ParetoArchive()
    archive.add(
        CandidateRecord(
            candidate_id="a",
            generation=0,
            variables={"x": 0.0},
            objectives={"f1": 1.0, "f2": 4.0},
            minimized=[1.0, 4.0],
            constraints={},
            feasible=True,
        )
    )
    archive.add(
        CandidateRecord(
            candidate_id="b",
            generation=0,
            variables={"x": 1.0},
            objectives={"f1": 2.0, "f2": 2.0},
            minimized=[2.0, 2.0],
            constraints={},
            feasible=True,
        )
    )
    archive.add(
        CandidateRecord(
            candidate_id="dominated",
            generation=0,
            variables={"x": 2.0},
            objectives={"f1": 3.0, "f2": 5.0},
            minimized=[3.0, 5.0],
            constraints={},
            feasible=True,
        )
    )
    archive.add(
        CandidateRecord(
            candidate_id="infeasible",
            generation=0,
            variables={"x": 3.0},
            objectives={"f1": 0.1, "f2": 0.1},
            minimized=[0.1, 0.1],
            constraints={"g1": 1.0},
            feasible=False,
        )
    )

    front = archive.rank_zero()

    assert {item.candidate_id for item in front} == {"a", "b"}
    assert all(item.feasible for item in front)
    assert not any(dominates(left.minimized, right.minimized) for left in front for right in front if left != right)


def test_metric_snapshot_reports_monotonic_two_dimensional_hypervolume() -> None:
    archive = ParetoArchive()
    archive.add(
        CandidateRecord(
            candidate_id="a",
            generation=0,
            variables={},
            objectives={"f1": 3.0, "f2": 3.0},
            minimized=[3.0, 3.0],
            constraints={},
            feasible=True,
        )
    )
    first = compute_metric_snapshot(archive, objective_names=["f1", "f2"], reference_point=[5.0, 5.0])
    archive.add(
        CandidateRecord(
            candidate_id="b",
            generation=1,
            variables={},
            objectives={"f1": 1.0, "f2": 4.0},
            minimized=[1.0, 4.0],
            constraints={},
            feasible=True,
        )
    )
    second = compute_metric_snapshot(archive, objective_names=["f1", "f2"], reference_point=[5.0, 5.0])

    assert first.hypervolume is not None
    assert second.hypervolume is not None
    assert math.isfinite(second.hypervolume)
    assert second.hypervolume >= first.hypervolume
    assert second.pareto_count == 2


def test_problem_spec_rejects_out_of_scope_dimensions() -> None:
    with pytest.raises(ValueError, match="at most 30"):
        ProblemSpec(
            variables=[VariableSpec(name=f"x{i}", type="float", lower=0.0, upper=1.0) for i in range(31)],
            objectives=[ObjectiveSpec(name="f1")],
            evaluator=EvaluatorSpec(type="builtin", name="zdt1"),
            budget=BudgetSpec(max_evals=10, seed=1),
        )

    with pytest.raises(ValueError, match="at most 6"):
        ProblemSpec(
            variables=[VariableSpec(name="x", type="float", lower=0.0, upper=1.0)],
            objectives=[ObjectiveSpec(name=f"f{i}") for i in range(7)],
            evaluator=EvaluatorSpec(type="builtin", name="dtlz2"),
            budget=BudgetSpec(max_evals=10, seed=1),
        )

