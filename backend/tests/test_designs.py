from __future__ import annotations

import numpy as np
import pytest

from optlab.core.designs import coverage_summary, space_filling_design, synthetic_objective_coverage_dataset


@pytest.mark.parametrize(
    ("n_dim", "min_nearest_p10", "min_projection_occupancy"),
    [
        (1, 0.01, 1.0),
        (2, 0.08, 1.0),
        (3, 0.20, 0.95),
        (10, 0.90, 0.75),
        (20, 1.40, 0.75),
        (30, 1.80, 0.75),
    ],
)
def test_space_filling_design_covers_encoded_variable_bounds(
    n_dim: int,
    min_nearest_p10: float,
    min_projection_occupancy: float,
) -> None:
    design = space_filling_design(n_samples=64, n_dim=n_dim, seed=100 + n_dim)
    summary = coverage_summary(design)

    assert design.shape == (64, n_dim)
    assert np.all(design >= 0.0)
    assert np.all(design <= 1.0)
    assert summary["axis_range_min"] > 0.94
    assert summary["nearest_p10"] > min_nearest_p10
    assert summary["projection_occupancy_min"] >= min_projection_occupancy
    assert np.isfinite(summary["centered_discrepancy"])


def test_space_filling_design_avoids_existing_points() -> None:
    existing = space_filling_design(n_samples=16, n_dim=6, seed=8)
    design = space_filling_design(n_samples=16, n_dim=6, seed=8, existing=existing)
    distances = np.sqrt(np.sum((design[:, None, :] - existing[None, :, :]) ** 2, axis=2))

    assert distances.min() > 0.05


def test_space_filling_design_rejects_existing_points_with_wrong_dimension() -> None:
    with pytest.raises(ValueError, match="expected existing points with 4 columns"):
        space_filling_design(n_samples=4, n_dim=4, seed=8, existing=np.zeros((3, 2)))


def test_coverage_summary_detects_poor_diagonal_projection_coverage() -> None:
    diagonal = np.linspace(0.0, 1.0, 64)
    points = np.column_stack([diagonal, diagonal])
    summary = coverage_summary(points)

    assert summary["axis_range_min"] == pytest.approx(1.0)
    assert summary["projection_occupancy_min"] <= 0.25


@pytest.mark.parametrize("n_objectives", [2, 3, 4, 6])
def test_synthetic_objective_coverage_dataset_spans_every_objective(n_objectives: int) -> None:
    x, y = synthetic_objective_coverage_dataset(
        n_samples=96,
        n_variables=12,
        n_objectives=n_objectives,
        seed=300 + n_objectives,
    )

    objective_summary = coverage_summary(y)

    assert x.shape == (96, 12)
    assert y.shape == (96, n_objectives)
    assert np.all(y >= 0.0)
    assert np.all(y <= 1.0)
    assert objective_summary["axis_range_min"] > 0.95
    assert objective_summary["projection_occupancy_min"] >= 0.90
    assert objective_summary["nearest_p10"] > 0.03
    assert objective_summary["centered_discrepancy"] < 0.06
    assert objective_summary["mean_nearest_distance"] > 0.05
    assert np.linalg.matrix_rank(np.cov(y, rowvar=False), tol=1.0e-6) == n_objectives
