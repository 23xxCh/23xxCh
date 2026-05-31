"""Tests for navigation_executor pure functions."""

import math

from h2track_tracking.gas_model import Pose2D
from h2track_tracking.navigation_executor import (
    coerce_patrol_points,
    map_pose_from_amcl,
    should_skip_patrol_goal,
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
