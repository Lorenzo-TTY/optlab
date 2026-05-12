"""FastAPI application factory."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import ValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from optlab.core.advisor import AdvisorRequest, suggest_candidates
from optlab.services import JobManager, SQLiteStore


@dataclass
class _VariableSpec:
    name: str
    type: str
    lower: float | int | None = None
    upper: float | int | None = None
    choices: list[Any] | None = None


@dataclass
class _ObjectiveSpec:
    name: str
    direction: str = "min"


@dataclass
class _EvaluatorSpec:
    type: str
    name: str | None = None
    module_path: str | None = None
    function_name: str = "evaluate"
    url: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 0


@dataclass
class _BudgetSpec:
    max_evals: int
    seed: int | None = None


@dataclass
class _ProblemSpec:
    variables: list[_VariableSpec]
    objectives: list[_ObjectiveSpec]
    evaluator: _EvaluatorSpec
    budget: _BudgetSpec
    algorithm: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_minimized_objectives(self, values: dict[str, float]) -> list[float]:
        result = []
        for objective in self.objectives:
            value = float(values[objective.name])
            result.append(value if objective.direction != "max" else -value)
        return result


def create_app(db_path: str | Path | None = None) -> FastAPI:
    if db_path is None:
        db_path = Path(tempfile.gettempdir()) / "optlab.db"
    store = SQLiteStore(db_path)
    manager = JobManager(store, _build_problem_spec)

    app = FastAPI(title="OptLab API")
    app.state.store = store
    app.state.manager = manager

    @app.post("/api/configs/validate")
    def validate_config(payload: dict[str, Any]) -> dict[str, Any]:
        spec = _build_problem_spec(payload)
        return {
            "valid": True,
            "summary": {
                "variables": len(spec.variables),
                "objectives": len(spec.objectives),
                "maxEvals": spec.budget.max_evals,
                "evaluator": spec.evaluator.type,
            },
        }

    @app.post("/api/jobs")
    def create_job(payload: dict[str, Any]) -> dict[str, str]:
        _build_problem_spec(payload)
        job_id = manager.submit(payload)
        return {"jobId": job_id, "status": "queued"}

    @app.post("/api/advisor/suggest")
    def advisor_suggest(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            request = AdvisorRequest.model_validate(payload)
            response = suggest_candidates(request)
            return response.model_dump(mode="json", by_alias=True)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects")
    def get_projects() -> dict[str, Any]:
        return store.get_project_state() or {
            "schemaVersion": 1,
            "projects": [],
            "activeProjectId": "",
        }

    @app.put("/api/projects")
    def save_projects(payload: dict[str, Any]) -> dict[str, bool]:
        projects = payload.get("projects")
        active_project_id = payload.get("activeProjectId", "")
        if not isinstance(projects, list):
            raise HTTPException(status_code=400, detail="projects must be a list")
        if active_project_id is not None and not isinstance(active_project_id, str):
            raise HTTPException(status_code=400, detail="activeProjectId must be a string")
        store.save_project_state(
            {
                "schemaVersion": 1,
                "projects": projects,
                "activeProjectId": active_project_id or "",
            }
        )
        return {"saved": True}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_response(job)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        if not manager.cancel(job_id):
            raise HTTPException(status_code=404, detail="job not found")
        return {"jobId": job_id, "status": "stopping", "cancelled": True}

    @app.get("/api/jobs/{job_id}/results")
    def get_results(job_id: str) -> dict[str, Any]:
        if store.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job not found")
        return store.results(job_id)

    @app.get("/api/jobs/{job_id}/export.csv")
    def export_csv(job_id: str) -> PlainTextResponse:
        if store.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job not found")
        return PlainTextResponse(store.export_csv(job_id), media_type="text/csv")

    @app.get("/api/jobs/{job_id}/export.json")
    def export_json(job_id: str) -> JSONResponse:
        if store.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JSONResponse(store.export_json(job_id))

    @app.websocket("/ws/jobs/{job_id}")
    async def job_events(websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        if store.get_job(job_id) is None:
            await websocket.send_json({"type": "error", "message": "job not found"})
            await websocket.close()
            return
        for event in store.list_events(job_id):
            await websocket.send_json(event)
        await websocket.close()

    return app


def _job_response(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": job["id"],
        "id": job["id"],
        "status": job["status"],
        "evaluations": job["evaluations"],
        "paretoCount": job["paretoCount"],
        "error": job.get("error"),
        "createdAt": job["createdAt"],
        "updatedAt": job["updatedAt"],
    }


def _build_problem_spec(payload: dict[str, Any]) -> Any:
    try:
        from optlab.core.models import (
            BudgetSpec,
            ConstraintSpec,
            EvaluatorSpec,
            ObjectiveSpec,
            ProblemSpec,
            VariableSpec,
        )

        return ProblemSpec(
            variables=[VariableSpec(**item) for item in payload["variables"]],
            objectives=[ObjectiveSpec(**item) for item in payload["objectives"]],
            constraints=[ConstraintSpec(**item) for item in payload.get("constraints", [])],
            evaluator=EvaluatorSpec(**payload["evaluator"]),
            budget=BudgetSpec(**payload["budget"]),
            algorithm=payload.get("algorithm", "auto"),
        )
    except ModuleNotFoundError:
        return _build_fallback_problem_spec(payload)
    except ImportError:
        return _build_fallback_problem_spec(payload)


def _build_fallback_problem_spec(payload: dict[str, Any]) -> _ProblemSpec:
    variables = [_VariableSpec(**item) for item in payload["variables"]]
    objectives = [_ObjectiveSpec(**item) for item in payload["objectives"]]
    evaluator = _EvaluatorSpec(**payload["evaluator"])
    budget = _BudgetSpec(**payload["budget"])
    if len(variables) > 30:
        raise ValueError("problem supports at most 30 variables")
    if len(objectives) > 6:
        raise ValueError("problem supports at most 6 objectives")
    if budget.max_evals < 1:
        raise ValueError("max_evals must be positive")
    return _ProblemSpec(
        variables=variables,
        objectives=objectives,
        evaluator=evaluator,
        budget=budget,
        algorithm=payload.get("algorithm", "auto"),
    )
