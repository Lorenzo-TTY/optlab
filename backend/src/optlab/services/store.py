"""SQLite persistence for jobs, events, and optimization results."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _loads(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


class SQLiteStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def create_job(self, job_id: str, spec: dict[str, Any]) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO jobs
                (id, status, spec_json, created_at, updated_at, evaluations, pareto_count)
                VALUES (?, 'queued', ?, ?, ?, 0, 0)
                """,
                (job_id, _json(spec), now, now),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        evaluations: int | None = None,
        pareto_count: int | None = None,
        error: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [time.time()]
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if evaluations is not None:
            fields.append("evaluations = ?")
            values.append(evaluations)
        if pareto_count is not None:
            fields.append("pareto_count = ?")
            values.append(pareto_count)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        values.append(job_id)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def add_event(self, job_id: str, event: dict[str, Any]) -> None:
        event_type = str(event.get("type", "event"))
        payload = dict(event)
        payload.setdefault("jobId", job_id)
        payload.setdefault("timestamp", time.time())
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO events (job_id, type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (job_id, event_type, _json(payload), float(payload["timestamp"])),
            )

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM events WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def replace_results(
        self,
        job_id: str,
        evaluations: Iterable[dict[str, Any]],
        pareto_front: Iterable[dict[str, Any]],
    ) -> None:
        eval_rows = list(evaluations)
        pareto_rows = list(pareto_front)
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM evaluations WHERE job_id = ?", (job_id,))
            self._conn.execute("DELETE FROM pareto_front WHERE job_id = ?", (job_id,))
            self._conn.executemany(
                """
                INSERT INTO evaluations
                (job_id, candidate_id, generation, variables_json, objectives_json, constraints_json, feasible)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        row["candidate_id"],
                        row.get("generation", 0),
                        _json(row.get("variables", {})),
                        _json(row.get("objectives", {})),
                        _json(row.get("constraints", {})),
                        1 if row.get("feasible", True) else 0,
                    )
                    for row in eval_rows
                ],
            )
            self._conn.executemany(
                """
                INSERT INTO pareto_front
                (job_id, candidate_id, generation, variables_json, objectives_json, constraints_json, feasible)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        row["candidate_id"],
                        row.get("generation", 0),
                        _json(row.get("variables", {})),
                        _json(row.get("objectives", {})),
                        _json(row.get("constraints", {})),
                        1 if row.get("feasible", True) else 0,
                    )
                    for row in pareto_rows
                ],
            )
        self.update_job(job_id, evaluations=len(eval_rows), pareto_count=len(pareto_rows))

    def results(self, job_id: str) -> dict[str, Any]:
        return {
            "evaluations": self._read_rows("evaluations", job_id),
            "paretoFront": self._read_rows("pareto_front", job_id),
        }

    def export_json(self, job_id: str) -> dict[str, Any]:
        return {"job": self.get_job(job_id), **self.results(job_id)}

    def export_csv(self, job_id: str) -> str:
        rows = self._read_rows("evaluations", job_id)
        output = io.StringIO()
        fieldnames = ["candidate_id", "generation", "feasible", "variables", "objectives", "constraints"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "candidate_id": row["candidate_id"],
                    "generation": row.get("generation", 0),
                    "feasible": row.get("feasible", True),
                    "variables": _json(row.get("variables", {})),
                    "objectives": _json(row.get("objectives", {})),
                    "constraints": _json(row.get("constraints", {})),
                }
            )
        return output.getvalue()

    def get_project_state(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM project_state WHERE key = 'default'"
            ).fetchone()
        return _loads(row["payload_json"], {}) if row else None

    def save_project_state(self, payload: dict[str, Any]) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO project_state (key, payload_json, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (_json(payload), now),
            )

    def _read_rows(self, table: str, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM {table} WHERE job_id = ? ORDER BY id ASC", (job_id,)
            ).fetchall()
        return [
            {
                "candidate_id": row["candidate_id"],
                "generation": row["generation"],
                "variables": _loads(row["variables_json"], {}),
                "objectives": _loads(row["objectives_json"], {}),
                "constraints": _loads(row["constraints_json"], {}),
                "feasible": bool(row["feasible"]),
            }
            for row in rows
        ]

    def _job_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "spec": _loads(row["spec_json"], {}),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "evaluations": row["evaluations"],
            "paretoCount": row["pareto_count"],
            "error": row["error"],
        }

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    evaluations INTEGER NOT NULL DEFAULT 0,
                    pareto_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    variables_json TEXT NOT NULL,
                    objectives_json TEXT NOT NULL,
                    constraints_json TEXT NOT NULL,
                    feasible INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pareto_front (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    variables_json TEXT NOT NULL,
                    objectives_json TEXT NOT NULL,
                    constraints_json TEXT NOT NULL,
                    feasible INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_state (
                    key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
