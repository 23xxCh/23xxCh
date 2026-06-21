"""Parameter declaration and config construction for BTNodeRunner.

Extracted from BTNodeRunner.__init__ to separate concerns:
- Parameter declaration (ROS param↔dataclass bridge)
- Config construction (MissionConfig, SurgeCastConfig, FusionConfig)
"""

from __future__ import annotations

from rclpy.node import Node

from h2track_tracking.mission_logic import MissionConfig
from h2track_tracking.tracking.types import SurgeCastConfig
from h2track_tracking.tracking.fusion import FusionConfig
from h2track_utils.navigation_executor import coerce_patrol_points


_DEFAULT_PATROL = "[3.0, 3.0, -3.0, 3.0, -3.0, -3.0, 3.0, -3.0]"


def declare_parameters(node: Node) -> None:
    """Declare all ROS parameters for the BT node runner."""
    _mc = MissionConfig(patrol_points=[])
    _sc = SurgeCastConfig()

    node.declare_parameter("initial_pose_x", 0.0)
    node.declare_parameter("initial_pose_y", 0.0)
    node.declare_parameter("initial_pose_yaw", 0.0)
    node.declare_parameter("patrol_points", _DEFAULT_PATROL)
    node.declare_parameter("enter_threshold", _mc.enter_threshold)
    node.declare_parameter("exit_threshold", _mc.exit_threshold)
    node.declare_parameter("source_threshold", _mc.source_threshold)
    node.declare_parameter("confirm_samples", _mc.confirm_samples)
    node.declare_parameter("track_exit_samples", _mc.track_exit_samples or _mc.confirm_samples)
    node.declare_parameter("source_radius", _mc.source_radius)
    node.declare_parameter("source_hold_steps", _mc.source_hold_steps)
    node.declare_parameter("track_timeout_sec", _mc.track_timeout_sec)
    node.declare_parameter("adaptive_source_ratio", _mc.adaptive_source_ratio)
    node.declare_parameter("source_x", -3.5)
    node.declare_parameter("source_y", -3.5)
    node.declare_parameter("patrol_goal_timeout_sec", 45.0)
    node.declare_parameter("goal_reject_retry_sec", 2.0)
    node.declare_parameter("localizer_node", "amcl")
    node.declare_parameter("use_slam", False)
    node.declare_parameter("publish_initial_pose", True)
    node.declare_parameter("use_particle_filter_estimate", True)
    node.declare_parameter("particle_filter_min_confidence", _sc.min_pf_confidence)
    node.declare_parameter("use_surge_cast", True)
    node.declare_parameter("surge_step", _sc.surge_step)
    node.declare_parameter("cast_step", _sc.cast_step)
    node.declare_parameter("cast_distance_limit", _sc.cast_distance_limit)
    node.declare_parameter("wind_x", _sc.wind_x)
    node.declare_parameter("wind_y", _sc.wind_y)
    node.declare_parameter("estimate_wind", True)
    node.declare_parameter("wind_estimation_min_samples", 10)
    node.declare_parameter("use_fusion", True)
    node.declare_parameter("fusion_mode", "weighted")
    node.declare_parameter("fusion_pf_weight", 0.3)
    node.declare_parameter("fusion_surge_weight", 0.7)


def _pf(node: Node, name: str) -> float:
    return float(node.get_parameter(name).value)


def _pi(node: Node, name: str) -> int:
    return int(node.get_parameter(name).value)


def build_mission_config(node: Node) -> MissionConfig:
    """Build MissionConfig from declared ROS parameters."""
    patrol_points = coerce_patrol_points(node.get_parameter("patrol_points").value)
    return MissionConfig(
        patrol_points=patrol_points,
        enter_threshold=_pf(node, "enter_threshold"),
        exit_threshold=_pf(node, "exit_threshold"),
        source_threshold=_pf(node, "source_threshold"),
        confirm_samples=_pi(node, "confirm_samples"),
        track_exit_samples=_pi(node, "track_exit_samples"),
        source_radius=_pf(node, "source_radius"),
        source_hold_steps=_pi(node, "source_hold_steps"),
        track_timeout_sec=_pf(node, "track_timeout_sec"),
        adaptive_source_ratio=_pf(node, "adaptive_source_ratio"),
        actual_source=(_pf(node, "source_x"), _pf(node, "source_y")),
    )


def build_surge_config(node: Node) -> SurgeCastConfig:
    """Build SurgeCastConfig from declared ROS parameters."""
    return SurgeCastConfig(
        plume_found_threshold=_pf(node, "enter_threshold"),
        plume_lost_threshold=_pf(node, "exit_threshold"),
        source_threshold=_pf(node, "source_threshold"),
        surge_step=_pf(node, "surge_step"),
        cast_step=_pf(node, "cast_step"),
        cast_distance_limit=_pf(node, "cast_distance_limit"),
        wind_x=_pf(node, "wind_x"),
        wind_y=_pf(node, "wind_y"),
        source_radius=_pf(node, "source_radius"),
        source_hold_steps=_pi(node, "source_hold_steps"),
    )


def build_fusion_config(node: Node) -> FusionConfig:
    """Build FusionConfig from declared ROS parameters."""
    return FusionConfig(
        blending_mode=str(node.get_parameter("fusion_mode").value),
        pf_weight_base=_pf(node, "fusion_pf_weight"),
        surge_weight=_pf(node, "fusion_surge_weight"),
        pf_confidence_threshold=_pf(node, "particle_filter_min_confidence"),
    )
