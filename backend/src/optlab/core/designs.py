from __future__ import annotations

import math

import numpy as np


def space_filling_design(
    n_samples: int,
    n_dim: int,
    seed: int,
    *,
    existing: np.ndarray | None = None,
    pool_multiplier: int = 8,
) -> np.ndarray:
    """Hybrid Sobol/LHS/maximin design in the encoded [0, 1] parameter cube."""
    if n_samples <= 0 or n_dim <= 0:
        return np.empty((0, max(0, n_dim)), dtype=float)

    existing_array = _as_2d(existing, n_dim)
    rng = np.random.default_rng(seed)
    pool_size = max(n_samples * pool_multiplier, 64, 4 * n_dim)
    pool = np.vstack(
        [
            _sobol(pool_size, n_dim, seed),
            _lhs(pool_size, n_dim, seed + 104729),
            rng.random((pool_size, n_dim)),
        ]
    )
    return _maximin_select(np.clip(pool, 0.0, 1.0), n_samples, existing_array)


def synthetic_objective_coverage_dataset(
    n_samples: int,
    n_variables: int,
    n_objectives: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate deterministic synthetic X/Y data with non-degenerate ranges per objective."""
    x = space_filling_design(n_samples, n_variables, seed)
    if n_samples <= 0 or n_objectives <= 0:
        return x, np.empty((max(0, n_samples), max(0, n_objectives)), dtype=float)

    objectives: list[np.ndarray] = []
    objective_anchors = space_filling_design(n_samples, n_objectives, seed + 65537)
    variable_weights = np.linspace(0.7, 1.3, max(1, n_variables))
    for objective_index in range(n_objectives):
        phase = (objective_index + 1) / (n_objectives + 1)
        rotated = np.roll(x, objective_index % max(1, n_variables), axis=1)
        weighted = rotated @ np.roll(variable_weights, objective_index % max(1, n_variables))
        weighted = weighted / max(1.0, variable_weights.sum())
        wave = np.sin((objective_index + 1) * math.pi * weighted + phase)
        radial = np.mean((rotated - phase) ** 2, axis=1)
        anchor = objective_anchors[:, objective_index]
        objectives.append(0.52 * anchor + 0.28 * weighted + 0.14 * wave + 0.24 * radial + 0.03 * objective_index)

    y = np.column_stack(objectives)
    lower = y.min(axis=0)
    upper = y.max(axis=0)
    span = np.where((upper - lower) > 1.0e-12, upper - lower, 1.0)
    return x, (y - lower) / span


def coverage_summary(points: np.ndarray) -> dict[str, float]:
    if points.size == 0:
        return {
            "min_pairwise_distance": 0.0,
            "mean_nearest_distance": 0.0,
            "nearest_p10": 0.0,
            "nearest_p50": 0.0,
            "axis_range_min": 0.0,
            "projection_occupancy_min": 0.0,
            "projection_occupancy_mean": 0.0,
            "centered_discrepancy": 0.0,
        }
    values = np.asarray(points, dtype=float)
    axis_range_min = float(np.min(values.max(axis=0) - values.min(axis=0)))
    projection_min, projection_mean = projection_occupancy(values)
    discrepancy = centered_discrepancy(values)
    if len(values) < 2:
        return {
            "min_pairwise_distance": 0.0,
            "mean_nearest_distance": 0.0,
            "nearest_p10": 0.0,
            "nearest_p50": 0.0,
            "axis_range_min": axis_range_min,
            "projection_occupancy_min": projection_min,
            "projection_occupancy_mean": projection_mean,
            "centered_discrepancy": discrepancy,
        }
    distances = pairwise_distances(values, values)
    np.fill_diagonal(distances, np.inf)
    nearest = distances.min(axis=1)
    return {
        "min_pairwise_distance": float(nearest.min()),
        "mean_nearest_distance": float(nearest.mean()),
        "nearest_p10": float(np.quantile(nearest, 0.10)),
        "nearest_p50": float(np.quantile(nearest, 0.50)),
        "axis_range_min": axis_range_min,
        "projection_occupancy_min": projection_min,
        "projection_occupancy_mean": projection_mean,
        "centered_discrepancy": discrepancy,
    }


def pairwise_distances(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    if len(right) == 0:
        return np.full((len(left), 1), 1.0, dtype=float)
    diff = left[:, None, :] - right[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def projection_occupancy(points: np.ndarray, bins: int = 4) -> tuple[float, float]:
    values = _scale_unit(points)
    if values.size == 0:
        return 0.0, 0.0
    n_dim = values.shape[1]
    if n_dim == 1:
        occupied = len(np.unique(np.clip(np.floor(values[:, 0] * bins), 0, bins - 1).astype(int)))
        value = occupied / bins
        return float(value), float(value)

    ratios: list[float] = []
    for left in range(n_dim):
        for right in range(left + 1, n_dim):
            grid = np.clip(np.floor(values[:, [left, right]] * bins), 0, bins - 1).astype(int)
            occupied = len(np.unique(grid, axis=0))
            ratios.append(occupied / float(bins * bins))
    if not ratios:
        return 0.0, 0.0
    return float(min(ratios)), float(np.mean(ratios))


def centered_discrepancy(points: np.ndarray) -> float:
    values = _scale_unit(points)
    if values.size == 0:
        return 0.0
    try:
        from scipy.stats import qmc

        return float(qmc.discrepancy(values, method="CD"))
    except Exception:
        return float("nan")


def _lhs(n_samples: int, n_dim: int, seed: int) -> np.ndarray:
    try:
        from scipy.stats import qmc

        sampler = qmc.LatinHypercube(d=n_dim, scramble=True, optimization="random-cd", seed=seed)
        return np.asarray(sampler.random(n_samples), dtype=float)
    except Exception:
        rng = np.random.default_rng(seed)
        samples = np.empty((n_samples, n_dim), dtype=float)
        for dim in range(n_dim):
            samples[:, dim] = (rng.permutation(n_samples) + rng.random(n_samples)) / n_samples
        return samples


def _sobol(n_samples: int, n_dim: int, seed: int) -> np.ndarray:
    try:
        from scipy.stats import qmc

        sampler = qmc.Sobol(d=n_dim, scramble=True, seed=seed)
        count = 2 ** math.ceil(math.log2(max(1, n_samples)))
        return np.asarray(sampler.random_base2(int(math.log2(count)))[:n_samples], dtype=float)
    except Exception:
        return _lhs(n_samples, n_dim, seed + 8191)


def _maximin_select(pool: np.ndarray, n_samples: int, existing: np.ndarray) -> np.ndarray:
    candidates = _unique_rows(np.asarray(pool, dtype=float))
    if len(candidates) == 0:
        return np.empty((0, pool.shape[1]), dtype=float)

    selected: list[np.ndarray] = []
    reference = existing if len(existing) else np.empty((0, candidates.shape[1]), dtype=float)
    center = np.full(candidates.shape[1], 0.5, dtype=float)

    while len(selected) < n_samples and len(candidates) > 0:
        if len(reference):
            nearest = pairwise_distances(candidates, reference).min(axis=1)
        else:
            nearest = np.linalg.norm(candidates - center, axis=1)
        winner = int(np.argmax(nearest))
        point = candidates[winner]
        selected.append(point)
        reference = np.vstack([reference, point.reshape(1, -1)])
        candidates = np.delete(candidates, winner, axis=0)

    return np.asarray(selected, dtype=float)


def _as_2d(values: np.ndarray | None, n_dim: int) -> np.ndarray:
    if values is None:
        return np.empty((0, n_dim), dtype=float)
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return np.empty((0, n_dim), dtype=float)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.shape[1] != n_dim:
        raise ValueError(f"expected existing points with {n_dim} columns, got {array.shape[1]}")
    return array


def _scale_unit(points: np.ndarray) -> np.ndarray:
    values = np.asarray(points, dtype=float)
    if values.size == 0:
        return values.reshape(0, 0) if values.ndim == 1 else values
    if values.ndim == 1:
        values = values.reshape(-1, 1)
    lower = values.min(axis=0)
    upper = values.max(axis=0)
    span = np.where((upper - lower) > 1.0e-12, upper - lower, 1.0)
    return np.clip((values - lower) / span, 0.0, 1.0)


def _unique_rows(values: np.ndarray, precision: int = 12) -> np.ndarray:
    if len(values) == 0:
        return values
    rounded = np.round(values, precision)
    _, index = np.unique(rounded, axis=0, return_index=True)
    return values[np.sort(index)]
