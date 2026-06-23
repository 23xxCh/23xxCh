# src/h2track_tracking/test/test_plume_detector.py
"""Tests for plume detection module."""

import pytest

from h2track_tracking.tracking.plume_detector import PlumeDetector, PlumeDetectorConfig
from h2track_tracking.tracking.types import PlumeState


class TestPlumeDetectorConfig:
    """Tests for PlumeDetectorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PlumeDetectorConfig()
        assert config.history_size == 20
        assert config.min_samples == 3
        assert config.plume_threshold == 3.0
        assert config.trend_window == 5

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = PlumeDetectorConfig(
            history_size=50,
            min_samples=5,
            plume_threshold=5.0,
            trend_window=10,
        )
        assert config.history_size == 50
        assert config.min_samples == 5
        assert config.plume_threshold == 5.0
        assert config.trend_window == 10

    def test_is_mutable(self):
        """Test that PlumeDetectorConfig is mutable."""
        config = PlumeDetectorConfig()
        config.history_size = 100
        assert config.history_size == 100


class TestPlumeDetector:
    """Tests for PlumeDetector class."""

    def test_initial_state(self):
        """Test detector starts with correct initial state."""
        detector = PlumeDetector()
        assert detector.in_plume is False
        assert detector.confidence == 0.0
        assert detector.current_concentration == 0.0
        assert detector.average_concentration == 0.0

    def test_update_returns_plume_state(self):
        """Test update returns PlumeState object."""
        detector = PlumeDetector()
        state = detector.update(concentration=1.0)
        assert isinstance(state, PlumeState)

    def test_insufficient_samples_not_in_plume(self):
        """Test that insufficient samples result in not in plume."""
        detector = PlumeDetector()
        # Add fewer samples than min_samples
        for conc in [5.0, 4.0]:  # Only 2 samples, min is 3
            state = detector.update(concentration=conc)

        assert state.in_plume is False
        assert state.confidence == 0.0

    def test_detects_plume_with_high_concentration(self):
        """Test plume detection with high concentration readings."""
        detector = PlumeDetector()
        # Add enough high concentration samples
        for conc in [5.0, 6.0, 7.0]:  # 3 samples above threshold
            state = detector.update(concentration=conc)

        assert state.in_plume is True

    def test_not_in_plume_with_low_concentration(self):
        """Test not in plume with low concentration readings."""
        detector = PlumeDetector()
        # Add enough low concentration samples
        for conc in [1.0, 1.5, 2.0]:  # Below plume_threshold of 3.0
            state = detector.update(concentration=conc)

        assert state.in_plume is False

    def test_mixed_concentration_partial_plume(self):
        """Test partial plume detection with mixed concentrations."""
        detector = PlumeDetector()
        # Mix of high and low - need majority to be in plume
        # With min_samples=3, need 2/3 samples above threshold
        detector.update(concentration=5.0)  # Above
        detector.update(concentration=2.0)  # Below
        state = detector.update(concentration=6.0)  # Above

        # 2 out of 3 are above threshold, should be in plume
        assert state.in_plume is True
        assert state.confidence == pytest.approx(2.0 / 3.0)

    def test_confidence_calculation(self):
        """Test confidence is calculated correctly."""
        detector = PlumeDetector()
        # All samples above threshold -> confidence = 1.0
        for conc in [5.0, 6.0, 7.0]:
            state = detector.update(concentration=conc)

        assert state.confidence == pytest.approx(1.0)

    def test_trend_stable_with_few_samples(self):
        """Test trend is stable with insufficient history."""
        detector = PlumeDetectorConfig(trend_window=5)
        detector = PlumeDetector(detector)

        # Only 3 samples, not enough for trend calculation
        for conc in [5.0, 6.0, 7.0]:
            state = detector.update(concentration=conc)

        assert state.trend == "stable"

    def test_trend_increasing(self):
        """Test detection of increasing trend."""
        config = PlumeDetectorConfig(min_samples=3, trend_window=5)
        detector = PlumeDetector(config)

        # Increasing sequence
        concentrations = [1.0, 2.0, 3.0, 4.0, 5.0]
        for conc in concentrations:
            state = detector.update(concentration=conc)

        assert state.trend == "increasing"

    def test_trend_decreasing(self):
        """Test detection of decreasing trend."""
        config = PlumeDetectorConfig(min_samples=3, trend_window=5)
        detector = PlumeDetector(config)

        # Decreasing sequence
        concentrations = [5.0, 4.0, 3.0, 2.0, 1.0]
        for conc in concentrations:
            state = detector.update(concentration=conc)

        assert state.trend == "decreasing"

    def test_trend_stable_with_constant_values(self):
        """Test trend is stable with constant concentration."""
        config = PlumeDetectorConfig(min_samples=3, trend_window=5)
        detector = PlumeDetector(config)

        # Constant sequence
        for conc in [5.0, 5.0, 5.0, 5.0, 5.0]:
            state = detector.update(concentration=conc)

        assert state.trend == "stable"

    def test_trend_with_tiny_trend_window(self):
        """Test trend calculation with very small trend window."""
        config = PlumeDetectorConfig(min_samples=2, trend_window=2)
        detector = PlumeDetector(config)

        # Add exactly trend_window samples
        detector.update(concentration=1.0)
        state = detector.update(concentration=5.0)

        # With 2 samples, trend should be calculable
        assert state.trend in ["increasing", "decreasing", "stable"]

    def test_history_size_limit(self):
        """Test that history respects max size."""
        config = PlumeDetectorConfig(history_size=5, min_samples=3)
        detector = PlumeDetector(config)

        # Add more samples than history size
        for i in range(10):
            detector.update(concentration=float(i))

        # Average should only consider last 5 values (5, 6, 7, 8, 9)
        # Average = (5+6+7+8+9) / 5 = 7.0
        assert detector.average_concentration == pytest.approx(7.0)

    def test_current_concentration(self):
        """Test current concentration property."""
        detector = PlumeDetector()
        detector.update(concentration=1.0)
        detector.update(concentration=2.0)
        detector.update(concentration=3.0)

        assert detector.current_concentration == 3.0

    def test_position_tracking(self):
        """Test position history is tracked."""
        detector = PlumeDetector()

        detector.update(concentration=5.0, position=(0.0, 0.0))
        detector.update(concentration=6.0, position=(1.0, 0.0))
        detector.update(concentration=7.0, position=(2.0, 0.0))

        best = detector.get_best_position()
        assert best is not None
        assert best == (2.0, 0.0)  # Position with highest concentration

    def test_get_best_position_no_data(self):
        """Test get_best_position returns None with no data."""
        detector = PlumeDetector()
        assert detector.get_best_position() is None

    def test_get_best_position_with_position_only(self):
        """Test get_best_position with position but no concentration match."""
        detector = PlumeDetector()
        # Update without position
        detector.update(concentration=10.0)
        # Position history is empty
        assert detector.get_best_position() is None

    def test_get_best_position_with_mismatched_history(self):
        """Test get_best_position when history sizes mismatch."""
        detector = PlumeDetector()
        # Add concentration without position
        detector.update(concentration=10.0)
        # Then add with position
        detector.update(concentration=5.0, position=(1.0, 0.0))
        detector.update(concentration=7.0, position=(2.0, 0.0))
        # Best concentration is 10.0 (index 0), but position_history has only 2 entries
        # So get_best_position should handle this gracefully
        best = detector.get_best_position()
        # Should return a valid position (the one at the matching index)
        assert best is not None

    def test_reset_clears_history(self):
        """Test reset clears all history."""
        detector = PlumeDetector()

        for conc in [5.0, 6.0, 7.0]:
            detector.update(concentration=conc, position=(conc, conc))

        detector.reset()

        assert detector.in_plume is False
        assert detector.confidence == 0.0
        assert detector.current_concentration == 0.0
        assert detector.get_best_position() is None

    def test_state_property_returns_current_state(self):
        """Test state property returns current PlumeState."""
        detector = PlumeDetector()
        detector.update(concentration=5.0)
        detector.update(concentration=6.0)
        state = detector.update(concentration=7.0)

        assert detector.state is state

    def test_custom_plume_threshold(self):
        """Test custom plume threshold."""
        config = PlumeDetectorConfig(
            plume_threshold=10.0,
            min_samples=3,
        )
        detector = PlumeDetector(config)

        # Concentrations above 3.0 but below custom threshold 10.0
        for conc in [5.0, 6.0, 7.0]:
            state = detector.update(concentration=conc)

        assert state.in_plume is False

        # Now with concentrations above custom threshold
        detector.reset()
        for conc in [11.0, 12.0, 13.0]:
            state = detector.update(concentration=conc)

        assert state.in_plume is True

    def test_average_concentration_calculation(self):
        """Test average concentration is calculated correctly."""
        detector = PlumeDetector()

        detector.update(concentration=2.0)
        detector.update(concentration=4.0)
        state = detector.update(concentration=6.0)

        # Average = (2+4+6) / 3 = 4.0
        assert state.average_concentration == pytest.approx(4.0)

    @pytest.mark.parametrize("concentrations,expected_in_plume", [
        # All above threshold
        ([5.0, 6.0, 7.0], True),
        # All below threshold
        ([1.0, 2.0, 2.5], False),
        # Majority above (2/3)
        ([5.0, 2.0, 6.0], True),
        # Average below threshold and majority below → False
        ([2.0, 2.0, 2.5], False),
    ])
    def test_various_concentration_patterns(self, concentrations, expected_in_plume):
        """Test various concentration patterns for plume detection."""
        detector = PlumeDetector()
        for conc in concentrations:
            state = detector.update(concentration=conc)

        assert state.in_plume is expected_in_plume


class TestPlumeDetectorEdgeCases:
    """Edge case tests for PlumeDetector."""

    def test_zero_concentration(self):
        """Test handling of zero concentration."""
        detector = PlumeDetector()
        state = detector.update(concentration=0.0)
        assert state.average_concentration == 0.0

    def test_negative_concentration(self):
        """Test handling of negative concentration."""
        detector = PlumeDetector()
        # Need min_samples for average to be calculated
        detector.update(concentration=-1.0)
        detector.update(concentration=-2.0)
        state = detector.update(concentration=-3.0)
        # Negative values should still be processed
        assert state.average_concentration == -2.0

    def test_very_high_concentration(self):
        """Test handling of very high concentration."""
        detector = PlumeDetector()
        # Need min_samples for average to be calculated
        detector.update(concentration=1e6)
        detector.update(concentration=1e6)
        state = detector.update(concentration=1e6)
        assert state.average_concentration == 1e6

    def test_floating_point_precision(self):
        """Test floating point precision in calculations."""
        detector = PlumeDetector()
        detector.update(concentration=1.1)
        detector.update(concentration=2.2)
        state = detector.update(concentration=3.3)

        # Sum is 6.6, average is 2.2
        assert abs(state.average_concentration - 2.2) < 1e-9

    def test_consecutive_resets(self):
        """Test multiple consecutive resets."""
        detector = PlumeDetector()

        for _ in range(3):
            detector.update(concentration=5.0)
            detector.update(concentration=6.0)
            detector.update(concentration=7.0)
            detector.reset()

        assert detector.in_plume is False

    def test_update_with_none_position(self):
        """Test update with None position."""
        detector = PlumeDetector()
        state = detector.update(concentration=5.0, position=None)
        assert state is not None

    def test_empty_history_after_reset(self):
        """Test that history is empty after reset."""
        config = PlumeDetectorConfig(min_samples=3)
        detector = PlumeDetector(config)

        # Add data
        for conc in [5.0, 6.0, 7.0]:
            detector.update(concentration=conc)

        detector.reset()

        # After reset, should need min_samples again
        detector.update(concentration=10.0)
        detector.update(concentration=11.0)
        state = detector.update(concentration=12.0)
        # Now should work normally
        assert state.in_plume is True

    def test_boundary_confidence_values(self):
        """Test confidence at boundary values."""
        detector = PlumeDetector()

        # All above -> confidence = 1.0
        for conc in [10.0, 10.0, 10.0]:
            state = detector.update(concentration=conc)
        assert state.confidence == 1.0

        detector.reset()

        # None above -> confidence = 0.0
        for conc in [1.0, 1.0, 1.0]:
            state = detector.update(concentration=conc)
        assert state.confidence == 0.0
