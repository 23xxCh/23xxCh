"""Tests for web metrics_store module."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from h2track_tracking.web.metrics_store import (
    MetricsStore,
    _now_iso,
    summarize_gas_signal,
    MODE_TRANSITION_RE,
    CONCENTRATION_RE,
    NAV_BEGIN_RE,
)


class TestMetricsStoreInit:
    """Tests for MetricsStore initialization."""

    def test_init_default_max_points(self):
        store = MetricsStore()
        assert store._max_points == 600

    def test_init_custom_max_points(self):
        store = MetricsStore(max_points=100)
        assert store._max_points == 100

    def test_init_phase_starts_at_init(self):
        store = MetricsStore()
        assert store._phase_current == "INIT"

    def test_init_has_initial_phase_timeline(self):
        store = MetricsStore()
        timeline = list(store._phase_timeline)
        assert len(timeline) == 1
        assert timeline[0]["phase"] == "INIT"

    def test_init_mode_is_none(self):
        store = MetricsStore()
        assert store._mode_current is None

    def test_init_gas_is_none(self):
        store = MetricsStore()
        assert store._gas_current is None

    def test_init_source_found_is_none(self):
        store = MetricsStore()
        assert store._source_found is None

    def test_init_nav_stats_are_zero(self):
        store = MetricsStore()
        assert store._nav_goal_succeeded == 0
        assert store._nav_failed_to_make_progress == 0
        assert store._nav_goal_canceled == 0


class TestMetricsStoreSetPhase:
    """Tests for set_phase method."""

    def test_set_phase_updates_current(self):
        store = MetricsStore()
        store.set_phase("PREP", reason="demo_prep")
        assert store._phase_current == "PREP"

    def test_set_phase_normalizes_uppercase(self):
        store = MetricsStore()
        store.set_phase("launch", reason="test")
        assert store._phase_current == "LAUNCH"

    def test_set_phase_ignores_empty(self):
        store = MetricsStore()
        original = store._phase_current
        store.set_phase("")
        assert store._phase_current == original

    def test_set_phase_ignores_whitespace(self):
        store = MetricsStore()
        original = store._phase_current
        store.set_phase("   ")
        assert store._phase_current == original

    def test_set_phase_ignores_duplicate(self):
        store = MetricsStore()
        store.set_phase("PREP", reason="first")
        timeline_len = len(store._phase_timeline)
        store.set_phase("PREP", reason="second")
        assert len(store._phase_timeline) == timeline_len

    def test_set_phase_closes_previous_phase(self):
        store = MetricsStore()
        store.set_phase("PREP", reason="test")
        timeline = list(store._phase_timeline)
        assert timeline[0]["end_ts"] is not None
        assert timeline[0]["duration_ms"] is not None


class TestMetricsStoreSetMode:
    """Tests for set_mode method."""

    def test_set_mode_updates_current(self):
        store = MetricsStore()
        store.set_mode("PATROL")
        assert store._mode_current == "PATROL"

    def test_set_mode_appends_history(self):
        store = MetricsStore(max_points=10)
        store.set_mode("PATROL")
        store.set_mode("SEEK_TRACK")
        history = list(store._mode_history)
        assert len(history) == 2
        assert history[0]["value"] == "PATROL"
        assert history[1]["value"] == "SEEK_TRACK"

    def test_set_mode_marks_topic_tick(self):
        store = MetricsStore()
        store.set_mode("PATROL")
        stats = store._topic_stats["/robot_mode"]
        assert stats["last_value"] == "PATROL"
        assert len(stats["timestamps"]) == 1


class TestMetricsStoreSetGas:
    """Tests for set_gas method."""

    def test_set_gas_updates_current(self):
        store = MetricsStore()
        store.set_gas(1.5)
        assert store._gas_current == pytest.approx(1.5, abs=1e-9)

    def test_set_gas_appends_history(self):
        store = MetricsStore(max_points=10)
        store.set_gas(0.5)
        store.set_gas(1.0)
        history = list(store._gas_history)
        assert len(history) == 2

    def test_set_gas_marks_topic_tick(self):
        store = MetricsStore()
        store.set_gas(0.75)
        stats = store._topic_stats["/gas_concentration"]
        assert stats["last_value"] == pytest.approx(0.75, abs=1e-9)


class TestMetricsStoreSetGasRaw:
    """Tests for set_gas_raw method."""

    def test_set_gas_raw_updates_current(self):
        store = MetricsStore()
        store.set_gas_raw(2.5)
        assert store._gas_raw_current == pytest.approx(2.5, abs=1e-9)

    def test_set_gas_raw_appends_history(self):
        store = MetricsStore(max_points=10)
        store.set_gas_raw(1.0)
        store.set_gas_raw(2.0)
        history = list(store._gas_raw_history)
        assert len(history) == 2

    def test_set_gas_raw_marks_gaden_topic_tick(self):
        store = MetricsStore()
        store.set_gas_raw(1.25)
        stats = store._topic_stats["/gaden/sensor_reading"]
        assert stats["last_value"] == pytest.approx(1.25, abs=1e-9)


class TestMetricsStoreSetSourceFound:
    """Tests for set_source_found method."""

    def test_set_source_found_true(self):
        store = MetricsStore()
        store.set_source_found(True)
        assert store._source_found is True

    def test_set_source_found_false(self):
        store = MetricsStore()
        store.set_source_found(True)
        store.set_source_found(False)
        assert store._source_found is False

    def test_set_source_found_marks_topic_tick(self):
        store = MetricsStore()
        store.set_source_found(True)
        stats = store._topic_stats["/source_found"]
        assert stats["last_value"] is True


class TestMetricsStoreObserveOdomTick:
    """Tests for observe_odom_tick method."""

    def test_observe_odom_tick_marks_topic(self):
        store = MetricsStore()
        store.observe_odom_tick(x=1.0, y=2.0)
        stats = store._topic_stats["/odom"]
        assert stats["last_value"] == {"x": 1.0, "y": 2.0}
        assert len(stats["timestamps"]) == 1


class TestMetricsStoreUpdateNodeHealth:
    """Tests for update_node_health method."""

    def test_update_node_health_marks_up(self):
        store = MetricsStore()
        store.update_node_health({"/test_node": True})
        assert store._node_health["/test_node"]["up"] is True
        assert store._node_health["/test_node"]["status"] == "up"

    def test_update_node_health_marks_down(self):
        store = MetricsStore()
        store.update_node_health({"/test_node": False})
        assert store._node_health["/test_node"]["up"] is False
        assert store._node_health["/test_node"]["status"] == "down"

    def test_update_node_health_tracks_restart_count(self):
        store = MetricsStore()
        # First up
        store.update_node_health({"/node": True})
        assert store._node_health["/node"]["restart_count"] == 0
        # Then down
        store.update_node_health({"/node": False})
        # Then up again (should count as restart)
        store.update_node_health({"/node": True})
        assert store._node_health["/node"]["restart_count"] == 1

    def test_update_node_health_tracks_last_error(self):
        store = MetricsStore()
        store.update_node_health({"/node": False}, last_error="crashed")
        assert store._node_health["/node"]["last_error"] == "crashed"


class TestMetricsStoreObserveLogLine:
    """Tests for observe_log_line method."""

    def test_observe_mode_transition(self):
        store = MetricsStore()
        store.observe_log_line("Mode transition: PATROL -> SEEK_TRACK")
        assert store._mode_current == "SEEK_TRACK"

    def test_observe_concentration(self):
        store = MetricsStore()
        store.observe_log_line("concentration=2.5")
        assert store._gas_current == pytest.approx(2.5, abs=1e-6)

    def test_observe_concentration_with_conc_key(self):
        store = MetricsStore()
        store.observe_log_line("conc: 1.875")
        assert store._gas_current == pytest.approx(1.875, abs=1e-6)

    def test_observe_demo_prep_sets_prep_phase(self):
        store = MetricsStore()
        store.observe_log_line("Running demo_prep for scene warehouse")
        assert store._phase_current == "PREP"

    def test_observe_launching_sets_launch_phase(self):
        store = MetricsStore()
        store.observe_log_line("Launching: ros2 launch...")
        assert store._phase_current == "LAUNCH"

    def test_observe_nav2_ready_sets_nav_ready_phase(self):
        store = MetricsStore()
        store.observe_log_line("Nav2 is ready for use")
        assert store._phase_current == "NAV_READY"

    def test_observe_stopping_sets_stopping_phase(self):
        store = MetricsStore()
        store.observe_log_line("Stopping simulation")
        assert store._phase_current == "STOPPING"

    def test_observe_exited_sets_exited_phase(self):
        store = MetricsStore()
        store.observe_log_line("Simulation exited with code 0")
        assert store._phase_current == "EXITED"

    def test_observe_nav_begin_starts_goal(self):
        store = MetricsStore()
        store.observe_log_line("Begin navigating from current location")
        assert store._nav_goal_started_at_mono is not None

    def test_observe_goal_succeeded(self):
        store = MetricsStore()
        store.observe_log_line("Begin navigating from current location")
        time.sleep(0.01)
        store.observe_log_line("Goal succeeded")
        assert store._nav_goal_succeeded == 1
        assert len(store._nav_goal_durations_sec) == 1

    def test_observe_goal_canceled(self):
        store = MetricsStore()
        store.observe_log_line("Canceling current task")
        assert store._nav_goal_canceled == 1

    def test_observe_failed_to_make_progress(self):
        store = MetricsStore()
        store.observe_log_line("Failed to make progress")
        assert store._nav_failed_to_make_progress == 1

    def test_observe_source_found_true(self):
        store = MetricsStore()
        store.observe_log_line("source_found: true")
        assert store._source_found is True


class TestMetricsStoreSnapshot:
    """Tests for snapshot method."""

    def test_snapshot_includes_phase(self):
        store = MetricsStore()
        store.set_phase("LAUNCH", reason="test")
        snap = store.snapshot()
        assert snap["phase"]["current"] == "LAUNCH"
        assert isinstance(snap["phase"]["timeline"], list)

    def test_snapshot_includes_mode(self):
        store = MetricsStore()
        store.set_mode("SEEK_TRACK")
        snap = store.snapshot()
        assert snap["mode"]["current"] == "SEEK_TRACK"
        assert isinstance(snap["mode"]["history"], list)

    def test_snapshot_includes_gas(self):
        store = MetricsStore()
        store.set_gas(0.42)
        snap = store.snapshot()
        assert snap["gas"]["current"] == pytest.approx(0.42, abs=1e-6)

    def test_snapshot_includes_source_found(self):
        store = MetricsStore()
        store.set_source_found(True)
        snap = store.snapshot()
        assert snap["source_found"]["current"] is True

    def test_snapshot_includes_nav_stats(self):
        store = MetricsStore()
        store.observe_log_line("Begin navigating from current location")
        store.observe_log_line("Goal succeeded")
        snap = store.snapshot()
        assert snap["nav"]["goal_succeeded"] == 1
        assert isinstance(snap["nav"]["goal_durations_sec"], list)

    def test_snapshot_includes_topic_health(self):
        store = MetricsStore()
        store.set_gas(1.0)
        snap = store.snapshot()
        assert "/gas_concentration" in snap["topic_health"]
        assert snap["topic_health"]["/gas_concentration"]["last_value"] == pytest.approx(1.0, abs=1e-6)

    def test_snapshot_includes_node_health(self):
        store = MetricsStore()
        store.update_node_health({"/test_node": True})
        snap = store.snapshot()
        assert "nodes" in snap["node_health"]
        assert len(snap["node_health"]["nodes"]) == 1

    def test_snapshot_respects_limit(self):
        store = MetricsStore(max_points=100)
        for i in range(50):
            store.set_gas(float(i))
        snap = store.snapshot(limit=10)
        assert len(snap["gas"]["history"]) == 10

    def test_snapshot_strips_internal_mono_from_timeline(self):
        store = MetricsStore()
        store.set_phase("LAUNCH", reason="test")
        snap = store.snapshot()
        for entry in snap["phase"]["timeline"]:
            assert "_start_mono" not in entry


class TestMetricsStoreTopicHealth:
    """Tests for topic health tracking."""

    def test_topic_health_stale_when_no_data(self):
        store = MetricsStore()
        snap = store.snapshot()
        assert snap["topic_health"]["/gas_concentration"]["status"] == "stale"

    def test_topic_health_ok_when_recent_data(self):
        store = MetricsStore()
        store.set_gas(1.0)
        snap = store.snapshot()
        assert snap["topic_health"]["/gas_concentration"]["status"] == "ok"

    def test_topic_health_computes_hz(self):
        store = MetricsStore()
        # Add multiple data points quickly
        for _ in range(5):
            store.set_gas(1.0)
        snap = store.snapshot()
        assert snap["topic_health"]["/gas_concentration"]["hz"] > 0


class TestMetricsStoreThreadSafety:
    """Tests for thread safety of MetricsStore."""

    def test_concurrent_set_gas(self):
        import threading

        store = MetricsStore(max_points=1000)
        errors = []

        def writer(start_val: int):
            try:
                for i in range(100):
                    store.set_gas(float(start_val + i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i * 1000,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store._gas_history) == 500

    def test_concurrent_snapshot_and_write(self):
        import threading

        store = MetricsStore(max_points=1000)
        errors = []
        snapshots = []

        def writer():
            try:
                for i in range(100):
                    store.set_gas(float(i))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(10):
                    snap = store.snapshot(limit=10)
                    snapshots.append(snap)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer)] + [
            threading.Thread(target=reader) for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(snapshots) == 30


class TestNowIso:
    """Tests for _now_iso helper."""

    def test_now_iso_returns_iso_format(self):
        result = _now_iso()
        assert isinstance(result, str)
        assert "T" in result

    def test_now_iso_has_timezone(self):
        result = _now_iso()
        assert "+" in result or "Z" in result or result.endswith("UTC")


class TestSummarizeGasSignal:
    """Tests for summarize_gas_signal helper."""

    def test_no_samples(self):
        result = summarize_gas_signal(raw_history=[], raw_topic_health={})
        assert result["signal_status"] == "no_samples"
        assert "未收到" in result["signal_reason"]

    def test_stale_topic(self):
        history = [{"value": 1.0}]
        result = summarize_gas_signal(raw_history=history, raw_topic_health={"status": "stale"})
        assert result["signal_status"] == "stale"
        assert "过期" in result["signal_reason"]

    def test_flatline_zero(self):
        history = [{"value": 0.0}, {"value": 0.0}, {"value": 0.0}]
        result = summarize_gas_signal(raw_history=history, raw_topic_health={"status": "ok"})
        assert result["signal_status"] == "flatline_zero"
        assert "全零" in result["signal_reason"]

    def test_active_signal(self):
        history = [{"value": 0.0}, {"value": 1.5}, {"value": 2.0}]
        result = summarize_gas_signal(raw_history=history, raw_topic_health={"status": "ok"})
        assert result["signal_status"] == "active"
        assert "正常" in result["signal_reason"]


class TestRegexPatterns:
    """Tests for regex patterns used in log parsing."""

    def test_mode_transition_re(self):
        match = MODE_TRANSITION_RE.search("Mode transition: PATROL -> SEEK_TRACK")
        assert match is not None
        assert match.group(1) == "SEEK_TRACK"

    def test_mode_transition_re_various_formats(self):
        cases = [
            ("Mode transition: INIT -> PATROL", "PATROL"),
            ("Mode transition: SEEK_CONFIRM -> SEEK_TRACK", "SEEK_TRACK"),
        ]
        for text, expected in cases:
            match = MODE_TRANSITION_RE.search(text)
            assert match is not None
            assert match.group(1) == expected

    def test_concentration_re_equals(self):
        match = CONCENTRATION_RE.search("concentration=2.5")
        assert match is not None
        assert float(match.group(1)) == pytest.approx(2.5, abs=1e-6)

    def test_concentration_re_colon(self):
        match = CONCENTRATION_RE.search("conc: 1.875")
        assert match is not None
        assert float(match.group(1)) == pytest.approx(1.875, abs=1e-6)

    def test_nav_begin_re(self):
        match = NAV_BEGIN_RE.search("Begin navigating from current location")
        assert match is not None


class TestMetricsStoreIntegration:
    """Integration tests for MetricsStore with typical usage patterns."""

    def test_full_mission_flow(self):
        """Test a complete mission flow from INIT to SOURCE_FOUND."""
        store = MetricsStore()

        # Demo prep
        store.observe_log_line("Running demo_prep for scene warehouse")
        assert store._phase_current == "PREP"

        # Launch
        store.observe_log_line("Launching: ros2 launch h2track_sim demo.launch.py")
        assert store._phase_current == "LAUNCH"

        # Nav2 ready
        store.observe_log_line("Nav2 is ready for use")
        assert store._phase_current == "NAV_READY"

        # Mode transitions
        store.observe_log_line("Mode transition: INIT -> PATROL")
        assert store._mode_current == "PATROL"

        # Gas detection
        store.observe_log_line("concentration=0.65")
        assert store._gas_current == pytest.approx(0.65, abs=1e-6)

        # Mode transition to tracking
        store.observe_log_line("Mode transition: PATROL -> SEEK_CONFIRM")
        store.observe_log_line("Mode transition: SEEK_CONFIRM -> SEEK_TRACK")
        assert store._mode_current == "SEEK_TRACK"

        # Navigation events
        store.observe_log_line("Begin navigating from current location")
        store.observe_log_line("Goal succeeded")

        # Source found
        store.observe_log_line("Mode transition: SEEK_TRACK -> SOURCE_FOUND")
        store.observe_log_line("source_found: true")
        assert store._mode_current == "SOURCE_FOUND"
        assert store._source_found is True

        # Snapshot
        snap = store.snapshot()
        assert snap["mode"]["current"] == "SOURCE_FOUND"
        assert snap["source_found"]["current"] is True
        assert snap["nav"]["goal_succeeded"] == 1
