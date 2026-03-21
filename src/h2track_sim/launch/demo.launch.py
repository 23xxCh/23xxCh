#!/usr/bin/env python3

import json
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
import yaml


def _load_demo_profile(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _flatten_patrol_points(points: list[list[float]]) -> list[float]:
    flattened: list[float] = []
    for x, y in points:
        flattened.extend([float(x), float(y)])
    return flattened


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")
    bringup_path = os.path.join(pkg_share, "launch", "bringup.launch.py")
    demo_config_path = os.path.join(pkg_share, "config", "demo.yaml")
    demo_nav2_params_path = os.path.join(pkg_share, "config", "nav2_demo_params.yaml")
    demo = _load_demo_profile(demo_config_path)
    mission = demo["mission_manager"]
    source = demo["gas_source"]
    initial_pose = mission["initial_pose"]

    use_rviz = LaunchConfiguration("use_rviz")
    headless = LaunchConfiguration("headless")
    use_gaden = LaunchConfiguration("use_gaden")
    nav2_params_file = LaunchConfiguration("nav2_params_file")

    declare_use_rviz = DeclareLaunchArgument("use_rviz", default_value=str(demo.get("use_rviz", True)).lower())
    declare_headless = DeclareLaunchArgument("headless", default_value=str(demo.get("headless", False)).lower())
    declare_use_gaden = DeclareLaunchArgument("use_gaden", default_value=str(demo.get("use_gaden", True)).lower())
    declare_nav2_params_file = DeclareLaunchArgument("nav2_params_file", default_value=demo_nav2_params_path)

    set_demo_values = [
        SetLaunchConfiguration("mission_manager_delay", str(demo.get("mission_manager_delay", 10.0))),
        SetLaunchConfiguration("gaden_sensor_gate_timeout", str(demo.get("gaden_sensor_gate_timeout", 30.0))),
        SetLaunchConfiguration("gaden_sensor_gate_poll_period", str(demo.get("gaden_sensor_gate_poll_period", 0.5))),
        SetLaunchConfiguration("initial_pose_x", str(initial_pose["x"])),
        SetLaunchConfiguration("initial_pose_y", str(initial_pose["y"])),
        SetLaunchConfiguration("initial_pose_yaw", str(initial_pose["yaw"])),
        SetLaunchConfiguration("patrol_points", json.dumps(_flatten_patrol_points(mission["patrol_points"]))),
        SetLaunchConfiguration("enter_threshold", str(mission["enter_threshold"])),
        SetLaunchConfiguration("exit_threshold", str(mission["exit_threshold"])),
        SetLaunchConfiguration("source_threshold", str(mission["source_threshold"])),
        SetLaunchConfiguration("confirm_samples", str(mission["confirm_samples"])),
        SetLaunchConfiguration("source_radius", str(mission["source_radius"])),
        SetLaunchConfiguration("source_hold_steps", str(mission["source_hold_steps"])),
        SetLaunchConfiguration("track_step", str(mission["track_step"])),
        SetLaunchConfiguration("sweep_angle_deg", str(mission["sweep_angle_deg"])),
        SetLaunchConfiguration("source_x", str(source["x"])),
        SetLaunchConfiguration("source_y", str(source["y"])),
    ]

    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(bringup_path),
        launch_arguments={
            "use_rviz": use_rviz,
            "headless": headless,
            "use_gaden": use_gaden,
            "nav2_params_file": nav2_params_file,
        }.items(),
    )

    return LaunchDescription([
        declare_use_rviz,
        declare_headless,
        declare_use_gaden,
        declare_nav2_params_file,
        *set_demo_values,
        bringup,
    ])
