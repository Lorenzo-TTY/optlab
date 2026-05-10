from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .archive import CandidateRecord, ParetoArchive
from .encoding import decode_vector
from .metrics import MetricSnapshot, compute_metric_snapshot
from .models import EvaluationResult, ProblemSpec


EventSink = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


@dataclass(slots=True)
class RunResult:
    algorithm: str
    archive: ParetoArchive
    metrics: list[MetricSnapshot]
    summary: dict[str, Any]


class CancelledRun(Exception):
    pass


class BudgetReached(Exception):
    pass


def run_problem(
    spec: ProblemSpec,
    event_sink: EventSink | None = None,
    cancel_check: CancelCheck | None = None,
) -> RunResult:
    algorithm = spec.selected_algorithm()
    if event_sink:
        event_sink({"type": "job.started", "algorithm": algorithm})
    if algorithm == "random":
        return _run_random(spec, algorithm, event_sink, cancel_check)
    return _run_pymoo(spec, algorithm, event_sink, cancel_check)


def _run_random(
    spec: ProblemSpec,
    algorithm: str,
    event_sink: EventSink | None,
    cancel_check: CancelCheck | None,
) -> RunResult:
    from optlab.evaluators import EvaluatorError, make_evaluator

    rng = np.random.default_rng(spec.budget.seed)
    evaluator = make_evaluator(spec, job_id="local")
    archive = ParetoArchive()
    metrics: list[MetricSnapshot] = []
    for index in range(spec.budget.max_evals):
        if cancel_check and cancel_check():
            raise CancelledRun()
        vector = rng.random(len(spec.variables))
        variables = decode_vector(spec.variables, vector)
        record = _evaluate_candidate(
            spec=spec,
            evaluator=evaluator,
            candidate_id=f"cand_{index + 1:06d}",
            generation=index,
            variables=variables,
            context={"seed": spec.budget.seed, "algorithm": algorithm},
            evaluator_error_type=EvaluatorError,
        )
        archive.add(record)
        _emit_evaluation(event_sink, record)
        snapshot = compute_metric_snapshot(archive, spec.objective_names, generation=index)
        metrics.append(snapshot)
        _emit_metrics(event_sink, snapshot, archive)
    return _final_result(algorithm, archive, metrics)


def _run_pymoo(
    spec: ProblemSpec,
    algorithm: str,
    event_sink: EventSink | None,
    cancel_check: CancelCheck | None,
) -> RunResult:
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.algorithms.moo.nsga3 import NSGA3
    from pymoo.algorithms.moo.rvea import RVEA
    from pymoo.algorithms.soo.nonconvex.ga import GA
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.optimize import minimize
    from pymoo.util.ref_dirs import get_reference_directions

    from optlab.evaluators import EvaluatorError, make_evaluator

    evaluator = make_evaluator(spec, job_id="local")
    archive = ParetoArchive()
    metrics: list[MetricSnapshot] = []
    counter = {"value": 0}

    class OptLabProblem(ElementwiseProblem):
        def __init__(self) -> None:
            super().__init__(
                n_var=len(spec.variables),
                n_obj=len(spec.objectives),
                n_ieq_constr=len([c for c in spec.constraints if c.severity == "hard"]),
                xl=np.zeros(len(spec.variables)),
                xu=np.ones(len(spec.variables)),
            )

        def _evaluate(self, x, out, *args, **kwargs) -> None:
            if cancel_check and cancel_check():
                raise CancelledRun()
            if counter["value"] >= spec.budget.max_evals:
                raise BudgetReached()
            counter["value"] += 1
            variables = decode_vector(spec.variables, list(x))
            record = _evaluate_candidate(
                spec=spec,
                evaluator=evaluator,
                candidate_id=f"cand_{counter['value']:06d}",
                generation=max(0, counter["value"] // _population_size(spec)),
                variables=variables,
                context={"seed": spec.budget.seed, "algorithm": algorithm},
                evaluator_error_type=EvaluatorError,
            )
            archive.add(record)
            _emit_evaluation(event_sink, record)
            out["F"] = record.minimized
            hard_values = spec.hard_constraint_values(record.constraints)
            if hard_values:
                out["G"] = hard_values

    class MetricCallback:
        def __call__(self, algorithm_state) -> None:
            generation = int(getattr(algorithm_state, "n_gen", len(metrics)))
            snapshot = compute_metric_snapshot(archive, spec.objective_names, generation=generation)
            metrics.append(snapshot)
            _emit_metrics(event_sink, snapshot, archive)

    pop_size = _population_size(spec)
    if algorithm == "ga":
        algo = GA(pop_size=pop_size)
    elif algorithm in {"nsga3", "rvea"}:
        ref_dirs = get_reference_directions("das-dennis", len(spec.objectives), n_partitions=4)
        if algorithm == "rvea":
            algo = RVEA(ref_dirs=ref_dirs, pop_size=max(pop_size, len(ref_dirs)))
        else:
            algo = NSGA3(pop_size=max(pop_size, len(ref_dirs)), ref_dirs=ref_dirs)
    else:
        algo = NSGA2(pop_size=pop_size)

    try:
        minimize(
            OptLabProblem(),
            algo,
            ("n_eval", spec.budget.max_evals),
            seed=spec.budget.seed,
            verbose=False,
            callback=MetricCallback(),
        )
    except CancelledRun:
        raise
    except BudgetReached:
        pass

    if not metrics:
        metrics.append(compute_metric_snapshot(archive, spec.objective_names, generation=0))
    elif metrics[-1].evaluations != len(archive.records):
        metrics.append(
            compute_metric_snapshot(
                archive,
                spec.objective_names,
                generation=metrics[-1].generation + 1,
            )
        )
    return _final_result(algorithm, archive, metrics)


def _population_size(spec: ProblemSpec) -> int:
    return max(16, min(512, 8 * len(spec.variables) + 16 * len(spec.objectives)))


def _evaluate_candidate(
    *,
    spec: ProblemSpec,
    evaluator: Any,
    candidate_id: str,
    generation: int,
    variables: dict[str, Any],
    context: dict[str, Any],
    evaluator_error_type: type[Exception],
) -> CandidateRecord:
    started = time.perf_counter()
    try:
        result: EvaluationResult = evaluator.evaluate(candidate_id, variables, context=context)
        minimized = spec.to_minimized_objectives(result.objectives)
        feasible = spec.is_feasible(result.constraints)
        error = None
        objectives = result.objectives
        constraints = result.constraints
        metadata = result.metadata
    except evaluator_error_type as exc:
        minimized = [1.0e12] * len(spec.objectives)
        feasible = False
        error = str(exc)
        objectives = {objective.name: 1.0e12 for objective in spec.objectives}
        constraints = {constraint.name: 1.0e12 for constraint in spec.constraints}
        metadata = {}
    elapsed = (time.perf_counter() - started) * 1000.0
    return CandidateRecord(
        candidate_id=candidate_id,
        generation=generation,
        variables=variables,
        objectives=objectives,
        minimized=minimized,
        constraints=constraints,
        feasible=feasible,
        error=error,
        elapsed_ms=elapsed,
        metadata=metadata,
    )


def _emit_evaluation(event_sink: EventSink | None, record: CandidateRecord) -> None:
    if event_sink:
        event_sink(
            {
                "type": "evaluation.completed",
                "candidate": {
                    "candidateId": record.candidate_id,
                    "generation": record.generation,
                    "variables": record.variables,
                    "objectives": record.objectives,
                    "constraints": record.constraints,
                    "feasible": record.feasible,
                    "error": record.error,
                    "elapsedMs": record.elapsed_ms,
                },
            }
        )


def _emit_metrics(event_sink: EventSink | None, snapshot: MetricSnapshot, archive: ParetoArchive) -> None:
    if event_sink:
        event_sink({"type": "metrics.updated", "metrics": snapshot.to_payload()})
        event_sink({"type": "pareto.updated", "points": archive.to_payload()["paretoFront"]})


def _final_result(algorithm: str, archive: ParetoArchive, metrics: list[MetricSnapshot]) -> RunResult:
    final_metrics = metrics[-1] if metrics else compute_metric_snapshot(archive, [])
    return RunResult(
        algorithm=algorithm,
        archive=archive,
        metrics=metrics,
        summary={
            "algorithm": algorithm,
            "evaluations": len(archive.records),
            "paretoCount": len(archive.rank_zero()),
            "feasibleRatio": final_metrics.feasible_ratio,
        },
    )
