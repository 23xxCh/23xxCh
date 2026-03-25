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
            source_hold_steps=3,
        )
    )

    machine.update(3.2, (0.0, 0.0), False)
    machine.update(3.5, (0.0, 0.0), False)
    machine.update(5.0, (0.3, 0.3), False)

    machine.update(9.5, (1.9, 2.1), False)
    machine.update(9.3, (3.0, 3.0), False)
    machine.update(9.2, (1.8, 2.0), False)
    machine.update(9.4, (1.9, 2.2), False)

    assert machine.mode is not MissionMode.SOURCE_FOUND


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


def test_tracking_does_not_declare_source_found_when_estimate_is_far_from_actual_source():
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

    assert machine.mode is MissionMode.SEEK_TRACK


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
