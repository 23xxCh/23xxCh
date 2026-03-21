import math

import rclpy

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D
from h2track_tracking.mission_manager_node import MissionManagerNode, select_tracking_target


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


def test_select_tracking_target_holds_position_once_source_threshold_is_reached():
    current_pose = Pose2D(-2.4, 1.4)
    target = select_tracking_target(
        gas_model=_make_tracking_model(),
        current_pose=current_pose,
        current_yaw=math.pi,
        history=[(Pose2D(-2.0, 1.5), 2.1), (current_pose, 2.7)],
        step_size=0.4,
        sweep_angle=math.pi / 6.0,
        source_threshold=2.5,
    )

    assert target == current_pose


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
