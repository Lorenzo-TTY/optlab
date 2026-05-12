from __future__ import annotations

import time

from fastapi.testclient import TestClient

from optlab.api.main import create_app


def zdt1_payload(max_evals: int = 24) -> dict:
    return {
        "variables": [
            {"name": f"x{i + 1}", "type": "float", "lower": 0.0, "upper": 1.0}
            for i in range(10)
        ],
        "objectives": [
            {"name": "f1", "direction": "min"},
            {"name": "f2", "direction": "min"},
        ],
        "evaluator": {"type": "builtin", "name": "zdt1"},
        "budget": {"max_evals": max_evals, "seed": 11},
        "algorithm": "random",
    }


def wait_for_terminal_status(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        if last["status"] in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.1)
    raise AssertionError(f"job did not finish: {last}")


def test_validate_config_accepts_valid_problem(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)

    response = client.post("/api/configs/validate", json=zdt1_payload())

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["summary"]["objectives"] == 2


def test_project_snapshot_persists_across_app_restart(tmp_path) -> None:
    db_path = tmp_path / "optlab.db"
    snapshot = {
        "schemaVersion": 1,
        "activeProjectId": "project_saved",
        "projects": [
            {
                "schemaVersion": 1,
                "id": "project_saved",
                "name": "Restart-safe sweep",
                "problem": {
                    "variables": [{"name": "x1", "type": "float", "lower": 0, "upper": 1, "scale": "linear"}],
                    "objectives": [{"name": "f1", "direction": "min"}],
                    "evaluator": {"type": "builtin", "name": "manual"},
                    "budget": {"max_evals": 200, "seed": 11},
                    "algorithm": "auto",
                    "batchSize": 1,
                },
                "rows": [],
                "observations": [
                    {
                        "candidateId": "manual_000001",
                        "generation": 0,
                        "variables": {"x1": 0.2},
                        "objectives": {"f1": 0.4},
                        "constraints": {},
                        "feasible": True,
                        "metadata": {"source": "manual-dataset"},
                    }
                ],
                "advisor": None,
                "createdAt": "2026-05-12T00:00:00.000Z",
                "updatedAt": "2026-05-12T00:00:00.000Z",
            }
        ],
    }
    client = TestClient(create_app(db_path=db_path))

    save_response = client.put("/api/projects", json=snapshot)

    assert save_response.status_code == 200
    restarted_client = TestClient(create_app(db_path=db_path))
    restored = restarted_client.get("/api/projects")
    assert restored.status_code == 200
    assert restored.json()["activeProjectId"] == "project_saved"
    assert restored.json()["projects"][0]["name"] == "Restart-safe sweep"
    assert restored.json()["projects"][0]["observations"][0]["objectives"] == {"f1": 0.4}


def test_job_lifecycle_results_and_exports(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)

    created = client.post("/api/jobs", json=zdt1_payload(max_evals=16))
    assert created.status_code == 200
    job_id = created.json()["jobId"]

    status = wait_for_terminal_status(client, job_id)
    assert status["status"] == "completed"
    assert status["evaluations"] == 16
    assert status["paretoCount"] > 0

    results = client.get(f"/api/jobs/{job_id}/results").json()
    assert len(results["evaluations"]) == 16
    assert len(results["paretoFront"]) == status["paretoCount"]

    csv_response = client.get(f"/api/jobs/{job_id}/export.csv")
    assert csv_response.status_code == 200
    assert "candidate_id" in csv_response.text

    json_response = client.get(f"/api/jobs/{job_id}/export.json")
    assert json_response.status_code == 200
    assert json_response.json()["job"]["id"] == job_id


def test_cancel_marks_long_running_job_cancelled(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)
    payload = zdt1_payload(max_evals=5000)

    created = client.post("/api/jobs", json=payload)
    job_id = created.json()["jobId"]
    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200
    terminal = wait_for_terminal_status(client, job_id, timeout=10.0)
    assert terminal["status"] == "cancelled"
    assert terminal["evaluations"] < 5000


def test_cancel_terminates_stuck_python_plugin_worker(tmp_path) -> None:
    plugin = tmp_path / "stuck_plugin.py"
    marker = tmp_path / "entered.txt"
    plugin.write_text(
        f"""
import time
from pathlib import Path

def evaluate(x):
    Path({str(marker)!r}).write_text("entered", encoding="utf-8")
    time.sleep(30)
    return {{"objectives": {{"f1": 1.0}}, "constraints": {{}}, "metadata": {{}}}}
""".strip(),
        encoding="utf-8",
    )
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)
    payload = {
        "variables": [{"name": "x1", "type": "float", "lower": 0.0, "upper": 1.0}],
        "objectives": [{"name": "f1", "direction": "min"}],
        "evaluator": {
            "type": "python",
            "module_path": str(plugin),
            "function_name": "evaluate",
        },
        "budget": {"max_evals": 10, "seed": 13},
        "algorithm": "random",
    }

    created = client.post("/api/jobs", json=payload)
    job_id = created.json()["jobId"]
    deadline = time.time() + 5.0
    while time.time() < deadline and not marker.exists():
        time.sleep(0.05)
    assert marker.exists()
    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200
    terminal = wait_for_terminal_status(client, job_id, timeout=5.0)
    assert terminal["status"] == "cancelled"


def test_websocket_replays_job_events(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "optlab.db")
    client = TestClient(app)
    created = client.post("/api/jobs", json=zdt1_payload(max_evals=8))
    job_id = created.json()["jobId"]
    wait_for_terminal_status(client, job_id)

    with client.websocket_connect(f"/ws/jobs/{job_id}") as websocket:
        event_types = {websocket.receive_json()["type"] for _ in range(3)}

    assert "job.started" in event_types
    assert "evaluation.completed" in event_types
