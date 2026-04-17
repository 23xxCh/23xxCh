"""Tests for TrackingFusion."""

from __future__ import annotations

import pytest

from h2track_tracking.tracking.fusion import (
    TrackingFusion,
    FusionConfig,
    FusionState,
)
from h2track_tracking.tracking.types import Pose2D, TrackingAction, TrackingState


class TestFusionConfig:
    """Tests for FusionConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = FusionConfig()
        assert config.pf_weight_base == 0.3
        assert config.pf_confidence_threshold == 0.5
        assert config.surge_weight == 0.7
        assert config.blending_mode == "weighted"
        assert config.min_plume_strength == 2.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = FusionConfig(
            pf_weight_base=0.5,
            blending_mode="switching",
        )
        assert config.pf_weight_base == 0.5
        assert config.blending_mode == "switching"

    def test_all_blending_modes(self) -> None:
        """Test all valid blending modes."""
        for mode in ["weighted", "switching", "cascade"]:
            config = FusionConfig(blending_mode=mode)
            assert config.blending_mode == mode

    def test_frozen(self) -> None:
        """Test that config is immutable."""
        config = FusionConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.pf_weight_base = 0.5


class TestFusionState:
    """Tests for FusionState."""

    def test_default_values(self) -> None:
        """Test default state values."""
        state = FusionState()
        assert state.current_mode == "surge_cast"
        assert state.pf_contribution == 0.0
        assert state.surge_contribution == 1.0
        assert state.last_fused_target is None

    def test_mutable(self) -> None:
        """Test that state is mutable."""
        state = FusionState()
        state.current_mode = "weighted"
        assert state.current_mode == "weighted"


class TestTrackingFusion:
    """Tests for TrackingFusion."""

    @pytest.fixture
    def fusion(self) -> TrackingFusion:
        """Create a TrackingFusion with default config."""
        return TrackingFusion(FusionConfig())

    @pytest.fixture
    def fusion_switching(self) -> TrackingFusion:
        """Create a TrackingFusion with switching mode."""
        config = FusionConfig(blending_mode="switching")
        return TrackingFusion(config)

    @pytest.fixture
    def fusion_cascade(self) -> TrackingFusion:
        """Create a TrackingFusion with cascade mode."""
        config = FusionConfig(blending_mode="cascade")
        return TrackingFusion(config)

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

    @pytest.fixture
    def robot_pose(self) -> Pose2D:
        """Create a sample robot pose."""
        return Pose2D(0.0, 0.0)

    def test_init_default_config(self, fusion: TrackingFusion) -> None:
        """Test initialization with default config."""
        assert fusion.config.blending_mode == "weighted"
        assert fusion.state.current_mode == "surge_cast"

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = FusionConfig(blending_mode="switching")
        fusion = TrackingFusion(config)
        assert fusion.config.blending_mode == "switching"

    def test_weighted_no_pf_estimate(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test weighted fusion without PF estimate."""
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=None,
            pf_confidence=0.0,
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Should return surge action unchanged
        assert result.target.x == surge_action.target.x
        assert result.target.y == surge_action.target.y
        assert fusion.state.surge_contribution == 1.0

    def test_weighted_low_pf_confidence(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test weighted fusion with low PF confidence."""
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.2,  # Below threshold
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Should use surge action due to low confidence
        assert result.target.x == surge_action.target.x

    def test_weighted_with_pf_estimate(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test weighted fusion with valid PF estimate."""
        pf_position = Pose2D(3.0, 3.0)
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=pf_position,
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Result should be between surge target (1,1) and PF target (3,3)
        assert 1.0 < result.target.x < 3.0
        assert 1.0 < result.target.y < 3.0
        assert result.use_particle_filter is True

    def test_switching_high_concentration(
        self,
        fusion_switching: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test switching fusion with high concentration (in plume)."""
        result = fusion_switching.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.9,
            concentration=10.0,  # Above min_plume_strength
            robot_pose=robot_pose,
        )
        # Should use surge-cast
        assert result.target.x == surge_action.target.x
        assert fusion_switching.state.current_mode == "surge_cast"

    def test_switching_low_concentration(
        self,
        fusion_switching: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test switching fusion with low concentration (lost plume)."""
        pf_position = Pose2D(5.0, 5.0)
        result = fusion_switching.compute_fused_action(
            surge_action=surge_action,
            pf_position=pf_position,
            pf_confidence=0.9,
            concentration=1.0,  # Below min_plume_strength
            robot_pose=robot_pose,
        )
        # Should use particle filter
        assert result.target.x == pf_position.x
        assert result.target.y == pf_position.y
        assert fusion_switching.state.current_mode == "particle_filter"

    def test_switching_low_concentration_no_pf(
        self,
        fusion_switching: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test switching with low concentration but no valid PF."""
        result = fusion_switching.compute_fused_action(
            surge_action=surge_action,
            pf_position=None,
            pf_confidence=0.0,
            concentration=1.0,  # Below min_plume_strength
            robot_pose=robot_pose,
        )
        # Should fall back to surge-cast
        assert result.target.x == surge_action.target.x

    def test_cascade_no_pf_estimate(
        self,
        fusion_cascade: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test cascade fusion without PF estimate."""
        result = fusion_cascade.compute_fused_action(
            surge_action=surge_action,
            pf_position=None,
            pf_confidence=0.0,
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Should use surge action
        assert result.target.x == surge_action.target.x
        assert fusion_cascade.state.current_mode == "surge_cast"

    def test_cascade_with_pf_nearby(
        self,
        fusion_cascade: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test cascade fusion with PF estimate near surge target."""
        result = fusion_cascade.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(1.5, 1.5),  # Close to surge target (1,1)
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Result should be close to surge target
        assert abs(result.target.x - surge_action.target.x) < 0.5

    def test_cascade_with_pf_far(
        self,
        fusion_cascade: TrackingFusion,
        surge_action: TrackingAction,
        robot_pose: Pose2D,
    ) -> None:
        """Test cascade fusion with PF estimate far from surge target."""
        result = fusion_cascade.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),  # Far from surge target (1,1)
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=robot_pose,
        )
        # Result should be biased toward PF
        assert result.target.x > surge_action.target.x
        assert fusion_cascade.state.current_mode == "cascade"

    def test_reset(self, fusion: TrackingFusion, surge_action: TrackingAction, robot_pose: Pose2D) -> None:
        """Test reset clears state."""
        # Compute a fused action to modify state
        fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(3.0, 3.0),
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=robot_pose,
        )

        assert fusion.state.last_fused_target is not None

        fusion.reset()

        assert fusion.state.current_mode == "surge_cast"
        assert fusion.state.pf_contribution == 0.0
        assert fusion.state.last_fused_target is None

    def test_state_property(self, fusion: TrackingFusion) -> None:
        """Test state property returns current state."""
        state = fusion.state
        assert isinstance(state, FusionState)
        assert state.current_mode == "surge_cast"


class TestTrackingFusionEdgeCases:
    """Edge case tests for TrackingFusion."""

    @pytest.fixture
    def fusion(self) -> TrackingFusion:
        return TrackingFusion(FusionConfig())

    @pytest.fixture
    def surge_action(self) -> TrackingAction:
        return TrackingAction(
            target=Pose2D(1.0, 1.0),
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )

    def test_zero_pf_confidence(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
    ) -> None:
        """Test with zero PF confidence."""
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.0,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )
        # Should use surge action
        assert result.target.x == surge_action.target.x

    def test_perfect_pf_confidence(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
    ) -> None:
        """Test with perfect PF confidence."""
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(3.0, 3.0),
            pf_confidence=1.0,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )
        # Should blend toward PF
        assert result.target.x > surge_action.target.x

    def test_negative_positions(
        self,
        fusion: TrackingFusion,
        surge_action: TrackingAction,
    ) -> None:
        """Test with negative position values."""
        result = fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(-3.0, -3.0),
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=Pose2D(-5.0, -5.0),
        )
        # Should handle negative positions
        assert isinstance(result.target.x, float)

    def test_patrol_state(
        self,
        fusion: TrackingFusion,
    ) -> None:
        """Test with PATROL state."""
        patrol_action = TrackingAction(
            target=Pose2D(0.0, 0.0),
            state=TrackingState.PATROL,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )
        result = fusion.compute_fused_action(
            surge_action=patrol_action,
            pf_position=Pose2D(5.0, 5.0),
            pf_confidence=0.8,
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
        )
        # Should handle PATROL state
        assert result.state == TrackingState.PATROL

    def test_source_found_state(
        self,
        fusion: TrackingFusion,
    ) -> None:
        """Test with SOURCE_FOUND state."""
        found_action = TrackingAction(
            target=Pose2D(5.0, 5.0),
            state=TrackingState.SOURCE_FOUND,
            heading=0.0,
            step_size=0.0,
            use_particle_filter=False,
        )
        result = fusion.compute_fused_action(
            surge_action=found_action,
            pf_position=Pose2D(6.0, 6.0),
            pf_confidence=0.9,
            concentration=10.0,
            robot_pose=Pose2D(4.0, 4.0),
        )
        # Should preserve SOURCE_FOUND state
        assert result.state == TrackingState.SOURCE_FOUND
