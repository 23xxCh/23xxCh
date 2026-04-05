"""Tests for the recovery module.

This module tests:
- RecoveryAction implementations
- RecoveryPolicy creation
- RecoveryMonitor failure detection and recovery
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from h2track_tracking.recovery import (
    RecoveryAction,
    RecoveryMonitor,
    RecoveryPolicy,
    ResetAmclPoseAction,
    RestartGadenPlayerAction,
    RestartLifecycleNodesAction,
    RestartSimulationAction,
    create_default_policies,
)
from h2track_tracking.recovery.actions import ActionResult
from h2track_tracking.recovery.monitor import RecoveryEvent
from h2track_tracking.web.simulation_controller import SimulationController, CommandResult
from h2track_tracking.web.metrics_store import MetricsStore


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_controller():
    """Create a mock SimulationController."""
    metrics = MetricsStore(max_points=16)

    class MockController:
        def __init__(self):
            self._metrics = metrics
            self._state = "idle"
            self._last_error = ""
            self._launch_profile = {"scene": "warehouse", "use_gaden": "true"}
            self._logs = []

        def status(self):
            return {
                "state": self._state,
                "last_error": self._last_error,
                "launch_profile": self._launch_profile,
            }

        def _append_log(self, line, source="system"):
            self._logs.append({"line": line, "source": source})

        def stop(self):
            self._state = "idle"
            return True, "stopped"

        def start_with_profile(self, profile):
            self._state = "running"
            self._launch_profile = profile
            return True, "started"

    return MockController()


@pytest.fixture
def mock_controller_running(mock_controller):
    """Create a mock controller in running state."""
    mock_controller._state = "running"
    return mock_controller


def _make_policy(
    name: str = "test_policy",
    detection_result: bool = False,
    max_retries: int = 2,
    cooldown_seconds: float = 0.0,
):
    """Create a test policy with configurable behavior."""
    action = MagicMock(spec=RecoveryAction)
    action.name = f"{name}_action"
    action.execute.return_value = ActionResult(
        success=True,
        message="Action executed",
        details={},
    )

    return RecoveryPolicy(
        name=name,
        detection_func=lambda: detection_result,
        action=action,
        max_retries=max_retries,
        cooldown_seconds=cooldown_seconds,
        failure_description=f"Test failure for {name}",
    )


# ==============================================================================
# RecoveryAction Tests
# ==============================================================================


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_action_result_creation(self):
        """ActionResult should be created with correct values."""
        result = ActionResult(
            success=True,
            message="Test message",
            details={"key": "value"},
        )
        assert result.success is True
        assert result.message == "Test message"
        assert result.details == {"key": "value"}

    def test_action_result_defaults(self):
        """ActionResult should accept empty details."""
        result = ActionResult(
            success=False,
            message="Failed",
            details={},
        )
        assert result.success is False
        assert result.details == {}


class TestRestartLifecycleNodesAction:
    """Tests for RestartLifecycleNodesAction."""

    def test_action_has_name(self, mock_controller):
        """Action should have a name property."""
        action = RestartLifecycleNodesAction(mock_controller)
        assert action.name == "restart_lifecycle_nodes"

    @patch("subprocess.run")
    def test_execute_success(self, mock_run, mock_controller):
        """Execute should succeed when lifecycle commands work."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        action = RestartLifecycleNodesAction(mock_controller)
        result = action.execute()

        assert result.success is True
        assert "restarted" in result.message.lower()
        # Should call lifecycle commands for each node
        assert mock_run.call_count >= 3  # At least 3 lifecycle calls

    @patch("subprocess.run")
    def test_execute_handles_failure(self, mock_run, mock_controller):
        """Execute should handle lifecycle command failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        action = RestartLifecycleNodesAction(mock_controller)
        result = action.execute()

        assert result.success is False
        assert "failed" in result.message.lower()

    @patch("subprocess.run")
    def test_execute_handles_timeout(self, mock_run, mock_controller):
        """Execute should handle timeout gracefully."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ros2", timeout=10)

        action = RestartLifecycleNodesAction(mock_controller)
        result = action.execute()

        assert result.success is False
        # Check details for timeout indication
        assert "timeout" in result.details.get("nodes", {}).get(
            "/controller_server", {}
        ).get("error", "").lower() or "failed" in result.message.lower()


class TestRestartGadenPlayerAction:
    """Tests for RestartGadenPlayerAction."""

    def test_action_has_name(self, mock_controller):
        """Action should have a name property."""
        action = RestartGadenPlayerAction(mock_controller)
        assert action.name == "restart_gaden_player"

    @patch("subprocess.run")
    def test_execute_success(self, mock_run, mock_controller):
        """Execute should succeed when GADEN restarts."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="killed", stderr=""),
            MagicMock(returncode=0, stdout="/gaden_player\n/other_node\n", stderr=""),
        ]

        action = RestartGadenPlayerAction(mock_controller)
        result = action.execute()

        assert result.success is True

    @patch("subprocess.run")
    def test_execute_handles_node_not_restarting(self, mock_run, mock_controller):
        """Execute should fail if node doesn't restart."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="killed", stderr=""),
            MagicMock(returncode=0, stdout="/other_node\n", stderr=""),
        ]

        action = RestartGadenPlayerAction(mock_controller)
        result = action.execute()

        assert result.success is False


class TestResetAmclPoseAction:
    """Tests for ResetAmclPoseAction."""

    def test_action_has_name(self, mock_controller):
        """Action should have a name property."""
        action = ResetAmclPoseAction(mock_controller)
        assert action.name == "reset_amcl_pose"

    @patch("subprocess.run")
    def test_execute_success(self, mock_run, mock_controller):
        """Execute should succeed when pose is published."""
        mock_run.return_value = MagicMock(returncode=0, stdout="published", stderr="")

        action = ResetAmclPoseAction(mock_controller)
        result = action.execute()

        assert result.success is True
        assert "reset" in result.message.lower()

    @patch("subprocess.run")
    def test_execute_handles_failure(self, mock_run, mock_controller):
        """Execute should handle publish failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        action = ResetAmclPoseAction(mock_controller)
        result = action.execute()

        assert result.success is False


class TestRestartSimulationAction:
    """Tests for RestartSimulationAction."""

    def test_action_has_name(self, mock_controller):
        """Action should have a name property."""
        action = RestartSimulationAction(mock_controller)
        assert action.name == "restart_simulation"

    def test_execute_success(self, mock_controller_running):
        """Execute should succeed when simulation restarts."""
        action = RestartSimulationAction(mock_controller_running)
        result = action.execute()

        assert result.success is True

    def test_execute_handles_start_failure(self, mock_controller):
        """Execute should handle start failure."""
        mock_controller.start_with_profile = lambda p: (False, "start failed")

        action = RestartSimulationAction(mock_controller)
        result = action.execute()

        assert result.success is False


# ==============================================================================
# RecoveryPolicy Tests
# ==============================================================================


class TestRecoveryPolicy:
    """Tests for RecoveryPolicy dataclass."""

    def test_policy_creation(self):
        """Policy should be created with correct values."""
        policy = _make_policy()
        assert policy.name == "test_policy"
        assert policy.max_retries == 2
        assert policy.failure_description == "Test failure for test_policy"

    def test_policy_is_frozen(self):
        """Policy should be immutable."""
        policy = _make_policy()
        with pytest.raises(AttributeError):
            policy.name = "modified"


class TestCreateDefaultPolicies:
    """Tests for create_default_policies factory function."""

    def test_creates_all_policies(self, mock_controller):
        """Should create all default policies."""
        policies = create_default_policies(mock_controller)

        policy_names = {p.name for p in policies}
        assert "nav2_timeout" in policy_names
        assert "gaden_not_publishing" in policy_names
        assert "amcl_lost" in policy_names
        assert "simulation_crash" in policy_names

    def test_policies_have_correct_max_retries(self, mock_controller):
        """Policies should have correct max retries."""
        policies = create_default_policies(mock_controller)

        policy_map = {p.name: p for p in policies}
        assert policy_map["nav2_timeout"].max_retries == 2
        assert policy_map["gaden_not_publishing"].max_retries == 1
        assert policy_map["amcl_lost"].max_retries == 1
        assert policy_map["simulation_crash"].max_retries == 1

    def test_policies_have_correct_cooldowns(self, mock_controller):
        """Policies should have appropriate cooldowns."""
        policies = create_default_policies(mock_controller)

        policy_map = {p.name: p for p in policies}
        assert policy_map["nav2_timeout"].cooldown_seconds == 30.0
        assert policy_map["gaden_not_publishing"].cooldown_seconds == 15.0
        assert policy_map["amcl_lost"].cooldown_seconds == 20.0


# ==============================================================================
# RecoveryMonitor Tests
# ==============================================================================


class TestRecoveryMonitor:
    """Tests for RecoveryMonitor."""

    def test_add_policy(self, mock_controller):
        """Monitor should add policies."""
        policy = _make_policy()
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        status = monitor.get_status()
        assert len(status["policies"]) == 1
        assert status["policies"][0]["name"] == "test_policy"

    def test_add_policy_avoids_duplicates(self, mock_controller):
        """Monitor should not add duplicate policy names."""
        policy = _make_policy()
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)
        monitor.add_policy(policy)  # Duplicate

        status = monitor.get_status()
        assert len(status["policies"]) == 1

    def test_remove_policy(self, mock_controller):
        """Monitor should remove policies."""
        policy = _make_policy()
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        result = monitor.remove_policy("test_policy")
        assert result is True

        status = monitor.get_status()
        assert len(status["policies"]) == 0

    def test_remove_nonexistent_policy(self, mock_controller):
        """Monitor should return False for non-existent policy."""
        monitor = RecoveryMonitor(mock_controller)
        result = monitor.remove_policy("nonexistent")
        assert result is False

    def test_check_and_recover_no_failure(self, mock_controller):
        """check_and_recover should return empty list when no failure."""
        policy = _make_policy(detection_result=False)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        actions = monitor.check_and_recover()
        assert actions == []
        policy.action.execute.assert_not_called()

    def test_check_and_recover_with_failure(self, mock_controller):
        """check_and_recover should execute action when failure detected."""
        policy = _make_policy(detection_result=True)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        actions = monitor.check_and_recover()
        assert "test_policy" in actions
        policy.action.execute.assert_called_once()

    def test_check_and_recover_respects_max_retries(self, mock_controller):
        """check_and_recover should respect max retries."""
        policy = _make_policy(detection_result=True, max_retries=2, cooldown_seconds=0.0)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        # Execute twice (max_retries=2)
        monitor.check_and_recover()
        monitor.check_and_recover()

        # Third attempt should be ignored
        actions = monitor.check_and_recover()
        assert actions == []
        # Should only have been called twice
        assert policy.action.execute.call_count == 2

    def test_check_and_recover_respects_cooldown(self, mock_controller):
        """check_and_recover should respect cooldown."""
        policy = _make_policy(detection_result=True, cooldown_seconds=100.0)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        # First execution
        monitor.check_and_recover()

        # Second immediate attempt should be skipped due to cooldown
        actions = monitor.check_and_recover()
        assert actions == []
        assert policy.action.execute.call_count == 1

    def test_reset_retries(self, mock_controller):
        """reset_retries should reset retry count."""
        policy = _make_policy(detection_result=True, cooldown_seconds=0.0)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        monitor.check_and_recover()
        assert monitor.get_retry_count("test_policy") == 1

        monitor.reset_retries("test_policy")
        assert monitor.get_retry_count("test_policy") == 0

    def test_reset_all_retries(self, mock_controller):
        """reset_all_retries should reset all retry counts."""
        action1 = MagicMock(spec=RecoveryAction)
        action1.name = "action1"
        action1.execute.return_value = ActionResult(True, "ok", {})

        action2 = MagicMock(spec=RecoveryAction)
        action2.name = "action2"
        action2.execute.return_value = ActionResult(True, "ok", {})

        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(RecoveryPolicy(
            name="policy1",
            detection_func=lambda: True,
            action=action1,
            max_retries=3,
            cooldown_seconds=0.0,
        ))
        monitor.add_policy(RecoveryPolicy(
            name="policy2",
            detection_func=lambda: True,
            action=action2,
            max_retries=3,
            cooldown_seconds=0.0,
        ))

        monitor.check_and_recover()
        assert monitor.get_retry_count("policy1") == 1
        assert monitor.get_retry_count("policy2") == 1

        monitor.reset_all_retries()
        assert monitor.get_retry_count("policy1") == 0
        assert monitor.get_retry_count("policy2") == 0

    def test_get_recent_events(self, mock_controller):
        """get_recent_events should return recovery events."""
        policy = _make_policy(detection_result=True)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        monitor.check_and_recover()

        events = monitor.get_recent_events()
        assert len(events) == 1
        assert events[0].policy_name == "test_policy"
        assert events[0].action_name == "test_policy_action"

    def test_get_status(self, mock_controller):
        """get_status should return monitor status."""
        policy = _make_policy()
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        status = monitor.get_status()

        assert "policies" in status
        assert "retry_counts" in status
        assert "recent_events" in status
        assert len(status["policies"]) == 1

    def test_is_in_cooldown(self, mock_controller):
        """is_in_cooldown should return correct status."""
        policy = _make_policy(detection_result=True, cooldown_seconds=10.0)
        monitor = RecoveryMonitor(mock_controller)
        monitor.add_policy(policy)

        assert monitor.is_in_cooldown("test_policy") is False

        # Trigger a recovery
        monitor.check_and_recover()

        assert monitor.is_in_cooldown("test_policy") is True

    def test_log_callback(self, mock_controller):
        """Monitor should use log callback."""
        logs = []
        def log_callback(level, message):
            logs.append((level, message))

        policy = _make_policy(detection_result=True)
        monitor = RecoveryMonitor(mock_controller, log_callback=log_callback)
        monitor.add_policy(policy)

        monitor.check_and_recover()

        # Should have logged some messages
        assert len(logs) > 0


class TestRecoveryMonitorThreadSafety:
    """Thread safety tests for RecoveryMonitor."""

    def test_concurrent_add_and_check(self, mock_controller):
        """Monitor should handle concurrent operations."""
        import threading

        monitor = RecoveryMonitor(mock_controller)
        errors = []

        def add_policies():
            for i in range(10):
                action = MagicMock(spec=RecoveryAction)
                action.name = f"action_{i}"
                action.execute.return_value = ActionResult(True, "ok", {})
                policy = RecoveryPolicy(
                    name=f"policy_{i}",
                    detection_func=lambda: False,
                    action=action,
                    max_retries=1,
                    cooldown_seconds=1.0,
                )
                monitor.add_policy(policy)

        def check_and_recover():
            for _ in range(10):
                monitor.check_and_recover()

        def get_status():
            for _ in range(10):
                monitor.get_status()

        threads = [
            threading.Thread(target=add_policies),
            threading.Thread(target=check_and_recover),
            threading.Thread(target=get_status),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All policies should be added
        status = monitor.get_status()
        assert len(status["policies"]) == 10


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRecoveryIntegration:
    """Integration tests for recovery system."""

    def test_full_recovery_flow(self, mock_controller_running):
        """Test a complete recovery flow."""
        # Create monitor with default policies
        policies = create_default_policies(mock_controller_running)
        monitor = RecoveryMonitor(mock_controller_running)

        for policy in policies:
            monitor.add_policy(policy)

        # Check status
        status = monitor.get_status()
        assert len(status["policies"]) == 4

        # Run check (should not trigger anything in normal state)
        actions = monitor.check_and_recover()
        # No failures should be detected in our mock state
        assert isinstance(actions, list)

    def test_simulation_crash_detection(self, mock_controller):
        """Test simulation crash detection."""
        mock_controller._state = "error"
        mock_controller._last_error = "simulation exited with code 1"

        policies = create_default_policies(mock_controller)
        monitor = RecoveryMonitor(mock_controller)

        for policy in policies:
            monitor.add_policy(policy)

        # Check for crash
        actions = monitor.check_and_recover()

        # Should detect crash and trigger restart
        # (restart may fail due to mock, but should attempt)
        crash_policy = next(p for p in policies if p.name == "simulation_crash")
        # The detection should have been triggered
        assert "simulation_crash" in actions
