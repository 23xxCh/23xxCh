from h2track_tracking.demo_regression import (
    RegressionRound,
    build_demo_launch_command,
    evaluate_round_success,
    extract_round_metrics,
    extract_failure_hotspots,
    parse_source_found_output,
    summarize_rounds,
    write_rounds_csv,
)


def test_parse_source_found_output_detects_true():
    assert parse_source_found_output("data: true\n---\n") is True
    assert parse_source_found_output("header\ndata: True\n") is True


def test_parse_source_found_output_rejects_false_or_empty():
    assert parse_source_found_output("data: false\n") is False
    assert parse_source_found_output("") is False


def test_summarize_rounds_computes_success_rate_and_latency():
    rounds = [
        RegressionRound(
            index=1,
            success=True,
            seek_track_seen=True,
            source_found=True,
            source_found_seen=True,
            source_found_time=82.1,
            failed_to_make_progress=0,
            patrol_timeouts=0,
            goal_succeeded=4,
            notes="",
        ),
        RegressionRound(
            index=2,
            success=False,
            seek_track_seen=False,
            source_found=False,
            source_found_seen=False,
            source_found_time=None,
            failed_to_make_progress=1,
            patrol_timeouts=1,
            goal_succeeded=1,
            notes="timeout",
        ),
        RegressionRound(
            index=3,
            success=True,
            seek_track_seen=True,
            source_found=True,
            source_found_seen=True,
            source_found_time=95.6,
            failed_to_make_progress=0,
            patrol_timeouts=0,
            goal_succeeded=3,
            notes="",
        ),
    ]

    summary = summarize_rounds(rounds)

    assert summary["rounds"] == 3
    assert summary["successes"] == 2
    assert summary["success_rate"] == 2 / 3
    assert summary["seek_track_rounds"] == 2
    assert summary["source_found_rounds"] == 2
    assert summary["total_failed_to_make_progress"] == 1
    assert summary["total_patrol_timeouts"] == 1
    assert summary["mean_goal_succeeded"] == (4 + 1 + 3) / 3
    assert summary["mean_source_found_time"] == (82.1 + 95.6) / 2


def test_summarize_rounds_handles_zero_success():
    rounds = [
        RegressionRound(
            index=1,
            success=False,
            seek_track_seen=False,
            source_found=False,
            source_found_seen=False,
            source_found_time=None,
            failed_to_make_progress=1,
            patrol_timeouts=1,
            goal_succeeded=0,
            notes="timeout",
        ),
        RegressionRound(
            index=2,
            success=False,
            seek_track_seen=False,
            source_found=False,
            source_found_seen=False,
            source_found_time=None,
            failed_to_make_progress=2,
            patrol_timeouts=0,
            goal_succeeded=0,
            notes="timeout",
        ),
    ]

    summary = summarize_rounds(rounds)

    assert summary["rounds"] == 2
    assert summary["successes"] == 0
    assert summary["success_rate"] == 0.0
    assert summary["seek_track_rounds"] == 0
    assert summary["source_found_rounds"] == 0
    assert summary["total_failed_to_make_progress"] == 3
    assert summary["total_patrol_timeouts"] == 1
    assert summary["mean_goal_succeeded"] == 0.0
    assert summary["mean_source_found_time"] is None


def test_build_demo_launch_command_includes_use_slam_override_when_explicit():
    cmd = build_demo_launch_command(scene="warehouse", use_gaden="true", use_slam="false")
    assert "scene:=warehouse" in cmd
    assert "use_gaden:=true" in cmd
    assert "use_slam:=false" in cmd


def test_build_demo_launch_command_omits_use_slam_when_auto():
    cmd = build_demo_launch_command(scene="warehouse", use_gaden="true", use_slam="auto")
    assert "scene:=warehouse" in cmd
    assert "use_gaden:=true" in cmd
    assert not any(arg.startswith("use_slam:=") for arg in cmd)


def test_extract_round_metrics_parses_key_nav_and_mode_signals():
    log_text = """
    [controller_server] Failed to make progress
    [bt_node_runner] Patrol goal timed out; skipping to next waypoint.
    [bt_navigator] Goal succeeded
    [bt_node_runner] Mode transition: PATROL -> SEEK_CONFIRM (conc=0.8, pose=(1.0, 1.0))
    [bt_node_runner] Mode transition: SEEK_CONFIRM -> SEEK_TRACK (conc=1.2, pose=(1.1, 1.1))
    [bt_node_runner] Mode transition: SEEK_TRACK -> SOURCE_FOUND (conc=3.5, pose=(3.4, -2.9))
    """
    metrics = extract_round_metrics(log_text)
    assert metrics["failed_to_make_progress"] == 1
    assert metrics["patrol_timeouts"] == 1
    assert metrics["goal_succeeded"] == 1
    assert metrics["seek_track_seen"] is True
    assert metrics["source_found_seen"] is True


def test_evaluate_round_success_uses_nav_robustness_gate():
    assert evaluate_round_success(
        failed_to_make_progress=0,
        goal_succeeded=1,
        seek_track_seen=True,
        source_found=False,
        require_seek_track=True,
        require_source_found=False,
    )
    assert not evaluate_round_success(
        failed_to_make_progress=1,
        goal_succeeded=2,
        seek_track_seen=True,
        source_found=True,
        require_seek_track=True,
        require_source_found=False,
    )
    assert not evaluate_round_success(
        failed_to_make_progress=0,
        goal_succeeded=0,
        seek_track_seen=True,
        source_found=False,
        require_seek_track=False,
        require_source_found=False,
    )
    assert not evaluate_round_success(
        failed_to_make_progress=0,
        goal_succeeded=2,
        seek_track_seen=False,
        source_found=True,
        require_seek_track=True,
        require_source_found=False,
    )
    assert not evaluate_round_success(
        failed_to_make_progress=0,
        goal_succeeded=3,
        seek_track_seen=True,
        source_found=False,
        require_seek_track=True,
        require_source_found=True,
    )
    # Navigation-only mode: allow rounds without seek-track as long as there is no progress failure.
    assert evaluate_round_success(
        failed_to_make_progress=0,
        goal_succeeded=1,
        seek_track_seen=False,
        source_found=False,
        require_seek_track=False,
        require_source_found=False,
    )


def test_write_rounds_csv_outputs_expected_columns(tmp_path):
    rounds = [
        RegressionRound(
            index=1,
            success=True,
            seek_track_seen=True,
            source_found=True,
            source_found_seen=True,
            source_found_time=72.4,
            failed_to_make_progress=0,
            patrol_timeouts=0,
            goal_succeeded=3,
            notes="",
        )
    ]
    csv_path = tmp_path / "rounds.csv"
    write_rounds_csv(rounds, csv_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "round,success,seek_track_seen,source_found,source_found_seen,source_found_time_sec,failed_to_make_progress,patrol_timeouts,goal_succeeded,notes" in text
    assert "1,1,1,1,1,72.400,0,0,3," in text


def test_extract_failure_hotspots_aggregates_progress_fail_positions():
    log_text = """
    [bt_navigator] Begin navigating from current location (3.12, -2.31) to (3.48, -2.92)
    [controller_server] Failed to make progress
    [bt_navigator] Begin navigating from current location (3.10, -2.28) to (3.48, -2.92)
    [controller_server] Failed to make progress
    [bt_navigator] Begin navigating from current location (1.82, 2.08) to (2.80, -0.70)
    [controller_server] Failed to make progress
    """
    hotspots = extract_failure_hotspots(log_text, top_k=3)

    assert len(hotspots) >= 2
    assert hotspots[0]["count"] == 2
    assert hotspots[0]["x"] == 3.1
    assert hotspots[0]["y"] == -2.3
