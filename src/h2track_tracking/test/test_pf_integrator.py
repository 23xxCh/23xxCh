# src/h2track_tracking/test/test_pf_integrator.py
"""Tests for particle filter integrator module."""

import pytest

from h2track_tracking.tracking.pf_integrator import (
    SourceEstimate,
    ParticleFilterIntegratorConfig,
    ParticleFilterIntegrator,
)
from h2track_tracking.tracking.types import Pose2D


class TestSourceEstimate:
    """Tests for SourceEstimate dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating SourceEstimate with all fields."""
        estimate = SourceEstimate(
            position=(3.0, 4.0),
            confidence=0.85,
            covariance=(0.1, 0.2, 0.0, 0.0),
        )
        assert estimate.position == (3.0, 4.0)
        assert estimate.confidence == 0.85
        assert estimate.covariance == (0.1, 0.2, 0.0, 0.0)

    def test_default_values(self):
        """Test SourceEstimate with minimal fields."""
        estimate = SourceEstimate(
            position=(0.0, 0.0),
            confidence=0.5,
            covariance=(1.0, 1.0, 0.0, 0.0),
        )
        assert estimate.position == (0.0, 0.0)
        assert estimate.confidence == 0.5

    def test_is_mutable(self):
        """Test that SourceEstimate is mutable."""
        estimate = SourceEstimate(
            position=(0.0, 0.0),
            confidence=0.5,
            covariance=(1.0, 1.0, 0.0, 0.0),
        )
        estimate.confidence = 0.7
        assert estimate.confidence == 0.7

    @pytest.mark.parametrize("covariance", [
        (0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0, 0.0),
        (0.5, 0.3, 0.1, 0.1),
        (10.0, 10.0, 0.0, 0.0),
    ])
    def test_various_covariance_values(self, covariance):
        """Test creating SourceEstimate with various covariance values."""
        estimate = SourceEstimate(
            position=(0.0, 0.0),
            confidence=0.5,
            covariance=covariance,
        )
        assert estimate.covariance == covariance


class TestParticleFilterIntegratorConfig:
    """Tests for ParticleFilterIntegratorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ParticleFilterIntegratorConfig()
        assert config.min_confidence == 0.3
        assert config.max_covariance == 10.0
        assert config.position_weight == 0.5

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = ParticleFilterIntegratorConfig(
            min_confidence=0.5,
            max_covariance=5.0,
            position_weight=0.7,
        )
        assert config.min_confidence == 0.5
        assert config.max_covariance == 5.0
        assert config.position_weight == 0.7

    def test_is_mutable(self):
        """Test that config is mutable."""
        config = ParticleFilterIntegratorConfig()
        config.min_confidence = 0.6
        assert config.min_confidence == 0.6

    @pytest.mark.parametrize("min_confidence,expected", [
        (0.0, 0.0),
        (0.3, 0.3),
        (0.5, 0.5),
        (1.0, 1.0),
    ])
    def test_various_min_confidence_values(self, min_confidence, expected):
        """Test creating config with various min_confidence values."""
        config = ParticleFilterIntegratorConfig(min_confidence=min_confidence)
        assert config.min_confidence == expected


class TestParticleFilterIntegrator:
    """Tests for ParticleFilterIntegrator class."""

    @pytest.fixture
    def integrator(self):
        """Create integrator with default config."""
        return ParticleFilterIntegrator()

    @pytest.fixture
    def integrator_with_config(self):
        """Create integrator with custom config."""
        config = ParticleFilterIntegratorConfig(
            min_confidence=0.5,
            max_covariance=5.0,
            position_weight=0.6,
        )
        return ParticleFilterIntegrator(config)

    def test_initial_state(self, integrator):
        """Test integrator starts with no estimate."""
        assert integrator.confidence == 0.0
        assert integrator.position is None
        assert integrator.average_confidence == 0.0

    def test_update_sets_estimate(self, integrator):
        """Test update sets the estimate."""
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        assert integrator.position == (5.0, 5.0)
        assert integrator.confidence == 0.8

    def test_update_without_covariance(self, integrator):
        """Test update without covariance uses default."""
        integrator.update(position=(5.0, 5.0), confidence=0.8)

        assert integrator.position == (5.0, 5.0)
        assert integrator.confidence == 0.8

    def test_get_navigational_hint_reliable(self, integrator):
        """Test get_navigational_hint returns position when reliable."""
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.8,  # Above min_confidence
            covariance=(0.5, 0.5, 0.0, 0.0),  # Below max_covariance
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is not None
        assert hint.x == 10.0
        assert hint.y == 10.0

    def test_get_navigational_hint_unreliable_no_estimate(self, integrator):
        """Test get_navigational_hint returns None with no estimate."""
        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

    def test_get_navigational_hint_unreliable_low_confidence(self, integrator):
        """Test get_navigational_hint returns None with low confidence."""
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.1,  # Below min_confidence of 0.3
            covariance=(0.5, 0.5, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

    def test_get_navigational_hint_unreliable_high_covariance(self, integrator):
        """Test get_navigational_hint returns None with high covariance."""
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.8,
            covariance=(15.0, 15.0, 0.0, 0.0),  # Above max_covariance of 10.0
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

    def test_get_weighted_target_reliable(self, integrator):
        """Test get_weighted_target returns weighted position when reliable."""
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.8,
            covariance=(0.5, 0.5, 0.0, 0.0),
        )

        current_target = Pose2D(0.0, 0.0)
        weighted = integrator.get_weighted_target(Pose2D(0.0, 0.0), current_target)

        assert weighted is not None
        # Weight = position_weight * confidence = 0.5 * 0.8 = 0.4
        # weighted_x = (1 - 0.4) * 0 + 0.4 * 10 = 4.0
        assert weighted.x == pytest.approx(4.0)
        assert weighted.y == pytest.approx(4.0)

    def test_get_weighted_target_unreliable(self, integrator):
        """Test get_weighted_target returns None when unreliable."""
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.1,  # Below min_confidence
            covariance=(0.5, 0.5, 0.0, 0.0),
        )

        weighted = integrator.get_weighted_target(
            Pose2D(0.0, 0.0), Pose2D(5.0, 5.0)
        )
        assert weighted is None

    def test_get_weighted_target_no_estimate(self, integrator):
        """Test get_weighted_target returns None with no estimate."""
        weighted = integrator.get_weighted_target(
            Pose2D(0.0, 0.0), Pose2D(5.0, 5.0)
        )
        assert weighted is None

    def test_confidence_history(self, integrator):
        """Test confidence is tracked in history."""
        integrator.update(position=(0.0, 0.0), confidence=0.5)
        integrator.update(position=(1.0, 1.0), confidence=0.7)
        integrator.update(position=(2.0, 2.0), confidence=0.9)

        # Average of 0.5, 0.7, 0.9 = 0.7
        assert integrator.average_confidence == pytest.approx(0.7)

    def test_confidence_history_max_size(self):
        """Test confidence history is limited to 20 entries."""
        config = ParticleFilterIntegratorConfig()
        integrator = ParticleFilterIntegrator(config)

        # Add more than 20 updates
        for i in range(25):
            integrator.update(position=(float(i), 0.0), confidence=float(i) / 100.0)

        # Should only have last 20 entries
        # Last 20: 0.05, 0.06, ..., 0.24
        # Average = (5+6+...+24) / 20 / 100 = 14.5 / 100 = 0.145
        expected = sum(range(5, 25)) / 20 / 100
        assert integrator.average_confidence == pytest.approx(expected)

    def test_reset_clears_state(self, integrator):
        """Test reset clears all state."""
        integrator.update(position=(5.0, 5.0), confidence=0.8)
        integrator.reset()

        assert integrator.confidence == 0.0
        assert integrator.position is None
        assert integrator.average_confidence == 0.0

    def test_custom_min_confidence(self):
        """Test custom min_confidence threshold."""
        config = ParticleFilterIntegratorConfig(min_confidence=0.6)
        integrator = ParticleFilterIntegrator(config)

        # Confidence of 0.5 should be unreliable
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.5,
            covariance=(0.5, 0.5, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

        # Confidence of 0.7 should be reliable
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.7,
            covariance=(0.5, 0.5, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is not None

    def test_custom_max_covariance(self):
        """Test custom max_covariance threshold."""
        config = ParticleFilterIntegratorConfig(max_covariance=5.0)
        integrator = ParticleFilterIntegrator(config)

        # Variance of 6.0 should be unreliable
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.8,
            covariance=(6.0, 0.5, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

        # Variance below threshold should be reliable
        integrator.update(
            position=(10.0, 10.0),
            confidence=0.8,
            covariance=(4.0, 4.0, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is not None

    def test_custom_position_weight(self):
        """Test custom position_weight affects weighting."""
        config = ParticleFilterIntegratorConfig(position_weight=0.8)
        integrator = ParticleFilterIntegrator(config)

        integrator.update(
            position=(10.0, 10.0),
            confidence=1.0,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        current_target = Pose2D(0.0, 0.0)
        weighted = integrator.get_weighted_target(Pose2D(0.0, 0.0), current_target)

        # Weight = 0.8 * 1.0 = 0.8
        # weighted_x = (1 - 0.8) * 0 + 0.8 * 10 = 8.0
        assert weighted.x == pytest.approx(8.0)
        assert weighted.y == pytest.approx(8.0)

    def test_position_property(self, integrator):
        """Test position property returns current estimate."""
        integrator.update(position=(3.0, 4.0), confidence=0.5)
        assert integrator.position == (3.0, 4.0)

    def test_confidence_property(self, integrator):
        """Test confidence property returns current confidence."""
        integrator.update(position=(0.0, 0.0), confidence=0.75)
        assert integrator.confidence == 0.75

    def test_weighted_target_with_same_position(self, integrator):
        """Test weighted target when PF and current target are same."""
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        weighted = integrator.get_weighted_target(
            Pose2D(0.0, 0.0), Pose2D(5.0, 5.0)
        )

        # Should be closer to (5, 5) due to weighting
        assert weighted.x == pytest.approx(5.0)
        assert weighted.y == pytest.approx(5.0)


class TestParticleFilterIntegratorEdgeCases:
    """Edge case tests for ParticleFilterIntegrator."""

    @pytest.fixture
    def integrator(self):
        """Create integrator for edge case testing."""
        return ParticleFilterIntegrator()

    def test_zero_confidence(self, integrator):
        """Test handling of zero confidence."""
        integrator.update(position=(5.0, 5.0), confidence=0.0)
        assert integrator.confidence == 0.0

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

    def test_maximum_confidence(self, integrator):
        """Test handling of maximum confidence."""
        integrator.update(
            position=(5.0, 5.0),
            confidence=1.0,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is not None

    def test_zero_covariance(self, integrator):
        """Test handling of zero covariance."""
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(0.0, 0.0, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is not None

    def test_negative_position(self, integrator):
        """Test handling of negative position values."""
        integrator.update(
            position=(-5.0, -10.0),
            confidence=0.8,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        assert integrator.position == (-5.0, -10.0)

    def test_large_position_values(self, integrator):
        """Test handling of large position values."""
        integrator.update(
            position=(1e6, 1e6),
            confidence=0.8,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        assert integrator.position == (1e6, 1e6)

    def test_boundary_min_confidence(self):
        """Test behavior at exact min_confidence boundary."""
        config = ParticleFilterIntegratorConfig(min_confidence=0.5)
        integrator = ParticleFilterIntegrator(config)

        # Exactly at threshold
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.5,
            covariance=(1.0, 1.0, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        # At threshold (>=) should be reliable
        assert hint is not None

    def test_boundary_max_covariance(self):
        """Test behavior at exact max_covariance boundary."""
        config = ParticleFilterIntegratorConfig(max_covariance=5.0)
        integrator = ParticleFilterIntegrator(config)

        # Exactly at threshold
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(5.0, 1.0, 0.0, 0.0),  # var_x == max
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        # At threshold (<=) should be reliable
        assert hint is not None

    def test_asymmetric_covariance(self, integrator):
        """Test handling of asymmetric covariance."""
        # High variance in X but low in Y
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(8.0, 0.1, 0.0, 0.0),  # X variance high
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        # X variance (8.0) < max (10.0), so should be reliable
        assert hint is not None

        # But if X variance exceeds max
        integrator.update(
            position=(5.0, 5.0),
            confidence=0.8,
            covariance=(15.0, 0.1, 0.0, 0.0),  # X variance too high
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        assert hint is None

    def test_multiple_updates_overwrite(self, integrator):
        """Test that multiple updates overwrite previous estimate."""
        integrator.update(position=(1.0, 1.0), confidence=0.5)
        integrator.update(position=(2.0, 2.0), confidence=0.7)
        integrator.update(position=(3.0, 3.0), confidence=0.9)

        assert integrator.position == (3.0, 3.0)
        assert integrator.confidence == 0.9

    def test_multiple_resets(self, integrator):
        """Test multiple consecutive resets."""
        for _ in range(3):
            integrator.update(position=(5.0, 5.0), confidence=0.8)
            integrator.reset()

        assert integrator.confidence == 0.0
        assert integrator.position is None

    def test_floating_point_precision(self, integrator):
        """Test floating point precision in calculations."""
        integrator.update(
            position=(1.1, 2.2),
            confidence=0.7,
            covariance=(0.1, 0.1, 0.0, 0.0),
        )

        current_target = Pose2D(3.3, 4.4)
        weighted = integrator.get_weighted_target(Pose2D(0.0, 0.0), current_target)

        assert weighted is not None
        # Weight = 0.5 * 0.7 = 0.35
        # weighted_x = (1 - 0.35) * 3.3 + 0.35 * 1.1
        #           = 0.65 * 3.3 + 0.35 * 1.1
        #           = 2.145 + 0.385 = 2.53
        expected_x = 0.65 * 3.3 + 0.35 * 1.1
        assert abs(weighted.x - expected_x) < 1e-9

    def test_confidence_history_with_zeros(self, integrator):
        """Test average_confidence with zero values in history."""
        integrator.update(position=(0.0, 0.0), confidence=0.0)
        integrator.update(position=(1.0, 1.0), confidence=0.5)
        integrator.update(position=(2.0, 2.0), confidence=1.0)

        # Average = (0.0 + 0.5 + 1.0) / 3 = 0.5
        assert integrator.average_confidence == pytest.approx(0.5)

    @pytest.mark.parametrize("confidence", [0.3, 0.5, 0.7, 1.0])
    def test_various_reliable_confidences(self, confidence):
        """Test various confidence values that should be reliable."""
        integrator = ParticleFilterIntegrator()
        integrator.update(
            position=(5.0, 5.0),
            confidence=confidence,
            covariance=(1.0, 1.0, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        # All should be >= min_confidence of 0.3
        assert hint is not None

    @pytest.mark.parametrize("confidence", [0.0, 0.1, 0.2, 0.29])
    def test_various_unreliable_confidences(self, confidence):
        """Test various confidence values that should be unreliable."""
        integrator = ParticleFilterIntegrator()
        integrator.update(
            position=(5.0, 5.0),
            confidence=confidence,
            covariance=(1.0, 1.0, 0.0, 0.0),
        )

        hint = integrator.get_navigational_hint(Pose2D(0.0, 0.0))
        # All should be < min_confidence of 0.3
        assert hint is None
