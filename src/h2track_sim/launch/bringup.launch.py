#!/usr/bin/env python3

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable, SetLaunchConfiguration, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
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
load_scene_profile = SCENE_LOADER.load_scene_profile
resolve_scene_nav2_params = SCENE_LOADER.resolve_scene_nav2_params
resolve_scene_model_path = SCENE_LOADER.resolve_scene_model_path
resolve_scene_world = SCENE_LOADER.resolve_scene_world


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_sim")

    scene = LaunchConfiguration("scene")
    use_rviz = LaunchConfiguration("use_rviz")
    use_sim_time = LaunchConfiguration("use_sim_time")
    headless = LaunchConfiguration("headless")
    world = LaunchConfiguration("world")
    gazebo_model_path = LaunchConfiguration("gazebo_model_path")
    use_gaden = LaunchConfiguration("use_gaden")
    use_slam = LaunchConfiguration("use_slam")
    nav2_map_file = LaunchConfiguration("nav2_map_file")
    nav2_params_file = LaunchConfiguration("nav2_params_file")
    nav2_autostart = LaunchConfiguration("nav2_autostart")
    nav2_launch_delay = LaunchConfiguration("nav2_launch_delay")
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
    patrol_goal_timeout_sec = LaunchConfiguration("patrol_goal_timeout_sec")
    patrol_points = LaunchConfiguration("patrol_points")
    enter_threshold = LaunchConfiguration("enter_threshold")
    exit_threshold = LaunchConfiguration("exit_threshold")
    source_threshold = LaunchConfiguration("source_threshold")
    confirm_samples = LaunchConfiguration("confirm_samples")
    track_exit_samples = LaunchConfiguration("track_exit_samples")
    source_radius = LaunchConfiguration("source_radius")
    source_hold_steps = LaunchConfiguration("source_hold_steps")
    track_step = LaunchConfiguration("track_step")
    surge_step = LaunchConfiguration("surge_step")
    cast_step = LaunchConfiguration("cast_step")
    sweep_angle_deg = LaunchConfiguration("sweep_angle_deg")
    source_x = LaunchConfiguration("source_x")
    source_y = LaunchConfiguration("source_y")
    localizer_node = LaunchConfiguration("localizer_node")
    publish_initial_pose = LaunchConfiguration("publish_initial_pose")
    gas_source_strength = LaunchConfiguration("gas_source_strength")
    gas_decay_rate = LaunchConfiguration("gas_decay_rate")
    gas_plume_stddev = LaunchConfiguration("gas_plume_stddev")
    gas_wind_x = LaunchConfiguration("gas_wind_x")
    gas_wind_y = LaunchConfiguration("gas_wind_y")
    gas_noise_stddev = LaunchConfiguration("gas_noise_stddev")
    gas_publish_rate_hz = LaunchConfiguration("gas_publish_rate_hz")
    gaden_project_path = LaunchConfiguration("gaden_project_path")
    gaden_playback_id = LaunchConfiguration("gaden_playback_id")
    gaden_player_freq = LaunchConfiguration("gaden_player_freq")
    gaden_sensor_topic = LaunchConfiguration("gaden_sensor_topic")
    gaden_sensor_frame = LaunchConfiguration("gaden_sensor_frame")
    gaden_fixed_frame = LaunchConfiguration("gaden_fixed_frame")
    gaden_map_offset_x = LaunchConfiguration("gaden_map_offset_x")
    gaden_map_offset_y = LaunchConfiguration("gaden_map_offset_y")
    gaden_map_offset_z = LaunchConfiguration("gaden_map_offset_z")
    gaden_map_roll = LaunchConfiguration("gaden_map_roll")
    gaden_map_pitch = LaunchConfiguration("gaden_map_pitch")
    gaden_map_yaw = LaunchConfiguration("gaden_map_yaw")
    use_particle_filter = LaunchConfiguration("use_particle_filter")
    particle_filter_num_particles = LaunchConfiguration("particle_filter_num_particles")
    particle_filter_motion_sigma = LaunchConfiguration("particle_filter_motion_sigma")
    particle_filter_observation_sigma = LaunchConfiguration("particle_filter_observation_sigma")
    particle_filter_plume_sigma = LaunchConfiguration("particle_filter_plume_sigma")
    particle_filter_source_strength = LaunchConfiguration("particle_filter_source_strength")
    particle_filter_bounds = LaunchConfiguration("particle_filter_bounds")
    particle_filter_publish_rate = LaunchConfiguration("particle_filter_publish_rate")
    particle_filter_resample_threshold = LaunchConfiguration("particle_filter_resample_threshold")

    declare_scene = DeclareLaunchArgument("scene", default_value="baseline")
    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_use_rviz = DeclareLaunchArgument("use_rviz", default_value="true")
    declare_headless = DeclareLaunchArgument("headless", default_value="false")
    declare_world = DeclareLaunchArgument("world", default_value="")
    declare_gazebo_model_path = DeclareLaunchArgument("gazebo_model_path", default_value="")
    declare_use_gaden = DeclareLaunchArgument("use_gaden", default_value="")
    declare_use_slam = DeclareLaunchArgument("use_slam", default_value="")
    declare_nav2_map_file = DeclareLaunchArgument("nav2_map_file", default_value="")
    declare_nav2_params_file = DeclareLaunchArgument("nav2_params_file", default_value="")
    declare_nav2_autostart = DeclareLaunchArgument("nav2_autostart", default_value="")
    declare_nav2_launch_delay = DeclareLaunchArgument("nav2_launch_delay", default_value="12.0")
    declare_mission_manager_delay = DeclareLaunchArgument("mission_manager_delay", default_value="10.0")
    declare_nav2_startup_gate_timeout = DeclareLaunchArgument("nav2_startup_gate_timeout", default_value="30.0")
    declare_nav2_startup_gate_poll_period = DeclareLaunchArgument("nav2_startup_gate_poll_period", default_value="0.5")
    declare_nav2_startup_gate_stable_ready_count = DeclareLaunchArgument("nav2_startup_gate_stable_ready_count", default_value="2")
    declare_gaden_sensor_gate_timeout = DeclareLaunchArgument("gaden_sensor_gate_timeout", default_value="60.0")
    declare_gaden_sensor_gate_poll_period = DeclareLaunchArgument("gaden_sensor_gate_poll_period", default_value="0.5")
    declare_gaden_sensor_gate_stable_ready_count = DeclareLaunchArgument("gaden_sensor_gate_stable_ready_count", default_value="3")
    declare_initial_pose_x = DeclareLaunchArgument("initial_pose_x", default_value="")
    declare_initial_pose_y = DeclareLaunchArgument("initial_pose_y", default_value="")
    declare_initial_pose_yaw = DeclareLaunchArgument("initial_pose_yaw", default_value="")
    declare_patrol_goal_timeout_sec = DeclareLaunchArgument("patrol_goal_timeout_sec", default_value="")
    declare_patrol_points = DeclareLaunchArgument("patrol_points", default_value="")
    declare_enter_threshold = DeclareLaunchArgument("enter_threshold", default_value="")
    declare_exit_threshold = DeclareLaunchArgument("exit_threshold", default_value="")
    declare_source_threshold = DeclareLaunchArgument("source_threshold", default_value="")
    declare_confirm_samples = DeclareLaunchArgument("confirm_samples", default_value="")
    declare_track_exit_samples = DeclareLaunchArgument("track_exit_samples", default_value="")
    declare_source_radius = DeclareLaunchArgument("source_radius", default_value="")
    declare_source_hold_steps = DeclareLaunchArgument("source_hold_steps", default_value="")
    declare_track_step = DeclareLaunchArgument("track_step", default_value="")
    declare_surge_step = DeclareLaunchArgument("surge_step", default_value="")
    declare_cast_step = DeclareLaunchArgument("cast_step", default_value="")
    declare_sweep_angle_deg = DeclareLaunchArgument("sweep_angle_deg", default_value="")
    declare_source_x = DeclareLaunchArgument("source_x", default_value="")
    declare_source_y = DeclareLaunchArgument("source_y", default_value="")
    declare_localizer_node = DeclareLaunchArgument("localizer_node", default_value="")
    declare_publish_initial_pose = DeclareLaunchArgument("publish_initial_pose", default_value="")
    declare_gas_source_strength = DeclareLaunchArgument("gas_source_strength", default_value="")
    declare_gas_decay_rate = DeclareLaunchArgument("gas_decay_rate", default_value="")
    declare_gas_plume_stddev = DeclareLaunchArgument("gas_plume_stddev", default_value="")
    declare_gas_wind_x = DeclareLaunchArgument("gas_wind_x", default_value="")
    declare_gas_wind_y = DeclareLaunchArgument("gas_wind_y", default_value="")
    declare_gas_noise_stddev = DeclareLaunchArgument("gas_noise_stddev", default_value="")
    declare_gas_publish_rate_hz = DeclareLaunchArgument("gas_publish_rate_hz", default_value="")
    declare_gaden_project_path = DeclareLaunchArgument("gaden_project_path", default_value="")
    declare_gaden_playback_id = DeclareLaunchArgument("gaden_playback_id", default_value="")
    declare_gaden_player_freq = DeclareLaunchArgument("gaden_player_freq", default_value="")
    declare_gaden_sensor_topic = DeclareLaunchArgument("gaden_sensor_topic", default_value="")
    declare_gaden_sensor_frame = DeclareLaunchArgument("gaden_sensor_frame", default_value="")
    declare_gaden_fixed_frame = DeclareLaunchArgument("gaden_fixed_frame", default_value="")
    declare_gaden_map_offset_x = DeclareLaunchArgument("gaden_map_offset_x", default_value="")
    declare_gaden_map_offset_y = DeclareLaunchArgument("gaden_map_offset_y", default_value="")
    declare_gaden_map_offset_z = DeclareLaunchArgument("gaden_map_offset_z", default_value="")
    declare_gaden_map_roll = DeclareLaunchArgument("gaden_map_roll", default_value="")
    declare_gaden_map_pitch = DeclareLaunchArgument("gaden_map_pitch", default_value="")
    declare_gaden_map_yaw = DeclareLaunchArgument("gaden_map_yaw", default_value="")
    declare_use_particle_filter = DeclareLaunchArgument("use_particle_filter", default_value="true")
    declare_particle_filter_num_particles = DeclareLaunchArgument("particle_filter_num_particles", default_value="500")
    declare_particle_filter_motion_sigma = DeclareLaunchArgument("particle_filter_motion_sigma", default_value="0.3")
    declare_particle_filter_observation_sigma = DeclareLaunchArgument("particle_filter_observation_sigma", default_value="0.5")
    declare_particle_filter_plume_sigma = DeclareLaunchArgument("particle_filter_plume_sigma", default_value="2.0")
    declare_particle_filter_source_strength = DeclareLaunchArgument("particle_filter_source_strength", default_value="")
    declare_particle_filter_bounds = DeclareLaunchArgument("particle_filter_bounds", default_value="")
    declare_particle_filter_publish_rate = DeclareLaunchArgument("particle_filter_publish_rate", default_value="2.0")
    declare_particle_filter_resample_threshold = DeclareLaunchArgument("particle_filter_resample_threshold", default_value="0.5")

    def _scene_defaults(context):
        scene_name = scene.perform(context)
        scene_profile = load_scene_profile(pkg_share, scene_name)
        gas_field = scene_profile.get("gas_field", {})
        gaden = scene_profile.get("gaden")
        mission_mgr = scene_profile.get("mission_manager", {})
        gas_source = scene_profile.get("gas_source", {})

        # -- use_gaden: if user didn't set, read from scene
        requested_use_gaden = use_gaden.perform(context).strip().lower()
        if requested_use_gaden:
            use_gaden_enabled = requested_use_gaden in ("1", "true", "yes", "on")
        else:
            use_gaden_enabled = bool(scene_profile.get("use_gaden", False))

        requested_use_slam = use_slam.perform(context).strip().lower()
        if requested_use_slam:
            use_slam_enabled = requested_use_slam in ("1", "true", "yes", "on")
        else:
            use_slam_enabled = bool(scene_profile.get("use_slam", False))
        requested_nav2_autostart = nav2_autostart.perform(context).strip().lower()
        if requested_nav2_autostart:
            resolved_nav2_autostart = requested_nav2_autostart in ("1", "true", "yes", "on")
        else:
            resolved_nav2_autostart = bool(scene_profile.get("nav2_autostart", True))
        resolved_world = world.perform(context).strip() or resolve_scene_world(pkg_share, scene_name)
        resolved_model_path = gazebo_model_path.perform(context).strip() or resolve_scene_model_path(pkg_share, scene_name)
        resolved_nav2_params_file = nav2_params_file.perform(context).strip() or resolve_scene_nav2_params(pkg_share, scene_name)
        # When use_slam is false, always use amcl regardless of scene config
        if not use_slam_enabled:
            resolved_localizer_node = "amcl"
            # When using AMCL (non-SLAM mode), force autostart=true because
            # lifecycle_manager_localization needs to auto-activate amcl and map_server
            resolved_nav2_autostart = True
        else:
            resolved_localizer_node = localizer_node.perform(context).strip() or str(
                scene_profile.get("localizer_node", "none")
            )
        requested_publish_initial_pose = publish_initial_pose.perform(context).strip().lower()
        if requested_publish_initial_pose:
            resolved_publish_initial_pose = requested_publish_initial_pose in ("1", "true", "yes", "on")
        else:
            resolved_publish_initial_pose = not use_slam_enabled
        resolved_gaden_project_path = gaden_project_path.perform(context).strip()
        resolved_gaden_playback_id = gaden_playback_id.perform(context).strip()
        resolved_gaden_player_freq = gaden_player_freq.perform(context).strip()
        resolved_gaden_sensor_topic = gaden_sensor_topic.perform(context).strip()
        resolved_gaden_sensor_frame = gaden_sensor_frame.perform(context).strip()
        resolved_gaden_fixed_frame = gaden_fixed_frame.perform(context).strip()
        resolved_gaden_map_offset_x = gaden_map_offset_x.perform(context).strip()
        resolved_gaden_map_offset_y = gaden_map_offset_y.perform(context).strip()
        resolved_gaden_map_offset_z = gaden_map_offset_z.perform(context).strip()
        resolved_gaden_map_roll = gaden_map_roll.perform(context).strip()
        resolved_gaden_map_pitch = gaden_map_pitch.perform(context).strip()
        resolved_gaden_map_yaw = gaden_map_yaw.perform(context).strip()
        resolved_gas_source_strength = gas_source_strength.perform(context).strip() or str(gas_field.get("source_strength", 120.0))
        resolved_gas_decay_rate = gas_decay_rate.perform(context).strip() or str(gas_field.get("decay_rate", 0.55))
        resolved_gas_plume_stddev = gas_plume_stddev.perform(context).strip() or str(gas_field.get("plume_stddev", 1.2))
        resolved_gas_wind_x = gas_wind_x.perform(context).strip() or str(gas_field.get("wind_x", 0.4))
        resolved_gas_wind_y = gas_wind_y.perform(context).strip() or str(gas_field.get("wind_y", 0.0))
        resolved_gas_noise_stddev = gas_noise_stddev.perform(context).strip() or str(gas_field.get("noise_stddev", 0.05))
        resolved_gas_publish_rate_hz = gas_publish_rate_hz.perform(context).strip() or str(gas_field.get("publish_rate_hz", 5.0))
        # Resolve particle filter bounds - use default warehouse bounds
        resolved_particle_filter_bounds = particle_filter_bounds.perform(context).strip() or "[-6.0, -6.0, 6.0, 6.0]"

        # -- mission_manager defaults --------------------------------------------
        mm_initial = mission_mgr.get("initial_pose", {})
        resolved_initial_pose_x = initial_pose_x.perform(context).strip() or str(mm_initial.get("x", "0.0"))
        resolved_initial_pose_y = initial_pose_y.perform(context).strip() or str(mm_initial.get("y", "0.0"))
        resolved_initial_pose_yaw = initial_pose_yaw.perform(context).strip() or str(mm_initial.get("yaw", "0.0"))
        resolved_patrol_goal_timeout = patrol_goal_timeout_sec.perform(context).strip() or str(mission_mgr.get("patrol_goal_timeout_sec", "45.0"))

        # patrol_points: scene.yaml [[x,y],[x,y],...] → flat string "[x, y, x, y, ...]"
        raw_patrol = patrol_points.perform(context).strip()
        if raw_patrol:
            resolved_patrol_points = raw_patrol
        else:
            pp = mission_mgr.get("patrol_points", [])
            if pp:
                flat = [str(v) for point in pp for v in point]
                resolved_patrol_points = "[" + ", ".join(flat) + "]"
            else:
                resolved_patrol_points = ""

        resolved_enter_threshold = enter_threshold.perform(context).strip() or str(mission_mgr.get("enter_threshold", 2.0))
        resolved_exit_threshold = exit_threshold.perform(context).strip() or str(mission_mgr.get("exit_threshold", 1.0))
        resolved_source_threshold = source_threshold.perform(context).strip() or str(mission_mgr.get("source_threshold", 10.0))
        resolved_confirm_samples = confirm_samples.perform(context).strip() or str(mission_mgr.get("confirm_samples", 3))
        resolved_track_exit_samples = track_exit_samples.perform(context).strip() or str(mission_mgr.get("track_exit_samples", 3))
        resolved_source_radius = source_radius.perform(context).strip() or str(mission_mgr.get("source_radius", 1.0))
        resolved_source_hold_steps = source_hold_steps.perform(context).strip() or str(mission_mgr.get("source_hold_steps", 5))
        resolved_track_step = track_step.perform(context).strip() or str(mission_mgr.get("track_step", 0.7))
        resolved_surge_step = surge_step.perform(context).strip() or str(mission_mgr.get("track_step", 0.5))
        resolved_cast_step = cast_step.perform(context).strip() or str(mission_mgr.get("cast_step", 0.3))
        resolved_sweep_angle_deg = sweep_angle_deg.perform(context).strip() or str(mission_mgr.get("sweep_angle_deg", 30.0))

        # -- gas_source ----------------------------------------------------------
        resolved_source_x = source_x.perform(context).strip() or str(gas_source.get("x", -3.5))
        resolved_source_y = source_y.perform(context).strip() or str(gas_source.get("y", -3.5))

        if use_gaden_enabled:
            if not gaden:
                raise RuntimeError(f"Scene '{scene_name}' is missing a gaden configuration block")
            scene_gaden_project_path = str(gaden.get("project_path", "")).strip()
            if not scene_gaden_project_path:
                raise RuntimeError(f"Scene '{scene_name}' GADEN config is missing project_path")
            resolved_gaden_project_path = resolved_gaden_project_path or scene_gaden_project_path
            if not Path(resolved_gaden_project_path).exists():
                raise RuntimeError(
                    f"Scene '{scene_name}' GADEN project_path does not exist: {resolved_gaden_project_path}"
                )
            resolved_gaden_playback_id = resolved_gaden_playback_id or str(gaden.get("playback_id", "scene1"))
            resolved_gaden_player_freq = resolved_gaden_player_freq or str(gaden.get("player_freq", 1.0))
            resolved_gaden_sensor_topic = resolved_gaden_sensor_topic or str(gaden.get("sensor_topic", "/gaden/sensor_reading"))
            resolved_gaden_sensor_frame = resolved_gaden_sensor_frame or str(gaden.get("sensor_frame", "base_link"))
            resolved_gaden_fixed_frame = resolved_gaden_fixed_frame or str(gaden.get("fixed_frame", "gaden_map"))
            resolved_gaden_map_offset_x = resolved_gaden_map_offset_x or str(gaden.get("map_offset_x", 0.0))
            resolved_gaden_map_offset_y = resolved_gaden_map_offset_y or str(gaden.get("map_offset_y", 0.0))
            resolved_gaden_map_offset_z = resolved_gaden_map_offset_z or str(gaden.get("map_offset_z", 0.0))
            resolved_gaden_map_roll = resolved_gaden_map_roll or str(gaden.get("map_roll", 0.0))
            resolved_gaden_map_pitch = resolved_gaden_map_pitch or str(gaden.get("map_pitch", 0.0))
            resolved_gaden_map_yaw = resolved_gaden_map_yaw or str(gaden.get("map_yaw", 0.0))
        return [
            SetLaunchConfiguration("world", resolved_world),
            SetLaunchConfiguration("gazebo_model_path", resolved_model_path),
            SetLaunchConfiguration("nav2_params_file", resolved_nav2_params_file),
            SetLaunchConfiguration("nav2_autostart", str(resolved_nav2_autostart).lower()),
            SetLaunchConfiguration("use_slam", str(use_slam_enabled).lower()),
            SetLaunchConfiguration("localizer_node", resolved_localizer_node),
            SetLaunchConfiguration("publish_initial_pose", str(resolved_publish_initial_pose).lower()),
            SetLaunchConfiguration("gas_source_strength", resolved_gas_source_strength),
            SetLaunchConfiguration("gas_decay_rate", resolved_gas_decay_rate),
            SetLaunchConfiguration("gas_plume_stddev", resolved_gas_plume_stddev),
            SetLaunchConfiguration("gas_wind_x", resolved_gas_wind_x),
            SetLaunchConfiguration("gas_wind_y", resolved_gas_wind_y),
            SetLaunchConfiguration("gas_noise_stddev", resolved_gas_noise_stddev),
            SetLaunchConfiguration("gas_publish_rate_hz", resolved_gas_publish_rate_hz),
            SetLaunchConfiguration("gaden_project_path", resolved_gaden_project_path),
            SetLaunchConfiguration("gaden_playback_id", resolved_gaden_playback_id),
            SetLaunchConfiguration("gaden_player_freq", resolved_gaden_player_freq),
            SetLaunchConfiguration("gaden_sensor_topic", resolved_gaden_sensor_topic),
            SetLaunchConfiguration("gaden_sensor_frame", resolved_gaden_sensor_frame),
            SetLaunchConfiguration("gaden_fixed_frame", resolved_gaden_fixed_frame),
            SetLaunchConfiguration("gaden_map_offset_x", resolved_gaden_map_offset_x),
            SetLaunchConfiguration("gaden_map_offset_y", resolved_gaden_map_offset_y),
            SetLaunchConfiguration("gaden_map_offset_z", resolved_gaden_map_offset_z),
            SetLaunchConfiguration("gaden_map_roll", resolved_gaden_map_roll),
            SetLaunchConfiguration("gaden_map_pitch", resolved_gaden_map_pitch),
            SetLaunchConfiguration("gaden_map_yaw", resolved_gaden_map_yaw),
            SetLaunchConfiguration("particle_filter_bounds", resolved_particle_filter_bounds),
            SetLaunchConfiguration("use_gaden", str(use_gaden_enabled).lower()),
            # mission_manager
            SetLaunchConfiguration("initial_pose_x", resolved_initial_pose_x),
            SetLaunchConfiguration("initial_pose_y", resolved_initial_pose_y),
            SetLaunchConfiguration("initial_pose_yaw", resolved_initial_pose_yaw),
            SetLaunchConfiguration("patrol_goal_timeout_sec", resolved_patrol_goal_timeout),
            SetLaunchConfiguration("patrol_points", resolved_patrol_points),
            SetLaunchConfiguration("enter_threshold", resolved_enter_threshold),
            SetLaunchConfiguration("exit_threshold", resolved_exit_threshold),
            SetLaunchConfiguration("source_threshold", resolved_source_threshold),
            SetLaunchConfiguration("confirm_samples", resolved_confirm_samples),
            SetLaunchConfiguration("track_exit_samples", resolved_track_exit_samples),
            SetLaunchConfiguration("source_radius", resolved_source_radius),
            SetLaunchConfiguration("source_hold_steps", resolved_source_hold_steps),
            SetLaunchConfiguration("track_step", resolved_track_step),
            SetLaunchConfiguration("surge_step", resolved_surge_step),
            SetLaunchConfiguration("cast_step", resolved_cast_step),
            SetLaunchConfiguration("sweep_angle_deg", resolved_sweep_angle_deg),
            # gas_source
            SetLaunchConfiguration("source_x", resolved_source_x),
            SetLaunchConfiguration("source_y", resolved_source_y),
        ]

    scene_defaults = OpaqueFunction(function=_scene_defaults)
    set_fastdds_udp = SetEnvironmentVariable("FASTDDS_BUILTIN_TRANSPORTS", "UDPv4")

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

    nav2_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "nav2.launch.py")),
        launch_arguments={
            "scene": scene,
            "use_sim_time": use_sim_time,
            "params_file": nav2_params_file,
            "map": nav2_map_file,
            "autostart": nav2_autostart,
            "use_slam": use_slam,
        }.items(),
    )
    nav2 = TimerAction(
        period=nav2_launch_delay,
        actions=[nav2_include],
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
                "source_strength": gas_source_strength,
                "decay_rate": gas_decay_rate,
                "plume_stddev": gas_plume_stddev,
                "wind_x": gas_wind_x,
                "wind_y": gas_wind_y,
                "noise_stddev": gas_noise_stddev,
                "publish_rate_hz": gas_publish_rate_hz,
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
            {"player_freq": gaden_player_freq},
        ],
    )

    gaden_map_tf = Node(
        condition=IfCondition(use_gaden),
        package="tf2_ros",
        executable="static_transform_publisher",
        name="gaden_map_tf",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
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

    # Static map->odom transform for non-SLAM mode with GADEN
    # When use_slam=false, we need map->odom to connect the TF tree
    map_to_odom_tf = Node(
        condition=IfCondition(PythonExpression(["'", use_gaden, "'.lower() in ('1', 'true', 'yes', 'on') and '", use_slam, "'.lower() not in ('1', 'true', 'yes', 'on')"])),
        package="tf2_ros",
        executable="static_transform_publisher",
        name="map_to_odom_tf",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=[
            "--x", "0.0",
            "--y", "0.0",
            "--z", "0.0",
            "--roll", "0.0",
            "--pitch", "0.0",
            "--yaw", "0.0",
            "--frame-id", "map",
            "--child-frame-id", "odom",
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

    # BT-based mission manager
    bt_mission_node = Node(
        package="h2track_tracking",
        executable="bt_node_runner",
        name="bt_node_runner",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "initial_pose_x": initial_pose_x,
                "initial_pose_y": initial_pose_y,
                "initial_pose_yaw": initial_pose_yaw,
                "patrol_goal_timeout_sec": patrol_goal_timeout_sec,
                "patrol_points": ParameterValue(patrol_points, value_type=str),
                "enter_threshold": enter_threshold,
                "exit_threshold": exit_threshold,
                "source_threshold": source_threshold,
                "confirm_samples": confirm_samples,
                "track_exit_samples": track_exit_samples,
                "source_radius": source_radius,
                "source_hold_steps": source_hold_steps,
                "track_step": track_step,
                "surge_step": surge_step,
                "cast_step": cast_step,
                "sweep_angle_deg": sweep_angle_deg,
                "source_x": source_x,
                "source_y": source_y,
                "wind_x": gas_wind_x,
                "wind_y": gas_wind_y,
                "localizer_node": localizer_node,
                "use_slam": ParameterValue(use_slam, value_type=bool),
                "publish_initial_pose": ParameterValue(publish_initial_pose, value_type=bool),
                "estimate_wind": True,
                "use_fusion": True,
                "use_particle_filter_estimate": True,
            },
        ],
    )

    mission_manager = TimerAction(
        period=PythonExpression([nav2_launch_delay, " + ", mission_manager_delay]),
        actions=[bt_mission_node],
    )

    # Activate localization nodes (AMCL, map_server) when not using SLAM
    activate_localization = TimerAction(
        period=PythonExpression([nav2_launch_delay, " + 5.0"]),
        condition=UnlessCondition(use_slam),
        actions=[
            ExecuteProcess(
                cmd=["ros2", "run", "h2track_tracking", "activate_localization"],
                output="screen",
            )
        ],
    )

    particle_filter = Node(
        condition=IfCondition(use_particle_filter),
        package="h2track_tracking",
        executable="particle_filter_node",
        name="particle_filter_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "num_particles": particle_filter_num_particles,
                "motion_sigma": particle_filter_motion_sigma,
                "observation_sigma": particle_filter_observation_sigma,
                "plume_sigma": particle_filter_plume_sigma,
                "source_strength": gas_source_strength,
                "bounds": particle_filter_bounds,
                "publish_rate": particle_filter_publish_rate,
                "resample_threshold": particle_filter_resample_threshold,
            },
        ],
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
            declare_use_slam,
            declare_nav2_map_file,
            declare_nav2_params_file,
            declare_nav2_autostart,
            declare_nav2_launch_delay,
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
            declare_patrol_goal_timeout_sec,
            declare_patrol_points,
            declare_enter_threshold,
            declare_exit_threshold,
            declare_source_threshold,
            declare_confirm_samples,
            declare_track_exit_samples,
            declare_source_radius,
            declare_source_hold_steps,
            declare_track_step,
            declare_surge_step,
            declare_cast_step,
            declare_sweep_angle_deg,
            declare_source_x,
            declare_source_y,
            declare_localizer_node,
            declare_publish_initial_pose,
            declare_gas_source_strength,
            declare_gas_decay_rate,
            declare_gas_plume_stddev,
            declare_gas_wind_x,
            declare_gas_wind_y,
            declare_gas_noise_stddev,
            declare_gas_publish_rate_hz,
            declare_gaden_project_path,
            declare_gaden_playback_id,
            declare_gaden_player_freq,
            declare_gaden_sensor_topic,
            declare_gaden_sensor_frame,
            declare_gaden_fixed_frame,
            declare_gaden_map_offset_x,
            declare_gaden_map_offset_y,
            declare_gaden_map_offset_z,
            declare_gaden_map_roll,
            declare_gaden_map_pitch,
            declare_gaden_map_yaw,
            declare_use_particle_filter,
            declare_particle_filter_num_particles,
            declare_particle_filter_motion_sigma,
            declare_particle_filter_observation_sigma,
            declare_particle_filter_plume_sigma,
            declare_particle_filter_source_strength,
            declare_particle_filter_bounds,
            declare_particle_filter_publish_rate,
            declare_particle_filter_resample_threshold,
            set_fastdds_udp,
            scene_defaults,
            sim,
            nav2,
            nav2_startup_gate,
            gas_field,
            gaden_environment,
            gaden_player,
            gaden_map_tf,
            map_to_odom_tf,
            gaden_sensor_gate,
            gaden_adapter,
            mission_manager,
            particle_filter,
            rviz,
        ]
    )
