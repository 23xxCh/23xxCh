"""Recovery monitor for detecting failures and triggering recovery actions.

This module provides the RecoveryMonitor class which:
- Periodically checks for failures using registered policies
- Executes recovery actions when failures are detected
- Tracks retry counts and cooldowns per policy
- Logs all recovery events
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from .actions import ActionResult
from .policies import RecoveryPolicy

if TYPE_CHECKING:
    from ..web.simulation_controller import SimulationController


def _now_iso() -> str:
    """Return current time as ISO format string with timezone."""
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class RecoveryEvent:
    """Record of a recovery event.

    Attributes:
        timestamp: When the event occurred
        policy_name: Name of the policy that triggered
        action_name: Name of the action executed
        success: Whether the recovery succeeded
        message: Result message
        retry_count: Current retry count after this event
    """

    timestamp: str
    policy_name: str
    action_name: str
    success: bool
    message: str
    retry_count: int


@dataclass
class RecoveryMonitorState:
    """Internal state for tracking recovery attempts.

    Attributes:
        retry_counts: Map of policy name to retry count
        last_attempt_times: Map of policy name to last attempt timestamp
        events: List of recent recovery events
    """

    retry_counts: dict[str, int] = field(default_factory=dict)
    last_attempt_times: dict[str, float] = field(default_factory=dict)
    events: list[RecoveryEvent] = field(default_factory=list)
    max_events: int = 100


class RecoveryMonitor:
    """Monitors system health and triggers recovery actions.

    This class provides:
    - Policy registration for different failure types
    - Failure detection via registered detection functions
    - Recovery action execution with retry limits
    - Cooldown enforcement between recovery attempts
    - Event logging for auditing

    Thread Safety:
        All public methods are thread-safe.

    Usage:
        monitor = RecoveryMonitor(controller)
        monitor.add_policy(nav2_policy)
        monitor.add_policy(gaden_policy)

        # In a background thread:
        while running:
            actions = monitor.check_and_recover()
            time.sleep(5.0)
    """

    def __init__(
        self,
        controller: "SimulationController",
        *,
        max_events: int = 100,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        """Initialize the recovery monitor.

        Args:
            controller: SimulationController instance
            max_events: Maximum number of events to retain
            log_callback: Optional callback for logging (level, message)
        """
        self._controller = controller
        self._lock = threading.Lock()
        self._policies: list[RecoveryPolicy] = []
        self._state = RecoveryMonitorState(max_events=max_events)
        self._log_callback = log_callback

    def _log(self, level: str, message: str) -> None:
        """Log a message via the configured callback.

        Args:
            level: Log level (info, warning, error)
            message: Log message
        """
        if self._log_callback is not None:
            self._log_callback(level, message)
        # Also append to controller logs if available
        try:
            self._controller._append_log(f"[recovery] {message}", source="recovery")
        except Exception:
            pass

    def add_policy(self, policy: RecoveryPolicy) -> None:
        """Register a recovery policy.

        Args:
            policy: RecoveryPolicy to add
        """
        with self._lock:
            # Avoid duplicate policy names
            existing_names = {p.name for p in self._policies}
            if policy.name in existing_names:
                return
            self._policies.append(policy)
            self._state.retry_counts[policy.name] = 0

    def remove_policy(self, policy_name: str) -> bool:
        """Remove a registered policy.

        Args:
            policy_name: Name of the policy to remove

        Returns:
            True if policy was removed, False if not found
        """
        with self._lock:
            for i, p in enumerate(self._policies):
                if p.name == policy_name:
                    self._policies.pop(i)
                    return True
            return False

    def check_and_recover(self) -> list[str]:
        """Check all policies and execute recovery if needed.

        This method:
        1. Iterates through all registered policies
        2. Calls detection functions to identify failures
        3. Checks retry limits and cooldowns
        4. Executes recovery actions as needed
        5. Logs all events

        Returns:
            List of policy names that triggered recovery
        """
        actions_taken: list[str] = []
        now = time.monotonic()

        with self._lock:
            policies = list(self._policies)

        for policy in policies:
            try:
                # Check if failure is detected
                if not policy.detection_func():
                    continue

                with self._lock:
                    # Check retry limit
                    retry_count = self._state.retry_counts.get(policy.name, 0)
                    if retry_count >= policy.max_retries:
                        self._log(
                            "warning",
                            f"Policy '{policy.name}' exceeded max retries ({policy.max_retries}), skipping"
                        )
                        continue

                    # Check cooldown
                    last_attempt = self._state.last_attempt_times.get(policy.name, 0.0)
                    if now - last_attempt < policy.cooldown_seconds:
                        continue

                    # Update state before recovery
                    self._state.last_attempt_times[policy.name] = now

                # Execute recovery action (outside lock to avoid blocking)
                self._log(
                    "info",
                    f"Failure detected: {policy.failure_description}, executing recovery action: {policy.action.name}"
                )

                result: ActionResult = policy.action.execute()

                with self._lock:
                    if result.success:
                        self._state.retry_counts[policy.name] = retry_count + 1
                        self._log("info", f"Recovery succeeded for '{policy.name}': {result.message}")
                    else:
                        self._state.retry_counts[policy.name] = retry_count + 1
                        self._log("error", f"Recovery failed for '{policy.name}': {result.message}")

                    # Record event
                    event = RecoveryEvent(
                        timestamp=_now_iso(),
                        policy_name=policy.name,
                        action_name=policy.action.name,
                        success=result.success,
                        message=result.message,
                        retry_count=self._state.retry_counts[policy.name],
                    )
                    self._state.events.append(event)
                    if len(self._state.events) > self._state.max_events:
                        self._state.events.pop(0)

                actions_taken.append(policy.name)

            except Exception as e:
                self._log("error", f"Error checking policy '{policy.name}': {e}")

        return actions_taken

    def reset_retries(self, policy_name: str) -> None:
        """Reset the retry count for a specific policy.

        This should be called when the system has been healthy for a period,
        allowing recovery to be attempted again if a new failure occurs.

        Args:
            policy_name: Name of the policy to reset
        """
        with self._lock:
            if policy_name in self._state.retry_counts:
                self._state.retry_counts[policy_name] = 0
                self._log("info", f"Reset retry count for policy '{policy_name}'")

    def reset_all_retries(self) -> None:
        """Reset retry counts for all policies."""
        with self._lock:
            for name in list(self._state.retry_counts.keys()):
                self._state.retry_counts[name] = 0
            self._log("info", "Reset retry counts for all policies")

    def get_retry_count(self, policy_name: str) -> int:
        """Get the current retry count for a policy.

        Args:
            policy_name: Name of the policy

        Returns:
            Current retry count, or 0 if policy not found
        """
        with self._lock:
            return self._state.retry_counts.get(policy_name, 0)

    def get_recent_events(self, limit: int = 20) -> list[RecoveryEvent]:
        """Get recent recovery events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent RecoveryEvent instances
        """
        with self._lock:
            return list(self._state.events[-limit:])

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the recovery monitor.

        Returns:
            Dictionary with policies, retry_counts, and recent_events
        """
        with self._lock:
            return {
                "policies": [
                    {
                        "name": p.name,
                        "max_retries": p.max_retries,
                        "cooldown_seconds": p.cooldown_seconds,
                        "failure_description": p.failure_description,
                    }
                    for p in self._policies
                ],
                "retry_counts": dict(self._state.retry_counts),
                "recent_events": [
                    {
                        "timestamp": e.timestamp,
                        "policy_name": e.policy_name,
                        "action_name": e.action_name,
                        "success": e.success,
                        "message": e.message,
                        "retry_count": e.retry_count,
                    }
                    for e in self._state.events[-10:]
                ],
            }

    def is_in_cooldown(self, policy_name: str) -> bool:
        """Check if a policy is currently in cooldown.

        Args:
            policy_name: Name of the policy to check

        Returns:
            True if policy is in cooldown, False otherwise
        """
        now = time.monotonic()
        with self._lock:
            for p in self._policies:
                if p.name == policy_name:
                    last_attempt = self._state.last_attempt_times.get(policy_name, 0.0)
                    return now - last_attempt < p.cooldown_seconds
            return False
