from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .archive import dominates
from .encoding import encode_variables, decode_vector
from .models import EvaluationResult, ProblemSpec, VariableSpec


class AdvisorObservation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    candidate_id: str = Field(alias="candidateId")
    variables: dict[str, Any]
    objectives: dict[str, float]
    constraints: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("candidate_id")
    @classmethod
    def candidate_id_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("candidateId must not be empty")
        return value


class AdvisorRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    problem: ProblemSpec
    observations: list[AdvisorObservation] = Field(default_factory=list)
    batch_size: int = Field(default=1, alias="batchSize", ge=1, le=16)
    seed: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_observations(self) -> "AdvisorRequest":
        seen_ids: set[str] = set()
        for observation in self.observations:
            if observation.candidate_id in seen_ids:
                raise ValueError(f"duplicate observation '{observation.candidate_id}'")
            seen_ids.add(observation.candidate_id)
            _validate_observation_variables(self.problem, observation)
            encode_variables(self.problem.variables, observation.variables)
            EvaluationResult(
                objectives=observation.objectives,
                constraints=observation.constraints,
                metadata=observation.metadata,
            )
            self.problem.to_minimized_objectives(observation.objectives)
        return self


class AdvisorSuggestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str = Field(alias="candidateId")
    variables: dict[str, Any]
    reason: str


class VisualizationPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommended_view: Literal["scatter2d", "scatter3d", "parallel-coordinates"] = Field(
        alias="recommendedView"
    )
    supporting_views: list[str] = Field(default_factory=list, alias="supportingViews")
    objective_names: list[str] = Field(default_factory=list, alias="objectiveNames")


class AdvisorResponse(BaseModel):
    phase: Literal["initial", "surrogate"]
    algorithm: Literal["lhs", "parego-idw"]
    suggestions: list[AdvisorSuggestion]
    visualization: VisualizationPolicy


def suggest_candidates(request: AdvisorRequest) -> AdvisorResponse:
    observed_count = len(request.observations)
    initial_target = _initial_design_size(request.problem)
    phase: Literal["initial", "surrogate"] = "initial" if observed_count < initial_target else "surrogate"
    if phase == "initial":
        suggestions = _initial_suggestions(request, initial_target)
        algorithm: Literal["lhs", "parego-idw"] = "lhs"
    else:
        suggestions = _surrogate_suggestions(request)
        algorithm = "parego-idw"

    return AdvisorResponse(
        phase=phase,
        algorithm=algorithm,
        suggestions=suggestions,
        visualization=_visualization_policy(request.problem),
    )


def _initial_design_size(problem: ProblemSpec) -> int:
    return min(problem.budget.max_evals, max(6, min(24, 2 * len(problem.variables)), len(problem.objectives) + 1))


def _initial_suggestions(request: AdvisorRequest, initial_target: int) -> list[AdvisorSuggestion]:
    n_dim = len(request.problem.variables)
    observed = _observed_vectors(request)
    design_size = max(initial_target, len(request.observations) + request.batch_size)
    design = _latin_hypercube(design_size, n_dim, request.seed)
    suggestions: list[AdvisorSuggestion] = []
    index = len(request.observations)

    for vector in design:
        if _is_duplicate(vector, observed) or _is_duplicate(vector, [np.asarray(_encode_suggestion(s), dtype=float) for s in suggestions]):
            continue
        index += 1
        suggestions.append(
            AdvisorSuggestion(
                candidateId=f"suggest_{index:06d}",
                variables=decode_vector(request.problem.variables, vector.tolist()),
                reason="Latin hypercube initial design covers the encoded parameter space.",
            )
        )
        if len(suggestions) >= request.batch_size:
            break

    return suggestions


def _surrogate_suggestions(request: AdvisorRequest) -> list[AdvisorSuggestion]:
    rng = np.random.default_rng(request.seed + 7919 * (len(request.observations) + 1))
    x_obs = np.asarray(_observed_vectors(request), dtype=float)
    y_obs = np.asarray([request.problem.to_minimized_objectives(obs.objectives) for obs in request.observations], dtype=float)
    y_norm = _normalize_columns(y_obs)
    weights = rng.dirichlet(np.ones(y_norm.shape[1]))
    scalar = _augmented_tchebycheff(y_norm, weights)

    pool = _candidate_pool(rng, request.problem, x_obs)
    selected: list[np.ndarray] = []
    suggestions: list[AdvisorSuggestion] = []
    next_index = len(request.observations) + 1

    while len(suggestions) < request.batch_size and len(pool) > 0:
        scores = _idw_expected_score(pool, x_obs, scalar)
        if selected:
            selected_array = np.vstack(selected)
            selected_distance = _pairwise_distances(pool, selected_array).min(axis=1)
            scores += 0.2 * np.exp(-selected_distance * max(4.0, len(request.problem.variables)))
        scores += np.asarray([1.0e6 if _is_duplicate(row, x_obs) else 0.0 for row in pool])
        winner_index = int(np.argmin(scores))
        vector = np.clip(pool[winner_index], 0.0, 1.0)
        if not _is_duplicate(vector, x_obs) and not _is_duplicate(vector, selected):
            selected.append(vector)
            suggestions.append(
                AdvisorSuggestion(
                    candidateId=f"suggest_{next_index:06d}",
                    variables=decode_vector(request.problem.variables, vector.tolist()),
                    reason="ParEGO scalarization with inverse-distance surrogate uncertainty search.",
                )
            )
            next_index += 1
        pool = np.delete(pool, winner_index, axis=0)

    if len(suggestions) < request.batch_size:
        fallback = _initial_suggestions(request, len(request.observations) + request.batch_size)
        used_ids = {suggestion.candidate_id for suggestion in suggestions}
        suggestions.extend([item for item in fallback if item.candidate_id not in used_ids])
    return suggestions[: request.batch_size]


def _candidate_pool(rng: np.random.Generator, problem: ProblemSpec, x_obs: np.ndarray) -> np.ndarray:
    n_dim = len(problem.variables)
    lhs_count = max(512, 64 * n_dim)
    random_pool = _latin_hypercube(lhs_count, n_dim, int(rng.integers(0, 2**31 - 1)))
    front_pool = _pareto_perturbation_pool(rng, problem, x_obs)
    return np.vstack([random_pool, front_pool]) if len(front_pool) else random_pool


def _pareto_perturbation_pool(
    rng: np.random.Generator,
    problem: ProblemSpec,
    x_obs: np.ndarray,
) -> np.ndarray:
    if len(x_obs) == 0:
        return np.empty((0, len(problem.variables)))
    scale = max(0.04, 0.18 / np.sqrt(len(problem.variables)))
    repeats = max(4, 96 // max(1, len(x_obs)))
    noise = rng.normal(0.0, scale, size=(len(x_obs) * repeats, len(problem.variables)))
    anchors = np.repeat(x_obs, repeats, axis=0)
    return np.clip(anchors + noise, 0.0, 1.0)


def _observed_vectors(request: AdvisorRequest) -> list[np.ndarray]:
    return [
        np.asarray(encode_variables(request.problem.variables, observation.variables), dtype=float)
        for observation in request.observations
    ]


def _encode_suggestion(suggestion: AdvisorSuggestion) -> list[float]:
    return [float(value) if isinstance(value, (float, int)) else 0.0 for value in suggestion.variables.values()]


def _latin_hypercube(n_samples: int, n_dim: int, seed: int) -> np.ndarray:
    if n_samples <= 0 or n_dim <= 0:
        return np.empty((0, max(0, n_dim)))
    rng = np.random.default_rng(seed)
    samples = np.empty((n_samples, n_dim), dtype=float)
    for dim in range(n_dim):
        samples[:, dim] = (rng.permutation(n_samples) + rng.random(n_samples)) / n_samples
    return np.clip(samples, 0.0, 1.0)


def _normalize_columns(values: np.ndarray) -> np.ndarray:
    lower = values.min(axis=0)
    upper = values.max(axis=0)
    span = np.where((upper - lower) > 1.0e-12, upper - lower, 1.0)
    return (values - lower) / span


def _augmented_tchebycheff(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    weighted = values * weights
    return weighted.max(axis=1) + 0.05 * weighted.sum(axis=1)


def _idw_expected_score(pool: np.ndarray, x_obs: np.ndarray, scalar: np.ndarray) -> np.ndarray:
    distances = _pairwise_distances(pool, x_obs)
    nearest = distances.min(axis=1)
    weights = 1.0 / (distances**2 + 1.0e-9)
    prediction = (weights @ scalar) / weights.sum(axis=1)
    return prediction - 0.15 * nearest


def _pairwise_distances(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    if len(right) == 0:
        return np.full((len(left), 1), 1.0)
    diff = left[:, None, :] - right[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def _is_duplicate(vector: np.ndarray, existing: list[np.ndarray] | np.ndarray, eps: float = 1.0e-8) -> bool:
    if len(existing) == 0:
        return False
    existing_array = np.asarray(existing, dtype=float)
    if existing_array.ndim == 1:
        existing_array = existing_array.reshape(1, -1)
    return bool(np.any(np.linalg.norm(existing_array - vector, axis=1) <= eps))


def _visualization_policy(problem: ProblemSpec) -> VisualizationPolicy:
    names = problem.objective_names
    if len(names) <= 2:
        return VisualizationPolicy(
            recommendedView="scatter2d",
            supportingViews=["parallel-coordinates", "best-per-objective"],
            objectiveNames=names,
        )
    if len(names) == 3:
        return VisualizationPolicy(
            recommendedView="scatter3d",
            supportingViews=["scatter2d", "parallel-coordinates"],
            objectiveNames=names,
        )
    return VisualizationPolicy(
        recommendedView="parallel-coordinates",
        supportingViews=["projection2d", "scatter-matrix", "best-per-objective"],
        objectiveNames=names,
    )


def non_dominated_observations(request: AdvisorRequest) -> list[AdvisorObservation]:
    minimized = [request.problem.to_minimized_objectives(obs.objectives) for obs in request.observations]
    front: list[AdvisorObservation] = []
    for index, observation in enumerate(request.observations):
        if not any(other != index and dominates(values, minimized[index]) for other, values in enumerate(minimized)):
            front.append(observation)
    return front


def _validate_observation_variables(problem: ProblemSpec, observation: AdvisorObservation) -> None:
    for variable in problem.variables:
        if variable.name not in observation.variables:
            if variable.default is None:
                raise ValueError(f"missing variable '{variable.name}'")
            observation.variables[variable.name] = variable.default
        observation.variables[variable.name] = _normalize_observation_variable(variable, observation.variables[variable.name])


def _normalize_observation_variable(variable: VariableSpec, value: Any) -> Any:
    if variable.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError(f"invalid boolean value for '{variable.name}'")

    if variable.type == "categorical":
        choices = list(variable.choices or [])
        if value not in choices:
            raise ValueError(f"invalid choice for '{variable.name}'")
        return value

    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"variable '{variable.name}' must be finite")
    lower = float(variable.lower)
    upper = float(variable.upper)
    if number < lower or number > upper:
        raise ValueError(f"variable '{variable.name}' must be within [{lower}, {upper}]")
    if variable.type == "int":
        if not number.is_integer():
            raise ValueError(f"integer variable '{variable.name}' requires an integer value")
        return int(number)
    return number
