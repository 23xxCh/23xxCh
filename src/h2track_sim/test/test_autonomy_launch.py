from pathlib import Path

import yaml


def _autonomy_launch_text() -> str:
    path = Path(__file__).resolve().parents[1] / "launch" / "autonomy.launch.py"
    return path.read_text(encoding="utf-8")


def _baseline_scene() -> dict:
    path = Path(__file__).resolve().parents[1] / "scenes" / "baseline" / "scene.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_baseline_autonomy_declares_tracking_source_seed_max_distance():
    scene = _baseline_scene()
    tracking_handoff = scene["autonomy"]["tracking_handoff"]
    assert float(tracking_handoff["source_seed_max_distance"]) >= 6.0


def test_baseline_autonomy_declares_tracking_handoff_track_step():
    scene = _baseline_scene()
    tracking_handoff = scene["autonomy"]["tracking_handoff"]
    assert float(tracking_handoff["track_step"]) >= 0.8


def test_autonomy_launch_routes_tracking_source_seed_max_distance_from_scene_defaults():
    text = _autonomy_launch_text()
    assert "tracking_source_seed_max_distance" in text
    assert "declare_tracking_source_seed_max_distance = DeclareLaunchArgument(" in text
    assert "SetLaunchConfiguration(" in text
    assert "'tracking_source_seed_max_distance'," in text
    assert "'tracking_source_seed_max_distance': tracking_source_seed_max_distance" in text


def test_autonomy_launch_routes_tracking_track_step_from_scene_defaults():
    text = _autonomy_launch_text()
    assert "tracking_track_step" in text
    assert "declare_tracking_track_step = DeclareLaunchArgument(" in text
    assert "'tracking_track_step'," in text
    assert "'tracking_track_step': tracking_track_step" in text
