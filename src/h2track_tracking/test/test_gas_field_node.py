from h2track_tracking.gas_field_node import select_pose_for_gas_field
from h2track_tracking.gas_model import Pose2D


def test_select_pose_for_gas_field_prefers_amcl_pose_in_auto_mode():
    pose = select_pose_for_gas_field(
        pose_source="auto",
        odom_pose=Pose2D(3.2, 2.6),
        amcl_pose=Pose2D(-4.0, 1.95),
    )

    assert pose == Pose2D(-4.0, 1.95)


def test_select_pose_for_gas_field_falls_back_to_odom_when_amcl_missing():
    pose = select_pose_for_gas_field(
        pose_source="auto",
        odom_pose=Pose2D(3.2, 2.6),
        amcl_pose=None,
    )

    assert pose == Pose2D(3.2, 2.6)


def test_select_pose_for_gas_field_honors_explicit_odom_mode():
    pose = select_pose_for_gas_field(
        pose_source="odom",
        odom_pose=Pose2D(3.2, 2.6),
        amcl_pose=Pose2D(-4.0, 1.95),
    )

    assert pose == Pose2D(3.2, 2.6)


def test_select_pose_for_gas_field_honors_explicit_amcl_mode():
    pose = select_pose_for_gas_field(
        pose_source="amcl",
        odom_pose=Pose2D(3.2, 2.6),
        amcl_pose=Pose2D(-4.0, 1.95),
    )

    assert pose == Pose2D(-4.0, 1.95)
