from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from optlab.api.main import create_app
from optlab.core.advisor import AdvisorRequest, suggest_candidates
from optlab.core.models import BudgetSpec, EvaluatorSpec, ObjectiveSpec, ProblemSpec, VariableSpec


def make_problem(n_var: int = 4, n_obj: int = 2) -> ProblemSpec:
    return ProblemSpec(
        variables=[
            VariableSpec(name=f"x{i + 1}", type="float", lower=-5.0, upper=5.0)
            for i in range(n_var)
        ],
        objectives=[
            ObjectiveSpec(name=f"f{i + 1}", direction="min" if i % 2 == 0 else "max")
            for i in range(n_obj)
        ],
        evaluator=EvaluatorSpec(type="builtin", name="dtlz2"),
        budget=BudgetSpec(max_evals=64, seed=17),
    )


def test_initial_lhs_suggestions_are_deterministic_and_within_bounds() -> None:
    problem = make_problem(n_var=3, n_obj=2)
    request = AdvisorRequest(problem=problem, observations=[], batch_size=3, seed=101)

    first = suggest_candidates(request)
    second = suggest_candidates(request)

    assert first.phase == "initial"
    assert first.algorithm == "lhs"
    assert first.suggestions == second.suggestions
    assert len(first.suggestions) == 3
    for suggestion in first.suggestions:
        assert suggestion.candidate_id.startswith("suggest_")
        assert set(suggestion.variables) == {"x1", "x2", "x3"}
        assert all(-5.0 <= value <= 5.0 for value in suggestion.variables.values())


def test_surrogate_suggestions_avoid_observed_candidates_after_initial_design() -> None:
    problem = make_problem(n_var=2, n_obj=2)
    initial = suggest_candidates(AdvisorRequest(problem=problem, observations=[], batch_size=10, seed=7))
    observations = []
    for index, suggestion in enumerate(initial.suggestions):
        x1 = suggestion.variables["x1"]
        x2 = suggestion.variables["x2"]
        observations.append(
            {
                "candidateId": suggestion.candidate_id,
                "variables": suggestion.variables,
                "objectives": {"f1": (x1 - 1.0) ** 2 + x2**2, "f2": -((x1 + 1.0) ** 2 + x2**2)},
                "constraints": {},
                "metadata": {"index": index},
            }
        )

    response = suggest_candidates(AdvisorRequest(problem=problem, observations=observations, batch_size=2, seed=7))

    assert response.phase == "surrogate"
    assert response.algorithm == "parego-idw"
    observed_vectors = {
        tuple(round(obs["variables"][name], 8) for name in problem.variable_names) for obs in observations
    }
    for suggestion in response.suggestions:
        vector = tuple(round(suggestion.variables[name], 8) for name in problem.variable_names)
        assert vector not in observed_vectors


def test_many_objective_visualization_policy_prefers_parallel_coordinates() -> None:
    response = suggest_candidates(
        AdvisorRequest(problem=make_problem(n_var=6, n_obj=6), observations=[], batch_size=1, seed=3)
    )

    assert response.visualization.recommended_view == "parallel-coordinates"
    assert response.visualization.objective_names == ["f1", "f2", "f3", "f4", "f5", "f6"]
    assert "projection2d" in response.visualization.supporting_views


def test_advisor_api_returns_suggestions(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)
    payload = make_problem(n_var=2, n_obj=3).model_dump(mode="json")

    response = client.post(
        "/api/advisor/suggest",
        json={"problem": payload, "observations": [], "batchSize": 2, "seed": 13},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "initial"
    assert body["algorithm"] == "lhs"
    assert len(body["suggestions"]) == 2
    assert body["visualization"]["recommendedView"] == "scatter3d"


def test_advisor_rejects_observations_missing_objectives() -> None:
    problem = make_problem(n_var=2, n_obj=2)
    with pytest.raises(ValueError, match="missing objective"):
        AdvisorRequest(
            problem=problem,
            observations=[
                {
                    "candidateId": "bad",
                    "variables": {"x1": 0.0, "x2": 0.0},
                    "objectives": {"f1": 1.0},
                }
            ],
            batch_size=1,
            seed=1,
        )
