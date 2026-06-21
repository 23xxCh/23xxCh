#!/usr/bin/env python3
"""Backward-compatible bringup entry point.

Delegates to robot.launch.py (Layer 1) which includes all subsystems.
All parameters are forwarded transparently.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


# Same parameter schema as robot.launch.py — forwarded transparently
_PARAMS = [
    ("scene", "baseline"),
    ("use_sim_time", "true"),
    ("use_rviz", "true"),
    ("headless", "false"),
    ("world", ""),
    ("gazebo_model_path", ""),
    ("use_gaden", ""),
    ("use_slam", ""),
    ("nav2_map_file", ""),
    ("nav2_params_file", ""),
    ("nav2_autostart", ""),
    ("nav2_launch_delay", "12.0"),
    ("mission_manager_delay", "10.0"),
    ("nav2_startup_gate_timeout", "30.0"),
    ("nav2_startup_gate_poll_period", "0.5"),
    ("nav2_startup_gate_stable_ready_count", "2"),
    ("gaden_sensor_gate_timeout", "60.0"),
    ("gaden_sensor_gate_poll_period", "0.5"),
    ("gaden_sensor_gate_stable_ready_count", "3"),
    ("initial_pose_x", ""),
    ("initial_pose_y", ""),
    ("initial_pose_yaw", ""),
    ("patrol_goal_timeout_sec", ""),
    ("patrol_points", ""),
    ("enter_threshold", ""),
    ("exit_threshold", ""),
    ("source_threshold", ""),
    ("confirm_samples", ""),
    ("track_exit_samples", ""),
    ("source_radius", ""),
    ("source_hold_steps", ""),
    ("track_timeout_sec", "60.0"),
    ("adaptive_source_ratio", "0.0"),
    ("track_step", ""),
    ("surge_step", ""),
    ("cast_step", ""),
    ("sweep_angle_deg", ""),
    ("source_x", ""),
    ("source_y", ""),
    ("localizer_node", ""),
    ("publish_initial_pose", ""),
    ("gas_source_strength", ""),
    ("gas_decay_rate", ""),
    ("gas_plume_stddev", ""),
    ("gas_wind_x", ""),
    ("gas_wind_y", ""),
    ("gas_noise_stddev", ""),
    ("gas_type", "H2"),
    ("gas_publish_rate_hz", ""),
    ("gaden_project_path", ""),
    ("gaden_playback_id", ""),
    ("gaden_player_freq", ""),
    ("gaden_sensor_topic", ""),
    ("gaden_sensor_frame", ""),
    ("gaden_fixed_frame", ""),
    ("gaden_map_offset_x", ""),
    ("gaden_map_offset_y", ""),
    ("gaden_map_offset_z", ""),
    ("gaden_map_roll", ""),
    ("gaden_map_pitch", ""),
    ("gaden_map_yaw", ""),
    ("use_particle_filter", "true"),
    ("particle_filter_num_particles", "500"),
    ("particle_filter_motion_sigma", "0.3"),
    ("particle_filter_observation_sigma", "0.5"),
    ("particle_filter_plume_sigma", "2.0"),
    ("particle_filter_source_strength", ""),
    ("particle_filter_bounds", ""),
    ("particle_filter_publish_rate", "2.0"),
    ("particle_filter_resample_threshold", "0.5"),
]


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_bringup")

    declares = [DeclareLaunchArgument(name, default_value=dflt) for name, dflt in _PARAMS]
    lc = {name: LaunchConfiguration(name) for name, _ in _PARAMS}

    # Forward all parameters to robot.launch.py
    launch_args = {name: lc[name] for name, _ in _PARAMS}

    robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "robot.launch.py")),
        launch_arguments=launch_args.items(),
    )

    return LaunchDescription(declares + [robot])
