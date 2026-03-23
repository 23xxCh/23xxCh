from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re


def _launch_text(name: str) -> str:
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    return launch_path.read_text(encoding="utf-8")


def _load_launch_module(name: str):
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    spec = spec_from_file_location(name.replace('.', '_'), launch_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _default_value(text: str, argument_name: str) -> str:
    pattern = rf'DeclareLaunchArgument\("{argument_name}", default_value="([^"]+)"\)'
    match = re.search(pattern, text)
    assert match is not None, argument_name
    return match.group(1)


def test_bringup_launch_exposes_mission_manager_delay_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("mission_manager_delay"' in text
    assert 'period=mission_manager_delay' in text


def test_bringup_declares_scene_launch_argument():
    text = _launch_text("bringup.launch.py")
    assert "scene" in text


def test_bringup_launch_module_imports_without_launch_pythonpath_side_effects():
    module = _load_launch_module("bringup.launch.py")
    assert hasattr(module, 'generate_launch_description')


def test_bringup_launch_exposes_sensor_gate_timeout_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_sensor_gate_timeout"' in text


def test_bringup_launch_defers_test_env_lookup_until_gaden_is_enabled():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_project_path", default_value="")' in text or "DeclareLaunchArgument('gaden_project_path', default_value='')" in text
    assert 'use_gaden.perform(context)' in text or 'LaunchConfiguration("use_gaden").perform(context)' in text

def test_bringup_launch_reads_scene_specific_gaden_block():
    text = _launch_text("bringup.launch.py")
    assert 'scene_profile.get("gaden"' in text or "scene_profile.get('gaden'" in text
    assert 'gaden_project_path' in text
    assert 'gaden_playback_id' in text
    assert 'gaden_sensor_topic' in text
    assert 'gaden_player_freq' in text


def test_bringup_launch_routes_scene_specific_gaden_player_frequency():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_player_freq"' in text or "DeclareLaunchArgument('gaden_player_freq'" in text
    assert 'str(gaden.get("player_freq"' in text or "str(gaden.get('player_freq'" in text
    assert '"player_freq": gaden_player_freq' in text or "'player_freq': gaden_player_freq" in text


def test_bringup_launch_fails_fast_if_scene_gaden_config_is_missing():
    text = _launch_text("bringup.launch.py")
    assert 'raise RuntimeError' in text
    assert 'project_path' in text


def test_bringup_launch_exposes_sensor_gate_stable_ready_count_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_sensor_gate_stable_ready_count"' in text
    assert '"stable_ready_count": gaden_sensor_gate_stable_ready_count' in text




def test_bringup_launch_routes_scene_specific_gas_field_parameters():
    text = _launch_text("bringup.launch.py")
    assert 'scene_profile.get("gas_field"' in text or "scene_profile.get('gas_field'" in text
    assert 'SetLaunchConfiguration("gas_source_strength"' in text or "SetLaunchConfiguration('gas_source_strength'" in text
    assert 'SetLaunchConfiguration("gas_decay_rate"' in text or "SetLaunchConfiguration('gas_decay_rate'" in text
    assert 'SetLaunchConfiguration("gas_plume_stddev"' in text or "SetLaunchConfiguration('gas_plume_stddev'" in text
    assert 'SetLaunchConfiguration("gas_wind_x"' in text or "SetLaunchConfiguration('gas_wind_x'" in text
    assert 'SetLaunchConfiguration("gas_wind_y"' in text or "SetLaunchConfiguration('gas_wind_y'" in text

def test_bringup_launch_forwards_initial_pose_to_sim_spawn():
    text = _launch_text("bringup.launch.py")
    assert '"spawn_x": initial_pose_x' in text
    assert '"spawn_y": initial_pose_y' in text
    assert '"spawn_yaw": initial_pose_yaw' in text


def test_bringup_launch_uses_tf_gate_node_instead_of_direct_sensor_delay():
    text = _launch_text("bringup.launch.py")
    assert 'executable="gaden_sensor_gate_node"' in text
    assert 'DeclareLaunchArgument("gaden_sensor_delay"' not in text


def test_sensor_gate_timeout_default_is_longer_than_mission_manager_delay():
    text = _launch_text("bringup.launch.py")
    mission_delay = float(_default_value(text, "mission_manager_delay"))
    gate_timeout = float(_default_value(text, "gaden_sensor_gate_timeout"))
    assert gate_timeout > mission_delay


def test_bringup_launch_exposes_nav2_params_file_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("nav2_params_file"' in text
    assert '"params_file": nav2_params_file' in text


def test_bringup_launch_routes_scene_specific_nav2_params_file():
    text = _launch_text("bringup.launch.py")
    assert 'resolve_scene_nav2_params' in text
    assert 'SetLaunchConfiguration("nav2_params_file"' in text or "SetLaunchConfiguration('nav2_params_file'" in text


def test_bringup_launch_forwards_scene_to_sim_launch():
    text = _launch_text("bringup.launch.py")
    assert '"scene": scene' in text


def test_bringup_launch_forwards_world_and_model_path_to_sim_launch():
    text = _launch_text("bringup.launch.py")
    assert '"world": world' in text
    assert '"gazebo_model_path": gazebo_model_path' in text


def test_bringup_launch_forwards_scene_to_nav2_launch():
    text = _launch_text("bringup.launch.py")
    assert '"scene": scene' in text


def test_bringup_launch_forces_patrol_points_parameter_to_string():
    text = _launch_text("bringup.launch.py")
    assert 'ParameterValue(patrol_points, value_type=str)' in text


def test_bringup_launch_exposes_nav2_autostart_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("nav2_autostart"' in text
    assert '"autostart": nav2_autostart' in text


def test_bringup_launch_exposes_nav2_startup_retry_limit_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("nav2_startup_gate_retry_limit"' in text
    assert '"startup_retry_limit": nav2_startup_gate_retry_limit' in text


def test_bringup_launch_exposes_track_exit_samples_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("track_exit_samples"' in text
    assert '"track_exit_samples": track_exit_samples' in text


def test_bringup_launch_uses_nav2_startup_gate_node_when_autostart_is_disabled():
    text = _launch_text("bringup.launch.py")
    assert 'executable="nav2_startup_gate_node"' in text
    assert 'UnlessCondition(nav2_autostart)' in text
    assert '"lifecycle_manager_service": "/lifecycle_manager_navigation/manage_nodes"' in text


def test_bringup_launch_starts_mission_manager_after_successful_nav2_gate_exit():
    text = _launch_text("bringup.launch.py")
    assert 'RegisterEventHandler(' in text
    assert 'OnProcessExit(' in text
    assert 'target_action=nav2_startup_gate' in text
    assert 'event.returncode == 0' in text
    assert 'Shutdown(reason="Nav2 startup gate failed")' in text


def test_sim_launch_exposes_spawn_pose_arguments():
    text = _launch_text("sim.launch.py")
    assert 'DeclareLaunchArgument("spawn_x"' in text
    assert 'DeclareLaunchArgument("spawn_y"' in text
    assert 'DeclareLaunchArgument("spawn_z"' in text
    assert 'DeclareLaunchArgument("spawn_yaw"' in text


def test_sim_launch_uses_world_launch_argument():
    text = _launch_text("sim.launch.py")
    assert 'DeclareLaunchArgument("world"' in text
    assert 'LaunchConfiguration("world")' in text


def test_nav2_launch_resolves_runtime_map_from_selected_scene():
    text = _launch_text("nav2.launch.py")
    assert 'DeclareLaunchArgument("scene"' in text or "DeclareLaunchArgument('scene'" in text
    assert 'resolve_scene_map' in text
    assert 'scene.perform(context)' in text or 'LaunchConfiguration("scene").perform(context)' in text or "LaunchConfiguration('scene').perform(context)" in text


def test_nav2_launch_rewrites_runtime_params_for_selected_scene_initial_pose():
    text = _launch_text("nav2.launch.py")
    assert 'initial_pose.x' in text
    assert 'initial_pose.y' in text
    assert 'initial_pose.yaw' in text
    assert 'runtime_params_path' in text


def test_sim_launch_sets_gazebo_model_path_for_scene_assets():
    text = _launch_text("sim.launch.py")
    assert 'DeclareLaunchArgument("gazebo_model_path"' in text
    assert 'SetEnvironmentVariable(' in text
    assert '"GAZEBO_MODEL_PATH"' in text


def test_sim_launch_uses_launch_configurations_for_spawn_pose():
    text = _launch_text("sim.launch.py")
    assert '"-x",\n                    spawn_x,' in text
    assert '"-y",\n                    spawn_y,' in text
    assert '"-z",\n                    spawn_z,' in text
    assert '"-Y",\n                    spawn_yaw,' in text


def test_sim_launch_shuts_down_if_gazebo_exits():
    text = _launch_text("sim.launch.py")
    assert "RegisterEventHandler(" in text
    assert "OnProcessExit(" in text
    assert "target_action=gazebo_gui" in text
    assert "target_action=gazebo_headless" in text
    assert 'Shutdown(reason="Gazebo process exited")' in text


def test_autonomy_launch_exists_and_imports():
    module = _load_launch_module("autonomy.launch.py")
    assert hasattr(module, 'generate_launch_description')


def test_autonomy_launch_generate_launch_description_constructs_without_name_errors():
    module = _load_launch_module("autonomy.launch.py")
    module.get_package_share_directory = lambda package_name: str(Path(__file__).resolve().parents[1])
    launch_description = module.generate_launch_description()
    assert launch_description is not None


def test_autonomy_launch_includes_slam_navigation_and_exploration_manager():
    text = _launch_text("autonomy.launch.py")
    assert 'slam_nav2.launch.py' in text
    assert 'exploration_manager_node' in text
    assert '"scene": scene' in text or "'scene': scene" in text


def test_autonomy_launch_includes_mapping_mission_manager_for_gas_detection():
    text = _launch_text("autonomy.launch.py")
    assert 'mapping_mission_manager_node' in text
    assert '"enter_threshold": enter_threshold' in text or "'enter_threshold': enter_threshold" in text
    assert '"exit_threshold": exit_threshold' in text or "'exit_threshold': exit_threshold" in text
    assert '"confirm_samples": confirm_samples' in text or "'confirm_samples': confirm_samples" in text


def test_autonomy_launch_includes_transition_manager_for_map_freeze():
    text = _launch_text("autonomy.launch.py")
    assert 'transition_manager_node' in text
    assert '"scene_name": scene' in text or "'scene_name': scene" in text


def test_autonomy_launch_disables_nav2_autostart_until_gate_releases_it():
    text = _launch_text("autonomy.launch.py")
    assert '"autostart": "false"' in text or "'autostart': 'false'" in text
    assert '"map_saver_autostart": "true"' in text or "'map_saver_autostart': 'true'" in text
    assert 'nav2_startup_gate_node' in text
    assert '"/lifecycle_manager_navigation/manage_nodes"' in text or "'/lifecycle_manager_navigation/manage_nodes'" in text


def test_autonomy_launch_routes_scene_gas_source_into_gas_field_node():
    text = _launch_text("autonomy.launch.py")
    assert 'SetLaunchConfiguration(\'source_x\'' in text or 'SetLaunchConfiguration("source_x"' in text
    assert 'SetLaunchConfiguration(\'source_y\'' in text or 'SetLaunchConfiguration("source_y"' in text
    assert "'source_x': source_x" in text or '"source_x": source_x' in text
    assert "'source_y': source_y" in text or '"source_y": source_y' in text
    assert "'source_x': '-4.0'" not in text
    assert '"source_x": "-4.0"' not in text


def test_autonomy_launch_sets_gas_field_pose_source_to_auto():
    text = _launch_text("autonomy.launch.py")
    assert "'pose_source': 'auto'" in text or '"pose_source": "auto"' in text


def test_autonomy_launch_honors_explicit_source_override_before_scene_default():
    text = _launch_text("autonomy.launch.py")
    assert "source_x.perform(context).strip() or str(gas_source.get('x'" in text or 'source_x.perform(context).strip() or str(gas_source.get("x"' in text
    assert "source_y.perform(context).strip() or str(gas_source.get('y'" in text or 'source_y.perform(context).strip() or str(gas_source.get("y"' in text


def test_autonomy_launch_honors_explicit_gas_confirm_threshold_overrides():
    text = _launch_text("autonomy.launch.py")
    assert "autonomy.get('mapping_detection'" in text or 'autonomy.get("mapping_detection"' in text
    assert "enter_threshold.perform(context).strip() or str(" in text
    assert "exit_threshold.perform(context).strip() or str(" in text
    assert "confirm_samples.perform(context).strip() or str(" in text


def test_autonomy_launch_routes_min_explore_samples_to_mapping_mission_manager():
    text = _launch_text("autonomy.launch.py")
    assert "DeclareLaunchArgument('min_explore_samples'" in text or 'DeclareLaunchArgument("min_explore_samples"' in text
    assert "mapping_detection.get('min_explore_samples'" in text or 'mapping_detection.get("min_explore_samples"' in text
    assert "'min_explore_samples': min_explore_samples" in text or '"min_explore_samples": min_explore_samples' in text


def test_autonomy_launch_declares_tracking_handoff_overrides_once():
    text = _launch_text("autonomy.launch.py")
    assert text.count("LaunchConfiguration('tracking_source_x')") == 2
    assert text.count("LaunchConfiguration('tracking_source_y')") == 2
    assert text.count("LaunchConfiguration('tracking_enter_threshold')") == 2
    assert text.count("LaunchConfiguration('tracking_exit_threshold')") == 2
    assert text.count("LaunchConfiguration('tracking_source_threshold')") == 2
    assert text.count("LaunchConfiguration('tracking_confirm_samples')") == 2
    assert text.count("LaunchConfiguration('tracking_track_exit_samples')") == 2
    assert text.count("LaunchConfiguration('tracking_source_radius')") == 2
    assert text.count("LaunchConfiguration('tracking_source_hold_steps')") == 2


def test_autonomy_launch_applies_tracking_handoff_defaults_from_scene():
    text = _launch_text("autonomy.launch.py")
    assert "autonomy.get('tracking_handoff'" in text or 'autonomy.get("tracking_handoff"' in text
    assert "SetLaunchConfiguration(\n            'tracking_source_x'" in text
    assert "SetLaunchConfiguration(\n            'tracking_source_y'" in text
    assert "SetLaunchConfiguration(\n            'tracking_enter_threshold'" in text
    assert "SetLaunchConfiguration(\n            'tracking_exit_threshold'" in text
    assert "SetLaunchConfiguration(\n            'tracking_source_threshold'" in text
    assert "SetLaunchConfiguration(\n            'tracking_track_exit_samples'" in text


def test_autonomy_launch_declares_startup_gate_timeout_overrides():
    text = _launch_text("autonomy.launch.py")
    assert "DeclareLaunchArgument('nav2_startup_gate_timeout'" in text or 'DeclareLaunchArgument("nav2_startup_gate_timeout"' in text
    assert "DeclareLaunchArgument('gaden_sensor_gate_timeout'" in text or 'DeclareLaunchArgument("gaden_sensor_gate_timeout"' in text


def test_autonomy_launch_applies_startup_gate_timeout_defaults_from_scene():
    text = _launch_text("autonomy.launch.py")
    assert "autonomy.get('startup_gates'" in text or 'autonomy.get("startup_gates"' in text
    assert "SetLaunchConfiguration(\n            'nav2_startup_gate_timeout'" in text
    assert "SetLaunchConfiguration(\n            'gaden_sensor_gate_timeout'" in text
    assert "'timeout_sec': nav2_startup_gate_timeout" in text or '"timeout_sec": nav2_startup_gate_timeout' in text
    assert "'timeout_sec': gaden_sensor_gate_timeout" in text or '"timeout_sec": gaden_sensor_gate_timeout' in text


def test_slam_nav2_launch_exists_and_enables_slam_mode():
    text = _launch_text("slam_nav2.launch.py")
    assert "online_async_launch.py" in text
    assert "navigation_launch.py" in text
    assert 'resolve_scene_slam_nav2_params' in text


def test_slam_nav2_launch_separates_map_saver_autostart_from_navigation_autostart():
    text = _launch_text("slam_nav2.launch.py")
    assert 'DeclareLaunchArgument(\'map_saver_autostart\'' in text or 'DeclareLaunchArgument("map_saver_autostart"' in text
    assert "'autostart': map_saver_autostart" in text or '"autostart": map_saver_autostart' in text


def test_tracking_localization_launch_exists_and_uses_localization_bringup():
    text = _launch_text("tracking_localization.launch.py")
    assert "localization_launch.py" in text
    assert "mission_manager_node" in text
    assert '"start_in_tracking_mode": True' in text or "'start_in_tracking_mode': True" in text
    assert '"tracking_only_mode": True' in text or "'tracking_only_mode': True" in text
    assert 'runtime_map' in text


def test_tracking_localization_launch_also_starts_navigation_bringup():
    text = _launch_text("tracking_localization.launch.py")
    assert "navigation_launch.py" in text
    assert '"autostart": "true"' in text or "'autostart': 'true'" in text


def test_tracking_localization_launch_honors_explicit_source_override_before_scene_default():
    text = _launch_text("tracking_localization.launch.py")
    assert 'LaunchConfiguration("source_x").perform(context).strip()' in text
    assert 'LaunchConfiguration("source_y").perform(context).strip()' in text
    assert 'resolved_source_x' in text
    assert 'resolved_source_y' in text
    assert 'SetLaunchConfiguration("source_x", resolved_source_x)' in text
    assert 'SetLaunchConfiguration("source_y", resolved_source_y)' in text


def test_tracking_localization_launch_routes_track_exit_samples():
    text = _launch_text("tracking_localization.launch.py")
    assert 'DeclareLaunchArgument("track_exit_samples"' in text
    assert '"track_exit_samples": track_exit_samples' in text
