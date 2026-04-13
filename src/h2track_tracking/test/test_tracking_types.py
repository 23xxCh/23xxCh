# src/h2track_tracking/test/test_tracking_types.py
"""Tests for tracking module type definitions."""

import math
import pytest

from h2track_tracking.tracking.types import (
    TrackingState,
    Pose2D,
    TrackingAction,
    SurgeCastConfig,
    PlumeState,
)


class TestTrackingState:
    """Tests for TrackingState enum."""

    def test_has_expected_states(self):
        """Verify all expected states exist."""
        assert hasattr(TrackingState, "PATROL")
        assert hasattr(TrackingState, "SURGE")
        assert hasattr(TrackingState, "CAST")
        assert hasattr(TrackingState, "SOURCE_FOUND")

    def test_states_are_unique(self):
        """Verify each state has unique value."""
        states = [TrackingState.PATROL, TrackingState.SURGE, TrackingState.CAST, TrackingState.SOURCE_FOUND]
        values = [s.value for s in states]
        assert len(values) == len(set(values))

    def test_state_ordering(self):
        """Verify states are comparable."""
        assert TrackingState.PATROL != TrackingState.SURGE
        assert TrackingState.SURGE != TrackingState.CAST
        assert TrackingState.CAST != TrackingState.SOURCE_FOUND


class TestPose2D:
    """Tests for Pose2D dataclass."""

    def test_creation_with_position(self):
        """Test creating a Pose2D with x, y coordinates."""
        pose = Pose2D(1.0, 2.0)
        assert pose.x == 1.0
        assert pose.y == 2.0

    def test_creation_with_zero(self):
        """Test creating a Pose2D at origin."""
        pose = Pose2D(0.0, 0.0)
        assert pose.x == 0.0
        assert pose.y == 0.0

    def test_creation_with_negative_values(self):
        """Test creating a Pose2D with negative coordinates."""
        pose = Pose2D(-1.5, -2.5)
        assert pose.x == -1.5
        assert pose.y == -2.5

    def test_is_frozen(self):
        """Test that Pose2D is immutable."""
        pose = Pose2D(1.0, 2.0)
        with pytest.raises(Exception):
            pose.x = 3.0

    def test_distance_to_same_point(self):
        """Test distance to same point is zero."""
        pose = Pose2D(1.0, 2.0)
        assert pose.distance_to(pose) == 0.0

    def test_distance_to_different_point(self):
        """Test distance calculation between two points."""
        pose1 = Pose2D(0.0, 0.0)
        pose2 = Pose2D(3.0, 4.0)
        assert pose1.distance_to(pose2) == 5.0

    def test_distance_to_negative_point(self):
        """Test distance with negative coordinates."""
        pose1 = Pose2D(-1.0, -1.0)
        pose2 = Pose2D(2.0, 3.0)
        expected = math.hypot(3.0, 4.0)
        assert pose1.distance_to(pose2) == expected

    def test_distance_symmetry(self):
        """Test that distance is symmetric."""
        pose1 = Pose2D(1.0, 2.0)
        pose2 = Pose2D(4.0, 6.0)
        assert pose1.distance_to(pose2) == pose2.distance_to(pose1)

    def test_distance_with_float_precision(self):
        """Test distance calculation with float values."""
        pose1 = Pose2D(0.0, 0.0)
        pose2 = Pose2D(1.0, 1.0)
        expected = math.sqrt(2.0)
        assert abs(pose1.distance_to(pose2) - expected) < 1e-9


class TestTrackingAction:
    """Tests for TrackingAction dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating TrackingAction with all fields."""
        target = Pose2D(5.0, 5.0)
        action = TrackingAction(
            target=target,
            state=TrackingState.SURGE,
            heading=math.pi / 4,
            step_size=0.5,
            use_particle_filter=True,
        )
        assert action.target == target
        assert action.state == TrackingState.SURGE
        assert action.heading == math.pi / 4
        assert action.step_size == 0.5
        assert action.use_particle_filter is True

    def test_is_frozen(self):
        """Test that TrackingAction is immutable."""
        target = Pose2D(0.0, 0.0)
        action = TrackingAction(
            target=target,
            state=TrackingState.PATROL,
            heading=0.0,
            step_size=0.3,
            use_particle_filter=False,
        )
        with pytest.raises(Exception):
            action.step_size = 1.0

    @pytest.mark.parametrize("state", [
        TrackingState.PATROL,
        TrackingState.SURGE,
        TrackingState.CAST,
        TrackingState.SOURCE_FOUND,
    ])
    def test_can_create_with_each_state(self, state):
        """Test creating action with each tracking state."""
        action = TrackingAction(
            target=Pose2D(0.0, 0.0),
            state=state,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )
        assert action.state == state

    @pytest.mark.parametrize("heading,expected_sin", [
        (0.0, 0.0),           # East
        (math.pi / 2, 1.0),   # North
        (math.pi, 0.0),       # West
        (-math.pi / 2, -1.0), # South
    ])
    def test_heading_values(self, heading, expected_sin):
        """Test various heading values."""
        action = TrackingAction(
            target=Pose2D(0.0, 0.0),
            state=TrackingState.SURGE,
            heading=heading,
            step_size=1.0,
            use_particle_filter=False,
        )
        assert abs(math.sin(action.heading) - expected_sin) < 1e-9


class TestSurgeCastConfig:
    """Tests for SurgeCastConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SurgeCastConfig()
        assert config.plume_found_threshold == 5.0
        assert config.plume_lost_threshold == 2.0
        assert config.source_threshold == 20.0
        assert config.surge_step == 0.5
        assert config.cast_step == 0.3
        assert config.cast_distance_limit == 3.0
        assert config.use_particle_filter is True
        assert config.min_pf_confidence == 0.3
        assert config.wind_x == 0.4
        assert config.wind_y == 0.0
        assert config.history_size == 50
        assert config.plume_confirm_samples == 3
        assert config.source_radius == 1.0
        assert config.source_hold_steps == 2

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = SurgeCastConfig(
            plume_found_threshold=3.0,
            plume_lost_threshold=1.0,
            source_threshold=15.0,
            surge_step=0.8,
            cast_step=0.4,
        )
        assert config.plume_found_threshold == 3.0
        assert config.plume_lost_threshold == 1.0
        assert config.source_threshold == 15.0
        assert config.surge_step == 0.8
        assert config.cast_step == 0.4

    def test_is_frozen(self):
        """Test that config is immutable."""
        config = SurgeCastConfig()
        with pytest.raises(Exception):
            config.surge_step = 1.0

    def test_upwind_direction_no_wind(self):
        """Test upwind direction when there's no wind."""
        config = SurgeCastConfig(wind_x=0.0, wind_y=0.0)
        assert config.upwind_direction == 0.0

    def test_upwind_direction_with_wind(self):
        """Test upwind direction calculation with wind."""
        # Wind blowing in +X direction (to the east)
        config = SurgeCastConfig(wind_x=1.0, wind_y=0.0)
        # Upwind should be opposite: west (pi or -pi, both are equivalent)
        # atan2(0, -1) returns -pi in Python, which is equivalent to pi
        assert abs(abs(config.upwind_direction) - math.pi) < 1e-9

    def test_upwind_direction_with_negative_wind(self):
        """Test upwind direction with negative wind components."""
        # Wind blowing in -Y direction (to the south)
        config = SurgeCastConfig(wind_x=0.0, wind_y=-1.0)
        # Upwind should be north (pi/2)
        assert abs(config.upwind_direction - math.pi / 2) < 1e-9

    def test_wind_direction(self):
        """Test wind direction property."""
        config = SurgeCastConfig(wind_x=1.0, wind_y=0.0)
        assert config.wind_direction == 0.0

        config2 = SurgeCastConfig(wind_x=0.0, wind_y=1.0)
        assert abs(config2.wind_direction - math.pi / 2) < 1e-9

    def test_has_wind_true(self):
        """Test has_wind property when wind is present."""
        config = SurgeCastConfig(wind_x=0.5, wind_y=0.5)
        assert config.has_wind is True

    def test_has_wind_false_no_wind(self):
        """Test has_wind property when wind is negligible."""
        config = SurgeCastConfig(wind_x=0.05, wind_y=0.05)
        # hypot(0.05, 0.05) = 0.0707... which is < 0.1
        assert config.has_wind is False

    def test_has_wind_false_zero(self):
        """Test has_wind property when wind is zero."""
        config = SurgeCastConfig(wind_x=0.0, wind_y=0.0)
        assert config.has_wind is False

    def test_threshold_ordering(self):
        """Test that thresholds maintain expected ordering."""
        config = SurgeCastConfig()
        # plume_lost < plume_found < source
        assert config.plume_lost_threshold < config.plume_found_threshold
        assert config.plume_found_threshold < config.source_threshold


class TestPlumeState:
    """Tests for PlumeState dataclass."""

    def test_default_state(self):
        """Test default PlumeState values."""
        state = PlumeState()
        assert state.in_plume is False
        assert state.confidence == 0.0
        assert state.average_concentration == 0.0
        assert state.trend == "stable"

    def test_custom_state(self):
        """Test creating PlumeState with custom values."""
        state = PlumeState(
            in_plume=True,
            confidence=0.85,
            average_concentration=7.5,
            trend="increasing",
        )
        assert state.in_plume is True
        assert state.confidence == 0.85
        assert state.average_concentration == 7.5
        assert state.trend == "increasing"

    def test_is_mutable(self):
        """Test that PlumeState is mutable (not frozen)."""
        state = PlumeState()
        state.in_plume = True
        state.confidence = 0.5
        assert state.in_plume is True
        assert state.confidence == 0.5

    @pytest.mark.parametrize("trend", ["increasing", "decreasing", "stable"])
    def test_valid_trend_values(self, trend):
        """Test creating PlumeState with valid trend values."""
        state = PlumeState(trend=trend)
        assert state.trend == trend

    def test_confidence_range(self):
        """Test confidence is typically in [0, 1] range."""
        # Create states with various confidence values
        state_low = PlumeState(confidence=0.0)
        state_mid = PlumeState(confidence=0.5)
        state_high = PlumeState(confidence=1.0)

        assert state_low.confidence == 0.0
        assert state_mid.confidence == 0.5
        assert state_high.confidence == 1.0
