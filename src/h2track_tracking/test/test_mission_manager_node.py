import math
from pathlib import Path

from geometry_msgs.msg import PoseWithCovarianceStamped
import rclpy

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D
from h2track_tracking.mission_manager_node import (
    MissionManagerNode,
    map_pose_from_amcl,
    select_tracking_target,
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


def test_mission_manager_supports_tracking_mode_startup():
    text = (
        Path(__file__).resolve().parents[1]
        / 'h2track_tracking'
        / 'mission_manager_node.py'
    ).read_text(encoding='utf-8')

    assert 'declare_parameter("start_in_tracking_mode"' in text or "declare_parameter('start_in_tracking_mode'" in text
    assert 'MissionMode.SEEK_TRACK' in text


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
