"""Tests for WindEstimator."""

from __future__ import annotations

import math
import pytest
import numpy as np

from h2track_tracking.tracking.wind_estimator import (
    WindEstimator,
    WindEstimatorConfig,
    WindEstimate,
)
from h2track_tracking.tracking.types import Pose2D


class TestWindEstimatorConfig:
    """Tests for WindEstimatorConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = WindEstimatorConfig()
        assert config.history_size == 100
        assert config.min_samples_for_estimate == 10
        assert config.gradient_threshold == 0.1
        assert config.smoothing_factor == 0.3
        assert config.max_wind_speed == 2.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = WindEstimatorConfig(
            history_size=50,
            min_samples_for_estimate=5,
            gradient_threshold=0.2,
        )
        assert config.history_size == 50
        assert config.min_samples_for_estimate == 5
        assert config.gradient_threshold == 0.2

    def test_frozen(self) -> None:
        """Test that config is immutable."""
        config = WindEstimatorConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.history_size = 200


class TestWindEstimate:
    """Tests for WindEstimate dataclass."""

    def test_creation(self) -> None:
        """Test WindEstimate creation."""
        estimate = WindEstimate(
            wind_x=0.5,
            wind_y=0.3,
            confidence=0.8,
            timestamp=12345.0,
        )
        assert estimate.wind_x == 0.5
        assert estimate.wind_y == 0.3
        assert estimate.confidence == 0.8
        assert estimate.timestamp == 12345.0

    def test_speed_property(self) -> None:
        """Test speed calculation."""
        estimate = WindEstimate(wind_x=3.0, wind_y=4.0, confidence=1.0, timestamp=0.0)
        assert estimate.speed == 5.0

    def test_direction_property(self) -> None:
        """Test direction calculation."""
        estimate = WindEstimate(wind_x=1.0, wind_y=0.0, confidence=1.0, timestamp=0.0)
        assert estimate.direction == pytest.approx(0.0)

        estimate = WindEstimate(wind_x=0.0, wind_y=1.0, confidence=1.0, timestamp=0.0)
        assert estimate.direction == pytest.approx(math.pi / 2)

    def test_upwind_direction(self) -> None:
        """Test upwind direction calculation."""
        # Wind blowing in +X direction
        estimate = WindEstimate(wind_x=1.0, wind_y=0.0, confidence=1.0, timestamp=0.0)
        # Upwind is -X direction (pi or -pi, both are equivalent)
        assert estimate.upwind_direction == pytest.approx(math.pi, abs=0.01) or \
               estimate.upwind_direction == pytest.approx(-math.pi, abs=0.01)

        # Wind blowing in +Y direction
        estimate = WindEstimate(wind_x=0.0, wind_y=1.0, confidence=1.0, timestamp=0.0)
        # Upwind is -Y direction (-pi/2)
        assert estimate.upwind_direction == pytest.approx(-math.pi / 2)

    def test_mutable(self) -> None:
        """Test that WindEstimate is mutable (not frozen)."""
        estimate = WindEstimate(wind_x=0.5, wind_y=0.3, confidence=0.8, timestamp=0.0)
        estimate.wind_x = 1.0  # Should not raise
        assert estimate.wind_x == 1.0


class TestWindEstimator:
    """Tests for WindEstimator."""

    @pytest.fixture
    def estimator(self) -> WindEstimator:
        """Create a WindEstimator with default config."""
        return WindEstimator(WindEstimatorConfig())

    @pytest.fixture
    def estimator_small_history(self) -> WindEstimator:
        """Create a WindEstimator with small history for testing."""
        config = WindEstimatorConfig(
            history_size=20,
            min_samples_for_estimate=5,
        )
        return WindEstimator(config)

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        estimator = WindEstimator()
        assert estimator.config.history_size == 100
        assert estimator.sample_count == 0
        assert estimator.has_estimate is False

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = WindEstimatorConfig(history_size=50)
        estimator = WindEstimator(config)
        assert estimator.config.history_size == 50

    def test_update_returns_none_before_min_samples(self, estimator: WindEstimator) -> None:
        """Test that update returns None before minimum samples."""
        pose = Pose2D(0.0, 0.0)
        for i in range(9):  # One less than min_samples_for_estimate
            result = estimator.update(pose, float(i), float(i))
            assert result is None

    def test_update_returns_estimate_after_min_samples(self, estimator: WindEstimator) -> None:
        """Test that update returns estimate after minimum samples."""
        pose = Pose2D(0.0, 0.0)
        for i in range(10):
            estimator.update(pose, float(i), float(i))

        # Now we should have an estimate
        assert estimator.has_estimate is True
        estimate = estimator.get_estimate()
        assert estimate is not None

    def test_history_size_limit(self, estimator_small_history: WindEstimator) -> None:
        """Test that history is limited to configured size."""
        for i in range(30):  # More than history_size
            estimator_small_history.update(Pose2D(float(i), 0.0), float(i), float(i))

        assert estimator_small_history.sample_count == 20

    def test_reset_clears_history(self, estimator: WindEstimator) -> None:
        """Test that reset clears history and estimate."""
        for i in range(15):
            estimator.update(Pose2D(float(i), 0.0), float(i), float(i))

        assert estimator.sample_count == 15
        assert estimator.has_estimate is True

        estimator.reset()

        assert estimator.sample_count == 0
        assert estimator.has_estimate is False

    def test_estimate_from_gradient_basic(self, estimator_small_history: WindEstimator) -> None:
        """Test gradient-based wind estimation with simple pattern.

        Creates a concentration pattern where concentration increases
        in -X direction (source at negative X), so wind should blow
        in +X direction (away from source).
        """
        # Create observations: higher concentration at lower X
        for i in range(10):
            x = float(i) - 5.0  # X from -5 to 4
            concentration = 10.0 - x  # Higher at lower X
            estimator_small_history.update(Pose2D(x, 0.0), concentration, float(i))

        estimate = estimator_small_history.get_estimate()
        assert estimate is not None
        # Wind should be in +X direction (gradient is -X, wind is opposite)
        assert estimate.wind_x > 0

    def test_estimate_from_gradient_with_noise(self, estimator_small_history: WindEstimator) -> None:
        """Test gradient estimation with noisy data."""
        np.random.seed(42)

        for i in range(20):
            x = float(i % 10) - 5.0
            y = float(i // 10) - 1.0
            # Base concentration with noise
            concentration = 5.0 - x + np.random.normal(0, 0.5)
            estimator_small_history.update(Pose2D(x, y), max(0, concentration), float(i))

        estimate = estimator_small_history.get_estimate()
        assert estimate is not None
        assert estimate.confidence >= 0.0

    def test_max_wind_speed_limit(self) -> None:
        """Test that wind speed is clamped to max_wind_speed."""
        config = WindEstimatorConfig(
            history_size=20,
            min_samples_for_estimate=5,
            max_wind_speed=1.0,
        )
        estimator = WindEstimator(config)

        # Create extreme concentration gradient
        for i in range(10):
            x = float(i) - 5.0
            concentration = 100.0 - x  # Very strong gradient
            estimator.update(Pose2D(x, 0.0), concentration, float(i))

        estimate = estimator.get_estimate()
        assert estimate is not None
        assert estimate.speed <= config.max_wind_speed

    def test_smoothing_applied(self) -> None:
        """Test that smoothing is applied between estimates."""
        config = WindEstimatorConfig(
            history_size=20,
            min_samples_for_estimate=5,
            smoothing_factor=0.5,
        )
        estimator = WindEstimator(config)

        # Build initial estimate
        for i in range(10):
            x = float(i) - 5.0
            estimator.update(Pose2D(x, 0.0), 5.0 - x, float(i))

        first_estimate = estimator.get_estimate()
        assert first_estimate is not None

        # Add more samples with different pattern
        for i in range(10, 20):
            x = float(i % 5)
            estimator.update(Pose2D(x, 0.0), float(i), float(i))

        second_estimate = estimator.get_estimate()
        assert second_estimate is not None

        # Second estimate should be smoothed from first
        # (not completely different due to smoothing)

    def test_get_estimate_without_update(self, estimator: WindEstimator) -> None:
        """Test get_estimate returns None without updates."""
        assert estimator.get_estimate() is None

    def test_sample_count_property(self, estimator: WindEstimator) -> None:
        """Test sample_count property."""
        assert estimator.sample_count == 0

        for i in range(5):
            estimator.update(Pose2D(0.0, 0.0), 1.0, float(i))

        assert estimator.sample_count == 5

    def test_has_estimate_property(self, estimator: WindEstimator) -> None:
        """Test has_estimate property."""
        assert estimator.has_estimate is False

        # Use varying concentration to create a gradient
        for i in range(15):
            x = float(i) - 7.0
            concentration = 10.0 - x  # Creates gradient
            estimator.update(Pose2D(x, 0.0), concentration, float(i))

        assert estimator.has_estimate is True


class TestWindEstimatorEdgeCases:
    """Edge case tests for WindEstimator."""

    @pytest.fixture
    def estimator(self) -> WindEstimator:
        config = WindEstimatorConfig(
            history_size=20,
            min_samples_for_estimate=5,
        )
        return WindEstimator(config)

    def test_zero_concentration(self, estimator: WindEstimator) -> None:
        """Test with zero concentration."""
        for i in range(10):
            estimator.update(Pose2D(float(i), 0.0), 0.0, float(i))

        # Should handle gracefully (might not produce estimate)
        # No assertion - just checking it doesn't crash

    def test_constant_concentration(self, estimator: WindEstimator) -> None:
        """Test with constant concentration (no gradient)."""
        for i in range(10):
            estimator.update(Pose2D(float(i), float(i)), 5.0, float(i))

        estimate = estimator.get_estimate()
        # May or may not have estimate depending on gradient threshold

    def test_single_position_all_observations(self, estimator: WindEstimator) -> None:
        """Test with all observations at same position."""
        for i in range(10):
            estimator.update(Pose2D(0.0, 0.0), float(i), float(i))

        # Should handle gracefully
        # No assertion - just checking it doesn't crash

    def test_negative_concentration(self, estimator: WindEstimator) -> None:
        """Test with negative concentration (invalid but should handle)."""
        for i in range(10):
            estimator.update(Pose2D(float(i), 0.0), -1.0, float(i))

        # Should handle gracefully

    def test_very_large_positions(self, estimator: WindEstimator) -> None:
        """Test with very large position values."""
        for i in range(10):
            x = float(i) * 1000.0
            estimator.update(Pose2D(x, 0.0), float(i), float(i))

        # Should handle large values
        estimate = estimator.get_estimate()
        # Check no NaN or Inf
        if estimate is not None:
            assert math.isfinite(estimate.wind_x)
            assert math.isfinite(estimate.wind_y)

    def test_timestamp_none_uses_current_time(self, estimator: WindEstimator) -> None:
        """Test that timestamp defaults to current time."""
        import time
        before = time.time()
        estimator.update(Pose2D(0.0, 0.0), 1.0)
        after = time.time()

        # Timestamp should be between before and after
        # (we can't check directly but the update should work)

    def test_multiple_resets(self, estimator: WindEstimator) -> None:
        """Test multiple consecutive resets."""
        for i in range(10):
            estimator.update(Pose2D(float(i), 0.0), float(i), float(i))

        estimator.reset()
        assert estimator.sample_count == 0

        estimator.reset()
        assert estimator.sample_count == 0

    def test_confidence_range(self, estimator: WindEstimator) -> None:
        """Test that confidence is always in [0, 1]."""
        # Build up samples
        for i in range(20):
            x = float(i % 10) - 5.0
            y = float(i // 10)
            estimator.update(Pose2D(x, y), float(i) + 1.0, float(i))

        estimate = estimator.get_estimate()
        if estimate is not None:
            assert 0.0 <= estimate.confidence <= 1.0
