from pathlib import Path


def test_exploration_manager_waits_for_nav2_not_slam_lifecycle_service():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'localizer="slam_toolbox"' not in source
    assert 'bt_navigator' in source


def test_exploration_manager_subscribes_to_map_with_transient_local_qos():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'QoSDurabilityPolicy.TRANSIENT_LOCAL' in source
    assert 'QoSProfile' in source


def test_exploration_manager_honors_pause_signal_from_mapping_manager():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert '/exploration_enabled' in source
    assert 'cancelTask()' in source
