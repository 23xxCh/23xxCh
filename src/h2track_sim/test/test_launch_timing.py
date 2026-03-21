from pathlib import Path
import re


def _launch_text(name: str) -> str:
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    return launch_path.read_text(encoding="utf-8")


def _default_value(text: str, argument_name: str) -> str:
    pattern = rf'DeclareLaunchArgument\("{argument_name}", default_value="([^"]+)"\)'
    match = re.search(pattern, text)
    assert match is not None, argument_name
    return match.group(1)


def test_bringup_launch_exposes_mission_manager_delay_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("mission_manager_delay"' in text
    assert 'period=mission_manager_delay' in text


def test_bringup_launch_exposes_sensor_gate_timeout_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_sensor_gate_timeout"' in text


def test_bringup_launch_exposes_sensor_gate_stable_ready_count_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("gaden_sensor_gate_stable_ready_count"' in text
    assert '"stable_ready_count": gaden_sensor_gate_stable_ready_count' in text


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


def test_bringup_launch_forces_patrol_points_parameter_to_string():
    text = _launch_text("bringup.launch.py")
    assert 'ParameterValue(patrol_points, value_type=str)' in text


def test_bringup_launch_exposes_nav2_autostart_argument():
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("nav2_autostart"' in text
    assert '"autostart": nav2_autostart' in text


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
