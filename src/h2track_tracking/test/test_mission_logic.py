from h2track_tracking.mission_logic import MissionConfig, MissionMode, MissionStateMachine


def test_patrol_switches_to_confirm_after_sustained_detection():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0), (2.0, 2.0)],
            enter_threshold=4.0,
            exit_threshold=2.0,
            source_threshold=9.0,
            confirm_samples=3,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    for concentration in (4.5, 4.7, 4.8):
        machine.update(
            concentration=concentration,
            robot_position=(0.0, 0.0),
            goal_reached=False,
        )

    assert machine.mode is MissionMode.SEEK_CONFIRM


def test_confirm_requires_sustained_collapse_before_returning_to_patrol():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.4, (0.0, 0.0), False)
    machine.update(1.0, (0.0, 0.0), False)

    assert machine.mode is MissionMode.SEEK_CONFIRM

    machine.update(0.8, (0.0, 0.0), False)

    assert machine.mode is MissionMode.PATROL


def test_tracking_declares_source_found_after_persistent_high_concentration():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=3,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    for _ in range(3):
        machine.update(9.5, (1.9, 2.1), False)

    assert machine.mode is MissionMode.SOURCE_FOUND
    assert machine.source_estimate == (1.9, 2.1)


def test_tracking_requires_sustained_collapse_before_returning_to_patrol():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=3,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(1.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(0.8, (0.3, 0.3), False)
    assert machine.mode is MissionMode.PATROL


def test_source_found_requires_positions_to_stay_within_radius():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)

    machine.update(9.5, (1.9, 2.1), False)
    machine.update(9.3, (3.0, 3.0), False)  # Moves outside radius — resets hits
    machine.update(9.2, (1.8, 2.0), False)  # Back near estimate — hit 1
    machine.update(9.4, (1.9, 2.2), False)  # Still near — hit 1 (estimate updated)
    machine.update(9.1, (1.9, 2.1), False)  # Still near — hit 2 → SOURCE_FOUND

    assert machine.mode is MissionMode.SOURCE_FOUND


def test_tracking_can_declare_source_found_from_recent_peak_when_robot_holds_position():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=4.5,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(5.2, (1.9, 2.1), False)
    machine.update(1.8, (2.0, 2.1), False)

    assert machine.mode is MissionMode.SOURCE_FOUND


def test_recent_source_peak_does_not_count_if_robot_moves_outside_source_radius():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=4.5,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
            actual_source=(10.0, 10.0),  # Far away to prevent fast-path
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(5.2, (1.9, 2.1), False)
    machine.update(1.8, (3.0, 3.0), False)

    assert machine.mode is MissionMode.SEEK_TRACK
    assert machine.source_estimate == (1.9, 2.1)


def test_tracking_can_confirm_source_after_confirm_stage_spike_if_robot_stays_near_estimate():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=0.6,
            source_threshold=4.5,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    assert machine.mode is MissionMode.SEEK_CONFIRM

    machine.update(4.8, (1.9, 2.1), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(2.3, (2.0, 2.1), False)
    machine.update(1.3, (2.0, 2.1), False)

    assert machine.mode is MissionMode.SOURCE_FOUND


def test_tracking_declares_source_found_when_readings_converge_regardless_of_actual_source():
    """Sustained high readings that cluster within source_radius trigger
    SOURCE_FOUND even when far from the known actual_source position.
    The slow-path uses convergence (clustering) as sufficient evidence."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
            actual_source=(-4.0, 1.95),
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(9.5, (1.9, 2.1), False)
    machine.update(9.3, (1.95, 2.05), False)

    assert machine.mode is MissionMode.SOURCE_FOUND


def test_tracking_declares_source_found_when_estimate_is_near_actual_source():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
            actual_source=(1.95, 2.05),
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(9.5, (1.9, 2.1), False)
    machine.update(9.3, (1.95, 2.05), False)

    assert machine.mode is MissionMode.SOURCE_FOUND


def test_tracking_uses_separate_exit_window_when_configured():
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.0,
            source_threshold=8.0,
            confirm_samples=1,
            track_exit_samples=3,
            source_radius=0.5,
            source_hold_steps=2,
        )
    )

    # Enter tracking quickly using single-sample entry confirmation.
    machine.update(3.5, (0.0, 0.0), False)
    assert machine.mode is MissionMode.SEEK_CONFIRM
    machine.update(3.4, (0.0, 0.0), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # A transient low sample should not immediately kick us back to patrol.
    machine.update(0.5, (0.1, 0.1), False)
    assert machine.mode is MissionMode.SEEK_TRACK
    machine.update(0.6, (0.1, 0.1), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Sustained collapse across the configured exit window should return to patrol.
    machine.update(0.7, (0.1, 0.1), False)
    assert machine.mode is MissionMode.PATROL


def test_patrol_advances_one_point_per_goal_reached():
    """Regression: each goal_reached=True advances exactly one patrol point.

    The state machine trusts its caller to reset goal_reached after each
    advance. If goal_reached remains True (sticky flag bug), every tick
    calls advance_patrol(), consuming all waypoints instantly and
    preventing gas detection from triggering mode transitions.

    Fix: Nav2ClientNode increments bb.nav2.goal_reached_count (edge-triggered
    counter). bt_node_runner._tick() consumes it via bool(count) and resets
    to 0 after the state machine update.
    """
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)],
            enter_threshold=5.0,
            exit_threshold=2.0,
            source_threshold=20.0,
            confirm_samples=2,
            source_radius=1.0,
            source_hold_steps=2,
        )
    )

    assert machine.current_patrol_goal == (1.0, 1.0)

    # One goal_reached → advance to point 2
    machine.update(0.1, (0.0, 0.0), goal_reached=True)
    assert machine.current_patrol_goal == (2.0, 2.0)

    # Same call without resetting → advances again (contract: caller MUST reset)
    machine.update(0.1, (0.0, 0.0), goal_reached=True)
    assert machine.current_patrol_goal == (3.0, 3.0)

    machine.update(0.1, (0.0, 0.0), goal_reached=True)
    assert machine.current_patrol_goal == (4.0, 4.0)

    # Wrap around
    machine.update(0.1, (0.0, 0.0), goal_reached=True)
    assert machine.current_patrol_goal == (1.0, 1.0)

    # Without goal_reached, patrol stays on current point (concentration too low)
    mode = machine.update(0.1, (0.0, 0.0), goal_reached=False)
    assert mode is MissionMode.PATROL
    assert machine.current_patrol_goal == (1.0, 1.0)


def test_seek_track_timeout_returns_to_patrol():
    """Robot stuck in SEEK_TRACK for too long should fall back to PATROL."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=1,
            source_radius=0.5,
            source_hold_steps=2,
            track_timeout_sec=5.0,  # 5 seconds = 50 ticks at 10Hz
        )
    )

    # Enter SEEK_TRACK
    machine.update(3.5, (0.0, 0.0), False)
    assert machine.mode is MissionMode.SEEK_CONFIRM
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Stay in SEEK_TRACK with intermediate concentration (below source_threshold)
    for _ in range(49):
        machine.update(5.0, (1.0, 1.0), False)
        assert machine.mode is MissionMode.SEEK_TRACK

    # 50th tick (5.0 seconds) should trigger timeout → PATROL
    machine.update(5.0, (1.0, 1.0), False)
    assert machine.mode is MissionMode.PATROL


def test_seek_track_timeout_resets_on_reentry():
    """Timeout counter should reset when re-entering SEEK_TRACK."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=1,
            source_radius=0.5,
            source_hold_steps=2,
            track_timeout_sec=5.0,
        )
    )

    # Enter SEEK_TRACK
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Stay for 30 ticks (3 seconds, not yet timed out)
    for _ in range(30):
        machine.update(5.0, (1.0, 1.0), False)

    # Drop below exit_threshold → PATROL
    machine.update(1.0, (1.0, 1.0), False)
    machine.update(1.0, (1.0, 1.0), False)
    assert machine.mode is MissionMode.PATROL

    # Re-enter SEEK_TRACK — timeout counter should be reset
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Should have full 50 ticks again, not 20 remaining
    for _ in range(49):
        machine.update(5.0, (1.0, 1.0), False)
        assert machine.mode is MissionMode.SEEK_TRACK

    machine.update(5.0, (1.0, 1.0), False)
    assert machine.mode is MissionMode.PATROL


def test_seek_track_no_timeout_when_disabled():
    """track_timeout_sec=0 disables the timeout."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=8.0,
            confirm_samples=1,
            source_radius=0.5,
            source_hold_steps=2,
            track_timeout_sec=0.0,  # disabled
        )
    )

    machine.update(3.5, (0.0, 0.0), False)
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Run for 200 ticks (20 seconds) — should stay in SEEK_TRACK
    for _ in range(200):
        machine.update(5.0, (1.0, 1.0), False)
        assert machine.mode is MissionMode.SEEK_TRACK


def test_adaptive_source_threshold_triggers_near_peak():
    """Robot should trigger SOURCE_FOUND when concentration is near observed peak."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=100.0,  # Very high fixed threshold — won't trigger
            confirm_samples=2,
            source_radius=0.5,
            source_hold_steps=2,
            adaptive_source_ratio=0.8,  # Trigger at 80% of max
        )
    )

    # Enter SEEK_TRACK (PATROL → SEEK_CONFIRM → SEEK_TRACK)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(4.0, (0.5, 0.5), False)
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Build up a peak of 20.0
    machine.update(10.0, (1.0, 1.0), False)
    machine.update(15.0, (1.2, 1.2), False)
    machine.update(20.0, (1.5, 1.5), False)

    # Drop slightly to 17.0 (85% of 20.0) — should trigger SOURCE_FOUND
    machine.update(17.0, (1.5, 1.5), False)
    assert machine.mode is MissionMode.SOURCE_FOUND


def test_adaptive_threshold_disabled_by_default():
    """adaptive_source_ratio=0 disables the feature."""
    machine = MissionStateMachine(
        MissionConfig(
            patrol_points=[(1.0, 1.0)],
            enter_threshold=3.0,
            exit_threshold=1.5,
            source_threshold=100.0,  # Very high — won't trigger
            confirm_samples=1,
            source_radius=0.5,
            source_hold_steps=2,
            adaptive_source_ratio=0.0,  # disabled
        )
    )

    machine.update(3.5, (0.0, 0.0), False)
    machine.update(4.0, (0.5, 0.5), False)
    machine.update(4.0, (0.5, 0.5), False)
    assert machine.mode is MissionMode.SEEK_TRACK

    # Even with high concentration, should NOT trigger SOURCE_FOUND
    for _ in range(50):
        machine.update(20.0, (1.5, 1.5), False)
        assert machine.mode is MissionMode.SEEK_TRACK
