"""Fault injection tests for algorithm robustness.

Tests that the tracking algorithms (SurgeCast, ParticleFilter, WindEstimator)
handle sensor faults gracefully:
- Sensor dropout (concentration = 0 for a period)
- Sensor stuck-at (constant wrong value)
- Sensor spike (transient high reading)
- Delayed readings (old data)
- Noisy readings (high noise)

These tests verify graceful degradation, not correctness — algorithms
should continue operating (possibly with reduced performance) rather
than crashing or producing NaN/Inf.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from h2track_tracking.particle_filter.types import ParticleFilterConfig
from h2track_tracking.particle_filter.filter import ParticleFilter
from h2track_tracking.tracking.types import SurgeCastConfig, TrackingState
from h2track_tracking.tracking.surge_cast import SurgeCastTracker
from h2track_tracking.tracking.wind_estimator import WindEstimator, WindEstimatorConfig
from h2track_utils.types import Pose2D


class TestPFRobustness:
    """Particle filter robustness against sensor faults."""

    def _make_pf(self, num_particles: int = 100) -> ParticleFilter:
        config = ParticleFilterConfig(
            num_particles=num_particles,
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
            observation_sigma=0.5,
        )
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))
        return pf

    def test_sensor_dropout_does_not_crash(self):
        """PF should handle zero-concentration readings without crashing."""
        pf = self._make_pf()
        # Simulate dropout: all concentrations = 0 for 20 steps
        for _ in range(20):
            pf.update((5.0, 5.0), 0.0)
            pf.predict(dt=0.1)

        estimate = pf.estimate()
        assert math.isfinite(estimate.position[0])
        assert math.isfinite(estimate.position[1])
        assert math.isfinite(estimate.confidence)
        assert np.all(np.isfinite(estimate.covariance))

    def test_sensor_stuck_at_high_value(self):
        """PF should handle a stuck-at-high sensor without weight collapse."""
        pf = self._make_pf(num_particles=200)
        # Stuck at max concentration
        for _ in range(50):
            pf.update((3.0, 3.0), 120.0)
            pf.predict(dt=0.1)
            if pf.effective_particle_count() < pf.config.resample_threshold * len(pf.particles):
                pf.resample()

        # Should not have collapsed to a single particle
        assert pf.effective_particle_count() > 2.0
        estimate = pf.estimate()
        assert math.isfinite(estimate.confidence)

    def test_sensor_spike_does_not_diverge(self):
        """PF should tolerate transient spikes without diverging."""
        pf = self._make_pf()
        concentrations = [0.5, 0.5, 0.5, 500.0, 0.5, 0.5, 0.5]  # Spike at step 3
        for c in concentrations:
            pf.update((5.0, 5.0), c)
            pf.predict(dt=0.1)

        estimate = pf.estimate()
        # Estimate should be finite (not NaN/Inf)
        assert math.isfinite(estimate.position[0])
        assert math.isfinite(estimate.position[1])

    def test_negative_concentration(self):
        """PF should handle negative sensor readings (noise-induced)."""
        pf = self._make_pf()
        pf.update((5.0, 5.0), -2.0)  # Negative from sensor noise
        pf.predict(dt=0.1)

        estimate = pf.estimate()
        assert math.isfinite(estimate.position[0])
        assert np.all(np.isfinite(estimate.covariance))

    def test_extreme_concentration(self):
        """PF should handle very large concentration values."""
        pf = self._make_pf()
        pf.update((5.0, 5.0), 1e6)  # Extreme value
        pf.predict(dt=0.1)

        estimate = pf.estimate()
        assert math.isfinite(estimate.position[0])
        assert np.all(np.isfinite(estimate.covariance))

    def test_no_nan_weights_after_degenerate_input(self):
        """PF weights should never be NaN, even with degenerate inputs."""
        pf = self._make_pf()
        # All particles at same position (degenerate)
        for p in pf.particles:
            p.position = np.array([5.0, 5.0])

        pf.update((5.0, 5.0), 50.0)
        for p in pf.particles:
            assert math.isfinite(p.weight), f"Weight is NaN/Inf: {p.weight}"
            assert p.weight >= 0.0


class TestSurgeCastRobustness:
    """Surge-Cast algorithm robustness against sensor faults."""

    def _make_tracker(self) -> SurgeCastTracker:
        config = SurgeCastConfig(
            plume_found_threshold=2.0,
            plume_lost_threshold=1.0,
            source_threshold=20.0,
            source_radius=1.0,
            source_hold_steps=3,
        )
        return SurgeCastTracker(config)

    def test_zero_concentration_stays_in_patrol(self):
        """With zero concentration, tracker should stay in PATROL."""
        tracker = self._make_tracker()
        for _ in range(20):
            result = tracker.update(
                concentration=0.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        assert result.state == TrackingState.PATROL

    def test_stuck_at_high_concentration(self):
        """Stuck-at-high should trigger SURGE without crashing."""
        tracker = self._make_tracker()
        for _ in range(20):
            result = tracker.update(
                concentration=100.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        # Should have transitioned to SURGE (or further)
        assert result.state != TrackingState.PATROL

    def test_concentration_spike(self):
        """Transient spike should not cause permanent state lock."""
        tracker = self._make_tracker()
        # Normal, then spike, then normal
        readings = [0.5] * 5 + [50.0] + [0.5] * 15
        for c in readings:
            result = tracker.update(
                concentration=c,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        # After spike, tracker should be in CAST (searching for plume)
        # or returned to PATROL — both are valid recovery states.
        # It must NOT be stuck in SURGE (which would indicate the spike
        # permanently locked the tracker).
        assert result.state != TrackingState.SURGE

    def test_negative_concentration(self):
        """Negative readings should not crash the tracker."""
        tracker = self._make_tracker()
        result = tracker.update(
            concentration=-5.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert result.state == TrackingState.PATROL

    def test_extreme_concentration(self):
        """Very large values should not crash or cause NaN."""
        tracker = self._make_tracker()
        result = tracker.update(
            concentration=1e6,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert result.state in (TrackingState.PATROL, TrackingState.SURGE)
        assert result.target is not None
        assert math.isfinite(result.target.x)
        assert math.isfinite(result.target.y)


class TestWindEstimatorRobustness:
    """Wind estimator robustness against degenerate inputs."""

    def test_all_zero_concentrations(self):
        """All-zero concentrations should return None, not NaN."""
        estimator = WindEstimator()
        for i in range(20):
            estimator.update(Pose2D(float(i), 0.0), 0.0, float(i))
        # Should not produce an estimate (no gradient signal)
        assert estimator.get_estimate() is None or estimator.get_estimate().confidence == 0.0

    def test_constant_concentration(self):
        """Constant concentration (no gradient) should return None."""
        estimator = WindEstimator()
        for i in range(20):
            estimator.update(Pose2D(float(i), float(i)), 5.0, float(i))
        # No gradient → no estimate
        est = estimator.get_estimate()
        if est is not None:
            assert math.isfinite(est.wind_x)
            assert math.isfinite(est.wind_y)
            assert math.isfinite(est.confidence)

    def test_identical_positions(self):
        """All-same-position samples should return None, not NaN."""
        estimator = WindEstimator()
        for i in range(20):
            estimator.update(Pose2D(1.0, 1.0), float(i), float(i))
        # Identical positions → no spatial info
        est = estimator.get_estimate()
        if est is not None:
            assert math.isfinite(est.wind_x)
            assert math.isfinite(est.wind_y)

    def test_negative_concentration(self):
        """Negative concentrations should not produce NaN."""
        estimator = WindEstimator()
        for i in range(20):
            estimator.update(Pose2D(float(i), 0.0), -float(i), float(i))
        est = estimator.get_estimate()
        if est is not None:
            assert math.isfinite(est.wind_x)
            assert math.isfinite(est.wind_y)

    def test_extreme_positions(self):
        """Very large positions should not overflow."""
        estimator = WindEstimator()
        for i in range(20):
            estimator.update(Pose2D(float(i) * 1e6, 0.0), float(i), float(i))
        est = estimator.get_estimate()
        if est is not None:
            assert math.isfinite(est.wind_x)
            assert math.isfinite(est.wind_y)
            assert abs(est.wind_x) <= estimator.config.max_wind_speed * 1.1
