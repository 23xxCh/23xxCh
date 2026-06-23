"""Tests for ground_truth_report — pure logic for RMSE and report generation.

GroundTruthSampler collects (estimate, truth) pairs over a run; this module
computes summary metrics (RMSE, success rate, path length) and formats them.
"""

from __future__ import annotations

import math

import pytest

from h2track_tracking.evaluation.ground_truth_report import (
    GroundTruthMetrics,
    GroundTruthSample,
    compute_ground_truth_metrics,
    format_report_json,
)


class TestGroundTruthMetrics:
    def test_zero_rmse_when_estimate_matches_truth(self) -> None:
        """RMSE = 0 when all estimates equal truth."""
        samples = [
            GroundTruthSample(
                timestamp=0.0,
                robot_pose=(0.0, 0.0),
                estimate=(1.0, 2.0),
                truth_concentration=5.0,
                estimated_concentration=5.0,
            ),
        ]
        source_truth = (1.0, 2.0)
        metrics = compute_ground_truth_metrics(samples, source_truth)
        assert metrics.source_rmse == pytest.approx(0.0)


class TestSourceRMSE:
    def test_rmse_computes_distance(self) -> None:
        """Single sample: estimate (2,0), truth (0,0) → RMSE = 2."""
        samples = [
            GroundTruthSample(
                timestamp=0.0,
                robot_pose=(0.0, 0.0),
                estimate=(2.0, 0.0),
                truth_concentration=0.0,
                estimated_concentration=0.0,
            ),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.source_rmse == pytest.approx(2.0)

    def test_rmse_averages_multiple_samples(self) -> None:
        """Two samples: errors 3m and 4m → RMSE = sqrt((9+16)/2) = sqrt(12.5)."""
        samples = [
            GroundTruthSample(
                timestamp=0.0,
                robot_pose=(0.0, 0.0),
                estimate=(3.0, 0.0),
                truth_concentration=0.0,
                estimated_concentration=0.0,
            ),
            GroundTruthSample(
                timestamp=1.0,
                robot_pose=(0.0, 0.0),
                estimate=(0.0, 4.0),
                truth_concentration=0.0,
                estimated_concentration=0.0,
            ),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.source_rmse == pytest.approx(math.sqrt(12.5))


class TestPathLength:
    def test_path_length_sums_consecutive_distances(self) -> None:
        """Three samples: (0,0)→(1,0)→(1,1) → path = 1 + 1 = 2."""
        samples = [
            GroundTruthSample(0.0, (0.0, 0.0), None, 0.0, 0.0),
            GroundTruthSample(1.0, (1.0, 0.0), None, 0.0, 0.0),
            GroundTruthSample(2.0, (1.0, 1.0), None, 0.0, 0.0),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.path_length_m == pytest.approx(2.0)

    def test_path_length_zero_for_single_sample(self) -> None:
        """Single sample → path length = 0."""
        samples = [GroundTruthSample(0.0, (0.0, 0.0), None, 0.0, 0.0)]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.path_length_m == pytest.approx(0.0)


class TestEmptyAndSuccess:
    def test_empty_samples_returns_inf_metrics(self) -> None:
        """No samples → inf RMSE, 0 path, 0 success."""
        metrics = compute_ground_truth_metrics([], source_truth=(0.0, 0.0))
        assert math.isinf(metrics.source_rmse)
        assert metrics.path_length_m == 0.0
        assert metrics.success_rate == 0.0
        assert metrics.num_samples == 0

    def test_success_rate_one_when_estimate_within_1m(self) -> None:
        """Estimate within 1m of truth → success_rate = 1.0."""
        samples = [
            GroundTruthSample(0.0, (0.0, 0.0), (0.5, 0.0), 0.0, 0.0),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.success_rate == 1.0
        assert metrics.time_to_source_sec == pytest.approx(0.0)

    def test_success_rate_zero_when_estimate_far(self) -> None:
        """Estimate 5m away → success_rate = 0.0, time_to_source = inf."""
        samples = [
            GroundTruthSample(10.0, (0.0, 0.0), (5.0, 0.0), 0.0, 0.0),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.success_rate == 0.0
        assert math.isinf(metrics.time_to_source_sec)


class TestJsonFormat:
    def test_json_contains_all_fields(self) -> None:
        """JSON report should contain all metric fields."""
        samples = [GroundTruthSample(0.0, (0.0, 0.0), (1.0, 0.0), 5.0, 4.0)]
        metrics = compute_ground_truth_metrics(samples, source_truth=(1.0, 0.0))
        report = format_report_json(metrics)
        assert "source_rmse" in report
        assert "concentration_rmse" in report
        assert "time_to_source_sec" in report
        assert "path_length_m" in report
        assert "success_rate" in report
        assert "num_samples" in report
        assert report["num_samples"] == 1

    def test_concentration_rmse_computes_error(self) -> None:
        """Two samples: conc errors 1 and 2 → RMSE = sqrt((1+4)/2)."""
        samples = [
            GroundTruthSample(0.0, (0.0, 0.0), None, 5.0, 4.0),
            GroundTruthSample(1.0, (0.0, 0.0), None, 5.0, 7.0),
        ]
        metrics = compute_ground_truth_metrics(samples, source_truth=(0.0, 0.0))
        assert metrics.concentration_rmse == pytest.approx(math.sqrt(2.5))
