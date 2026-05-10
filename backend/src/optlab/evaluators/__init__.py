"""Evaluator adapter package."""

from .base import EvaluationResult, EvaluatorError
from .factory import make_evaluator

__all__ = ["EvaluationResult", "EvaluatorError", "make_evaluator"]
