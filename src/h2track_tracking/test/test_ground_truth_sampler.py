"""Tests for GroundTruthSampler node — dump_to_json and get_metrics.

Service calls are mocked (GADEN /odor_value service not available in unit
tests). Verifies sample collection, JSON dump format, and metrics export.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from h2track_tracking.evaluation.ground_truth_report import GroundTruthSample
from h2track_tracking.evaluation.ground_truth_sampler import GroundTruthSampler


def _make_sample(t: float = 0.0, est: tuple[float, float] | None = None) -> GroundTruthSample:
    return GroundTruthSample(
        timestamp=t,
        robot_pose=(0.0, 0.0),
        estimate=est,
        truth_concentration=5.0,
        estimated_concentration=5.0,
    )


class TestGetMetrics:
    def test_empty_sampler_returns_inf_metrics(self) -> None:
        """Sampler with no samples → inf source_rmse."""
        sampler = GroundTruthSampler.__new__(GroundTruthSampler)
        sampler._samples = []
        sampler._source_truth = (0.0, 0.0)
        metrics = sampler.get_metrics()
        assert metrics["source_rmse"] == float("inf")
        assert metrics["num_samples"] == 0

    def test_metrics_reflect_collected_samples(self) -> None:
        """Sampler with 2 samples → num_samples = 2."""
        sampler = GroundTruthSampler.__new__(GroundTruthSampler)
        sampler._samples = [
            _make_sample(0.0, (1.0, 0.0)),
            _make_sample(1.0, (0.0, 1.0)),
        ]
        sampler._source_truth = (0.0, 0.0)
        metrics = sampler.get_metrics()
        assert metrics["num_samples"] == 2
        assert metrics["source_rmse"] == pytest.approx(1.0, abs=1e-6)
        assert metrics["success_rate"] == 1.0


class TestDumpToJson:
    def test_dump_creates_file_with_metrics(self, tmp_path: Path) -> None:
        """dump_to_json writes a valid JSON file with metrics."""
        sampler = GroundTruthSampler.__new__(GroundTruthSampler)
        sampler._samples = [_make_sample(0.0, (0.5, 0.0))]
        sampler._source_truth = (0.0, 0.0)
        out_file = tmp_path / "report.json"
        sampler.dump_to_json(out_file)
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "source_rmse" in data
        assert "samples" in data
        assert len(data["samples"]) == 1
        assert data["source_truth"] == [0.0, 0.0]

    def test_dump_creates_parent_directory(self, tmp_path: Path) -> None:
        """dump_to_json creates parent dirs if missing."""
        sampler = GroundTruthSampler.__new__(GroundTruthSampler)
        sampler._samples = []
        sampler._source_truth = (0.0, 0.0)
        nested = tmp_path / "nested" / "dir" / "report.json"
        sampler.dump_to_json(nested)
        assert nested.exists()


class TestSamplesProperty:
    def test_samples_returns_copy(self) -> None:
        """samples property returns a copy, not the internal list."""
        sampler = GroundTruthSampler.__new__(GroundTruthSampler)
        sampler._samples = [_make_sample(0.0)]
        sampler._source_truth = (0.0, 0.0)
        first = sampler.samples
        first.clear()
        # Internal list should be unaffected
        assert len(sampler._samples) == 1
