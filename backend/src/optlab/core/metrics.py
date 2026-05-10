from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .archive import ParetoArchive


@dataclass(slots=True)
class MetricSnapshot:
    generation: int
    evaluations: int
    pareto_count: int
    feasible_ratio: float
    best_objectives: dict[str, float | None]
    hypervolume: float | None
    approximate_hypervolume: float | None

    def to_payload(self) -> dict:
        return {
            "generation": self.generation,
            "evaluations": self.evaluations,
            "paretoCount": self.pareto_count,
            "feasibleRatio": self.feasible_ratio,
            "bestObjectives": self.best_objectives,
            "hypervolume": self.hypervolume,
            "approximateHypervolume": self.approximate_hypervolume,
        }


def compute_metric_snapshot(
    archive: ParetoArchive,
    objective_names: list[str],
    reference_point: list[float] | None = None,
    generation: int = 0,
) -> MetricSnapshot:
    front = archive.rank_zero()
    minimized = np.array([record.minimized for record in front], dtype=float) if front else np.empty((0, len(objective_names)))
    ref = np.array(reference_point if reference_point is not None else _reference_point(archive, len(objective_names)), dtype=float)
    hypervolume: float | None = None
    approximate_hypervolume: float | None = None

    if len(front) > 0:
        if len(objective_names) <= 4:
            hypervolume = _hypervolume(minimized, ref)
        else:
            approximate_hypervolume = _approximate_hypervolume(minimized, ref)

    evaluations = len(archive.records)
    feasible_ratio = archive.feasible_count() / evaluations if evaluations else 0.0
    return MetricSnapshot(
        generation=generation,
        evaluations=evaluations,
        pareto_count=len(front),
        feasible_ratio=feasible_ratio,
        best_objectives=archive.best_per_objective(objective_names),
        hypervolume=hypervolume,
        approximate_hypervolume=approximate_hypervolume,
    )


def _reference_point(archive: ParetoArchive, dimensions: int) -> list[float]:
    if not archive.records:
        return [1.0] * dimensions
    values = np.array([record.minimized for record in archive.records if record.error is None], dtype=float)
    if values.size == 0:
        return [1.0] * dimensions
    worst = np.max(values, axis=0)
    best = np.min(values, axis=0)
    span = np.maximum(worst - best, 1.0)
    return list(worst + 0.1 * span)


def _hypervolume(points: np.ndarray, reference_point: np.ndarray) -> float:
    try:
        from pymoo.indicators.hv import HV

        clipped = points[np.all(points <= reference_point, axis=1)]
        if clipped.size == 0:
            return 0.0
        return float(HV(ref_point=reference_point)(clipped))
    except Exception:
        if points.shape[1] == 2:
            return _hypervolume_2d(points, reference_point)
        return _approximate_hypervolume(points, reference_point)


def _hypervolume_2d(points: np.ndarray, reference_point: np.ndarray) -> float:
    clipped = points[np.all(points <= reference_point, axis=1)]
    if clipped.size == 0:
        return 0.0
    ordered = clipped[np.argsort(clipped[:, 0])]
    hv = 0.0
    current_y = reference_point[1]
    for x, y in ordered:
        if y < current_y:
            hv += max(0.0, reference_point[0] - x) * max(0.0, current_y - y)
            current_y = y
    return float(hv)


def _approximate_hypervolume(points: np.ndarray, reference_point: np.ndarray, samples: int = 4096) -> float:
    if points.size == 0:
        return 0.0
    ideal = np.min(points, axis=0)
    span = np.maximum(reference_point - ideal, 1e-12)
    rng = np.random.default_rng(20240510)
    sample_points = ideal + rng.random((samples, points.shape[1])) * span
    dominated = np.any(np.all(points[:, None, :] <= sample_points[None, :, :], axis=2), axis=0)
    return float(np.prod(span) * np.mean(dominated))

