"""Built-in benchmark evaluators."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .base import EvaluationResult, Evaluator, EvaluatorError


class BuiltinEvaluator(Evaluator):
    def __init__(self, spec: Any) -> None:
        self.spec = spec
        self.evaluator_spec = spec.evaluator
        self.name = str(getattr(self.evaluator_spec, "name", "")).lower()
        if self.name not in {"zdt1", "zdt2", "dtlz2", "dtlz7"}:
            raise EvaluatorError(f"unknown built-in evaluator: {self.name}")

    def evaluate(
        self,
        candidate_id: str,
        variables: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        del candidate_id, context
        values = [float(variables[var.name]) for var in self.spec.variables]
        if self.name == "zdt1":
            objectives = self._zdt1(values)
        elif self.name == "zdt2":
            objectives = self._zdt2(values)
        elif self.name == "dtlz2":
            objectives = self._dtlz2(values)
        else:
            objectives = self._dtlz7(values)
        names = [objective.name for objective in self.spec.objectives]
        return EvaluationResult(
            objectives={name: objectives[index] for index, name in enumerate(names)},
            constraints={},
            metadata={"evaluator": f"builtin:{self.name}"},
        )

    def _zdt1(self, values: list[float]) -> list[float]:
        if not values:
            raise EvaluatorError("zdt1 requires at least one variable")
        f1 = values[0]
        if len(values) == 1:
            g = 1.0
        else:
            g = 1.0 + 9.0 * sum(values[1:]) / (len(values) - 1)
        f2 = g * (1.0 - math.sqrt(max(f1 / g, 0.0)))
        return [f1, f2][: len(self.spec.objectives)]

    def _zdt2(self, values: list[float]) -> list[float]:
        if not values:
            raise EvaluatorError("zdt2 requires at least one variable")
        f1 = values[0]
        if len(values) == 1:
            g = 1.0
        else:
            g = 1.0 + 9.0 * sum(values[1:]) / (len(values) - 1)
        f2 = g * (1.0 - (f1 / g) ** 2)
        return [f1, f2][: len(self.spec.objectives)]

    def _dtlz2(self, values: list[float]) -> list[float]:
        m = len(self.spec.objectives)
        if m < 2:
            raise EvaluatorError("dtlz2 requires at least two objectives")
        if len(values) < m:
            raise EvaluatorError("dtlz2 requires at least as many variables as objectives")
        g = sum((x - 0.5) ** 2 for x in values[m - 1 :])
        result: list[float] = []
        for i in range(m):
            value = 1.0 + g
            for x in values[: m - i - 1]:
                value *= math.cos(x * math.pi / 2.0)
            if i > 0:
                value *= math.sin(values[m - i - 1] * math.pi / 2.0)
            result.append(value)
        return result

    def _dtlz7(self, values: list[float]) -> list[float]:
        m = len(self.spec.objectives)
        if m < 2:
            raise EvaluatorError("dtlz7 requires at least two objectives")
        if len(values) < m:
            raise EvaluatorError("dtlz7 requires at least as many variables as objectives")
        f = list(values[: m - 1])
        tail = values[m - 1 :]
        g = 1.0 + 9.0 * sum(tail) / max(1, len(tail))
        h_terms = [
            (fi / (1.0 + g)) * (1.0 + math.sin(3.0 * math.pi * fi))
            for fi in f
        ]
        h = m - sum(h_terms)
        f.append((1.0 + g) * h)
        return f
