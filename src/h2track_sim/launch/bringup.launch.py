#!/usr/bin/env python3

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, SetLaunchConfiguration, Shutdown, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

def _load_scene_loader():
    loader_path = Path(__file__).with_name('scene_loader.py')
    spec = spec_from_file_location('h2track_scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCENE_LOADER = _load_scene_loader()
resolve_scene_model_path = SCENE_LOADER.resolve_scene_model_path
resolve_scene_world = SCENE_LOADER.resolve_scene_world


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")
    default_nav2_params = os.path.join(pkg_share, "config", "nav2_params.yaml")

    scene = LaunchConfiguration("scene")
    use_rviz = LaunchConfiguration("use_rviz")
    use_sim_time = LaunchConfiguration("use_sim_time")
    headless = LaunchConfiguration("headless")
    world = LaunchConfiguration("world")
    gazebo_model_path = LaunchConfiguration("gazebo_model_path")
    use_gaden = LaunchConfiguration("use_gaden")
    nav2_params_file = LaunchConfiguration("nav2_params_file")
    nav2_autostart = LaunchConfiguration("nav2_autostart")
    mission_manager_delay = LaunchConfiguration("mission_manager_delay")
    nav2_startup_gate_timeout = LaunchConfiguration("nav2_startup_gate_timeout")
    nav2_startup_gate_poll_period = LaunchConfiguration("nav2_startup_gate_poll_period")
    nav2_startup_gate_stable_ready_count = LaunchConfiguration("nav2_startup_gate_stable_ready_count")
    gaden_sensor_gate_timeout = LaunchConfiguration("gaden_sensor_gate_timeout")
    gaden_sensor_gate_poll_period = LaunchConfiguration("gaden_sensor_gate_poll_period")
    gaden_sensor_gate_stable_ready_count = LaunchConfiguration("gaden_sensor_gate_stable_ready_count")
    initial_pose_x = LaunchConfiguration("initial_pose_x")
    initial_pose_y = LaunchConfiguration("initial_pose_y")
    initial_pose_yaw = LaunchConfiguration("initial_pose_yaw")
    patrol_points = LaunchConfiguration("patrol_points")
    enter_threshold = LaunchConfiguration("enter_threshold")
    exit_threshold = LaunchConfiguration("exit_threshold")
    source_threshold = LaunchConfiguration("source_threshold")
    confirm_samples = LaunchConfiguration("confirm_samples")
    source_radius = LaunchConfiguration("source_radius")
    source_hold_steps = LaunchConfiguration("source_hold_steps")
    track_step = LaunchConfiguration("track_step")
    sweep_angle_deg = LaunchConfiguration("sweep_angle_deg")
    source_x = LaunchConfiguration("source_x")
    source_y = LaunchConfiguration("source_y")
    gaden_project_path = LaunchConfiguration("gaden_project_path")
    gaden_playback_id = LaunchConfiguration("gaden_playback_id")
    gaden_sensor_topic = LaunchConfiguration("gaden_sensor_topic")
    gaden_sensor_frame = LaunchConfiguration("gaden_sensor_frame")
    gaden_fixed_frame = LaunchConfiguration("gaden_fixed_frame")
    gaden_map_offset_x = LaunchConfiguration("gaden_map_offset_x")
    gaden_map_offset_y = LaunchConfiguration("gaden_map_offset_y")
    gaden_map_offset_z = LaunchConfiguration("gaden_map_offset_z")
    gaden_map_roll = LaunchConfiguration("gaden_map_roll")
    gaden_map_pitch = LaunchConfiguration("gaden_map_pitch")
    gaden_map_yaw = LaunchConfiguration("gaden_map_yaw")

    declare_scene = DeclareLaunchArgument("scene", default_value="baseline")
    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_use_rviz = DeclareLaunchArgument("use_rviz", default_value="true")
    declare_headless = DeclareLaunchArgument("headless", default_value="false")
    declare_world = DeclareLaunchArgument("world", default_value="")
    declare_gazebo_model_path = DeclareLaunchArgument("gazebo_model_path", default_value="")
    declare_use_gaden = DeclareLaunchArgument("use_gaden", default_value="false")
    declare_nav2_params_file = DeclareLaunchArgument("nav2_params_file", default_value=default_nav2_params)
    declare_nav2_autostart = DeclareLaunchArgument("nav2_autostart", default_value="true")
    declare_mission_manager_delay = DeclareLaunchArgument("mission_manager_delay", default_value="10.0")
    declare_nav2_startup_gate_timeout = DeclareLaunchArgument("nav2_startup_gate_timeout", default_value="30.0")
    declare_nav2_startup_gate_poll_period = DeclareLaunchArgument("nav2_startup_gate_poll_period", default_value="0.5")
    declare_nav2_startup_gate_stable_ready_count = DeclareLaunchArgument("nav2_startup_gate_stable_ready_count", default_value="2")
    declare_gaden_sensor_gate_timeout = DeclareLaunchArgument("gaden_sensor_gate_timeout", default_value="30.0")
    declare_gaden_sensor_gate_poll_period = DeclareLaunchArgument("gaden_sensor_gate_poll_period", default_value="0.5")
    declare_gaden_sensor_gate_stable_ready_count = DeclareLaunchArgument("gaden_sensor_gate_stable_ready_count", default_value="3")
    declare_initial_pose_x = DeclareLaunchArgument("initial_pose_x", default_value="0.0")
    declare_initial_pose_y = DeclareLaunchArgument("initial_pose_y", default_value="0.0")
    declare_initial_pose_yaw = DeclareLaunchArgument("initial_pose_yaw", default_value="0.0")
    declare_patrol_points = DeclareLaunchArgument("patrol_points", default_value="[3.0, 3.0, -3.0, 3.0, -3.0, -3.0, 3.0, -3.0]")
    declare_enter_threshold = DeclareLaunchArgument("enter_threshold", default_value="4.0")
    declare_exit_threshold = DeclareLaunchArgument("exit_threshold", default_value="1.5")
    declare_source_threshold = DeclareLaunchArgument("source_threshold", default_value="8.0")
    declare_confirm_samples = DeclareLaunchArgument("confirm_samples", default_value="3")
    declare_source_radius = DeclareLaunchArgument("source_radius", default_value="0.6")
    declare_source_hold_steps = DeclareLaunchArgument("source_hold_steps", default_value="3")
    declare_track_step = DeclareLaunchArgument("track_step", default_value="0.7")
    declare_sweep_angle_deg = DeclareLaunchArgument("sweep_angle_deg", default_value="30.0")
    declare_source_x = DeclareLaunchArgument("source_x", default_value="-3.2")
    declare_source_y = DeclareLaunchArgument("source_y", default_value="-3.0")
    declare_gaden_project_path = DeclareLaunchArgument(
        "gaden_project_path",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("test_env"),
                "scenarios",
                "10x6_empty_room",
                "environment_configurations",
                "config1",
            ]
        ),
    )
    declare_gaden_playback_id = DeclareLaunchArgument("gaden_playback_id", default_value="scene1")
    declare_gaden_sensor_topic = DeclareLaunchArgument("gaden_sensor_topic", default_value="/gaden/sensor_reading")
    declare_gaden_sensor_frame = DeclareLaunchArgument("gaden_sensor_frame", default_value="base_link")
    declare_gaden_fixed_frame = DeclareLaunchArgument("gaden_fixed_frame", default_value="gaden_map")
    declare_gaden_map_offset_x = DeclareLaunchArgument("gaden_map_offset_x", default_value="5.0")
    declare_gaden_map_offset_y = DeclareLaunchArgument("gaden_map_offset_y", default_value="3.0")
    declare_gaden_map_offset_z = DeclareLaunchArgument("gaden_map_offset_z", default_value="0.0")
    declare_gaden_map_roll = DeclareLaunchArgument("gaden_map_roll", default_value="0.0")
    declare_gaden_map_pitch = DeclareLaunchArgument("gaden_map_pitch", default_value="0.0")
    declare_gaden_map_yaw = DeclareLaunchArgument("gaden_map_yaw", default_value="0.0")

    def _scene_defaults(context):
        scene_name = scene.perform(context)
        resolved_world = world.perform(context).strip() or resolve_scene_world(pkg_share, scene_name)
        resolved_model_path = gazebo_model_path.perform(context).strip() or resolve_scene_model_path(pkg_share, scene_name)
        return [
            SetLaunchConfiguration("world", resolved_world),
            SetLaunchConfiguration("gazebo_model_path", resolved_model_path),
        ]

    scene_defaults = OpaqueFunction(function=_scene_defaults)

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "sim.launch.py")),
        launch_arguments={
            "scene": scene,
            "world": world,
            "gazebo_model_path": gazebo_model_path,
            "use_sim_time": use_sim_time,
            "headless": headless,
            "spawn_x": initial_pose_x,
            "spawn_y": initial_pose_y,
            "spawn_yaw": initial_pose_yaw,
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "nav2.launch.py")),
        launch_arguments={"use_sim_time": use_sim_time, "params_file": nav2_params_file, "autostart": nav2_autostart}.items(),
    )

    nav2_startup_gate = Node(
        condition=UnlessCondition(nav2_autostart),
        package="h2track_tracking",
        executable="nav2_startup_gate_node",
        name="nav2_startup_gate_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "target_frame": "odom",
                "source_frame": "base_link",
                "lifecycle_manager_service": "/lifecycle_manager_navigation/manage_nodes",
                "timeout_sec": nav2_startup_gate_timeout,
                "poll_period_sec": nav2_startup_gate_poll_period,
                "stable_ready_count": nav2_startup_gate_stable_ready_count,
            },
        ],
    )


    gas_field = Node(
        condition=UnlessCondition(use_gaden),
        package="h2track_tracking",
        executable="gas_field_node",
        name="gas_field_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "source_x": source_x,
                "source_y": source_y,
                "source_strength": 120.0,
                "decay_rate": 0.55,
                "plume_stddev": 1.2,
                "wind_x": 0.4,
                "wind_y": 0.0,
                "noise_stddev": 0.05,
            },
        ],
    )

    gaden_environment = Node(
        condition=IfCondition(use_gaden),
        package="gaden_environment",
        executable="environment",
        name="gaden_environment",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}, {"projectPath": gaden_project_path}],
    )

    gaden_player = Node(
        condition=IfCondition(use_gaden),
        package="gaden_player",
        executable="player",
        name="gaden_player",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {"projectPath": gaden_project_path},
            {"playbackID": gaden_playback_id},
            {"player_freq": 1.0},
        ],
    )

    gaden_map_tf = Node(
        condition=IfCondition(use_gaden),
        package="tf2_ros",
        executable="static_transform_publisher",
        name="gaden_map_tf",
        output="screen",
        arguments=[
            "--x",
            gaden_map_offset_x,
            "--y",
            gaden_map_offset_y,
            "--z",
            gaden_map_offset_z,
            "--roll",
            gaden_map_roll,
            "--pitch",
            gaden_map_pitch,
            "--yaw",
            gaden_map_yaw,
            "--frame-id",
            gaden_fixed_frame,
            "--child-frame-id",
            "map",
        ],
    )

    gaden_sensor_gate = Node(
        condition=IfCondition(use_gaden),
        package="h2track_tracking",
        executable="gaden_sensor_gate_node",
        name="gaden_sensor_gate_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "fixed_frame": gaden_fixed_frame,
                "sensor_frame": gaden_sensor_frame,
                "timeout_sec": gaden_sensor_gate_timeout,
                "poll_period_sec": gaden_sensor_gate_poll_period,
                "stable_ready_count": gaden_sensor_gate_stable_ready_count,
                "sensor_node_name": "gaden_pid_sensor",
                "topic": gaden_sensor_topic,
                "sensor_model": 30,
                "rate": 5.0,
                "use_pid_correction_factors": False,
            },
        ],
    )

    gaden_adapter = Node(
        condition=IfCondition(use_gaden),
        package="h2track_tracking",
        executable="gaden_adapter_node",
        name="gaden_adapter_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "gas_sensor_topic": gaden_sensor_topic,
                "gas_concentration_topic": "/gas_concentration",
                "sensor_model": -1,
                "fallback_ohm_scale": 0.001,
                "voltage_scale": 1.0,
                "minimum_concentration_ppm": 0.0,
                "maximum_concentration_ppm": 0.0,
            },
        ],
    )

    mission_manager_node = Node(
        package="h2track_tracking",
        executable="mission_manager_node",
        name="mission_manager_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "initial_pose_x": initial_pose_x,
                "initial_pose_y": initial_pose_y,
                "initial_pose_yaw": initial_pose_yaw,
                "patrol_points": ParameterValue(patrol_points, value_type=str),
                "enter_threshold": enter_threshold,
                "exit_threshold": exit_threshold,
                "source_threshold": source_threshold,
                "confirm_samples": confirm_samples,
                "source_radius": source_radius,
                "source_hold_steps": source_hold_steps,
                "track_step": track_step,
                "sweep_angle_deg": sweep_angle_deg,
                "source_x": source_x,
                "source_y": source_y,
            },
        ],
    )

    def _mission_manager_actions_after_nav2_gate_exit(event, context):
        if event.returncode == 0:
            return [mission_manager_node]
        return [Shutdown(reason="Nav2 startup gate failed")]

    mission_manager = TimerAction(
        condition=IfCondition(nav2_autostart),
        period=mission_manager_delay,
        actions=[mission_manager_node],
    )

    gated_mission_manager = RegisterEventHandler(
        condition=UnlessCondition(nav2_autostart),
        event_handler=OnProcessExit(
            target_action=nav2_startup_gate,
            on_exit=_mission_manager_actions_after_nav2_gate_exit,
        ),
    )

    rviz = Node(
        condition=IfCondition(use_rviz),
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", os.path.join(pkg_share, "rviz", "h2track_nav2.rviz")],
        parameters=[{"use_sim_time": use_sim_time}],
    )

    return LaunchDescription(
        [
            declare_scene,
            declare_use_sim_time,
            declare_use_rviz,
            declare_headless,
            declare_world,
            declare_gazebo_model_path,
            declare_use_gaden,
            declare_nav2_params_file,
            declare_nav2_autostart,
            declare_mission_manager_delay,
            declare_nav2_startup_gate_timeout,
            declare_nav2_startup_gate_poll_period,
            declare_nav2_startup_gate_stable_ready_count,
            declare_gaden_sensor_gate_timeout,
            declare_gaden_sensor_gate_poll_period,
            declare_gaden_sensor_gate_stable_ready_count,
            declare_initial_pose_x,
            declare_initial_pose_y,
            declare_initial_pose_yaw,
            declare_patrol_points,
            declare_enter_threshold,
            declare_exit_threshold,
            declare_source_threshold,
            declare_confirm_samples,
            declare_source_radius,
            declare_source_hold_steps,
            declare_track_step,
            declare_sweep_angle_deg,
            declare_source_x,
            declare_source_y,
            declare_gaden_project_path,
            declare_gaden_playback_id,
            declare_gaden_sensor_topic,
            declare_gaden_sensor_frame,
            declare_gaden_fixed_frame,
            declare_gaden_map_offset_x,
            declare_gaden_map_offset_y,
            declare_gaden_map_offset_z,
            declare_gaden_map_roll,
            declare_gaden_map_pitch,
            declare_gaden_map_yaw,
            scene_defaults,
            sim,
            nav2,
            nav2_startup_gate,
            gas_field,
            gaden_environment,
            gaden_player,
            gaden_map_tf,
            gaden_sensor_gate,
            gaden_adapter,
            mission_manager,
            gated_mission_manager,
            rviz,
        ]
    )
