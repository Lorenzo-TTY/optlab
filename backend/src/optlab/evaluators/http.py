"""HTTP evaluator adapter."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from .base import EvaluationResult, Evaluator, EvaluatorError, normalize_result


class HttpEvaluator(Evaluator):
    def __init__(self, evaluator_spec: Any, job_id: str) -> None:
        self.url = getattr(evaluator_spec, "url", None)
        if not self.url:
            raise EvaluatorError("http evaluator requires url")
        self.timeout_seconds = float(getattr(evaluator_spec, "timeout_seconds", 30.0) or 30.0)
        self.max_retries = int(getattr(evaluator_spec, "max_retries", 0) or 0)
        self.job_id = job_id

    def evaluate(
        self,
        candidate_id: str,
        variables: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        payload = {
            "jobId": self.job_id,
            "candidateId": candidate_id,
            "variables": dict(variables),
            "context": dict(context or {}),
        }
        last_error: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(self.url, json=payload, timeout=self.timeout_seconds)
                response.raise_for_status()
                return normalize_result(response.json())
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                last_error = exc
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                break
        message = str(last_error) if last_error else "http evaluator failed"
        if isinstance(last_error, httpx.TimeoutException):
            message = f"http evaluator timed out after {self.timeout_seconds:g}s"
        raise EvaluatorError(message) from last_error
