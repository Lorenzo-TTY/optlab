"""Evaluator factory."""

from __future__ import annotations

from typing import Any

from .base import Evaluator, EvaluatorError
from .builtin import BuiltinEvaluator
from .http import HttpEvaluator
from .python import PythonEvaluator


def make_evaluator(spec: Any, job_id: str) -> Evaluator:
    evaluator_spec = spec.evaluator
    evaluator_type = str(getattr(evaluator_spec, "type", "")).lower()
    if evaluator_type == "builtin":
        return BuiltinEvaluator(spec)
    if evaluator_type == "python":
        return PythonEvaluator(evaluator_spec, job_id)
    if evaluator_type == "http":
        return HttpEvaluator(evaluator_spec, job_id)
    raise EvaluatorError(f"unknown evaluator type: {evaluator_type}")
