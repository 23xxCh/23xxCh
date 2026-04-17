"""Integration tests for tracking pipeline: WindEstimator -> TrackingFusion -> SurgeCast."""

from __future__ import annotations

import math
import pytest

from h2track_tracking.tracking import (
    FusionConfig,
    SurgeCastConfig,
    SurgeCastTracker,
    TrackingAction,
    TrackingFusion,
    TrackingState,
    WindEstimator,
    WindEstimatorConfig,
)
from h2track_tracking.tracking.types import Pose2D


class TestWindEstimatorFusionIntegration:
    """Test integration of WindEstimator with TrackingFusion."""

    @pytest.fixture
    def wind_estimator(self) -> WindEstimator:
        """Create a WindEstimator with small sample requirement."""
        config = WindEstimatorConfig(
            history_size=50,
            min_samples_for_estimate=5,
            gradient_threshold=0.05,
        )
        return WindEstimator(config)

    @pytest.fixture
    def surge_config(self) -> SurgeCastConfig:
        """Create SurgeCastConfig for testing."""
        return SurgeCastConfig(
            plume_found_threshold=2.0,
            plume_lost_threshold=1.0,
            source_threshold=8.0,
            surge_step=0.5,
            cast_step=0.3,
            cast_distance_limit=2.0,
            wind_x=0.4,
            wind_y=0.0,
            use_particle_filter=True,
            min_pf_confidence=0.3,
            source_radius=0.5,
            source_hold_steps=2,
        )

    @pytest.fixture
    def surge_tracker(self, surge_config: SurgeCastConfig) -> SurgeCastTracker:
        """Create a SurgeCastTracker."""
        return SurgeCastTracker(surge_config)

    @pytest.fixture
    def fusion(self) -> TrackingFusion:
        """Create a TrackingFusion with weighted mode."""
        return TrackingFusion(FusionConfig(
            blending_mode="weighted",
            pf_weight_base=0.4,
            surge_weight=0.6,
            pf_confidence_threshold=0.3,
        ))

    def test_wind_estimator_produces_valid_estimate(
        self, wind_estimator: WindEstimator
    ) -> None:
        """Test that wind estimator produces valid estimate with gradient pattern."""
        # Create observations with concentration gradient in -X direction
        # Source is at negative X, so wind blows in +X direction
        for i in range(15):
            x = float(i) - 7.0  # X from -7 to 7
            concentration = 10.0 - abs(x)  # Higher concentration near source (X=0)
            wind_estimator.update(Pose2D(x, 0.0), concentration, float(i))

        estimate = wind_estimator.get_estimate()
        assert estimate is not None
        assert estimate.confidence > 0.0
        assert math.isfinite(estimate.wind_x)
        assert math.isfinite(estimate.wind_y)

    def test_surge_cast_uses_wind_from_estimator(
        self,
        wind_estimator: WindEstimator,
        surge_tracker: SurgeCastTracker,
    ) -> None:
        """Test that SurgeCast can use wind from WindEstimator."""
        # Build up wind estimate
        for i in range(15):
            x = float(i) - 7.0
            concentration = 10.0 - abs(x)
            wind_estimator.update(Pose2D(x, 0.0), concentration, float(i))

        wind_estimate = wind_estimator.get_estimate()
        assert wind_estimate is not None

        # Use wind estimate in surge cast
        wind = (wind_estimate.wind_x, wind_estimate.wind_y)
        action = surge_tracker.update(
            concentration=5.0,  # High concentration to trigger SURGE
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
            wind=wind,
        )

        assert action.state in (TrackingState.SURGE, TrackingState.PATROL)
        assert action.target is not None

    def test_fusion_integrates_surge_and_pf(
        self,
        surge_tracker: SurgeCastTracker,
        fusion: TrackingFusion,
    ) -> None:
        """Test that fusion integrates surge-cast action with PF estimate."""
        # Get surge action
        surge_action = surge_tracker.update(
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
            wind=(0.4, 0.0),
        )

        # PF estimate at (3.0, 3.0)
        pf_position = Pose2D(3.0, 3.0)
        pf_confidence = 0.8

        # Fuse
        fused_action = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=pf_position,
            pf_confidence=pf_confidence,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )

        # Result should be between surge target and PF target
        assert fused_action.target is not None
        assert fused_action.use_particle_filter is True

        # Fusion state should be updated
        state = fusion.state
        assert state.current_mode == "weighted"
        assert 0.0 < state.pf_contribution < 1.0
        assert 0.0 < state.surge_contribution < 1.0

    def test_full_pipeline_integration(
        self,
        wind_estimator: WindEstimator,
        surge_tracker: SurgeCastTracker,
        fusion: TrackingFusion,
    ) -> None:
        """Test full pipeline: WindEstimator -> SurgeCast -> Fusion."""
        # Simulate robot moving toward source
        robot_poses = [
            Pose2D(5.0, 0.0),
            Pose2D(4.0, 0.0),
            Pose2D(3.0, 0.0),
            Pose2D(2.0, 0.0),
            Pose2D(1.0, 0.0),
        ]
        concentrations = [2.0, 3.0, 4.5, 6.0, 7.5]  # Increasing toward source

        pf_estimate = Pose2D(0.5, 0.2)
        pf_confidence = 0.7

        for i, (pose, conc) in enumerate(zip(robot_poses, concentrations)):
            # Update wind estimator
            wind_estimator.update(pose, conc, float(i))

            # Get wind estimate if available
            wind_est = wind_estimator.get_estimate()
            wind = (wind_est.wind_x, wind_est.wind_y) if wind_est else (0.4, 0.0)

            # Update surge cast
            surge_action = surge_tracker.update(
                concentration=conc,
                robot_pose=pose,
                robot_yaw=math.pi,  # Heading toward source
                wind=wind,
            )

            # Fuse with PF estimate
            if pf_confidence >= 0.3:
                fused_action = fusion.compute_fused_action(
                    surge_action=surge_action,
                    pf_position=pf_estimate,
                    pf_confidence=pf_confidence,
                    concentration=conc,
                    robot_pose=pose,
                )
                action = fused_action
            else:
                action = surge_action

            # Verify action is valid
            assert action.target is not None
            assert math.isfinite(action.target.x)
            assert math.isfinite(action.target.y)


class TestFusionModesIntegration:
    """Test different fusion modes in tracking context."""

    @pytest.fixture
    def surge_action(self) -> TrackingAction:
        """Create a sample surge action."""
        return TrackingAction(
            target=Pose2D(1.0, 1.0),
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )

    def test_weighted_mode_blends_targets(self, surge_action: TrackingAction) -> None:
        """Test weighted mode blends surge and PF targets."""
        fusion = TrackingFusion(FusionConfig(
            blending_mode="weighted",
            pf_weight_base=0.4,
            surge_weight=0.6,
        ))

        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(3.0, 3.0),
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )

        # Target should be between (1,1) and (3,3)
        assert 1.0 < result.target.x < 3.0
        assert 1.0 < result.target.y < 3.0

    def test_switching_mode_selects_based_on_concentration(
        self, surge_action: TrackingAction
    ) -> None:
        """Test switching mode selects algorithm based on concentration."""
        fusion = TrackingFusion(FusionConfig(
            blending_mode="switching",
            min_plume_strength=3.0,
        ))

        # High concentration: use surge
        result_high = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.9,
            concentration=5.0,  # Above threshold
            robot_pose=Pose2D(0.0, 0.0),
        )
        assert fusion.state.current_mode == "surge_cast"
        assert result_high.target.x == surge_action.target.x

        # Reset fusion
        fusion.reset()

        # Low concentration with valid PF: use PF
        result_low = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.9,
            concentration=1.0,  # Below threshold
            robot_pose=Pose2D(0.0, 0.0),
        )
        assert fusion.state.current_mode == "particle_filter"
        assert result_low.target.x == 5.0

    def test_cascade_mode_guides_surge(
        self, surge_action: TrackingAction
    ) -> None:
        """Test cascade mode biases surge toward PF region."""
        fusion = TrackingFusion(FusionConfig(
            blending_mode="cascade",
        ))

        # PF far from surge target
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),  # Far from (1,1)
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )

        # Result should be biased toward PF
        assert result.target.x > surge_action.target.x
        assert fusion.state.current_mode == "cascade"


class TestEdgeCases:
    """Edge case tests for the integration."""

    def test_wind_estimator_with_no_gradient(self) -> None:
        """Test wind estimator with uniform concentration (no gradient)."""
        estimator = WindEstimator(WindEstimatorConfig(
            min_samples_for_estimate=5,
        ))

        # All same concentration - no gradient
        for i in range(10):
            estimator.update(Pose2D(float(i), 0.0), 5.0, float(i))

        estimate = estimator.get_estimate()
        # May or may not have estimate depending on gradient threshold
        # Just verify it doesn't crash

    def test_fusion_with_zero_pf_confidence(self) -> None:
        """Test fusion with zero PF confidence uses surge action."""
        fusion = TrackingFusion(FusionConfig())
        surge_action = TrackingAction(
            target=Pose2D(1.0, 1.0),
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )

        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.0,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )

        # Should use surge action
        assert result.target.x == surge_action.target.x
        assert result.target.y == surge_action.target.y

    def test_fusion_without_pf_estimate(self) -> None:
        """Test fusion without PF estimate uses surge action."""
        fusion = TrackingFusion(FusionConfig())
        surge_action = TrackingAction(
            target=Pose2D(1.0, 1.0),
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )

        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=None,  # No PF estimate
            pf_confidence=0.0,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )

        # Should use surge action
        assert result.target.x == surge_action.target.x
