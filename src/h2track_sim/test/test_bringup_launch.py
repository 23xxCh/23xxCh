"""Tests for particle filter integration in bringup.launch.py."""

from pathlib import Path

import pytest


def _launch_text(name: str) -> str:
    """Read launch file content."""
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    return launch_path.read_text(encoding="utf-8")


def test_bringup_declares_use_particle_filter_argument():
    """Verify use_particle_filter launch argument is declared."""
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("use_particle_filter"' in text or "DeclareLaunchArgument('use_particle_filter'" in text
    assert 'default_value="true"' in text or "default_value='true'" in text


def test_bringup_declares_particle_filter_num_particles_argument():
    """Verify particle_filter_num_particles launch argument is declared."""
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("particle_filter_num_particles"' in text or "DeclareLaunchArgument('particle_filter_num_particles'" in text
    assert 'default_value="500"' in text or "default_value='500'" in text


def test_bringup_declares_particle_filter_motion_sigma_argument():
    """Verify particle_filter_motion_sigma launch argument is declared."""
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("particle_filter_motion_sigma"' in text or "DeclareLaunchArgument('particle_filter_motion_sigma'" in text
    assert 'default_value="0.3"' in text or "default_value='0.3'" in text


def test_bringup_declares_particle_filter_observation_sigma_argument():
    """Verify particle_filter_observation_sigma launch argument is declared."""
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("particle_filter_observation_sigma"' in text or "DeclareLaunchArgument('particle_filter_observation_sigma'" in text
    assert 'default_value="0.5"' in text or "default_value='0.5'" in text


def test_bringup_declares_particle_filter_plume_sigma_argument():
    """Verify particle_filter_plume_sigma launch argument is declared."""
    text = _launch_text("bringup.launch.py")
    assert 'DeclareLaunchArgument("particle_filter_plume_sigma"' in text or "DeclareLaunchArgument('particle_filter_plume_sigma'" in text
    assert 'default_value="2.0"' in text or "default_value='2.0'" in text


def test_bringup_includes_particle_filter_node():
    """Verify ParticleFilterNode is included in launch description."""
    text = _launch_text("bringup.launch.py")
    assert "particle_filter_node" in text
    assert 'executable="particle_filter_node"' in text or "executable='particle_filter_node'" in text
    assert "h2track_tracking" in text


def test_bringup_particle_filter_has_condition():
    """Verify particle filter node has IfCondition on use_particle_filter."""
    text = _launch_text("bringup.launch.py")
    assert "IfCondition(use_particle_filter)" in text


def test_bringup_particle_filter_passes_parameters():
    """Verify particle filter node receives required parameters."""
    text = _launch_text("bringup.launch.py")
    assert '"num_particles": particle_filter_num_particles' in text or "'num_particles': particle_filter_num_particles" in text
    assert '"motion_sigma": particle_filter_motion_sigma' in text or "'motion_sigma': particle_filter_motion_sigma" in text
    assert '"observation_sigma": particle_filter_observation_sigma' in text or "'observation_sigma': particle_filter_observation_sigma" in text
    assert '"plume_sigma": particle_filter_plume_sigma' in text or "'plume_sigma': particle_filter_plume_sigma" in text


def test_bringup_particle_filter_uses_sim_time():
    """Verify particle filter node uses simulation time."""
    text = _launch_text("bringup.launch.py")
    # Find the particle_filter node definition section
    assert "particle_filter_node" in text
    # Check for use_sim_time parameter in the node
    lines = text.split("\n")
    in_particle_filter_section = False
    found_use_sim_time = False
    for line in lines:
        if "particle_filter_node" in line and "executable" in line:
            in_particle_filter_section = True
        if in_particle_filter_section and "use_sim_time" in line:
            found_use_sim_time = True
            break
        if in_particle_filter_section and line.strip().startswith("rviz") or "Node(" in line and "particle_filter" not in line and in_particle_filter_section:
            break
    assert found_use_sim_time, "use_sim_time not found in particle_filter node definition"


def test_bringup_particle_filter_declared_in_launch_description():
    """Verify particle_filter node is added to LaunchDescription actions."""
    text = _launch_text("bringup.launch.py")
    # Check that declare_use_particle_filter is in the LaunchDescription
    assert "declare_use_particle_filter" in text
    assert "particle_filter," in text or "particle_filter" in text.split("return LaunchDescription")[1]
