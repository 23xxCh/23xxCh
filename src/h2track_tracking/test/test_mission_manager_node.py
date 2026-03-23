import math
from pathlib import Path

from geometry_msgs.msg import PoseWithCovarianceStamped
import rclpy

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D
from h2track_tracking.mission_manager_node import (
    MissionManagerNode,
    map_pose_from_amcl,
    select_tracking_target,
    should_force_exploration_target,
    step_toward_pose,
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


def test_mission_manager_accepts_string_patrol_points_override():
    node = None
    rclpy.init(args=["--ros-args", "-p", 'patrol_points:="[3.0, 3.0, -3.0, 3.0]"'])
    try:
        node = MissionManagerNode()
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_mission_manager_tracking_mode_primes_current_pose_from_initial_pose():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'self._current_pose = self._initial_pose' in text
    assert 'self._current_yaw = self._initial_yaw' in text


def test_map_pose_from_amcl_reads_map_frame_pose_and_yaw():
    yaw = math.pi / 3.0
    msg = PoseWithCovarianceStamped()
    msg.pose.pose.position.x = 3.12
    msg.pose.pose.position.y = -2.38
    msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
    msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

    pose, parsed_yaw = map_pose_from_amcl(msg)

    assert pose == Pose2D(3.12, -2.38)
    assert parsed_yaw == yaw


def test_mission_manager_uses_amcl_pose_subscription_for_tracking_reference():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'PoseWithCovarianceStamped' in text
    assert '"/amcl_pose"' in text


def test_mission_manager_waits_for_odom_before_initial_pose_publication():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'Odometry' in text
    assert '"/odom"' in text
    assert 'self._have_odom' in text
    assert 'if not self._have_odom:' in text
    assert 'self._odom_tf_ready()' in text
    assert 'can_transform(' in text


def test_should_force_exploration_target_when_goal_repeats_near_robot():
    current_pose = Pose2D(2.24, -0.19)
    target_pose = Pose2D(2.26, -0.20)
    assert should_force_exploration_target(
        current_pose=current_pose,
        proposed_target=target_pose,
        previous_target=target_pose,
        repeat_goal_radius=0.08,
        repeat_pose_radius=0.25,
        repeated_streak=1,
        streak_threshold=3,
    )


def test_should_not_force_exploration_when_target_changed():
    current_pose = Pose2D(2.24, -0.19)
    previous_target = Pose2D(2.26, -0.20)
    proposed_target = Pose2D(1.98, -0.41)
    assert not should_force_exploration_target(
        current_pose=current_pose,
        proposed_target=proposed_target,
        previous_target=previous_target,
        repeat_goal_radius=0.08,
        repeat_pose_radius=0.25,
        repeated_streak=1,
        streak_threshold=3,
    )


def test_should_force_exploration_when_repeat_streak_exceeds_threshold():
    current_pose = Pose2D(0.7, -1.4)
    repeated_target = Pose2D(1.32, -0.57)
    assert should_force_exploration_target(
        current_pose=current_pose,
        proposed_target=repeated_target,
        previous_target=repeated_target,
        repeat_goal_radius=0.08,
        repeat_pose_radius=0.25,
        repeated_streak=3,
        streak_threshold=3,
    )


def test_step_toward_pose_clamps_step_without_overshoot():
    current = Pose2D(0.0, 0.0)
    target = Pose2D(0.3, 0.4)
    stepped = step_toward_pose(current, target, max_step=1.0)
    assert stepped == target


def test_step_toward_pose_moves_by_max_step_for_far_targets():
    current = Pose2D(0.0, 0.0)
    target = Pose2D(3.0, 4.0)
    stepped = step_toward_pose(current, target, max_step=1.0)
    assert math.isclose(math.hypot(stepped.x, stepped.y), 1.0, abs_tol=1e-9)


def test_mission_manager_supports_tracking_mode_startup():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'declare_parameter("start_in_tracking_mode"' in text or "declare_parameter('start_in_tracking_mode'" in text
    assert 'MissionMode.SEEK_TRACK' in text


def test_mission_manager_supports_tracking_only_mode_to_prevent_patrol_fallback():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'declare_parameter("tracking_only_mode"' in text or "declare_parameter('tracking_only_mode'" in text
    assert 'self._tracking_only_mode' in text
    assert 'if self._tracking_only_mode and mode is MissionMode.PATROL' in text


def test_mission_manager_supports_duplicate_tracking_goal_escape():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'tracking_repeat_goal_radius' in text
    assert 'tracking_repeat_pose_radius' in text
    assert 'tracking_repeat_streak_threshold' in text
    assert 'should_force_exploration_target' in text
    assert 'Tracking target repeated near robot pose; forcing exploratory offset goal' in text


def test_mission_manager_supports_non_improving_tracking_source_pull():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'tracking_source_pull_after_streak' in text
    assert 'tracking_source_pull_step_scale' in text
    assert 'Tracking source pull engaged after non-improving streak' in text


def test_mission_manager_publishes_robot_mode_with_transient_local_qos():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'QoSProfile' in text
    assert 'DurabilityPolicy.TRANSIENT_LOCAL' in text
    assert 'self.create_publisher(String, "/robot_mode", mode_qos)' in text


def test_mission_manager_logs_patrol_and_tracking_goal_dispatches():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'Navigating to patrol goal' in text
    assert 'Navigating to tracking goal' in text


def test_mission_manager_publishes_initial_mode_after_nav_startup():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'self._mode_pub.publish(String(data=self._machine.mode.name))' in text
    assert 'self._active_mode = self._machine.mode' in text


def test_mission_manager_counts_goal_reached_only_on_success():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'goal_succeeded = task_result is TaskResult.SUCCEEDED' in text
    assert 'goal_reached=goal_succeeded' in text


def test_mission_manager_has_recovery_branch_for_failed_tracking_goals():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'def _send_tracking_recovery_goal' in text
    assert 'Tracking goal failed; issuing recovery sweep goal' in text
    assert 'Patrol goal did not succeed; advancing to next waypoint' in text


def test_mission_manager_separates_actual_source_and_tracking_model_source():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'declare_parameter("model_source_x"' in text
    assert 'declare_parameter("model_source_y"' in text
    assert 'actual_source=(' in text
    assert 'self.get_parameter("model_source_x").value' in text
    assert 'self.get_parameter("model_source_y").value' in text


def test_mission_manager_consumes_tracking_mode_start_flag_after_initial_entry():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert '_tracking_mode_start_consumed' in text
    assert 'self._start_in_tracking_mode and not self._tracking_mode_start_consumed' in text


def test_select_tracking_target_continues_search_when_current_pose_is_already_the_strongest_peak():
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


def test_select_tracking_target_continues_search_below_source_threshold():
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


def test_select_tracking_target_holds_highest_recent_pose_after_a_source_spike():
    source_pose = Pose2D(-1.72, 2.84)
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


def test_select_tracking_target_avoids_reissuing_tiny_goals_when_peak_pose_is_almost_current():
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

    assert target != source_pose
    assert target != current_pose
    displacement = math.hypot(target.x - current_pose.x, target.y - current_pose.y)
    assert displacement > 0.3
    assert target.y < current_pose.y


def test_select_tracking_target_steps_toward_source_when_recent_peak_matches_current_pose():
    gas_model = GasFieldModel(
        GasFieldParams(
            source_x=3.0,
            source_y=2.0,
            source_strength=260.0,
            decay_rate=0.55,
            plume_stddev=1.2,
            wind_x=0.4,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
    )
    current_pose = Pose2D(2.87, 4.16)

    target = select_tracking_target(
        gas_model=gas_model,
        current_pose=current_pose,
        current_yaw=0.0,
        history=[
            (Pose2D(2.87, 4.16), 162.0),
            (Pose2D(2.87, 4.16), 159.0),
        ],
        step_size=0.4,
        sweep_angle=math.pi / 6.0,
        source_threshold=4.5,
    )

    assert target != current_pose
    assert target.y < current_pose.y - 0.2


def test_select_tracking_target_uses_plume_search_when_history_is_empty():
    current_pose = Pose2D(1.0, 1.0)
    target = select_tracking_target(
        gas_model=_make_tracking_model(),
        current_pose=current_pose,
        current_yaw=0.0,
        history=[],
        step_size=0.4,
        sweep_angle=math.pi / 6.0,
        source_threshold=4.5,
    )

    displacement = math.hypot(target.x - current_pose.x, target.y - current_pose.y)
    assert displacement > 0.3
    assert target.x > current_pose.x


def test_select_tracking_target_does_not_overshoot_when_source_is_within_step_size():
    gas_model = GasFieldModel(
        GasFieldParams(
            source_x=1.18,
            source_y=1.12,
            source_strength=120.0,
            decay_rate=0.55,
            plume_stddev=1.2,
            wind_x=0.4,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
    )
    current_pose = Pose2D(1.0, 1.0)
    target = select_tracking_target(
        gas_model=gas_model,
        current_pose=current_pose,
        current_yaw=0.0,
        history=[
            (current_pose, 6.2),
            (Pose2D(1.05, 1.02), 1.1),
        ],
        step_size=0.4,
        sweep_angle=math.pi / 6.0,
        source_threshold=4.5,
    )

    assert target == Pose2D(1.18, 1.12)
