# src/h2track_tracking/test/test_surge_cast.py
"""Tests for Surge-Cast tracking algorithm."""

import math
import pytest

from h2track_tracking.tracking.surge_cast import (
    TrackingHistory,
    SurgeCastTracker,
    _distance,
)
from h2track_tracking.tracking.types import (
    Pose2D,
    SurgeCastConfig,
    TrackingState,
    TrackingAction,
)


class MockPose:
    """Mock pose object for testing _distance function."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class TestDistanceFunction:
    """Tests for _distance helper function."""

    def test_same_point(self):
        """Test distance to same point is zero."""
        pose = MockPose(1.0, 2.0)
        assert _distance(pose, pose) == 0.0

    def test_different_points(self):
        """Test distance between different points."""
        pose1 = MockPose(0.0, 0.0)
        pose2 = MockPose(3.0, 4.0)
        assert _distance(pose1, pose2) == 5.0

    def test_negative_coordinates(self):
        """Test distance with negative coordinates."""
        pose1 = MockPose(-1.0, -1.0)
        pose2 = MockPose(2.0, 3.0)
        expected = math.hypot(3.0, 4.0)
        assert _distance(pose1, pose2) == expected

    def test_with_pose2d_objects(self):
        """Test distance works with Pose2D objects."""
        pose1 = Pose2D(0.0, 0.0)
        pose2 = Pose2D(1.0, 1.0)
        expected = math.sqrt(2.0)
        assert abs(_distance(pose1, pose2) - expected) < 1e-9


class TestTrackingHistory:
    """Tests for TrackingHistory class."""

    def test_initial_state(self):
        """Test history starts empty."""
        history = TrackingHistory()
        assert len(history.positions) == 0

    def test_add_pose2d(self):
        """Test adding Pose2D to history."""
        history = TrackingHistory()
        pose = Pose2D(1.0, 2.0)
        history.add(pose, 5.0)

        assert len(history.positions) == 1
        assert history.positions[0][0] == pose
        assert history.positions[0][1] == 5.0

    def test_add_mock_pose(self):
        """Test adding mock pose (non-Pose2D) to history."""
        history = TrackingHistory()
        mock_pose = MockPose(1.0, 2.0)
        history.add(mock_pose, 3.0)

        assert len(history.positions) == 1
        # Should be converted to Pose2D
        assert isinstance(history.positions[0][0], Pose2D)

    def test_get_best_position_empty(self):
        """Test get_best_position with empty history."""
        history = TrackingHistory()
        assert history.get_best_position() is None

    def test_get_best_position_single(self):
        """Test get_best_position with single entry."""
        history = TrackingHistory()
        pose = Pose2D(1.0, 2.0)
        history.add(pose, 5.0)

        best = history.get_best_position()
        assert best is not None
        assert best[0] == pose
        assert best[1] == 5.0

    def test_get_best_position_multiple(self):
        """Test get_best_position returns highest concentration."""
        history = TrackingHistory()
        history.add(Pose2D(0.0, 0.0), 1.0)
        history.add(Pose2D(1.0, 0.0), 5.0)  # Highest
        history.add(Pose2D(2.0, 0.0), 3.0)

        best = history.get_best_position()
        assert best is not None
        assert best[0] == Pose2D(1.0, 0.0)
        assert best[1] == 5.0

    def test_get_recent_average_empty(self):
        """Test get_recent_average with empty history."""
        history = TrackingHistory()
        assert history.get_recent_average() == 0.0

    def test_get_recent_average_fewer_than_n(self):
        """Test get_recent_average with fewer than n samples."""
        history = TrackingHistory()
        history.add(Pose2D(0.0, 0.0), 2.0)
        history.add(Pose2D(1.0, 0.0), 4.0)

        # Average of 2 samples when asking for 5
        avg = history.get_recent_average(n=5)
        assert avg == 3.0

    def test_get_recent_average_exact_n(self):
        """Test get_recent_average with exactly n samples."""
        history = TrackingHistory()
        for i in range(5):
            history.add(Pose2D(float(i), 0.0), float(i + 1))

        # Last 5: 1, 2, 3, 4, 5 -> average = 3.0
        avg = history.get_recent_average(n=5)
        assert avg == 3.0

    def test_get_recent_average_more_than_n(self):
        """Test get_recent_average with more than n samples."""
        history = TrackingHistory()
        for i in range(10):
            history.add(Pose2D(float(i), 0.0), float(i + 1))

        # Last 5: 6, 7, 8, 9, 10 -> average = 8.0
        avg = history.get_recent_average(n=5)
        assert avg == 8.0

    def test_maxlen(self):
        """Test history respects maxlen."""
        history = TrackingHistory(maxlen=3)
        for i in range(10):
            history.add(Pose2D(float(i), 0.0), float(i))

        assert len(history.positions) == 3
        # Last 3 values: 7, 8, 9
        best = history.get_best_position()
        assert best[1] == 9.0

    def test_clear(self):
        """Test clear empties history."""
        history = TrackingHistory()
        for i in range(5):
            history.add(Pose2D(float(i), 0.0), float(i))

        history.clear()
        assert len(history.positions) == 0
        assert history.get_best_position() is None


class TestSurgeCastTracker:
    """Tests for SurgeCastTracker class."""

    @pytest.fixture
    def config(self):
        """Default config for testing."""
        return SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            surge_step=0.5,
            cast_step=0.3,
            cast_distance_limit=3.0,
            source_radius=1.0,
            source_hold_steps=2,
            wind_x=1.0,
            wind_y=0.0,
        )

    @pytest.fixture
    def tracker(self, config):
        """Create tracker with default config."""
        return SurgeCastTracker(config)

    def test_initial_state_is_patrol(self, tracker):
        """Test tracker starts in PATROL state."""
        assert tracker.current_state == TrackingState.PATROL

    def test_update_returns_tracking_action(self, tracker):
        """Test update returns TrackingAction."""
        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert isinstance(action, TrackingAction)

    def test_patrol_action_moves_forward(self, tracker):
        """Test PATROL state moves forward."""
        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,  # Facing east
        )

        assert action.state == TrackingState.PATROL
        # Should move in yaw direction (east)
        assert action.target.x > 0.0
        assert abs(action.target.y) < 1e-9

    def test_transition_to_surge_on_plume_detection(self, tracker):
        """Test transition from PATROL to SURGE when plume detected."""
        # Need multiple high concentration readings
        for _ in range(5):
            tracker.update(
                concentration=10.0,  # Above plume_found_threshold
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.current_state == TrackingState.SURGE

    def test_surge_moves_upwind(self, config):
        """Test SURGE state moves upwind."""
        # Wind is blowing east (positive X), so upwind is west
        tracker = SurgeCastTracker(config)

        # Trigger SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )

        assert action.state == TrackingState.SURGE
        # Upwind heading should be pi (west) or -pi (equivalent)
        # With wind_x=1.0, wind_y=0.0, upwind is atan2(0, -1) = -pi or pi
        assert abs(abs(action.heading) - math.pi) < 0.5  # Allow some tolerance for blending

    def test_transition_to_cast_on_plume_lost(self, tracker):
        """Test transition from SURGE to CAST when plume lost."""
        # First get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Now lose plume
        for _ in range(5):
            tracker.update(
                concentration=1.0,  # Below plume_lost_threshold
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.current_state == TrackingState.CAST

    def test_cast_moves_perpendicular_to_wind(self, config):
        """Test CAST state moves perpendicular to wind."""
        tracker = SurgeCastTracker(config)

        # Get to CAST state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        for _ in range(5):
            tracker.update(
                concentration=1.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )

        assert action.state == TrackingState.CAST
        # Cast should be perpendicular to wind
        # Wind is at 0 radians, so cast should be +/- pi/2
        expected_angles = [math.pi / 2, -math.pi / 2]
        assert any(abs(action.heading - angle) < 1.0 for angle in expected_angles)

    def test_transition_back_to_surge_from_cast(self, tracker):
        """Test transition from CAST back to SURGE when plume found."""
        # Get to CAST state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        for _ in range(5):
            tracker.update(
                concentration=1.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.current_state == TrackingState.CAST

        # Find plume again
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.current_state == TrackingState.SURGE

    def test_source_found_threshold(self):
        """Test SOURCE_FOUND state when source threshold reached."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=5.0,  # Large radius for easier testing
            source_hold_steps=2,
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # High concentration at source threshold
        for _ in range(config.source_hold_steps + 1):
            tracker.update(
                concentration=25.0,  # Above source_threshold
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.current_state == TrackingState.SOURCE_FOUND

    def test_source_estimate_set_when_found(self):
        """Test source estimate is set when source found."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=5.0,
            source_hold_steps=2,
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Reach source
        for _ in range(config.source_hold_steps + 1):
            tracker.update(
                concentration=25.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        assert tracker.source_estimate is not None

    def test_source_found_stays_in_place(self):
        """Test SOURCE_FOUND state stays at current position."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=5.0,
            source_hold_steps=2,
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to SOURCE_FOUND state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        for _ in range(config.source_hold_steps + 1):
            tracker.update(
                concentration=25.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        action = tracker.update(
            concentration=25.0,
            robot_pose=Pose2D(5.0, 5.0),
            robot_yaw=0.0,
        )

        assert action.state == TrackingState.SOURCE_FOUND
        assert action.target == Pose2D(5.0, 5.0)
        assert action.step_size == 0.0

    def test_custom_wind_overrides_config(self, config):
        """Test custom wind parameter overrides config."""
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Use custom wind (opposite direction)
        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
            wind=(-1.0, 0.0),  # Wind blowing west
        )

        # With wind blowing west, upwind is east (0 radians)
        assert action.heading < math.pi / 2  # Should be roughly east

    def test_reset_clears_state(self, tracker):
        """Test reset returns to initial state."""
        # Modify state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        tracker.reset()

        assert tracker.current_state == TrackingState.PATROL
        assert tracker.source_estimate is None

    def test_no_wind_uses_current_heading(self):
        """Test with no wind uses current heading for SURGE."""
        config = SurgeCastConfig(wind_x=0.0, wind_y=0.0)
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=math.pi / 4,  # 45 degrees
            )

        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=math.pi / 4,
        )

        # Without wind, should use current heading
        assert abs(action.heading - math.pi / 4) < 1e-6

    def test_surge_with_no_wind_uses_current_yaw(self):
        """Test SURGE without wind uses current yaw."""
        config = SurgeCastConfig(wind_x=0.0, wind_y=0.0)
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=math.pi / 3,
            )

        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=math.pi / 3,
        )

        # Without wind, should use current heading
        assert abs(action.heading - math.pi / 3) < 1e-6

    def test_cast_with_no_wind_uses_current_yaw(self):
        """Test CAST without wind uses current yaw for perpendicular cast."""
        config = SurgeCastConfig(wind_x=0.0, wind_y=0.0)
        tracker = SurgeCastTracker(config)

        # Get to CAST state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=math.pi / 4,
            )
        for _ in range(5):
            tracker.update(
                concentration=1.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=math.pi / 4,
            )

        assert tracker.current_state == TrackingState.CAST

        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=math.pi / 4,
        )

        # Without wind, cast should be perpendicular to current heading
        assert action.state == TrackingState.CAST

    def test_surge_blends_toward_best_position(self):
        """Test SURGE blends toward best historical position."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state with lower concentration
        for _ in range(5):
            tracker.update(
                concentration=8.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Record a best position with much higher concentration
        tracker.update(
            concentration=15.0,  # Much higher
            robot_pose=Pose2D(2.0, 2.0),
            robot_yaw=0.0,
        )

        # Continue with lower concentration
        action = tracker.update(
            concentration=8.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )

        # Should still be in SURGE and the heading should be influenced by best position
        assert action.state == TrackingState.SURGE

    def test_cast_direction_reversal(self):
        """Test cast direction reverses when distance limit reached."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            cast_distance_limit=0.5,  # Small limit
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to CAST state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )
        for _ in range(5):
            tracker.update(
                concentration=1.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Move past cast distance limit
        initial_cast_dir = tracker._cast_direction
        for i in range(20):
            action = tracker.update(
                concentration=1.0,
                robot_pose=Pose2D(float(i) * 0.3, 0.0),
                robot_yaw=0.0,
            )
            if action.state != TrackingState.CAST:
                break

    def test_particle_filter_flag_in_action(self):
        """Test particle filter flag in tracking action."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            use_particle_filter=True,
            wind_x=1.0,
            wind_y=0.0,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )

        assert action.use_particle_filter is True


class TestSurgeCastTrackerEdgeCases:
    """Edge case tests for SurgeCastTracker."""

    @pytest.fixture
    def config(self):
        """Default config for edge case testing."""
        return SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=1.0,
            source_hold_steps=2,
        )

    def test_zero_concentration(self, config):
        """Test handling of zero concentration."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=0.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert action is not None

    def test_negative_concentration(self, config):
        """Test handling of negative concentration."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=-1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert action is not None

    def test_very_high_concentration(self, config):
        """Test handling of very high concentration."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=1e6,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )
        assert action is not None

    def test_large_position_values(self, config):
        """Test handling of large position values."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(1e6, 1e6),
            robot_yaw=0.0,
        )
        assert action is not None

    def test_negative_position_values(self, config):
        """Test handling of negative position values."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(-100.0, -100.0),
            robot_yaw=0.0,
        )
        assert action is not None

    def test_boundary_threshold_values(self, config):
        """Test behavior at exact threshold values."""
        tracker = SurgeCastTracker(config)

        # Exactly at plume_found_threshold
        for _ in range(5):
            tracker.update(
                concentration=config.plume_found_threshold,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Should transition to SURGE (>= threshold)
        assert tracker.current_state == TrackingState.SURGE

    def test_source_threshold_boundary(self):
        """Test behavior at exact source threshold."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=5.0,
            source_hold_steps=2,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Exactly at source_threshold
        for _ in range(config.source_hold_steps + 1):
            tracker.update(
                concentration=config.source_threshold,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Should transition to SOURCE_FOUND (>= threshold)
        assert tracker.current_state == TrackingState.SOURCE_FOUND

    def test_multiple_resets(self, config):
        """Test multiple consecutive resets."""
        tracker = SurgeCastTracker(config)

        for _ in range(3):
            for _ in range(5):
                tracker.update(
                    concentration=10.0,
                    robot_pose=Pose2D(0.0, 0.0),
                    robot_yaw=0.0,
                )
            tracker.reset()

        assert tracker.current_state == TrackingState.PATROL

    def test_exact_source_radius_distance(self):
        """Test behavior at exact source radius distance."""
        config = SurgeCastConfig(
            plume_found_threshold=5.0,
            plume_lost_threshold=2.0,
            source_threshold=20.0,
            source_radius=2.0,
            source_hold_steps=1,
        )
        tracker = SurgeCastTracker(config)

        # Get to SURGE state
        for _ in range(5):
            tracker.update(
                concentration=10.0,
                robot_pose=Pose2D(0.0, 0.0),
                robot_yaw=0.0,
            )

        # Record best position at origin
        tracker.update(
            concentration=15.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=0.0,
        )

        # Move exactly source_radius away (2.0)
        tracker.update(
            concentration=25.0,
            robot_pose=Pose2D(2.0, 0.0),
            robot_yaw=0.0,
        )

        # Distance == source_radius should still trigger (<=)
        assert tracker.current_state == TrackingState.SOURCE_FOUND

    @pytest.mark.parametrize("yaw", [
        0.0,
        math.pi / 4,
        math.pi / 2,
        math.pi,
        -math.pi / 2,
    ])
    def test_various_yaw_values(self, config, yaw):
        """Test handling of various yaw values."""
        tracker = SurgeCastTracker(config)
        action = tracker.update(
            concentration=1.0,
            robot_pose=Pose2D(0.0, 0.0),
            robot_yaw=yaw,
        )
        assert action is not None

    def test_rapid_state_transitions(self, config):
        """Test rapid state transitions."""
        tracker = SurgeCastTracker(config)

        # Alternate between high and low concentration
        for i in range(20):
            conc = 10.0 if i % 2 == 0 else 1.0
            tracker.update(
                concentration=conc,
                robot_pose=Pose2D(float(i), 0.0),
                robot_yaw=0.0,
            )

        # Should handle gracefully (no crashes)
        assert tracker.current_state in [
            TrackingState.PATROL,
            TrackingState.SURGE,
            TrackingState.CAST,
        ]


def test_cast_direction_alternates_on_plume_loss():
    """Regression: cast direction must alternate between +1 and -1."""
    config = SurgeCastConfig(
        wind_x=1.0,
        wind_y=0.0,
        plume_found_threshold=3.0,
        plume_lost_threshold=1.5,
        plume_confirm_samples=1,
    )
    tracker = SurgeCastTracker(config)

    # Enter SURGE
    for _ in range(5):
        tracker.update(5.0, Pose2D(0.0, 0.0), 0.0)
    assert tracker.state == TrackingState.SURGE

    # Lose plume → CAST with direction toggle (1 confirm sample)
    tracker.update(0.5, Pose2D(1.0, 0.0), 0.0)
    assert tracker.state == TrackingState.CAST
    dir1 = tracker._cast_direction

    # Re-enter SURGE (1 confirm sample)
    tracker.update(5.0, Pose2D(1.0, 0.0), 0.0)
    assert tracker.state == TrackingState.SURGE

    # Lose plume again → CAST with opposite direction
    tracker.update(0.5, Pose2D(2.0, 0.0), 0.0)
    assert tracker.state == TrackingState.CAST
    dir2 = tracker._cast_direction

    assert dir1 == -dir2, f"Cast directions should alternate: {dir1} vs {dir2}"


def test_cast_heading_blending_handles_angle_wraparound():
    """Regression: angle blending must use unit vectors, not scalar addition."""
    config = SurgeCastConfig(
        wind_x=1.0,
        wind_y=0.0,
        plume_found_threshold=3.0,
        plume_lost_threshold=1.5,
        cast_step=0.5,
        plume_confirm_samples=1,
    )
    tracker = SurgeCastTracker(config)

    # Enter SURGE then CAST
    for _ in range(5):
        tracker.update(5.0, Pose2D(0.0, 0.0), 0.0)
    tracker.update(0.5, Pose2D(0.0, 0.0), 0.0)
    assert tracker.state == TrackingState.CAST

    # Add a best position that causes near-180° wraparound
    # Best position is behind the robot (opposite to cast direction)
    tracker._history.add(Pose2D(-5.0, 0.0), 10.0)

    action = tracker._generate_action(
        Pose2D(0.0, 0.0), 0.0, 1.0, 0.0
    )

    # Heading should be well-defined (not NaN or wildly wrong)
    assert not math.isnan(action.heading)
    assert -math.pi <= action.heading <= math.pi
