"""Background job orchestration with one worker process per optimization job."""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from .store import SQLiteStore


@dataclass
class _WorkerHandle:
    process: mp.Process
    events: mp.Queue
    cancel_event: Any
    spec: Any
    cancel_requested_at: float | None = None


class JobManager:
    def __init__(
        self,
        store: SQLiteStore,
        spec_builder: Callable[[dict[str, Any]], Any],
        *,
        cancel_grace_seconds: float = 0.5,
    ) -> None:
        self.store = store
        self.spec_builder = spec_builder
        self.cancel_grace_seconds = cancel_grace_seconds
        self._ctx = mp.get_context("spawn")
        self._workers: dict[str, _WorkerHandle] = {}
        self._lock = threading.RLock()

    def submit(self, payload: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        spec = self.spec_builder(payload)
        self.store.create_job(job_id, payload)
        events = self._ctx.Queue()
        cancel_event = self._ctx.Event()
        process = self._ctx.Process(
            target=_worker_entry,
            args=(job_id, payload, events, cancel_event),
            name=f"optlab-worker-{job_id}",
        )
        handle = _WorkerHandle(process=process, events=events, cancel_event=cancel_event, spec=spec)
        with self._lock:
            self._workers[job_id] = handle
        process.start()
        threading.Thread(
            target=self._monitor_worker,
            args=(job_id, handle),
            name=f"optlab-monitor-{job_id}",
            daemon=True,
        ).start()
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            handle = self._workers.get(job_id)
        if handle is None:
            return self.store.get_job(job_id) is not None
        handle.cancel_event.set()
        handle.cancel_requested_at = time.monotonic()
        self.store.update_job(job_id, status="stopping")
        self.store.add_event(job_id, {"type": "job.cancel_requested"})
        return True

    def _monitor_worker(self, job_id: str, handle: _WorkerHandle) -> None:
        self.store.update_job(job_id, status="running")
        finalized = False
        try:
            while not finalized:
                finalized = self._drain_messages(job_id, handle)
                if finalized:
                    break

                if self._should_terminate(handle):
                    if handle.process.is_alive():
                        handle.process.terminate()
                        handle.process.join(timeout=2.0)
                    self._finalize_cancelled(job_id, handle)
                    finalized = True
                    break

                if not handle.process.is_alive():
                    self._drain_messages(job_id, handle)
                    if self.store.get_job(job_id) and self.store.get_job(job_id)["status"] in {
                        "completed",
                        "failed",
                        "cancelled",
                    }:
                        finalized = True
                    elif handle.cancel_event.is_set():
                        self._finalize_cancelled(job_id, handle)
                        finalized = True
                    else:
                        self.store.update_job(
                            job_id,
                            status="failed",
                            error=f"worker exited with code {handle.process.exitcode}",
                        )
                        self.store.add_event(
                            job_id,
                            {
                                "type": "job.failed",
                                "error": f"worker exited with code {handle.process.exitcode}",
                            },
                        )
                        finalized = True
                if not finalized:
                    time.sleep(0.05)
        finally:
            if handle.process.is_alive():
                handle.process.join(timeout=0.2)
            with self._lock:
                self._workers.pop(job_id, None)

    def _drain_messages(self, job_id: str, handle: _WorkerHandle) -> bool:
        finalized = False
        while True:
            try:
                message = handle.events.get_nowait()
            except queue.Empty:
                break
            kind = message.get("kind")
            if kind == "event":
                self._store_event(job_id, handle.spec, message["event"])
            elif kind == "final":
                self._finalize_from_worker(job_id, message)
                finalized = True
            elif kind == "failed":
                self.store.update_job(job_id, status="failed", error=message.get("error"))
                self.store.add_event(job_id, {"type": "job.failed", "error": message.get("error")})
                finalized = True
        return finalized

    def _store_event(self, job_id: str, spec: Any, event: dict[str, Any]) -> None:
        self.store.add_event(job_id, event)
        if event.get("type") != "evaluation.completed":
            return
        row = _record_from_event(event)
        if row is None:
            return
        current = self.store.results(job_id)["evaluations"]
        if any(existing["candidate_id"] == row["candidate_id"] for existing in current):
            return
        evaluations = current + [row]
        self.store.replace_results(job_id, evaluations, _pareto_from_rows(evaluations, spec))

    def _finalize_from_worker(self, job_id: str, message: dict[str, Any]) -> None:
        status = str(message.get("status", "completed"))
        evaluations = [_normalize_record(row) for row in message.get("evaluations", [])]
        pareto_front = [_normalize_record(row) for row in message.get("paretoFront", [])]
        self.store.replace_results(job_id, evaluations, pareto_front)
        self.store.update_job(job_id, status=status)
        self.store.add_event(job_id, {"type": f"job.{status}", "summary": message.get("summary", {})})

    def _finalize_cancelled(self, job_id: str, handle: _WorkerHandle) -> None:
        current = self.store.results(job_id)["evaluations"]
        self.store.replace_results(job_id, current, _pareto_from_rows(current, handle.spec))
        self.store.update_job(job_id, status="cancelled")
        self.store.add_event(job_id, {"type": "job.cancelled"})

    def _should_terminate(self, handle: _WorkerHandle) -> bool:
        return (
            handle.cancel_requested_at is not None
            and handle.process.is_alive()
            and time.monotonic() - handle.cancel_requested_at >= self.cancel_grace_seconds
        )


def _worker_entry(job_id: str, payload: dict[str, Any], events: mp.Queue, cancel_event: Any) -> None:
    try:
        from optlab.core.runner import CancelledRun, run_problem

        spec = _problem_from_payload(payload)

        def event_sink(event: dict[str, Any]) -> None:
            events.put({"kind": "event", "event": event})

        result = run_problem(
            spec,
            event_sink=event_sink,
            cancel_check=cancel_event.is_set,
        )
        evaluations, pareto_front = _extract_result(result)
        events.put(
            {
                "kind": "final",
                "status": "cancelled" if cancel_event.is_set() else "completed",
                "evaluations": evaluations,
                "paretoFront": pareto_front,
                "summary": getattr(result, "summary", {}),
            }
        )
    except CancelledRun:
        events.put(
            {
                "kind": "final",
                "status": "cancelled",
                "evaluations": [],
                "paretoFront": [],
                "summary": {},
            }
        )
    except Exception as exc:  # noqa: BLE001 - worker boundary normalizes failures.
        if cancel_event.is_set():
            events.put(
                {
                    "kind": "final",
                    "status": "cancelled",
                    "evaluations": [],
                    "paretoFront": [],
                    "summary": {},
                }
            )
        else:
            events.put({"kind": "failed", "error": str(exc)})


def _problem_from_payload(payload: dict[str, Any]) -> Any:
    from optlab.core.models import (
        BudgetSpec,
        ConstraintSpec,
        EvaluatorSpec,
        ObjectiveSpec,
        ProblemSpec,
        VariableSpec,
    )

    return ProblemSpec(
        variables=[VariableSpec(**item) for item in payload.get("variables", [])],
        objectives=[ObjectiveSpec(**item) for item in payload.get("objectives", [])],
        constraints=[ConstraintSpec(**item) for item in payload.get("constraints", [])],
        evaluator=EvaluatorSpec(**payload["evaluator"]),
        budget=BudgetSpec(**payload["budget"]),
        algorithm=payload.get("algorithm", "auto"),
    )


def _extract_result(result: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    archive = getattr(result, "archive", None)
    if archive is None:
        return [], []
    records = [_normalize_record(row) for row in getattr(archive, "records", [])]
    rank_zero = archive.rank_zero() if hasattr(archive, "rank_zero") else []
    pareto = [_normalize_record(row) for row in rank_zero]
    return records, pareto


def _record_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    candidate = event.get("candidate") or event.get("record") or event.get("evaluation")
    if not isinstance(candidate, dict):
        return None
    return _normalize_record(candidate)


def _normalize_record(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        get = row.get
    else:
        get = lambda key, default=None: getattr(row, key, default)
    candidate_id = get("candidate_id") or get("candidateId")
    if not candidate_id:
        candidate_id = "unknown"
    return {
        "candidate_id": candidate_id,
        "generation": int(get("generation", 0) or 0),
        "variables": dict(get("variables", {}) or {}),
        "objectives": dict(get("objectives", {}) or {}),
        "constraints": dict(get("constraints", {}) or {}),
        "feasible": bool(get("feasible", True)),
    }


def _pareto_from_rows(rows: list[dict[str, Any]], spec: Any) -> list[dict[str, Any]]:
    objective_names = [objective.name for objective in spec.objectives]
    directions = [getattr(objective, "direction", "min") for objective in spec.objectives]

    def minimized(row: dict[str, Any]) -> list[float]:
        values = [float(row["objectives"][name]) for name in objective_names]
        return [value if direction != "max" else -value for value, direction in zip(values, directions)]

    feasible_rows = [row for row in rows if row.get("feasible", True)]
    front: list[dict[str, Any]] = []
    for candidate in feasible_rows:
        candidate_values = minimized(candidate)
        dominated = False
        for other in feasible_rows:
            if other is candidate:
                continue
            other_values = minimized(other)
            if all(o <= c for o, c in zip(other_values, candidate_values)) and any(
                o < c for o, c in zip(other_values, candidate_values)
            ):
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return front
