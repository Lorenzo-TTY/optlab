"""Shared evaluator contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class EvaluatorError(RuntimeError):
    """Normalized evaluator failure surfaced to the optimizer and API."""


@dataclass(slots=True)
class EvaluationResult:
    objectives: dict[str, float]
    constraints: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class Evaluator:
    def evaluate(
        self,
        candidate_id: str,
        variables: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        raise NotImplementedError


def normalize_result(value: Any) -> EvaluationResult:
    if isinstance(value, EvaluationResult):
        return value
    if not isinstance(value, Mapping):
        raise EvaluatorError("evaluator returned a non-object result")

    objectives = value.get("objectives")
    if not isinstance(objectives, Mapping):
        raise EvaluatorError("evaluator result must include an objectives object")

    constraints = value.get("constraints") or {}
    metadata = value.get("metadata") or {}
    if not isinstance(constraints, Mapping):
        raise EvaluatorError("evaluator constraints must be an object")
    if not isinstance(metadata, Mapping):
        raise EvaluatorError("evaluator metadata must be an object")

    try:
        normalized_objectives = {str(key): float(val) for key, val in objectives.items()}
        normalized_constraints = {str(key): float(val) for key, val in constraints.items()}
    except (TypeError, ValueError) as exc:
        raise EvaluatorError(f"evaluator returned non-numeric values: {exc}") from exc

    return EvaluationResult(
        objectives=normalized_objectives,
        constraints=normalized_constraints,
        metadata=dict(metadata),
    )
