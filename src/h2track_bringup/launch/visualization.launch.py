#!/usr/bin/env python3
"""Visualization subsystem launch.

Layer 2 launch file for the visualization subsystem.
Starts RViz2 with the h2track configuration.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_bringup")

    use_sim_time = LaunchConfiguration("use_sim_time")
    use_rviz = LaunchConfiguration("use_rviz")

    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_use_rviz = DeclareLaunchArgument("use_rviz", default_value="true")

    rviz = Node(
        condition=IfCondition(use_rviz),
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", os.path.join(pkg_share, "rviz", "h2track_nav2.rviz")],
        parameters=[{"use_sim_time": use_sim_time}],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_use_rviz,
        rviz,
    ])
