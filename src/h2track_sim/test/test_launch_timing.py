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


def _param_in_schema(text: str, param_name: str) -> bool:
    """Check if param_name is declared in the _PARAMS schema."""
    return f'("{param_name}",' in text or f"('{param_name}'," in text


def _default_value_from_schema(text: str, param_name: str) -> str:
    """Extract default value from _PARAMS schema entry."""
    pattern = rf'\("{param_name}",\s*"([^"]*)"\)'
    match = re.search(pattern, text)
    assert match is not None, f"{param_name} not found in _PARAMS"
    return match.group(1)


# ---------------------------------------------------------------------------
# Module-level tests
# ---------------------------------------------------------------------------

def test_bringup_launch_module_imports_without_launch_pythonpath_side_effects():
    module = _load_launch_module("bringup.launch.py")
    assert hasattr(module, 'generate_launch_description')


def test_bringup_declares_scene_launch_argument():
    text = _launch_text("bringup.launch.py")
    assert "scene" in text


# ---------------------------------------------------------------------------
# Schema parameter existence tests
# ---------------------------------------------------------------------------

def test_bringup_launch_exposes_mission_manager_delay_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "mission_manager_delay")


def test_bringup_launch_exposes_sensor_gate_timeout_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "gaden_sensor_gate_timeout")


def test_bringup_launch_exposes_sensor_gate_stable_ready_count_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "gaden_sensor_gate_stable_ready_count")


def test_bringup_launch_exposes_nav2_params_file_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "nav2_params_file")


def test_bringup_launch_exposes_nav2_map_override_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "nav2_map_file")


def test_bringup_launch_exposes_use_slam_argument_and_forwards_to_nav2():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "use_slam")


def test_bringup_launch_exposes_track_exit_samples_argument_and_routes_to_mission_manager():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "track_exit_samples")


def test_bringup_launch_exposes_patrol_goal_timeout_and_routes_to_mission_manager():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "patrol_goal_timeout_sec")


def test_bringup_launch_exposes_nav2_autostart_argument():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "nav2_autostart")


# ---------------------------------------------------------------------------
# Default value tests
# ---------------------------------------------------------------------------

def test_sensor_gate_timeout_default_is_longer_than_mission_manager_delay():
    text = _launch_text("bringup.launch.py")
    mission_delay = float(_default_value_from_schema(text, "mission_manager_delay"))
    gate_timeout = float(_default_value_from_schema(text, "gaden_sensor_gate_timeout"))
    assert gate_timeout > mission_delay


# ---------------------------------------------------------------------------
# Scene resolution tests
# ---------------------------------------------------------------------------

def test_bringup_launch_defers_test_env_lookup_until_gaden_is_enabled():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "gaden_project_path")
    assert 'use_gaden_enabled' in text


def test_bringup_launch_reads_scene_specific_gaden_block():
    text = _launch_text("bringup.launch.py")
    assert 'scene_profile.get("gaden"' in text or "scene_profile.get('gaden'" in text
    assert 'gaden_project_path' in text
    assert 'gaden_playback_id' in text
    assert 'gaden_sensor_topic' in text
    assert 'gaden_player_freq' in text


def test_bringup_launch_routes_scene_specific_gaden_player_frequency():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "gaden_player_freq")
    assert '"playback_id"' in text


def test_bringup_launch_fails_fast_if_scene_gaden_config_is_missing():
    text = _launch_text("bringup.launch.py")
    assert 'raise RuntimeError' in text
    assert 'project_path' in text


def test_bringup_launch_routes_scene_specific_gas_field_parameters():
    text = _launch_text("bringup.launch.py")
    assert 'scene_profile.get("gas_field"' in text or "scene_profile.get('gas_field'" in text
    # Data-driven: gas field params are in gf_defaults dict
    assert '"source_strength"' in text
    assert '"decay_rate"' in text


def test_bringup_launch_routes_scene_specific_nav2_params_file():
    text = _launch_text("bringup.launch.py")
    assert 'resolve_scene_nav2_params' in text
    assert 'SetLaunchConfiguration("nav2_params_file"' in text or "SetLaunchConfiguration('nav2_params_file'" in text


def test_bringup_launch_routes_scene_specific_nav2_autostart_default():
    text = _launch_text("bringup.launch.py")
    assert 'scene_profile.get("nav2_autostart"' in text or "scene_profile.get('nav2_autostart'" in text
    assert 'SetLaunchConfiguration("nav2_autostart"' in text or "SetLaunchConfiguration('nav2_autostart'" in text


# ---------------------------------------------------------------------------
# Forwarding tests
# ---------------------------------------------------------------------------

def test_bringup_launch_forwards_initial_pose_to_sim_spawn():
    text = _launch_text("bringup.launch.py")
    assert '"spawn_x":' in text
    assert '"spawn_y":' in text
    assert '"spawn_yaw":' in text


def test_bringup_launch_forwards_scene_to_sim_launch():
    text = _launch_text("bringup.launch.py")
    assert '"scene":' in text


def test_bringup_launch_forwards_world_and_model_path_to_sim_launch():
    text = _launch_text("bringup.launch.py")
    assert '"world":' in text
    assert '"gazebo_model_path":' in text


def test_bringup_launch_forwards_scene_to_nav2_launch():
    text = _launch_text("bringup.launch.py")
    assert '"scene":' in text


def test_bringup_launch_forces_patrol_points_parameter_to_string():
    text = _launch_text("bringup.launch.py")
    assert 'ParameterValue(lc["patrol_points"], value_type=str)' in text


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

def test_bringup_launch_uses_tf_gate_node_instead_of_direct_sensor_delay():
    text = _launch_text("bringup.launch.py")
    assert 'executable="gaden_sensor_gate_node"' in text
    assert 'DeclareLaunchArgument("gaden_sensor_delay"' not in text


def test_bringup_launch_delays_nav2_start_until_sim_is_up():
    text = _launch_text("bringup.launch.py")
    assert _param_in_schema(text, "nav2_launch_delay")
    assert "period=lc[\"nav2_launch_delay\"]" in text


def test_bringup_launch_uses_nav2_startup_gate_node_when_autostart_is_disabled():
    text = _launch_text("bringup.launch.py")
    assert 'executable="nav2_startup_gate_node"' in text
    assert 'UnlessCondition(lc["nav2_autostart"])' in text
    assert '"lifecycle_manager_service": "/lifecycle_manager_navigation/manage_nodes"' in text


def test_bringup_launch_starts_mission_manager_by_timer_in_both_autostart_modes():
    text = _launch_text("bringup.launch.py")
    assert "mission_manager = TimerAction(" in text
    # TimerAction should not have a condition (runs in both modes)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'mission_manager = TimerAction(' in line:
            block = '\n'.join(lines[i:i+5])
            assert 'condition=' not in block


def test_bringup_launch_forces_fastdds_udp_transport_for_stability():
    text = _launch_text("bringup.launch.py")
    assert "SetEnvironmentVariable(" in text
    assert '"FASTDDS_BUILTIN_TRANSPORTS"' in text
    assert '"UDPv4"' in text


# ---------------------------------------------------------------------------
# Data-driven schema tests
# ---------------------------------------------------------------------------

def test_bringup_launch_uses_data_driven_param_schema():
    """Verify the launch file uses a _PARAMS list for parameter declarations."""
    text = _launch_text("bringup.launch.py")
    assert "_PARAMS" in text
    assert "DeclareLaunchArgument(name, default_value=dflt)" in text or "DeclareLaunchArgument(name, default_value=default)" in text


def test_bringup_schema_contains_all_required_parameters():
    """Verify all required parameters are in the _PARAMS schema."""
    text = _launch_text("bringup.launch.py")
    required = [
        "scene", "use_sim_time", "use_rviz", "headless",
        "nav2_launch_delay", "mission_manager_delay",
        "initial_pose_x", "initial_pose_y", "initial_pose_yaw",
        "patrol_points", "enter_threshold", "exit_threshold", "source_threshold",
        "source_x", "source_y",
        "use_gaden", "use_slam", "nav2_autostart",
        "gas_type",
        "use_particle_filter",
    ]
    for param in required:
        assert _param_in_schema(text, param), f"{param} missing from _PARAMS"
