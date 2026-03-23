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


def test_exploration_manager_declares_relaxed_frontier_fallback_parameters():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'no_frontier_relaxed_after_cycles' in source
    assert 'no_frontier_relaxed_cluster_size' in source
    assert 'no_frontier_relaxed_min_goal_distance' in source


def test_exploration_manager_attempts_relaxed_frontier_selection_after_patience_window():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'self._no_frontier_cycles' in source
    assert 'self._no_frontier_cycles >= relaxed_after_cycles' in source
    assert 'min_frontier_cluster_size=relaxed_cluster_size' in source
    assert 'min_goal_distance=relaxed_min_goal_distance' in source


def test_exploration_manager_supports_scene_specific_exploration_bounds():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'min_goal_x' in source
    assert 'max_goal_x' in source
    assert 'min_goal_y' in source
    assert 'max_goal_y' in source


def test_exploration_manager_declares_stuck_goal_recovery_parameters():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'stuck_timeout_sec' in source
    assert 'stuck_movement_epsilon' in source
    assert 'stuck_goal_tolerance' in source
    assert 'blocked_goal_ttl_sec' in source
    assert 'blocked_goal_radius' in source


def test_exploration_manager_cancels_and_blocks_stalled_frontier_goal():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "exploration_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'goal_progress_stalled(' in source
    assert 'self._navigator.cancelTask()' in source
    assert 'self._blocked_goals' in source
    assert 'blocked_goals=self._blocked_goal_regions(now_sec)' in source
