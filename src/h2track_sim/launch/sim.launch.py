#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, RegisterEventHandler, Shutdown, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")
    default_world = os.path.join(pkg_share, "worlds", "h2track_lab.world")
    robot_xacro = PathJoinSubstitution([FindPackageShare("h2track_sim"), "urdf", "h2track_bot.urdf.xacro"])

    use_sim_time = LaunchConfiguration("use_sim_time")
    headless = LaunchConfiguration("headless")
    spawn_x = LaunchConfiguration("spawn_x")
    spawn_y = LaunchConfiguration("spawn_y")
    spawn_z = LaunchConfiguration("spawn_z")
    spawn_yaw = LaunchConfiguration("spawn_yaw")

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation clock if true",
    )
    declare_headless = DeclareLaunchArgument(
        "headless",
        default_value="false",
        description="Launch Gazebo without a GUI",
    )
    declare_spawn_x = DeclareLaunchArgument("spawn_x", default_value="0.0")
    declare_spawn_y = DeclareLaunchArgument("spawn_y", default_value="0.0")
    declare_spawn_z = DeclareLaunchArgument("spawn_z", default_value="0.05")
    declare_spawn_yaw = DeclareLaunchArgument("spawn_yaw", default_value="0.0")

    robot_description = {"robot_description": Command([FindExecutable(name="xacro"), " ", robot_xacro])}

    gazebo_gui = ExecuteProcess(
        cmd=["gazebo", "--verbose", "-s", "libgazebo_ros_init.so", "-s", "libgazebo_ros_factory.so", default_world],
        condition=UnlessCondition(headless),
        output="screen",
    )

    gazebo_headless = ExecuteProcess(
        cmd=["gzserver", "--verbose", "-s", "libgazebo_ros_init.so", "-s", "libgazebo_ros_factory.so", default_world],
        condition=IfCondition(headless),
        output="screen",
    )

    gazebo_gui_exit_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=gazebo_gui,
            on_exit=[Shutdown(reason="Gazebo process exited")],
        )
    )
    gazebo_headless_exit_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=gazebo_headless,
            on_exit=[Shutdown(reason="Gazebo process exited")],
        )
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[robot_description, {"use_sim_time": use_sim_time}],
    )

    robot_spawner = TimerAction(
        period=4.0,
        actions=[
            Node(
                package="gazebo_ros",
                executable="spawn_entity.py",
                arguments=[
                    "-entity",
                    "h2track_bot",
                    "-topic",
                    "robot_description",
                    "-x",
                    spawn_x,
                    "-y",
                    spawn_y,
                    "-z",
                    spawn_z,
                    "-Y",
                    spawn_yaw,
                ],
                output="screen",
            )
        ],
    )

    return LaunchDescription(
        [
            declare_use_sim_time,
            declare_headless,
            declare_spawn_x,
            declare_spawn_y,
            declare_spawn_z,
            declare_spawn_yaw,
            gazebo_gui,
            gazebo_headless,
            gazebo_gui_exit_handler,
            gazebo_headless_exit_handler,
            robot_state_publisher,
            robot_spawner,
        ]
    )
