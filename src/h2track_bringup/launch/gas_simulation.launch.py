#!/usr/bin/env python3
"""Gas simulation subsystem launch.

Layer 2 launch file for the gas simulation subsystem.
Starts either the simplified gas_field_node or the full GADEN pipeline
depending on the use_gaden parameter.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    lc = {name: LaunchConfiguration(name) for name in [
        "use_sim_time", "use_gaden",
        "source_x", "source_y",
        "gas_source_strength", "gas_decay_rate", "gas_plume_stddev",
        "gas_wind_x", "gas_wind_y", "gas_noise_stddev",
        "gas_type", "gas_publish_rate_hz",
        "gaden_project_path", "gaden_playback_id", "gaden_player_freq",
        "gaden_sensor_topic", "gaden_sensor_frame", "gaden_fixed_frame",
        "gaden_map_offset_x", "gaden_map_offset_y", "gaden_map_offset_z",
        "gaden_map_roll", "gaden_map_pitch", "gaden_map_yaw",
        "gaden_sensor_gate_timeout", "gaden_sensor_gate_poll_period",
        "gaden_sensor_gate_stable_ready_count",
        "use_slam",
    ]}

    declares = [
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("use_gaden", default_value="false"),
        DeclareLaunchArgument("source_x", default_value="-3.5"),
        DeclareLaunchArgument("source_y", default_value="-3.5"),
        DeclareLaunchArgument("gas_source_strength", default_value="120.0"),
        DeclareLaunchArgument("gas_decay_rate", default_value="0.55"),
        DeclareLaunchArgument("gas_plume_stddev", default_value="1.2"),
        DeclareLaunchArgument("gas_wind_x", default_value="0.4"),
        DeclareLaunchArgument("gas_wind_y", default_value="0.0"),
        DeclareLaunchArgument("gas_noise_stddev", default_value="0.05"),
        DeclareLaunchArgument("gas_type", default_value="H2"),
        DeclareLaunchArgument("gas_publish_rate_hz", default_value="5.0"),
        DeclareLaunchArgument("gaden_project_path", default_value=""),
        DeclareLaunchArgument("gaden_playback_id", default_value="scene1"),
        DeclareLaunchArgument("gaden_player_freq", default_value="1.0"),
        DeclareLaunchArgument("gaden_sensor_topic", default_value="/gaden/sensor_reading"),
        DeclareLaunchArgument("gaden_sensor_frame", default_value="base_link"),
        DeclareLaunchArgument("gaden_fixed_frame", default_value="gaden_map"),
        DeclareLaunchArgument("gaden_map_offset_x", default_value="0.0"),
        DeclareLaunchArgument("gaden_map_offset_y", default_value="0.0"),
        DeclareLaunchArgument("gaden_map_offset_z", default_value="0.0"),
        DeclareLaunchArgument("gaden_map_roll", default_value="0.0"),
        DeclareLaunchArgument("gaden_map_pitch", default_value="0.0"),
        DeclareLaunchArgument("gaden_map_yaw", default_value="0.0"),
        DeclareLaunchArgument("gaden_sensor_gate_timeout", default_value="60.0"),
        DeclareLaunchArgument("gaden_sensor_gate_poll_period", default_value="0.5"),
        DeclareLaunchArgument("gaden_sensor_gate_stable_ready_count", default_value="3"),
        DeclareLaunchArgument("use_slam", default_value="false"),
    ]

    # -- Simplified gas field (use_gaden:=false) ----------------------------
    gas_field_node = Node(
        condition=UnlessCondition(lc["use_gaden"]),
        package="h2track_gas_sim",
        executable="gas_field_node",
        name="gas_field_node",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "source_x": lc["source_x"],
                "source_y": lc["source_y"],
                "source_strength": lc["gas_source_strength"],
                "decay_rate": lc["gas_decay_rate"],
                "plume_stddev": lc["gas_plume_stddev"],
                "wind_x": lc["gas_wind_x"],
                "wind_y": lc["gas_wind_y"],
                "noise_stddev": lc["gas_noise_stddev"],
                "gas_type": lc["gas_type"],
                "publish_rate_hz": lc["gas_publish_rate_hz"],
            },
        ],
    )

    # -- GADEN pipeline (use_gaden:=true) -----------------------------------
    gaden_environment = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="gaden_environment",
        executable="environment",
        name="gaden_environment",
        output="screen",
        parameters=[{"use_sim_time": lc["use_sim_time"]}, {"projectPath": lc["gaden_project_path"]}],
    )

    gaden_player = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="gaden_player",
        executable="player",
        name="gaden_player",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {"projectPath": lc["gaden_project_path"]},
            {"playbackID": lc["gaden_playback_id"]},
            {"player_freq": lc["gaden_player_freq"]},
        ],
    )

    gaden_map_tf = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="tf2_ros",
        executable="static_transform_publisher",
        name="gaden_map_tf",
        output="screen",
        parameters=[{"use_sim_time": lc["use_sim_time"]}],
        arguments=[
            "--x", lc["gaden_map_offset_x"],
            "--y", lc["gaden_map_offset_y"],
            "--z", lc["gaden_map_offset_z"],
            "--roll", lc["gaden_map_roll"],
            "--pitch", lc["gaden_map_pitch"],
            "--yaw", lc["gaden_map_yaw"],
            "--frame-id", lc["gaden_fixed_frame"],
            "--child-frame-id", "map",
        ],
    )

    map_to_odom_tf = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="tf2_ros",
        executable="static_transform_publisher",
        name="map_to_odom_tf",
        output="screen",
        parameters=[{"use_sim_time": lc["use_sim_time"]}],
        arguments=[
            "--x", "0.0", "--y", "0.0", "--z", "0.0",
            "--roll", "0.0", "--pitch", "0.0", "--yaw", "0.0",
            "--frame-id", "map", "--child-frame-id", "odom",
        ],
    )

    gaden_sensor_gate = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="h2track_gas_sim",
        executable="gaden_sensor_gate_node",
        name="gaden_sensor_gate_node",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "fixed_frame": lc["gaden_fixed_frame"],
                "sensor_frame": lc["gaden_sensor_frame"],
                "timeout_sec": lc["gaden_sensor_gate_timeout"],
                "poll_period_sec": lc["gaden_sensor_gate_poll_period"],
                "stable_ready_count": lc["gaden_sensor_gate_stable_ready_count"],
                "sensor_node_name": "gaden_pid_sensor",
                "topic": lc["gaden_sensor_topic"],
                "sensor_model": 30,
                "rate": 5.0,
                "use_pid_correction_factors": False,
            },
        ],
    )

    gaden_adapter = Node(
        condition=IfCondition(lc["use_gaden"]),
        package="h2track_gas_sim",
        executable="gaden_adapter_node",
        name="gaden_adapter_node",
        output="screen",
        parameters=[
            {"use_sim_time": lc["use_sim_time"]},
            {
                "gas_sensor_topic": lc["gaden_sensor_topic"],
                "gas_concentration_topic": "/gas_concentration",
                "sensor_model": -1,
                "fallback_ohm_scale": 0.001,
                "voltage_scale": 1.0,
                "minimum_concentration_ppm": 0.0,
                "maximum_concentration_ppm": 0.0,
            },
        ],
    )

    return LaunchDescription(declares + [
        gas_field_node,
        gaden_environment,
        gaden_player,
        gaden_map_tf,
        map_to_odom_tf,
        gaden_sensor_gate,
        gaden_adapter,
    ])
