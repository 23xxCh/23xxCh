#!/usr/bin/env python3
"""Tracking subsystem launch.

Layer 2 launch file for the tracking subsystem.
Starts bt_node_runner, particle_filter_node, nav2_startup_gate,
and activate_localization.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    lc = {name: LaunchConfiguration(name) for name in [
        "use_sim_time",
        "initial_pose_x", "initial_pose_y", "initial_pose_yaw",
        "patrol_goal_timeout_sec", "patrol_points",
        "enter_threshold", "exit_threshold", "source_threshold",
        "confirm_samples", "track_exit_samples",
        "source_radius", "source_hold_steps",
        "track_timeout_sec", "adaptive_source_ratio",
        "track_step", "surge_step", "cast_step", "sweep_angle_deg",
        "source_x", "source_y",
        "gas_wind_x", "gas_wind_y",
        "localizer_node", "use_slam", "publish_initial_pose",
        "nav2_launch_delay", "mission_manager_delay",
        "nav2_autostart",
        "nav2_startup_gate_timeout", "nav2_startup_gate_poll_period",
        "nav2_startup_gate_stable_ready_count",
        "use_particle_filter",
        "particle_filter_num_particles", "particle_filter_motion_sigma",
        "particle_filter_observation_sigma", "particle_filter_plume_sigma",
        "particle_filter_source_strength", "particle_filter_bounds",
        "particle_filter_publish_rate", "particle_filter_resample_threshold",
        "gas_source_strength",
    ]}

    declares = [
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("initial_pose_x", default_value="0.0"),
        DeclareLaunchArgument("initial_pose_y", default_value="0.0"),
        DeclareLaunchArgument("initial_pose_yaw", default_value="0.0"),
        DeclareLaunchArgument("patrol_goal_timeout_sec", default_value="45.0"),
        DeclareLaunchArgument("patrol_points", default_value=""),
        DeclareLaunchArgument("enter_threshold", default_value="2.0"),
        DeclareLaunchArgument("exit_threshold", default_value="1.0"),
        DeclareLaunchArgument("source_threshold", default_value="10.0"),
        DeclareLaunchArgument("confirm_samples", default_value="3"),
        DeclareLaunchArgument("track_exit_samples", default_value="3"),
        DeclareLaunchArgument("source_radius", default_value="1.0"),
        DeclareLaunchArgument("source_hold_steps", default_value="5"),
        DeclareLaunchArgument("track_timeout_sec", default_value="60.0"),
        DeclareLaunchArgument("adaptive_source_ratio", default_value="0.0"),
        DeclareLaunchArgument("track_step", default_value="0.7"),
        DeclareLaunchArgument("surge_step", default_value="0.5"),
        DeclareLaunchArgument("cast_step", default_value="0.3"),
        DeclareLaunchArgument("sweep_angle_deg", default_value="30.0"),
        DeclareLaunchArgument("source_x", default_value="-3.5"),
        DeclareLaunchArgument("source_y", default_value="-3.5"),
        DeclareLaunchArgument("gas_wind_x", default_value="0.4"),
        DeclareLaunchArgument("gas_wind_y", default_value="0.0"),
        DeclareLaunchArgument("gas_source_strength", default_value="120.0"),
        DeclareLaunchArgument("localizer_node", default_value="amcl"),
        DeclareLaunchArgument("use_slam", default_value="false"),
        DeclareLaunchArgument("publish_initial_pose", default_value="true"),
        DeclareLaunchArgument("nav2_launch_delay", default_value="12.0"),
        DeclareLaunchArgument("mission_manager_delay", default_value="10.0"),
        DeclareLaunchArgument("nav2_autostart", default_value="true"),
        DeclareLaunchArgument("nav2_startup_gate_timeout", default_value="30.0"),
        DeclareLaunchArgument("nav2_startup_gate_poll_period", default_value="0.5"),
        DeclareLaunchArgument("nav2_startup_gate_stable_ready_count", default_value="2"),
        DeclareLaunchArgument("use_particle_filter", default_value="true"),
        DeclareLaunchArgument("particle_filter_num_particles", default_value="500"),
        DeclareLaunchArgument("particle_filter_motion_sigma", default_value="0.3"),
        DeclareLaunchArgument("particle_filter_observation_sigma", default_value="0.5"),
        DeclareLaunchArgument("particle_filter_plume_sigma", default_value="2.0"),
        DeclareLaunchArgument("particle_filter_source_strength", default_value="120.0"),
        DeclareLaunchArgument("particle_filter_bounds", default_value="[-6.0, -6.0, 6.0, 6.0]"),
        DeclareLaunchArgument("particle_filter_publish_rate", default_value="2.0"),
        DeclareLaunchArgument("particle_filter_resample_threshold", default_value="0.5"),
    ]

    # -- Nav2 startup gate --------------------------------------------------
    nav2_startup_gate = Node(
        condition=UnlessCondition(lc["nav2_autostart"]),
        package="h2track_utils",
        executable="nav2_startup_gate_node",
        name="nav2_startup_gate_node",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "target_frame": "odom",
                "source_frame": "base_link",
                "lifecycle_manager_service": "/lifecycle_manager_navigation/manage_nodes",
                "timeout_sec": lc["nav2_startup_gate_timeout"],
                "poll_period_sec": lc["nav2_startup_gate_poll_period"],
                "stable_ready_count": lc["nav2_startup_gate_stable_ready_count"],
            },
        ],
    )

    # -- BT Node Runner (delayed) -------------------------------------------
    bt_mission_node = Node(
        package="h2track_tracking",
        executable="bt_node_runner",
        name="bt_node_runner",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "initial_pose_x": lc["initial_pose_x"],
                "initial_pose_y": lc["initial_pose_y"],
                "initial_pose_yaw": lc["initial_pose_yaw"],
                "patrol_goal_timeout_sec": lc["patrol_goal_timeout_sec"],
                "patrol_points": ParameterValue(lc["patrol_points"], value_type=str),
                "enter_threshold": lc["enter_threshold"],
                "exit_threshold": lc["exit_threshold"],
                "source_threshold": lc["source_threshold"],
                "confirm_samples": lc["confirm_samples"],
                "track_exit_samples": lc["track_exit_samples"],
                "source_radius": lc["source_radius"],
                "source_hold_steps": lc["source_hold_steps"],
                "track_timeout_sec": lc["track_timeout_sec"],
                "adaptive_source_ratio": lc["adaptive_source_ratio"],
                "track_step": lc["track_step"],
                "surge_step": lc["surge_step"],
                "cast_step": lc["cast_step"],
                "sweep_angle_deg": lc["sweep_angle_deg"],
                "source_x": lc["source_x"],
                "source_y": lc["source_y"],
                "wind_x": lc["gas_wind_x"],
                "wind_y": lc["gas_wind_y"],
                "localizer_node": lc["localizer_node"],
                "use_slam": ParameterValue(lc["use_slam"], value_type=bool),
                "publish_initial_pose": ParameterValue(lc["publish_initial_pose"], value_type=bool),
                "estimate_wind": True,
                "use_fusion": True,
                "use_particle_filter_estimate": True,
            },
        ],
    )

    mission_manager = TimerAction(
        period=PythonExpression([lc["nav2_launch_delay"], " + ", lc["mission_manager_delay"]]),
        actions=[bt_mission_node],
    )

    # -- Activate localization (delayed) ------------------------------------
    activate_localization = TimerAction(
        period=PythonExpression([lc["nav2_launch_delay"], " + 5.0"]),
        condition=UnlessCondition(lc["use_slam"]),
        actions=[
            ExecuteProcess(
                cmd=["ros2", "run", "h2track_utils", "activate_localization"],
                output="screen",
            )
        ],
    )

    # -- Particle filter ----------------------------------------------------
    particle_filter = Node(
        condition=IfCondition(lc["use_particle_filter"]),
        package="h2track_tracking",
        executable="particle_filter_node",
        name="particle_filter_node",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "num_particles": lc["particle_filter_num_particles"],
                "motion_sigma": lc["particle_filter_motion_sigma"],
                "observation_sigma": lc["particle_filter_observation_sigma"],
                "plume_sigma": lc["particle_filter_plume_sigma"],
                "source_strength": lc["particle_filter_source_strength"],
                "bounds": lc["particle_filter_bounds"],
                "publish_rate": lc["particle_filter_publish_rate"],
                "resample_threshold": lc["particle_filter_resample_threshold"],
            },
        ],
    )

    return LaunchDescription(declares + [
        nav2_startup_gate,
        mission_manager,
        activate_localization,
        particle_filter,
    ])
