from pathlib import Path

import yaml


def _load_nav2_slam_params() -> dict:
    path = Path(__file__).resolve().parents[1] / "config" / "nav2_slam_baseline_params.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_slam_nav2_velocity_smoother_declares_required_timeout_and_deadband():
    params = _load_nav2_slam_params()
    smoother = params["velocity_smoother"]["ros__parameters"]
    assert "deadband_velocity" in smoother
    assert "velocity_timeout" in smoother


def test_slam_nav2_map_saver_server_enables_transient_local_map_subscription():
    params = _load_nav2_slam_params()
    map_saver = params["map_saver_server"]["ros__parameters"]
    assert map_saver["map_subscribe_transient_local"] is True
