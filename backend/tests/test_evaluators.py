from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from optlab.core.models import BudgetSpec, EvaluatorSpec, ObjectiveSpec, ProblemSpec, VariableSpec
from optlab.evaluators import EvaluatorError, make_evaluator


def make_spec(evaluator: EvaluatorSpec) -> ProblemSpec:
    return ProblemSpec(
        variables=[
            VariableSpec(name="x1", type="float", lower=0.0, upper=1.0),
            VariableSpec(name="x2", type="float", lower=0.0, upper=1.0),
        ],
        objectives=[ObjectiveSpec(name="f1"), ObjectiveSpec(name="f2")],
        evaluator=evaluator,
        budget=BudgetSpec(max_evals=8, seed=7),
    )


def test_builtin_evaluator_returns_named_objectives() -> None:
    spec = make_spec(EvaluatorSpec(type="builtin", name="zdt1"))
    evaluator = make_evaluator(spec, job_id="job_a")

    result = evaluator.evaluate("cand_1", {"x1": 0.0, "x2": 0.0}, context={"seed": 7})

    assert set(result.objectives) == {"f1", "f2"}
    assert result.objectives["f1"] == pytest.approx(0.0)
    assert result.objectives["f2"] == pytest.approx(1.0)
    assert result.constraints == {}
    assert result.metadata["evaluator"] == "builtin:zdt1"


def test_python_plugin_evaluator_loads_trusted_local_function(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.py"
    plugin.write_text(
        """
def evaluate(x):
    return {
        "objectives": {"f1": x["x1"] + x["x2"], "f2": x["x1"] * x["x2"]},
        "constraints": {},
        "metadata": {"source": "plugin"}
    }
""".strip(),
        encoding="utf-8",
    )
    spec = make_spec(
        EvaluatorSpec(type="python", module_path=str(plugin), function_name="evaluate")
    )
    evaluator = make_evaluator(spec, job_id="job_plugin")

    result = evaluator.evaluate("cand_2", {"x1": 0.25, "x2": 0.5}, context={})

    assert result.objectives == pytest.approx({"f1": 0.75, "f2": 0.125})
    assert result.metadata["source"] == "plugin"


def test_python_plugin_exception_is_normalized(tmp_path: Path) -> None:
    plugin = tmp_path / "bad_plugin.py"
    plugin.write_text(
        """
def evaluate(x):
    raise RuntimeError("simulator crashed")
""".strip(),
        encoding="utf-8",
    )
    spec = make_spec(
        EvaluatorSpec(type="python", module_path=str(plugin), function_name="evaluate")
    )
    evaluator = make_evaluator(spec, job_id="job_bad")

    with pytest.raises(EvaluatorError, match="simulator crashed"):
        evaluator.evaluate("cand_3", {"x1": 0.0, "x2": 0.0}, context={})


class _HttpHandler(BaseHTTPRequestHandler):
    delay_seconds = 0.0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        body = json.dumps(
            {
                "objectives": {
                    "f1": payload["variables"]["x1"],
                    "f2": payload["variables"]["x2"],
                },
                "constraints": {},
                "metadata": {"candidate": payload["candidateId"]},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def start_server(delay_seconds: float = 0.0) -> tuple[ThreadingHTTPServer, str]:
    handler = type("Handler", (_HttpHandler,), {"delay_seconds": delay_seconds})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}/evaluate"


def test_http_evaluator_posts_unified_payload_and_parses_response() -> None:
    server, url = start_server()
    try:
        spec = make_spec(EvaluatorSpec(type="http", url=url, timeout_seconds=2.0))
        evaluator = make_evaluator(spec, job_id="job_http")

        result = evaluator.evaluate("cand_http", {"x1": 0.2, "x2": 0.8}, context={"seed": 7})

        assert result.objectives == pytest.approx({"f1": 0.2, "f2": 0.8})
        assert result.metadata["candidate"] == "cand_http"
    finally:
        server.shutdown()


def test_http_evaluator_timeout_is_normalized() -> None:
    server, url = start_server(delay_seconds=0.4)
    try:
        spec = make_spec(EvaluatorSpec(type="http", url=url, timeout_seconds=0.05, max_retries=0))
        evaluator = make_evaluator(spec, job_id="job_timeout")

        with pytest.raises(EvaluatorError, match="timed out"):
            evaluator.evaluate("cand_timeout", {"x1": 0.2, "x2": 0.8}, context={})
    finally:
        server.shutdown()

