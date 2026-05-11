from __future__ import annotations

import pytest
import numpy as np
from fastapi.testclient import TestClient

from optlab.api.main import create_app
from optlab.core import advisor
from optlab.core.advisor import AdvisorRequest, suggest_candidates
from optlab.core.designs import space_filling_design
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


def test_initial_space_filling_suggestions_are_deterministic_and_within_bounds() -> None:
    problem = make_problem(n_var=3, n_obj=2)
    request = AdvisorRequest(problem=problem, observations=[], batch_size=3, seed=101)

    first = suggest_candidates(request)
    second = suggest_candidates(request)

    assert first.phase == "initial"
    assert first.algorithm == "sobol-lhs-maximin"
    assert first.suggestions == second.suggestions
    assert len(first.suggestions) == 3
    for suggestion in first.suggestions:
        assert suggestion.candidate_id.startswith("suggest_")
        assert set(suggestion.variables) == {"x1", "x2", "x3"}
        assert all(-5.0 <= value <= 5.0 for value in suggestion.variables.values())


def test_surrogate_suggestions_avoid_observed_candidates_after_initial_design() -> None:
    problem = make_problem(n_var=2, n_obj=2)
    initial = suggest_candidates(AdvisorRequest(problem=problem, observations=[], batch_size=12, seed=7))
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
    assert response.algorithm == "ensemble-mobo"
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
    assert body["algorithm"] == "sobol-lhs-maximin"
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


def test_manual_observations_with_arbitrary_ids_feed_surrogate_deterministically() -> None:
    problem = make_problem(n_var=2, n_obj=2)
    observations = [
        {
            "candidateId": f"manual_{index:06d}",
            "variables": {"x1": -5.0 + 10.0 * index / 11.0, "x2": 5.0 - 10.0 * index / 11.0},
            "objectives": {"f1": float(index), "f2": -float(index)},
            "constraints": {},
        }
        for index in range(12)
    ]

    request = AdvisorRequest(problem=problem, observations=observations, batch_size=3, seed=19)

    first = suggest_candidates(request)
    second = suggest_candidates(request)

    assert first.phase == "surrogate"
    assert first.algorithm == "ensemble-mobo"
    assert first.suggestions == second.suggestions
    assert len(first.suggestions) == 3


def test_ensemble_mobo_returns_deterministic_unique_suggestions_after_enough_observations() -> None:
    problem = make_problem(n_var=6, n_obj=3)
    observations = [
        {
            "candidateId": f"manual_{index:06d}",
            "variables": {
                variable.name: -5.0 + 10.0 * ((index + dim * 7) % 31) / 30.0
                for dim, variable in enumerate(problem.variables)
            },
            "objectives": {
                "f1": float(index % 11) + 0.01 * index,
                "f2": -float((index * 3) % 13) + 0.02 * index,
                "f3": float((index * 5) % 17) - 0.03 * index,
            },
            "constraints": {},
        }
        for index in range(24)
    ]
    request = AdvisorRequest(problem=problem, observations=observations, batch_size=6, seed=29)

    first = suggest_candidates(request)
    second = suggest_candidates(request)

    assert first.phase == "surrogate"
    assert first.algorithm == "ensemble-mobo"
    assert first.suggestions == second.suggestions
    assert len(first.suggestions) == 6
    assert all("full GP/RF/NN ensemble" in suggestion.reason for suggestion in first.suggestions)
    assert all("actual models: gp/rf/nn" in suggestion.reason for suggestion in first.suggestions)
    suggested_vectors = [
        tuple(round(float(suggestion.variables[name]), 10) for name in problem.variable_names)
        for suggestion in first.suggestions
    ]
    observed_vectors = [
        tuple(round(float(observation["variables"][name]), 10) for name in problem.variable_names)
        for observation in observations
    ]
    assert len(set(suggested_vectors)) == len(suggested_vectors)
    assert set(suggested_vectors).isdisjoint(observed_vectors)


def test_surrogate_prediction_ensemble_uses_gp_rf_and_nn_when_sklearn_is_available() -> None:
    x_train = space_filling_design(n_samples=24, n_dim=3, seed=123)
    y_train = np.sin(3.0 * x_train[:, 0]) + 0.4 * x_train[:, 1] ** 2 - 0.2 * x_train[:, 2]
    pool = space_filling_design(n_samples=32, n_dim=3, seed=456, existing=x_train)

    predictions = advisor._surrogate_predictions(pool, x_train, y_train, np.random.default_rng(5), seed=99)

    assert {name for name, _, _ in predictions} == {"gp", "rf", "nn"}
    for _, prediction, uncertainty in predictions:
        assert prediction.shape == (32,)
        assert uncertainty.shape == (32,)
        assert np.all(np.isfinite(prediction))
        assert np.all(np.isfinite(uncertainty))


def test_surrogate_reason_discloses_idw_fallback_when_models_are_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = make_problem(n_var=2, n_obj=2)
    observations = [
        {
            "candidateId": f"manual_{index:06d}",
            "variables": {"x1": -5.0 + index * (10.0 / 11.0), "x2": 5.0 - index * (10.0 / 11.0)},
            "objectives": {"f1": float(index), "f2": -float(index)},
            "constraints": {},
        }
        for index in range(12)
    ]
    monkeypatch.setattr(advisor, "_surrogate_predictions", lambda *args, **kwargs: [])

    response = suggest_candidates(AdvisorRequest(problem=problem, observations=observations, batch_size=1, seed=31))

    assert response.phase == "surrogate"
    assert response.algorithm == "ensemble-mobo"
    assert "degraded ensemble (idw)" in response.suggestions[0].reason
    assert "actual models: idw" in response.suggestions[0].reason


def test_advisor_rejects_empty_observation_ids_and_out_of_range_variables() -> None:
    problem = make_problem(n_var=2, n_obj=2)
    with pytest.raises(ValueError, match="candidateId must not be empty"):
        AdvisorRequest(
            problem=problem,
            observations=[
                {
                    "candidateId": " ",
                    "variables": {"x1": 0.0, "x2": 0.0},
                    "objectives": {"f1": 1.0, "f2": 1.0},
                }
            ],
            batch_size=1,
            seed=1,
        )

    with pytest.raises(ValueError, match="within"):
        AdvisorRequest(
            problem=problem,
            observations=[
                {
                    "candidateId": "manual_out_of_bounds",
                    "variables": {"x1": 10.0, "x2": 0.0},
                    "objectives": {"f1": 1.0, "f2": 1.0},
                }
            ],
            batch_size=1,
            seed=1,
        )


def test_advisor_normalizes_string_boolean_observations() -> None:
    problem = ProblemSpec(
        variables=[VariableSpec(name="enabled", type="bool")],
        objectives=[ObjectiveSpec(name="f1")],
        evaluator=EvaluatorSpec(type="builtin", name="manual"),
        budget=BudgetSpec(max_evals=64, seed=17),
    )

    request = AdvisorRequest(
        problem=problem,
        observations=[
            {
                "candidateId": "manual_bool_false",
                "variables": {"enabled": "false"},
                "objectives": {"f1": 1.0},
            }
        ],
        batch_size=1,
        seed=1,
    )

    assert request.observations[0].variables["enabled"] is False
