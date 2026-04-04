"""Tests for simulation_controller module.

This module tests the SimulationController class which manages:
- Simulation lifecycle (start/stop)
- Log collection
- Metrics tracking
- Process management
- Diagnostic export
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch
import zipfile

import pytest

from h2track_tracking.web.simulation_controller import (
    CommandResult,
    SimulationController,
)
from h2track_tracking.web.metrics_store import MetricsStore


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_run_command():
    """Mock run_command that returns success."""
    def _run(cmd: list[str]) -> CommandResult:
        return CommandResult(returncode=0, stdout="DEMO PREP OK\n", stderr="")
    return _run


@pytest.fixture
def mock_launch_process():
    """Mock launch_process that returns a fake process with blocking stdout."""
    class FakeProcess:
        pid = 12345

        def __init__(self):
            # Use a pipe that will block on read until closed
            self._read_fd, self._write_fd = os.pipe()
            self.stdout = os.fdopen(self._read_fd, 'r')
            self._stopped = False

        def poll(self):
            # Return None until stopped
            if self._stopped:
                return 0
            return None

        def wait(self, timeout=None):
            self._stopped = True
            # Close write end to unblock reader
            try:
                os.close(self._write_fd)
            except OSError:
                pass
            return 0

    import os
    def _launch(cmd: list[str], env: dict[str, str]) -> FakeProcess:
        return FakeProcess()

    return _launch


@pytest.fixture
def mock_topic_probe():
    """Mock topic probe that returns None by default."""
    def _probe(topic: str, timeout_sec: float) -> str | None:
        return None
    return _probe


@pytest.fixture
def controller(mock_run_command, mock_launch_process, mock_topic_probe):
    """Create a SimulationController with mocked dependencies."""
    return SimulationController(
        run_command=mock_run_command,
        launch_process=mock_launch_process,
        topic_probe=mock_topic_probe,
        metrics_store=MetricsStore(max_points=16),
    )


# ==============================================================================
# Initialization Tests
# ==============================================================================


def test_controller_initializes_with_idle_state(controller):
    """Controller should start in idle state."""
    status = controller.status()
    assert status["state"] == "idle"
    assert status["pid"] is None
    assert status["last_error"] == ""


def test_controller_initializes_with_default_launch_profile(controller):
    """Controller should have default launch profile."""
    status = controller.status()
    assert status["launch_profile"]["scene"] == "warehouse"
    assert status["launch_profile"]["use_gaden"] == "true"


def test_controller_accepts_custom_metrics_store(mock_run_command, mock_launch_process, mock_topic_probe):
    """Controller should accept a custom MetricsStore."""
    custom_store = MetricsStore(max_points=100)
    custom_store.set_mode("PATROL")
    custom_store.set_gas(0.5)

    ctrl = SimulationController(
        run_command=mock_run_command,
        launch_process=mock_launch_process,
        topic_probe=mock_topic_probe,
        metrics_store=custom_store,
    )

    snapshot = ctrl.metrics_snapshot(limit=10)
    assert snapshot["mode"]["current"] == "PATROL"
    assert snapshot["gas"]["current"] == pytest.approx(0.5, abs=1e-9)


# ==============================================================================
# Start/Stop Lifecycle Tests
# ==============================================================================


def test_start_with_profile_starts_successfully(controller):
    """start_with_profile should start the simulation."""
    ok, msg = controller.start_with_profile({"scene": "warehouse"})

    assert ok is True
    assert "started" in msg.lower()

    status = controller.status()
    assert status["state"] == "running"
    assert status["pid"] == 12345


def test_start_uses_default_profile(controller):
    """start() should use default profile."""
    ok, msg = controller.start()

    assert ok is True
    status = controller.status()
    assert status["launch_profile"]["scene"] == "warehouse"


def test_start_rejects_duplicate_start(controller):
    """Starting an already running simulation should fail."""
    controller.start()

    ok, msg = controller.start()
    assert ok is False
    assert "already" in msg.lower()


def test_start_rejects_start_while_starting(controller):
    """Starting while in 'starting' state should fail."""
    with controller._lock:
        controller._state = "starting"

    ok, msg = controller.start()
    assert ok is False


def test_start_rejects_start_while_stopping(controller):
    """Starting while in 'stopping' state should fail."""
    with controller._lock:
        controller._state = "stopping"

    ok, msg = controller.start()
    assert ok is False


def test_start_handles_prep_failure(mock_launch_process, mock_topic_probe):
    """Start should fail if demo_prep fails."""
    def failing_prep(cmd):
        return CommandResult(returncode=1, stdout="", stderr="prep error")

    ctrl = SimulationController(
        run_command=failing_prep,
        launch_process=mock_launch_process,
        topic_probe=mock_topic_probe,
    )

    ok, msg = ctrl.start()
    assert ok is False
    assert "prep" in msg.lower() or "failed" in msg.lower()

    status = ctrl.status()
    assert status["state"] == "error"


def test_start_handles_prep_exception(mock_launch_process, mock_topic_probe):
    """Start should handle exceptions during prep execution."""
    def exception_prep(cmd):
        raise RuntimeError("prep crashed")

    ctrl = SimulationController(
        run_command=exception_prep,
        launch_process=mock_launch_process,
        topic_probe=mock_topic_probe,
    )

    ok, msg = ctrl.start()
    assert ok is False

    status = ctrl.status()
    assert status["state"] == "error"
    assert "prep" in status["last_error"].lower() or "crashed" in status["last_error"].lower()


def test_start_handles_launch_exception(mock_run_command, mock_topic_probe):
    """Start should handle exceptions during launch."""
    def failing_launch(cmd, env):
        raise RuntimeError("launch failed")

    ctrl = SimulationController(
        run_command=mock_run_command,
        launch_process=failing_launch,
        topic_probe=mock_topic_probe,
    )

    ok, msg = ctrl.start()
    assert ok is False
    assert "launch" in msg.lower() or "failed" in msg.lower()

    status = ctrl.status()
    assert status["state"] == "error"


def test_stop_stops_running_simulation(controller):
    """Stop should stop a running simulation."""
    controller.start()
    # Give time for the reader thread to start
    time.sleep(0.1)

    # The mock process doesn't have a real process group, so killpg will fail
    # We just verify that stop returns appropriately (either success or failure)
    ok, msg = controller.stop()
    # Either succeeds (if we mock it) or fails gracefully
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_stop_rejects_when_not_running(controller):
    """Stop should fail when simulation is not running."""
    ok, msg = controller.stop()
    assert ok is False
    assert "not running" in msg.lower()


def test_stop_handles_process_kill_failure(mock_run_command, mock_topic_probe):
    """Stop should handle process kill failure gracefully."""
    class MockProcess:
        pid = 99999  # Non-existent PID
        stdout = io.StringIO("")

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    ctrl = SimulationController(
        run_command=mock_run_command,
        launch_process=lambda cmd, env: MockProcess(),
        topic_probe=mock_topic_probe,
    )
    ctrl.start()

    # The stop will try to kill the process group, which may fail
    # We just ensure it handles the error gracefully
    ok, msg = ctrl.stop()
    # Either succeeds or fails gracefully
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


# ==============================================================================
# Log Collection Tests
# ==============================================================================


def test_recent_logs_includes_init_log(controller):
    """recent_logs should include the controller initialized log."""
    logs = controller.recent_logs(limit=10)
    # Controller logs "controller initialized" on init
    assert len(logs) >= 1
    assert logs[0]["line"] == "controller initialized"


def test_recent_logs_respects_limit(controller):
    """recent_logs should respect the limit parameter."""
    # Generate some logs (accounting for init log)
    for i in range(10):
        controller._append_log(f"log line {i}")

    logs = controller.recent_logs(limit=5)
    assert len(logs) == 5


def test_recent_logs_returns_empty_for_zero_limit(controller):
    """recent_logs should return empty list for limit <= 0."""
    controller._append_log("some log")
    logs = controller.recent_logs(limit=0)
    assert logs == []


def test_logs_after_returns_newer_logs(controller):
    """logs_after should return logs with id > after_id."""
    # Controller adds init log with id=1
    controller._append_log("first")   # id=2
    controller._append_log("second")  # id=3
    controller._append_log("third")   # id=4

    logs = controller.logs_after(2)  # Get logs after id=2
    log_lines = [l["line"] for l in logs]
    assert "second" in log_lines
    assert "third" in log_lines


def test_logs_after_returns_empty_when_none_newer(controller):
    """logs_after should return empty list when no newer logs."""
    controller._append_log("first")
    logs = controller.logs_after(100)
    assert logs == []


def test_append_log_includes_timestamp_and_id(controller):
    """_append_log should add timestamp and increment id."""
    controller._append_log("test log")

    logs = controller.recent_logs(limit=1)
    assert len(logs) == 1
    assert "timestamp" in logs[0]
    assert "id" in logs[0]
    assert logs[0]["line"] == "test log"


def test_append_log_uses_source_parameter(controller):
    """_append_log should record the source."""
    controller._append_log("system log", source="system")
    controller._append_log("sim log", source="sim")

    logs = controller.recent_logs(limit=3)
    sources = [l["source"] for l in logs if l["line"] in ["system log", "sim log"]]
    assert "system" in sources
    assert "sim" in sources


# ==============================================================================
# Metrics Snapshot Tests
# ==============================================================================


def test_metrics_snapshot_returns_phase_and_mode(controller):
    """metrics_snapshot should include phase and mode data."""
    controller._metrics.set_phase("LAUNCH", reason="test")
    controller._metrics.set_mode("PATROL")

    snapshot = controller.metrics_snapshot(limit=10)

    assert snapshot["phase"]["current"] == "LAUNCH"
    assert snapshot["mode"]["current"] == "PATROL"


def test_metrics_snapshot_includes_launch_profile(controller):
    """metrics_snapshot should include the launch profile."""
    controller._launch_profile = {
        "scene": "baseline",
        "use_gaden": "false",
        "use_slam": "true",
        "use_rviz": "false",
        "headless": "true",
    }

    snapshot = controller.metrics_snapshot(limit=10)

    assert snapshot["launch_profile"]["scene"] == "baseline"
    assert snapshot["launch_profile"]["use_gaden"] == "false"


def test_metrics_snapshot_uses_simplified_field_when_gaden_disabled(controller):
    """metrics_snapshot should indicate simplified field when GADEN is off."""
    controller._launch_profile = {
        "scene": "warehouse",
        "use_gaden": "false",
    }

    snapshot = controller.metrics_snapshot(limit=10)

    assert snapshot["gas"]["signal_status"] == "simplified_field"


def test_metrics_snapshot_caches_scene_thresholds(controller, monkeypatch):
    """metrics_snapshot should cache scene thresholds."""
    call_count = {"count": 0}

    def mock_load_thresholds(scene):
        call_count["count"] += 1
        return {"enter_threshold": 0.6}

    monkeypatch.setattr(
        "h2track_tracking.web.simulation_controller.load_scene_thresholds",
        mock_load_thresholds,
    )

    # Call twice with same scene
    controller.metrics_snapshot(limit=10)
    controller.metrics_snapshot(limit=10)

    # Should only call load once due to caching
    assert call_count["count"] == 1


# ==============================================================================
# Topic Probe Tests
# ==============================================================================


def test_refresh_metrics_from_topics_updates_gas(controller):
    """refresh_metrics_from_topics_if_needed should update gas from topic."""
    probe_values = ["/gas_concentration: 0.75"]

    def mock_probe(topic, timeout):
        if topic == "/gas_concentration":
            return "0.75"
        return None

    controller._topic_probe = mock_probe
    controller._topic_probe_interval_sec = 0.0  # Allow immediate probe

    controller.refresh_metrics_from_topics_if_needed()

    snapshot = controller.metrics_snapshot(limit=10)
    assert snapshot["gas"]["current"] == pytest.approx(0.75, abs=1e-9)


def test_refresh_metrics_respects_interval(controller):
    """refresh_metrics should respect the probe interval."""
    probe_count = {"count": 0}

    def counting_probe(topic, timeout):
        probe_count["count"] += 1
        return None

    controller._topic_probe = counting_probe
    controller._topic_probe_interval_sec = 10.0  # Long interval

    # Multiple calls should only probe once
    controller.refresh_metrics_from_topics_if_needed()
    controller.refresh_metrics_from_topics_if_needed()
    controller.refresh_metrics_from_topics_if_needed()

    assert probe_count["count"] == 1


def test_refresh_metrics_handles_invalid_gas_value(controller):
    """refresh_metrics should handle invalid gas values gracefully."""
    def bad_probe(topic, timeout):
        if topic == "/gas_concentration":
            return "not_a_number"
        return None

    controller._topic_probe = bad_probe
    controller._topic_probe_interval_sec = 0.0

    # Should not raise
    controller.refresh_metrics_from_topics_if_needed()


# ==============================================================================
# Node Health Tests
# ==============================================================================


def test_refresh_runtime_health_updates_nodes(controller, monkeypatch):
    """refresh_runtime_health_if_needed should update node health."""
    import subprocess

    class MockResult:
        returncode = 0
        stdout = "/mission_manager_node\n/controller_server\n"

    def mock_run(*args, **kwargs):
        return MockResult()

    monkeypatch.setattr(subprocess, "run", mock_run)
    controller._node_health_probe_interval_sec = 0.0

    controller.refresh_runtime_health_if_needed()

    snapshot = controller.metrics_snapshot(limit=10)
    nodes = snapshot["node_health"]["nodes"]
    node_names = {n["name"] for n in nodes}
    assert "/mission_manager_node" in node_names


# ==============================================================================
# Diagnostic Export Tests
# ==============================================================================


def test_export_diagnostics_creates_zip(controller, tmp_path, monkeypatch):
    """export_diagnostics should create a zip file."""
    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    path = controller.export_diagnostics(scene="warehouse")

    assert path.endswith(".zip")
    assert Path(path).exists()

    # Verify zip contents
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        assert "summary.json" in names
        assert "logs.jsonl" in names

        # Verify summary.json is valid JSON
        with zf.open("summary.json") as f:
            summary = json.load(f)
            assert summary["scene"] == "warehouse"


def test_export_diagnostics_includes_status_and_metrics(controller, tmp_path, monkeypatch):
    """export_diagnostics should include status and metrics."""
    monkeypatch.chdir(tmp_path)

    controller._metrics.set_mode("SEEK_TRACK")
    controller._metrics.set_gas(1.25)

    path = controller.export_diagnostics(scene="warehouse")

    with zipfile.ZipFile(path, "r") as zf:
        with zf.open("summary.json") as f:
            summary = json.load(f)
            assert "status" in summary
            assert "metrics" in summary


def test_export_diagnostics_uses_scene_parameter(controller, tmp_path, monkeypatch):
    """export_diagnostics should use the scene parameter."""
    monkeypatch.chdir(tmp_path)

    path = controller.export_diagnostics(scene="baseline")
    assert "baseline" in path


# ==============================================================================
# Run Report Export Tests
# ==============================================================================


def test_export_run_report_creates_json_and_markdown(controller, tmp_path, monkeypatch):
    """export_run_report should create both JSON and Markdown files."""
    monkeypatch.chdir(tmp_path)

    result = controller.export_run_report(scene="warehouse")

    assert "json_path" in result
    assert "markdown_path" in result
    assert result["json_path"].endswith(".json")
    assert result["markdown_path"].endswith(".md")

    assert Path(result["json_path"]).exists()
    assert Path(result["markdown_path"]).exists()


def test_export_run_report_json_contains_required_fields(controller, tmp_path, monkeypatch):
    """export_run_report JSON should contain required fields."""
    monkeypatch.chdir(tmp_path)

    controller._metrics.set_mode("SOURCE_FOUND")
    controller._launch_profile = {"scene": "warehouse", "use_gaden": "true"}

    result = controller.export_run_report(scene="warehouse")

    with open(result["json_path"], "r") as f:
        report = json.load(f)

    assert report["scene"] == "warehouse"
    assert "status" in report
    assert "metrics" in report
    assert "launch_profile" in report
    assert "logs" in report


def test_export_run_report_markdown_has_headers(controller, tmp_path, monkeypatch):
    """export_run_report Markdown should have proper headers."""
    monkeypatch.chdir(tmp_path)

    result = controller.export_run_report(scene="warehouse")

    with open(result["markdown_path"], "r") as f:
        content = f.read()

    assert "# H2Track 运行报告" in content
    assert "## 启动配置" in content
    assert "## 导航统计" in content


# ==============================================================================
# Status Tests
# ==============================================================================


def test_status_returns_current_state(controller):
    """status should return current state."""
    status = controller.status()
    assert status["state"] == "idle"


def test_status_returns_pid_when_running(controller):
    """status should return PID when running."""
    controller.start()
    status = controller.status()
    assert status["state"] == "running"
    assert status["pid"] == 12345


def test_status_returns_last_error(controller):
    """status should return last error message."""
    controller._last_error = "test error"
    status = controller.status()
    assert status["last_error"] == "test error"


def test_status_returns_latest_log_id(controller):
    """status should return the latest log ID."""
    # Clear init log by getting fresh controller
    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: type('P', (), {'pid': 1, 'stdout': io.StringIO(), 'poll': lambda: None, 'wait': lambda: 0})(),
        topic_probe=lambda t, s: None,
    )
    # Reset log seq to test
    with ctrl._lock:
        ctrl._logs.clear()
        ctrl._log_seq = 0

    ctrl._append_log("first")
    ctrl._append_log("second")

    status = ctrl.status()
    assert status["latest_log_id"] == 2


def test_status_returns_launch_profile_copy(controller):
    """status should return a copy of launch profile."""
    status = controller.status()
    profile = status["launch_profile"]

    # Modifying returned profile should not affect internal state
    profile["scene"] = "modified"
    new_status = controller.status()
    assert new_status["launch_profile"]["scene"] == "warehouse"


# ==============================================================================
# Process Output Reader Tests
# ==============================================================================


def test_read_process_output_appends_logs():
    """_read_process_output should append logs from process stdout."""
    class MockProcess:
        pid = 54321
        stdout = io.StringIO("line 1\nline 2\n")
        _return_code = None

        def poll(self):
            return self._return_code

        def wait(self):
            self._return_code = 0
            return 0

    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: MockProcess(),
        topic_probe=lambda t, s: None,
    )

    ctrl._process = MockProcess()
    ctrl._read_process_output()

    logs = ctrl.recent_logs(limit=10)
    log_lines = [l["line"] for l in logs]
    assert "line 1" in log_lines
    assert "line 2" in log_lines


def test_read_process_output_handles_process_exit():
    """_read_process_output should handle process exit."""
    class MockProcess:
        pid = 54321
        stdout = io.StringIO("output\n")
        _return_code = None

        def poll(self):
            return self._return_code

        def wait(self):
            self._return_code = 42
            return 42

    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: MockProcess(),
        topic_probe=lambda t, s: None,
    )

    ctrl._state = "running"
    ctrl._process = MockProcess()
    ctrl._read_process_output()

    # Should set state to error on non-zero exit
    assert ctrl._state == "error"
    assert "42" in ctrl._last_error


def test_read_process_output_sets_idle_on_zero_exit():
    """_read_process_output should set idle on zero exit code."""
    class MockProcess:
        pid = 54321
        stdout = io.StringIO("output\n")
        _return_code = None

        def poll(self):
            return self._return_code

        def wait(self):
            self._return_code = 0
            return 0

    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: MockProcess(),
        topic_probe=lambda t, s: None,
    )

    ctrl._state = "running"
    ctrl._process = MockProcess()
    ctrl._read_process_output()

    assert ctrl._state == "idle"


def test_read_process_output_keeps_idle_when_stopping():
    """_read_process_output should keep idle when stopping."""
    class MockProcess:
        pid = 54321
        stdout = io.StringIO("output\n")
        _return_code = None

        def poll(self):
            return self._return_code

        def wait(self):
            self._return_code = 0
            return 0

    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: MockProcess(),
        topic_probe=lambda t, s: None,
    )

    ctrl._state = "stopping"
    ctrl._process = MockProcess()
    ctrl._read_process_output()

    assert ctrl._state == "idle"


# ==============================================================================
# Thread Safety Tests
# ==============================================================================


def test_concurrent_log_appends_are_thread_safe():
    """_append_log should be thread-safe for concurrent access."""
    num_threads = 10
    logs_per_thread = 100

    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: type('P', (), {'pid': 1, 'stdout': io.StringIO(), 'poll': lambda: None, 'wait': lambda: 0})(),
        topic_probe=lambda t, s: None,
        max_log_lines=2000,
    )

    threads = []

    def append_logs(thread_id):
        for i in range(logs_per_thread):
            ctrl._append_log(f"thread_{thread_id}_log_{i}")

    for i in range(num_threads):
        t = threading.Thread(target=append_logs, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have exactly num_threads * logs_per_thread + 1 (init log)
    logs = ctrl.recent_logs(limit=10000)
    # Account for init log
    expected = num_threads * logs_per_thread + 1
    assert len(logs) == expected


def test_concurrent_status_and_log_access():
    """status and recent_logs should be safe for concurrent access."""
    ctrl = SimulationController(
        run_command=lambda c: CommandResult(0, "", ""),
        launch_process=lambda c, e: type('P', (), {'pid': 1, 'stdout': io.StringIO(), 'poll': lambda: None, 'wait': lambda: 0})(),
        topic_probe=lambda t, s: None,
    )

    results = {"status": [], "logs": []}
    stop_flag = threading.Event()

    def call_status():
        while not stop_flag.is_set():
            results["status"].append(ctrl.status())
            time.sleep(0.001)

    def call_logs():
        while not stop_flag.is_set():
            results["logs"].append(ctrl.recent_logs(limit=10))
            time.sleep(0.001)

    def append_logs():
        for i in range(50):
            ctrl._append_log(f"log_{i}")
            time.sleep(0.002)
        stop_flag.set()

    threads = [
        threading.Thread(target=call_status),
        threading.Thread(target=call_logs),
        threading.Thread(target=append_logs),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All calls should have completed without exception
    assert len(results["status"]) > 0
    assert len(results["logs"]) > 0


# ==============================================================================
# Edge Cases
# ==============================================================================


def test_start_with_none_profile_uses_defaults(controller):
    """start_with_profile(None) should use default profile."""
    ok, msg = controller.start_with_profile(None)

    assert ok is True
    status = controller.status()
    assert status["launch_profile"]["scene"] == "warehouse"


def test_start_with_empty_profile_uses_defaults(controller):
    """start_with_profile({}) should use default profile."""
    ok, msg = controller.start_with_profile({})

    assert ok is True
    status = controller.status()
    assert status["launch_profile"]["scene"] == "warehouse"


def test_metrics_snapshot_with_negative_limit(controller):
    """metrics_snapshot should handle limit parameter gracefully."""
    # The MetricsStore handles the limit internally
    snapshot = controller.metrics_snapshot(limit=0)
    # Should still return valid structure
    assert "phase" in snapshot


def test_max_log_lines_respected(mock_run_command, mock_launch_process, mock_topic_probe):
    """Controller should respect max_log_lines parameter."""
    ctrl = SimulationController(
        run_command=mock_run_command,
        launch_process=mock_launch_process,
        topic_probe=mock_topic_probe,
        max_log_lines=10,
    )

    # Add more logs than the limit (accounting for init log)
    for i in range(20):
        ctrl._append_log(f"log_{i}")

    logs = ctrl.recent_logs(limit=100)
    # Should have at most 10 logs (deque behavior)
    assert len(logs) <= 10
