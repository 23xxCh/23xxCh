"""Tests for navigation_executor pure functions."""

import math

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D
from h2track_tracking.navigation_executor import (
    coerce_patrol_points,
    determine_nav_action_on_result,
    map_pose_from_amcl,
    select_tracking_target,
    should_skip_patrol_goal,
)


def _make_tracking_model() -> GasFieldModel:
    return GasFieldModel(
        GasFieldParams(
            source_x=-4.0,
            source_y=1.95,
            source_strength=120.0,
            decay_rate=0.55,
            plume_stddev=1.2,
            wind_x=0.4,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
    )


class TestMapPoseFromAmcl:
    def test_extracts_position_and_yaw_from_message(self):
        from geometry_msgs.msg import PoseWithCovarianceStamped

        yaw = math.pi / 3.0
        msg = PoseWithCovarianceStamped()
        msg.pose.pose.position.x = 3.12
        msg.pose.pose.position.y = -2.38
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        pose, parsed_yaw = map_pose_from_amcl(msg)

        assert pose == Pose2D(3.12, -2.38)
        assert parsed_yaw == yaw

    def test_handles_zero_yaw(self):
        from geometry_msgs.msg import PoseWithCovarianceStamped

        msg = PoseWithCovarianceStamped()
        msg.pose.pose.position.x = 1.0
        msg.pose.pose.position.y = 2.0
        msg.pose.pose.orientation.z = 0.0
        msg.pose.pose.orientation.w = 1.0

        pose, yaw = map_pose_from_amcl(msg)

        assert pose == Pose2D(1.0, 2.0)
        assert abs(yaw) < 1e-6


class TestSelectTrackingTarget:
    def test_continues_search_when_current_pose_is_already_the_strongest_peak(self):
        current_pose = Pose2D(3.13, -2.08)
        target = select_tracking_target(
            gas_model=_make_tracking_model(),
            current_pose=current_pose,
            current_yaw=-math.pi / 2.0,
            history=[
                (Pose2D(3.00, -1.80), 2.3),
                (Pose2D(3.12, -2.02), 4.8),
                (current_pose, 5.4),
            ],
            step_size=0.4,
            sweep_angle=math.pi / 6.0,
            source_threshold=4.5,
        )

        assert target != current_pose
        assert target.y < current_pose.y - 0.2

    def test_continues_search_below_source_threshold(self):
        current_pose = Pose2D(-2.4, 1.4)
        target = select_tracking_target(
            gas_model=_make_tracking_model(),
            current_pose=current_pose,
            current_yaw=math.pi,
            history=[(Pose2D(-2.0, 1.5), 1.7), (current_pose, 2.2)],
            step_size=0.4,
            sweep_angle=math.pi / 6.0,
            source_threshold=2.5,
        )

        assert target != current_pose

    def test_holds_highest_recent_pose_after_a_source_spike(self):
        source_pose = Pose2D(-1.44, 3.098)
        current_pose = Pose2D(-1.40, 3.10)
        target = select_tracking_target(
            gas_model=_make_tracking_model(),
            current_pose=current_pose,
            current_yaw=math.pi,
            history=[
                (Pose2D(-1.32, 3.285), 2.468),
                (source_pose, 5.42),
                (current_pose, 1.765),
            ],
            step_size=0.4,
            sweep_angle=math.pi / 6.0,
            source_threshold=4.5,
        )

        assert target == source_pose

    def test_returns_gas_model_target_when_history_empty(self):
        current_pose = Pose2D(0.0, 0.0)
        target = select_tracking_target(
            gas_model=_make_tracking_model(),
            current_pose=current_pose,
            current_yaw=0.0,
            history=[],
            step_size=0.5,
            sweep_angle=math.pi / 6.0,
            source_threshold=4.0,
        )

        # Should return a pose that's step_size away in the heading direction
        assert abs(target.x - current_pose.x - 0.5) < 1e-6
        assert abs(target.y - current_pose.y) < 1e-6


class TestCoercePatrolPoints:
    def test_handles_flat_list(self):
        result = coerce_patrol_points([1.0, 2.0, 3.0, 4.0])
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_handles_string_representation(self):
        result = coerce_patrol_points("[1.0, 2.0, 3.0, 4.0]")
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_handles_nested_pairs(self):
        result = coerce_patrol_points([[1.0, 2.0], [3.0, 4.0]])
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_handles_tuple_pairs(self):
        result = coerce_patrol_points([(1.0, 2.0), (3.0, 4.0)])
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_handles_empty_list(self):
        result = coerce_patrol_points([])
        assert result == []

    def test_raises_on_invalid_string(self):
        import pytest

        with pytest.raises(SyntaxError):
            coerce_patrol_points("not a list")

    def test_raises_on_dict_value(self):
        import pytest

        with pytest.raises(ValueError, match="Unsupported patrol_points"):
            coerce_patrol_points({"x": 1, "y": 2})


class TestShouldSkipPatrolGoal:
    def test_returns_true_when_timeout_exceeded(self):
        assert should_skip_patrol_goal(
            current_goal_kind="patrol",
            goal_started_at_sec=10.0,
            current_time_sec=60.0,
            timeout_sec=45.0,
            task_complete=False,
        )

    def test_returns_false_when_not_patrol_goal(self):
        assert not should_skip_patrol_goal(
            current_goal_kind="track",
            goal_started_at_sec=10.0,
            current_time_sec=60.0,
            timeout_sec=45.0,
            task_complete=False,
        )

    def test_returns_false_when_task_complete(self):
        assert not should_skip_patrol_goal(
            current_goal_kind="patrol",
            goal_started_at_sec=10.0,
            current_time_sec=60.0,
            timeout_sec=45.0,
            task_complete=True,
        )

    def test_returns_false_when_no_goal_started(self):
        assert not should_skip_patrol_goal(
            current_goal_kind="patrol",
            goal_started_at_sec=None,
            current_time_sec=60.0,
            timeout_sec=45.0,
            task_complete=False,
        )

    def test_returns_false_when_within_timeout(self):
        assert not should_skip_patrol_goal(
            current_goal_kind="patrol",
            goal_started_at_sec=50.0,
            current_time_sec=60.0,
            timeout_sec=45.0,
            task_complete=False,
        )


class TestDetermineNavActionOnResult:
    def test_returns_none_when_task_not_complete(self):
        assert determine_nav_action_on_result(
            mode_name="PATROL",
            nav_result=None,
            task_complete=False,
        ) is None

    def test_patrol_succeeded_sends_patrol(self):
        assert determine_nav_action_on_result(
            mode_name="PATROL",
            nav_result="SUCCEEDED",
            task_complete=True,
        ) == "send_patrol"

    def test_patrol_failed_skips_patrol(self):
        assert determine_nav_action_on_result(
            mode_name="PATROL",
            nav_result="FAILED",
            task_complete=True,
        ) == "skip_patrol"

    def test_patrol_canceled_skips_patrol(self):
        assert determine_nav_action_on_result(
            mode_name="PATROL",
            nav_result="CANCELED",
            task_complete=True,
        ) == "skip_patrol"

    def test_track_succeeded_sends_track(self):
        assert determine_nav_action_on_result(
            mode_name="SEEK_TRACK",
            nav_result="SUCCEEDED",
            task_complete=True,
        ) == "send_track"

    def test_track_failed_retries_track(self):
        assert determine_nav_action_on_result(
            mode_name="SEEK_TRACK",
            nav_result="FAILED",
            task_complete=True,
        ) == "retry_track"

    def test_track_canceled_retries_track(self):
        assert determine_nav_action_on_result(
            mode_name="SEEK_TRACK",
            nav_result="CANCELED",
            task_complete=True,
        ) == "retry_track"

    def test_seek_confirm_returns_none(self):
        assert determine_nav_action_on_result(
            mode_name="SEEK_CONFIRM",
            nav_result="SUCCEEDED",
            task_complete=True,
        ) is None

    def test_source_found_returns_none(self):
        assert determine_nav_action_on_result(
            mode_name="SOURCE_FOUND",
            nav_result="SUCCEEDED",
            task_complete=True,
        ) is None
