"""Tests for particle filter integration in bringup/tracking launch files."""

from pathlib import Path

import pytest


def _launch_text(name: str) -> str:
    """Read launch file content."""
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    return launch_path.read_text(encoding="utf-8")


def _param_in_schema(text: str, param_name: str) -> bool:
    """Check if param_name is declared in the _PARAMS schema."""
    return f'("{param_name}",' in text or f"('{param_name}'," in text


def _default_value_from_schema(text: str, param_name: str) -> str:
    """Extract default value from _PARAMS schema entry."""
    import re
    pattern = rf'\("{param_name}",\s*"([^"]*)"\)'
    match = re.search(pattern, text)
    assert match is not None, f"{param_name} not found in _PARAMS"
    return match.group(1)


# -- Parameter declaration tests (check robot.launch.py which owns _PARAMS) ---


def test_bringup_declares_use_particle_filter_argument():
    """Verify use_particle_filter launch argument is declared."""
    text = _launch_text("robot.launch.py")
    assert _param_in_schema(text, "use_particle_filter")
    assert _default_value_from_schema(text, "use_particle_filter") == "true"


def test_bringup_declares_particle_filter_num_particles_argument():
    """Verify particle_filter_num_particles launch argument is declared."""
    text = _launch_text("robot.launch.py")
    assert _param_in_schema(text, "particle_filter_num_particles")
    assert _default_value_from_schema(text, "particle_filter_num_particles") == "500"


def test_bringup_declares_particle_filter_motion_sigma_argument():
    """Verify particle_filter_motion_sigma launch argument is declared."""
    text = _launch_text("robot.launch.py")
    assert _param_in_schema(text, "particle_filter_motion_sigma")
    assert _default_value_from_schema(text, "particle_filter_motion_sigma") == "0.3"


def test_bringup_declares_particle_filter_observation_sigma_argument():
    """Verify particle_filter_observation_sigma launch argument is declared."""
    text = _launch_text("robot.launch.py")
    assert _param_in_schema(text, "particle_filter_observation_sigma")
    assert _default_value_from_schema(text, "particle_filter_observation_sigma") == "0.5"


def test_bringup_declares_particle_filter_plume_sigma_argument():
    """Verify particle_filter_plume_sigma launch argument is declared."""
    text = _launch_text("robot.launch.py")
    assert _param_in_schema(text, "particle_filter_plume_sigma")
    assert _default_value_from_schema(text, "particle_filter_plume_sigma") == "2.0"


# -- Node inclusion tests (check tracking.launch.py which owns the node) -------


def test_bringup_includes_particle_filter_node():
    """Verify ParticleFilterNode is included in tracking.launch.py."""
    text = _launch_text("tracking.launch.py")
    assert "particle_filter_node" in text
    assert 'executable="particle_filter_node"' in text or "executable='particle_filter_node'" in text
    assert "h2track_tracking" in text


def test_bringup_particle_filter_has_condition():
    """Verify particle filter node has IfCondition on use_particle_filter."""
    text = _launch_text("tracking.launch.py")
    assert 'IfCondition(lc["use_particle_filter"])' in text


def test_bringup_particle_filter_passes_parameters():
    """Verify particle filter node receives required parameters via lc[] dict."""
    text = _launch_text("tracking.launch.py")
    assert '"num_particles": lc["particle_filter_num_particles"]' in text
    assert '"motion_sigma": lc["particle_filter_motion_sigma"]' in text
    assert '"observation_sigma": lc["particle_filter_observation_sigma"]' in text
    assert '"plume_sigma": lc["particle_filter_plume_sigma"]' in text


def test_bringup_particle_filter_uses_sim_time():
    """Verify particle filter node uses simulation time."""
    text = _launch_text("tracking.launch.py")
    assert "particle_filter_node" in text
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
    text = _launch_text("tracking.launch.py")
    assert _param_in_schema(text, "use_particle_filter")
    assert "particle_filter," in text
