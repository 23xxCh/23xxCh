#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")
    demo_path = os.path.join(pkg_share, "launch", "demo.launch.py")

    scene = LaunchConfiguration("scene")
    use_rviz = LaunchConfiguration("use_rviz")
    headless = LaunchConfiguration("headless")
    use_gaden = LaunchConfiguration("use_gaden")
    nav2_map_file = LaunchConfiguration("nav2_map_file")
    nav2_params_file = LaunchConfiguration("nav2_params_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument("scene", default_value="warehouse"),
            DeclareLaunchArgument("use_rviz", default_value="true"),
            DeclareLaunchArgument("headless", default_value="false"),
            DeclareLaunchArgument("use_gaden", default_value=""),
            DeclareLaunchArgument("nav2_map_file", default_value=""),
            DeclareLaunchArgument("nav2_params_file", default_value=""),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(demo_path),
                launch_arguments={
                    "scene": scene,
                    "use_rviz": use_rviz,
                    "headless": headless,
                    "use_gaden": use_gaden,
                    "use_slam": "true",
                    "nav2_map_file": nav2_map_file,
                    "nav2_params_file": nav2_params_file,
                }.items(),
            ),
        ]
    )
