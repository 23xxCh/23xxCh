"""Ground-truth evaluation report — pure logic for RMSE and formatting.

GroundTruthSampler collects (estimate, truth) pairs over a run; this module
computes summary metrics (RMSE, success rate, path length) and formats them
as JSON/markdown. ROS-agnostic for easy unit testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class GroundTruthSample:
    """Single sample at a point in time during a run."""

    timestamp: float
    robot_pose: tuple[float, float]
    estimate: tuple[float, float] | None
    truth_concentration: float
    estimated_concentration: float


@dataclass(frozen=True)
class GroundTruthMetrics:
    """Summary metrics for a tracking run against ground truth."""

    source_rmse: float
    concentration_rmse: float
    time_to_source_sec: float
    path_length_m: float
    success_rate: float
    num_samples: int


def compute_ground_truth_metrics(
    samples: list[GroundTruthSample],
    source_truth: tuple[float, float],
) -> GroundTruthMetrics:
    """Compute summary metrics from samples and ground-truth source position.

    Args:
        samples: List of GroundTruthSample collected during the run.
        source_truth: True source position (x, y).

    Returns:
        GroundTruthMetrics with RMSE and path stats.
    """
    if not samples:
        return GroundTruthMetrics(
            source_rmse=float("inf"),
            concentration_rmse=float("inf"),
            time_to_source_sec=float("inf"),
            path_length_m=0.0,
            success_rate=0.0,
            num_samples=0,
        )

    # Source RMSE: only over samples that have an estimate
    estimated = [s for s in samples if s.estimate is not None]
    if estimated:
        squared_errors = [
            (s.estimate[0] - source_truth[0]) ** 2 + (s.estimate[1] - source_truth[1]) ** 2
            for s in estimated
        ]
        source_rmse = math.sqrt(sum(squared_errors) / len(squared_errors))
    else:
        source_rmse = float("inf")

    # Concentration RMSE
    conc_squared = [
        (s.estimated_concentration - s.truth_concentration) ** 2 for s in samples
    ]
    concentration_rmse = math.sqrt(sum(conc_squared) / len(conc_squared))

    # Path length: sum of consecutive robot pose distances
    path_length = 0.0
    for i in range(1, len(samples)):
        x1, y1 = samples[i - 1].robot_pose
        x2, y2 = samples[i].robot_pose
        path_length += math.hypot(x2 - x1, y2 - y1)

    # Time to source: first timestamp where estimate within 1m of truth
    time_to_source = float("inf")
    for s in estimated:
        dx = s.estimate[0] - source_truth[0]
        dy = s.estimate[1] - source_truth[1]
        if math.hypot(dx, dy) <= 1.0:
            time_to_source = s.timestamp
            break

    # Success rate: 1.0 if any estimate within 1m, else 0.0
    success = any(
        s.estimate is not None
        and math.hypot(
            s.estimate[0] - source_truth[0], s.estimate[1] - source_truth[1]
        )
        <= 1.0
        for s in samples
    )

    return GroundTruthMetrics(
        source_rmse=source_rmse,
        concentration_rmse=concentration_rmse,
        time_to_source_sec=time_to_source,
        path_length_m=path_length,
        success_rate=1.0 if success else 0.0,
        num_samples=len(samples),
    )


def format_report_json(metrics: GroundTruthMetrics) -> dict[str, Any]:
    """Format metrics as a JSON-serializable dict."""
    return {
        "source_rmse": metrics.source_rmse,
        "concentration_rmse": metrics.concentration_rmse,
        "time_to_source_sec": metrics.time_to_source_sec,
        "path_length_m": metrics.path_length_m,
        "success_rate": metrics.success_rate,
        "num_samples": metrics.num_samples,
    }
