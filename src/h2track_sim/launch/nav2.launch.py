#!/usr/bin/env python3

import os
import shutil

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def prepare_runtime_map(context, *args, **kwargs):
    pkg_share = get_package_share_directory("h2track_sim")
    source_dir = os.path.join(pkg_share, "maps")
    runtime_dir = "/tmp/h2track_xian_runtime_map"
    os.makedirs(runtime_dir, exist_ok=True)
    shutil.copy2(os.path.join(source_dir, "h2track_map.yaml"), os.path.join(runtime_dir, "h2track_map.yaml"))
    shutil.copy2(os.path.join(source_dir, "h2track_map.pgm"), os.path.join(runtime_dir, "h2track_map.pgm"))
    return []


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")
    nav2_share = get_package_share_directory("nav2_bringup")
    default_map = os.path.join("/tmp", "h2track_xian_runtime_map", "h2track_map.yaml")
    default_params = os.path.join(pkg_share, "config", "nav2_params.yaml")

    use_sim_time = LaunchConfiguration("use_sim_time")
    map_yaml = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
    autostart = LaunchConfiguration("autostart")

    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_map = DeclareLaunchArgument("map", default_value=default_map)
    declare_params = DeclareLaunchArgument("params_file", default_value=default_params)
    declare_autostart = DeclareLaunchArgument("autostart", default_value="true")

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, "launch", "bringup_launch.py")),
        launch_arguments={
            "slam": "False",
            "map": map_yaml,
            "use_sim_time": use_sim_time,
            "params_file": params_file,
            "autostart": autostart,
            "use_composition": "False",
            "use_respawn": "False",
        }.items(),
    )

    return LaunchDescription(
        [
            declare_use_sim_time,
            declare_map,
            declare_params,
            declare_autostart,
            OpaqueFunction(function=prepare_runtime_map),
            nav2_bringup,
        ]
    )
