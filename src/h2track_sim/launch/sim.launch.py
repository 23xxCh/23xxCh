#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, RegisterEventHandler, SetEnvironmentVariable, Shutdown, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, EnvironmentVariable, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_world = PathJoinSubstitution([FindPackageShare("h2track_sim"), "scenes", "baseline", "h2track_lab.world"])
    robot_xacro = PathJoinSubstitution([FindPackageShare("h2track_sim"), "urdf", "h2track_bot.urdf.xacro"])

    use_sim_time = LaunchConfiguration("use_sim_time")
    world = LaunchConfiguration("world")
    gazebo_model_path = LaunchConfiguration("gazebo_model_path")
    headless = LaunchConfiguration("headless")
    spawn_x = LaunchConfiguration("spawn_x")
    spawn_y = LaunchConfiguration("spawn_y")
    spawn_z = LaunchConfiguration("spawn_z")
    spawn_yaw = LaunchConfiguration("spawn_yaw")

    declare_scene = DeclareLaunchArgument("scene", default_value="baseline")
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
    declare_world = DeclareLaunchArgument("world", default_value=default_world)
    declare_gazebo_model_path = DeclareLaunchArgument("gazebo_model_path", default_value="")
    declare_spawn_x = DeclareLaunchArgument("spawn_x", default_value="0.0")
    declare_spawn_y = DeclareLaunchArgument("spawn_y", default_value="0.0")
    declare_spawn_z = DeclareLaunchArgument("spawn_z", default_value="0.05")
    declare_spawn_yaw = DeclareLaunchArgument("spawn_yaw", default_value="0.0")

    robot_description = {"robot_description": Command([FindExecutable(name="xacro"), " ", robot_xacro])}

    gazebo_model_path_env = SetEnvironmentVariable(
        name="GAZEBO_MODEL_PATH",
        value=[gazebo_model_path, ":", EnvironmentVariable("GAZEBO_MODEL_PATH", default_value="")],
    )

    gazebo_gui = ExecuteProcess(
        cmd=["gazebo", "--verbose", "-s", "libgazebo_ros_init.so", "-s", "libgazebo_ros_factory.so", world],
        condition=UnlessCondition(headless),
        output="screen",
    )

    gazebo_headless = ExecuteProcess(
        cmd=["gzserver", "--verbose", "-s", "libgazebo_ros_init.so", "-s", "libgazebo_ros_factory.so", world],
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
            declare_scene,
            declare_use_sim_time,
            declare_headless,
            declare_world,
            declare_gazebo_model_path,
            declare_spawn_x,
            declare_spawn_y,
            declare_spawn_z,
            declare_spawn_yaw,
            gazebo_model_path_env,
            gazebo_gui,
            gazebo_headless,
            gazebo_gui_exit_handler,
            gazebo_headless_exit_handler,
            robot_state_publisher,
            robot_spawner,
        ]
    )
