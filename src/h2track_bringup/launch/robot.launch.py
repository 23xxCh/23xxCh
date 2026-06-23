#!/usr/bin/env python3
"""Robot top-level launch (Layer 1).

Includes all subsystems: simulation, navigation, gas simulation, tracking, visualization.
Scene defaults are resolved here and passed down to subsystems.
"""

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
    SetLaunchConfiguration,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression


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

# ---------------------------------------------------------------------------
# Parameter schema: (name, default_value)
# Empty default = resolved from scene.yaml in _scene_defaults()
# ---------------------------------------------------------------------------
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
    # Sim2real: realistic sensor model (opt-in)
    ("use_realistic_sensor", "false"),
    ("sensor_response_tau", "8.0"),
    ("sensor_recovery_tau", "20.0"),
    ("sensor_noise_stddev", "0.5"),
    ("sensor_quantization", "0.1"),
    ("sensor_saturation", "500.0"),
    ("sensor_baseline_drift_rate", "0.01"),
    ("sensor_baseline_drift_max", "2.0"),
    # Sim2real: time-varying wind (opt-in)
    ("use_time_varying_wind", "false"),
    ("wind_mean_speed", "0.4"),
    ("wind_mean_direction_deg", "0.0"),
    ("wind_direction_stddev_deg", "15.0"),
    ("wind_gust_rate", "0.05"),
    ("wind_gust_strength_factor", "0.5"),
    ("wind_gust_duration", "3.0"),
    # Anemometer ground-truth wind (GADEN only, opt-in)
    ("use_anemometer_ground_truth", "false"),
    ("anemometer_noise_std", "0.1"),
    ("anemometer_frequency", "10.0"),
    ("anemometer_smoothing_alpha", "1.0"),
    ("anemometer_max_wind_speed", "10.0"),
    ("use_particle_filter", "true"),
    ("particle_filter_num_particles", "500"),
    ("particle_filter_motion_sigma", "0.3"),
    ("particle_filter_observation_sigma", "0.5"),
    ("particle_filter_plume_sigma", "2.0"),
    ("particle_filter_source_strength", ""),
    ("particle_filter_decay_rate", ""),
    ("particle_filter_plume_sigma", "1.2"),
    ("particle_filter_wind_x", ""),
    ("particle_filter_wind_y", ""),
    ("particle_filter_gas_type", ""),
    ("particle_filter_bounds", ""),
    ("particle_filter_publish_rate", "2.0"),
    ("particle_filter_resample_threshold", "0.5"),
]


def generate_launch_description():
    pkg_share = get_package_share_directory("h2track_bringup")

    # -- create all LaunchConfiguration + DeclareLaunchArgument via schema ---
    lc = {name: LaunchConfiguration(name) for name, _ in _PARAMS}
    declares = [DeclareLaunchArgument(name, default_value=dflt) for name, dflt in _PARAMS]

    def _scene_defaults(context):
        scene_name = lc["scene"].perform(context)
        scene_profile = load_scene_profile(pkg_share, scene_name)
        gas_field = scene_profile.get("gas_field", {})
        gaden = scene_profile.get("gaden")
        mission_mgr = scene_profile.get("mission_manager", {})
        gas_source = scene_profile.get("gas_source", {})

        def _resolve(key, fallback=""):
            val = lc[key].perform(context).strip()
            return val if val else str(fallback)

        def _resolve_bool(key, fallback):
            val = lc[key].perform(context).strip().lower()
            if val:
                return val in ("1", "true", "yes", "on")
            return bool(fallback)

        # -- booleans with scene defaults ------------------------------------
        use_gaden_enabled = _resolve_bool("use_gaden", scene_profile.get("use_gaden", False))
        use_slam_enabled = _resolve_bool("use_slam", scene_profile.get("use_slam", False))
        resolved_nav2_autostart = _resolve_bool("nav2_autostart", scene_profile.get("nav2_autostart", True))

        # -- localizer logic -------------------------------------------------
        if not use_slam_enabled:
            resolved_localizer = "amcl"
            resolved_nav2_autostart = True
        else:
            resolved_localizer = _resolve("localizer_node", scene_profile.get("localizer_node", "none"))

        resolved_publish_initial = _resolve_bool(
            "publish_initial_pose", not use_slam_enabled
        )

        # -- world / nav2 paths ----------------------------------------------
        resolved_world = _resolve("world", resolve_scene_world(pkg_share, scene_name))
        # Render @GADEN_WS@ placeholders in world files
        if "@GADEN_WS@" in resolved_world or (Path(resolved_world).exists() and "@GADEN_WS@" in Path(resolved_world).read_text(encoding="utf-8")):
            import tempfile
            gaden_ws = os.environ.get("GADEN_WS", "/home/user/gaden_ws")
            world_text = Path(resolved_world).read_text(encoding="utf-8")
            rendered = world_text.replace("@GADEN_WS@", gaden_ws)
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".world", delete=False, prefix=f"h2track_{scene_name}_")
            tmp.write(rendered)
            tmp.close()
            resolved_world = tmp.name
        resolved_model_path = _resolve("gazebo_model_path", resolve_scene_model_path(pkg_share, scene_name))
        resolved_nav2_params = _resolve("nav2_params_file", resolve_scene_nav2_params(pkg_share, scene_name))

        # -- gas_field --------------------------------------------------------
        gf_defaults = {
            "gas_source_strength": ("source_strength", 120.0),
            "gas_decay_rate": ("decay_rate", 0.55),
            "gas_plume_stddev": ("plume_stddev", 1.2),
            "gas_wind_x": ("wind_x", 0.4),
            "gas_wind_y": ("wind_y", 0.0),
            "gas_noise_stddev": ("noise_stddev", 0.05),
            "gas_type": ("gas_type", "H2"),
            "gas_publish_rate_hz": ("publish_rate_hz", 5.0),
        }
        resolved_gf = {}
        for key, (gf_key, default) in gf_defaults.items():
            resolved_gf[key] = _resolve(key, gas_field.get(gf_key, default))

        # -- particle filter --------------------------------------------------
        resolved_pf_bounds = _resolve("particle_filter_bounds", "[-6.0, -6.0, 6.0, 6.0]")
        resolved_pf_source_strength = _resolve("particle_filter_source_strength", gas_field.get("source_strength", 120.0))
        resolved_pf_decay_rate = _resolve("particle_filter_decay_rate", gas_field.get("decay_rate", 0.55))
        resolved_pf_plume_sigma = _resolve("particle_filter_plume_sigma", gas_field.get("plume_stddev", 1.2))
        resolved_pf_wind_x = _resolve("particle_filter_wind_x", gas_field.get("wind_x", 0.4))
        resolved_pf_wind_y = _resolve("particle_filter_wind_y", gas_field.get("wind_y", 0.0))
        resolved_pf_gas_type = _resolve("particle_filter_gas_type", gas_field.get("gas_type", "H2"))

        # -- mission_manager --------------------------------------------------
        mm_initial = mission_mgr.get("initial_pose", {})
        resolved_mm = {
            "initial_pose_x": _resolve("initial_pose_x", mm_initial.get("x", "0.0")),
            "initial_pose_y": _resolve("initial_pose_y", mm_initial.get("y", "0.0")),
            "initial_pose_yaw": _resolve("initial_pose_yaw", mm_initial.get("yaw", "0.0")),
            "patrol_goal_timeout_sec": _resolve("patrol_goal_timeout_sec", mission_mgr.get("patrol_goal_timeout_sec", "45.0")),
            "enter_threshold": _resolve("enter_threshold", mission_mgr.get("enter_threshold", 2.0)),
            "exit_threshold": _resolve("exit_threshold", mission_mgr.get("exit_threshold", 1.0)),
            "source_threshold": _resolve("source_threshold", mission_mgr.get("source_threshold", 10.0)),
            "confirm_samples": _resolve("confirm_samples", mission_mgr.get("confirm_samples", 3)),
            "track_exit_samples": _resolve("track_exit_samples", mission_mgr.get("track_exit_samples", 3)),
            "source_radius": _resolve("source_radius", mission_mgr.get("source_radius", 1.0)),
            "source_hold_steps": _resolve("source_hold_steps", mission_mgr.get("source_hold_steps", 5)),
            "track_timeout_sec": _resolve("track_timeout_sec", mission_mgr.get("track_timeout_sec", 60.0)),
            "adaptive_source_ratio": _resolve("adaptive_source_ratio", mission_mgr.get("adaptive_source_ratio", 0.0)),
            "track_step": _resolve("track_step", mission_mgr.get("track_step", 0.7)),
            "surge_step": _resolve("surge_step", mission_mgr.get("surge_step", 0.5)),
            "cast_step": _resolve("cast_step", mission_mgr.get("cast_step", 0.3)),
            "sweep_angle_deg": _resolve("sweep_angle_deg", mission_mgr.get("sweep_angle_deg", 30.0)),
        }

        # patrol_points: scene.yaml [[x,y],...] → flat "[x, y, x, y, ...]"
        raw_patrol = lc["patrol_points"].perform(context).strip()
        if raw_patrol:
            resolved_mm["patrol_points"] = raw_patrol
        else:
            pp = mission_mgr.get("patrol_points", [])
            if pp:
                flat = [str(v) for point in pp for v in point]
                resolved_mm["patrol_points"] = "[" + ", ".join(flat) + "]"
            else:
                resolved_mm["patrol_points"] = ""

        # -- gas_source -------------------------------------------------------
        resolved_source_x = _resolve("source_x", gas_source.get("x", -3.5))
        resolved_source_y = _resolve("source_y", gas_source.get("y", -3.5))

        # -- gaden (only when enabled) ----------------------------------------
        resolved_gaden = {}
        if use_gaden_enabled:
            if not gaden:
                raise RuntimeError(f"Scene '{scene_name}' is missing a gaden configuration block")
            scene_gaden_path = str(gaden.get("project_path", "")).strip()
            if not scene_gaden_path:
                raise RuntimeError(f"Scene '{scene_name}' GADEN config is missing project_path")
            # Resolve relative paths against GADEN_WS
            gaden_ws = os.environ.get("GADEN_WS", "/home/user/gaden_ws")
            if not os.path.isabs(scene_gaden_path):
                scene_gaden_path = str(Path(gaden_ws) / scene_gaden_path)
            gp = _resolve("gaden_project_path", scene_gaden_path)
            if not Path(gp).exists():
                raise RuntimeError(f"Scene '{scene_name}' GADEN project_path does not exist: {gp}")
            gaden_defaults = {
                "gaden_project_path": ("project_path", gp),
                "gaden_playback_id": ("playback_id", "scene1"),
                "gaden_player_freq": ("player_freq", 1.0),
                "gaden_sensor_topic": ("sensor_topic", "/gaden/sensor_reading"),
                "gaden_sensor_frame": ("sensor_frame", "gas_sensor_link"),
                "gaden_fixed_frame": ("fixed_frame", "gaden_map"),
                "gaden_map_offset_x": ("map_offset_x", 0.0),
                "gaden_map_offset_y": ("map_offset_y", 0.0),
                "gaden_map_offset_z": ("map_offset_z", 0.0),
                "gaden_map_roll": ("map_roll", 0.0),
                "gaden_map_pitch": ("map_pitch", 0.0),
                "gaden_map_yaw": ("map_yaw", 0.0),
            }
            for key, (g_key, default) in gaden_defaults.items():
                if key == "gaden_project_path":
                    resolved_gaden[key] = gp
                else:
                    resolved_gaden[key] = _resolve(key, gaden.get(g_key, default))

        # -- build SetLaunchConfiguration list --------------------------------
        actions = [
            SetLaunchConfiguration("world", resolved_world),
            SetLaunchConfiguration("gazebo_model_path", resolved_model_path),
            SetLaunchConfiguration("nav2_params_file", resolved_nav2_params),
            SetLaunchConfiguration("nav2_autostart", str(resolved_nav2_autostart).lower()),
            SetLaunchConfiguration("use_slam", str(use_slam_enabled).lower()),
            SetLaunchConfiguration("localizer_node", resolved_localizer),
            SetLaunchConfiguration("publish_initial_pose", str(resolved_publish_initial).lower()),
            SetLaunchConfiguration("use_gaden", str(use_gaden_enabled).lower()),
            SetLaunchConfiguration("particle_filter_bounds", resolved_pf_bounds),
            SetLaunchConfiguration("particle_filter_source_strength", resolved_pf_source_strength),
            SetLaunchConfiguration("particle_filter_decay_rate", resolved_pf_decay_rate),
            SetLaunchConfiguration("particle_filter_plume_sigma", resolved_pf_plume_sigma),
            SetLaunchConfiguration("particle_filter_wind_x", resolved_pf_wind_x),
            SetLaunchConfiguration("particle_filter_wind_y", resolved_pf_wind_y),
            SetLaunchConfiguration("particle_filter_gas_type", resolved_pf_gas_type),
        ]
        for key, val in {**resolved_gf, **resolved_mm, **resolved_gaden}.items():
            actions.append(SetLaunchConfiguration(key, val))
        actions.append(SetLaunchConfiguration("source_x", resolved_source_x))
        actions.append(SetLaunchConfiguration("source_y", resolved_source_y))
        return actions

    scene_defaults = OpaqueFunction(function=_scene_defaults)
    set_fastdds_udp = SetEnvironmentVariable("FASTDDS_BUILTIN_TRANSPORTS", "UDPv4")

    # -- Subsystem includes --------------------------------------------------
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "sim.launch.py")),
        launch_arguments={
            "scene": lc["scene"],
            "world": lc["world"],
            "gazebo_model_path": lc["gazebo_model_path"],
            "use_sim_time": lc["use_sim_time"],
            "headless": lc["headless"],
            "spawn_x": lc["initial_pose_x"],
            "spawn_y": lc["initial_pose_y"],
            "spawn_yaw": lc["initial_pose_yaw"],
        }.items(),
    )

    nav2_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "nav2.launch.py")),
        launch_arguments={
            "scene": lc["scene"],
            "use_sim_time": lc["use_sim_time"],
            "params_file": lc["nav2_params_file"],
            "map": lc["nav2_map_file"],
            "autostart": lc["nav2_autostart"],
            "use_slam": lc["use_slam"],
        }.items(),
    )
    nav2 = TimerAction(period=lc["nav2_launch_delay"], actions=[nav2_include])

    gas_simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "gas_simulation.launch.py")),
        launch_arguments={
            "use_sim_time": lc["use_sim_time"],
            "use_gaden": lc["use_gaden"],
            "source_x": lc["source_x"],
            "source_y": lc["source_y"],
            "gas_source_strength": lc["gas_source_strength"],
            "gas_decay_rate": lc["gas_decay_rate"],
            "gas_plume_stddev": lc["gas_plume_stddev"],
            "gas_wind_x": lc["gas_wind_x"],
            "gas_wind_y": lc["gas_wind_y"],
            "gas_noise_stddev": lc["gas_noise_stddev"],
            "gas_type": lc["gas_type"],
            "gas_publish_rate_hz": lc["gas_publish_rate_hz"],
            "gaden_project_path": lc["gaden_project_path"],
            "gaden_playback_id": lc["gaden_playback_id"],
            "gaden_player_freq": lc["gaden_player_freq"],
            "gaden_sensor_topic": lc["gaden_sensor_topic"],
            "gaden_sensor_frame": lc["gaden_sensor_frame"],
            "gaden_fixed_frame": lc["gaden_fixed_frame"],
            "gaden_map_offset_x": lc["gaden_map_offset_x"],
            "gaden_map_offset_y": lc["gaden_map_offset_y"],
            "gaden_map_offset_z": lc["gaden_map_offset_z"],
            "gaden_map_roll": lc["gaden_map_roll"],
            "gaden_map_pitch": lc["gaden_map_pitch"],
            "gaden_map_yaw": lc["gaden_map_yaw"],
            "gaden_sensor_gate_timeout": lc["gaden_sensor_gate_timeout"],
            "gaden_sensor_gate_poll_period": lc["gaden_sensor_gate_poll_period"],
            "gaden_sensor_gate_stable_ready_count": lc["gaden_sensor_gate_stable_ready_count"],
            "use_slam": lc["use_slam"],
            # Sim2real: realistic sensor model
            "use_realistic_sensor": lc["use_realistic_sensor"],
            "sensor_response_tau": lc["sensor_response_tau"],
            "sensor_recovery_tau": lc["sensor_recovery_tau"],
            "sensor_noise_stddev": lc["sensor_noise_stddev"],
            "sensor_quantization": lc["sensor_quantization"],
            "sensor_saturation": lc["sensor_saturation"],
            "sensor_baseline_drift_rate": lc["sensor_baseline_drift_rate"],
            "sensor_baseline_drift_max": lc["sensor_baseline_drift_max"],
            # Sim2real: time-varying wind
            "use_time_varying_wind": lc["use_time_varying_wind"],
            "wind_mean_speed": lc["wind_mean_speed"],
            "wind_mean_direction_deg": lc["wind_mean_direction_deg"],
            "wind_direction_stddev_deg": lc["wind_direction_stddev_deg"],
            "wind_gust_rate": lc["wind_gust_rate"],
            "wind_gust_strength_factor": lc["wind_gust_strength_factor"],
            "wind_gust_duration": lc["wind_gust_duration"],
            # Anemometer ground-truth wind (GADEN only, opt-in)
            "use_anemometer_ground_truth": lc["use_anemometer_ground_truth"],
            "anemometer_noise_std": lc["anemometer_noise_std"],
            "anemometer_frequency": lc["anemometer_frequency"],
            "anemometer_smoothing_alpha": lc["anemometer_smoothing_alpha"],
            "anemometer_max_wind_speed": lc["anemometer_max_wind_speed"],
        }.items(),
    )

    tracking = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "tracking.launch.py")),
        launch_arguments={
            "use_sim_time": lc["use_sim_time"],
            "initial_pose_x": lc["initial_pose_x"],
            "initial_pose_y": lc["initial_pose_y"],
            "initial_pose_yaw": lc["initial_pose_yaw"],
            "patrol_goal_timeout_sec": lc["patrol_goal_timeout_sec"],
            "patrol_points": lc["patrol_points"],
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
            "gas_wind_x": lc["gas_wind_x"],
            "gas_wind_y": lc["gas_wind_y"],
            "gas_source_strength": lc["gas_source_strength"],
            "localizer_node": lc["localizer_node"],
            "use_slam": lc["use_slam"],
            "publish_initial_pose": lc["publish_initial_pose"],
            "nav2_launch_delay": lc["nav2_launch_delay"],
            "mission_manager_delay": lc["mission_manager_delay"],
            "nav2_autostart": lc["nav2_autostart"],
            "nav2_startup_gate_timeout": lc["nav2_startup_gate_timeout"],
            "nav2_startup_gate_poll_period": lc["nav2_startup_gate_poll_period"],
            "nav2_startup_gate_stable_ready_count": lc["nav2_startup_gate_stable_ready_count"],
            "use_particle_filter": lc["use_particle_filter"],
            "particle_filter_num_particles": lc["particle_filter_num_particles"],
            "particle_filter_motion_sigma": lc["particle_filter_motion_sigma"],
            "particle_filter_observation_sigma": lc["particle_filter_observation_sigma"],
            "particle_filter_plume_sigma": lc["particle_filter_plume_sigma"],
            "particle_filter_source_strength": lc["particle_filter_source_strength"],
            "particle_filter_decay_rate": lc["particle_filter_decay_rate"],
            "particle_filter_plume_sigma": lc["particle_filter_plume_sigma"],
            "particle_filter_wind_x": lc["particle_filter_wind_x"],
            "particle_filter_wind_y": lc["particle_filter_wind_y"],
            "particle_filter_bounds": lc["particle_filter_bounds"],
            "particle_filter_publish_rate": lc["particle_filter_publish_rate"],
            "particle_filter_resample_threshold": lc["particle_filter_resample_threshold"],
            "gas_type": lc["particle_filter_gas_type"],
        }.items(),
    )

    visualization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, "launch", "visualization.launch.py")),
        launch_arguments={
            "use_sim_time": lc["use_sim_time"],
            "use_rviz": lc["use_rviz"],
        }.items(),
    )

    return LaunchDescription(declares + [
        set_fastdds_udp,
        scene_defaults,
        sim,
        nav2,
        gas_simulation,
        tracking,
        visualization,
    ])
