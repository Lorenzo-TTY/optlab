"""Trusted local Python evaluator adapter."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable, Mapping

from .base import EvaluationResult, Evaluator, EvaluatorError, normalize_result


class PythonEvaluator(Evaluator):
    def __init__(self, evaluator_spec: Any, job_id: str) -> None:
        module_path = getattr(evaluator_spec, "module_path", None)
        function_name = getattr(evaluator_spec, "function_name", "evaluate") or "evaluate"
        if not module_path:
            raise EvaluatorError("python evaluator requires module_path")
        self.job_id = job_id
        self.module_path = Path(module_path).expanduser().resolve()
        self.function = self._load_function(function_name)

    def evaluate(
        self,
        candidate_id: str,
        variables: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        try:
            value = self._call(candidate_id, dict(variables), dict(context or {}))
            return normalize_result(value)
        except EvaluatorError:
            raise
        except Exception as exc:  # noqa: BLE001 - plugin failures are normalized.
            raise EvaluatorError(str(exc)) from exc

    def _load_function(self, function_name: str) -> Callable[..., Any]:
        if not self.module_path.exists():
            raise EvaluatorError(f"python evaluator module not found: {self.module_path}")
        spec = importlib.util.spec_from_file_location(
            f"optlab_plugin_{self.job_id}", self.module_path
        )
        if spec is None or spec.loader is None:
            raise EvaluatorError(f"could not load python evaluator: {self.module_path}")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            raise EvaluatorError(str(exc)) from exc
        function = getattr(module, function_name, None)
        if not callable(function):
            raise EvaluatorError(f"python evaluator function not found: {function_name}")
        return function

    def _call(
        self,
        candidate_id: str,
        variables: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        signature = inspect.signature(self.function)
        kwargs = {
            "candidate_id": candidate_id,
            "candidateId": candidate_id,
            "variables": variables,
            "context": context,
            "job_id": self.job_id,
            "jobId": self.job_id,
        }
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return self.function(variables, **kwargs)
        accepted = {
            key: value for key, value in kwargs.items() if key in signature.parameters
        }
        if len(signature.parameters) <= len(accepted):
            return self.function(**accepted)
        return self.function(variables)
