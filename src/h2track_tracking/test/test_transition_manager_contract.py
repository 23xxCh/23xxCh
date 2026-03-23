from pathlib import Path


def test_transition_manager_listens_for_freeze_requests_and_uses_save_map_service():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert '/freeze_map_requested' in source
    assert 'SaveMap' in source
    assert '/map_saver_server/save_map' in source
    assert '/map_frozen' in source


def test_transition_manager_keeps_freeze_request_pending_until_save_service_is_ready():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert '_freeze_pending' in source
    assert 'wait_for_service(timeout_sec=0.0)' in source
    assert 'OccupancyGrid' in source
    assert 'freeze_ready_min_map_samples' in source
    assert 'freeze_ready_min_map_age_sec' in source
    assert 'freeze_gate_ready' in source


def test_transition_manager_starts_tracking_localization_and_stops_slam_after_freeze():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "subprocess" in source
    assert "tracking_localization.launch.py" in source
    assert "async_slam_toolbox_node" in source
    assert "baseline_freeze_map.yaml" not in source
    assert "source_x:=" in source
    assert "source_y:=" in source


def test_transition_manager_shuts_down_navigation_stack_before_tracking_handoff():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "ManageLifecycleNodes" in source
    assert "lifecycle_manager_service" in source
    assert "SHUTDOWN" in source


def test_transition_manager_terminates_primary_navigation_processes_before_tracking_handoff():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "_stop_primary_navigation_processes" in source
    assert "controller_server" in source
    assert "planner_server" in source
    assert "behavior_server" in source
    assert "bt_navigator" in source
    assert "waypoint_follower" in source
    assert "velocity_smoother" in source
    assert "lifecycle_manager_navigation" in source
    assert "/nav2_controller/controller_server" in source
    assert "/nav2_smoother/smoother_server" in source
    assert "/nav2_planner/planner_server" in source
    assert "/nav2_behaviors/behavior_server" in source
    assert "/nav2_bt_navigator/bt_navigator" in source
    assert "/nav2_waypoint_follower/waypoint_follower" in source
    assert "/nav2_velocity_smoother/velocity_smoother" in source


def test_transition_manager_forwards_tracking_handoff_overrides_to_tracking_launch():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "tracking_enter_threshold" in source
    assert "tracking_exit_threshold" in source
    assert "tracking_source_threshold" in source
    assert "tracking_confirm_samples" in source
    assert "tracking_track_exit_samples" in source
    assert "tracking_source_radius" in source
    assert "tracking_source_hold_steps" in source
    assert "launch_cmd.append(f\"enter_threshold:={" in source
    assert "launch_cmd.append(f\"source_threshold:={" in source
    assert "launch_cmd.append(f\"track_exit_samples:={" in source
    assert "launch_cmd.append(f\"source_hold_steps:={" in source


def test_transition_manager_can_disable_fastdds_shm_for_tracking_sublaunch():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "tracking_disable_fastdds_shm" in source
    assert "FASTDDS_BUILTIN_TRANSPORTS" in source
    assert "subprocess.Popen(launch_cmd, env=env)" in source


def test_transition_manager_transforms_source_from_odom_into_frozen_map_frame():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert 'source_frame' in source
    assert '"odom"' in source or "'odom'" in source
    assert '"map"' in source or "'map'" in source
    assert "transform_point_into_map_frame" in source


def test_transition_manager_clamps_far_tracking_source_seed_before_handoff():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "tracking_source_seed_max_distance" in source
    assert "clamp_tracking_source_seed" in source
    assert "Clamped projected source seed for tracking handoff" in source


def test_transition_manager_publishes_tracking_handoff_completion_and_failure_signals():
    source = (
        Path(__file__).resolve().parents[1]
        / "h2track_tracking"
        / "transition_manager_node.py"
    ).read_text(encoding="utf-8")

    assert "tracking_launch_healthcheck_sec" in source
    assert "/tracking_handoff_complete" in source
    assert "/tracking_handoff_failed" in source
    assert "Tracking handoff complete" in source
    assert "Tracking handoff failed" in source
