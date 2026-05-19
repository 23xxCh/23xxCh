"""Recovery policies and rules for automatic failure handling.

This module defines RecoveryPolicy dataclass for configuring failure detection
and recovery behavior, along with factory functions for standard policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .actions import RecoveryAction


@dataclass(frozen=True)
class RecoveryPolicy:
    """Immutable policy for detecting and recovering from failures.

    Attributes:
        name: Human-readable policy name (e.g., "nav2_timeout")
        detection_func: Function that returns True if failure is detected
        action: RecoveryAction to execute when failure is detected
        max_retries: Maximum number of recovery attempts before giving up
        cooldown_seconds: Minimum time between recovery attempts
        failure_description: Human-readable description of the failure
    """

    name: str
    detection_func: Callable[[], bool]
    action: RecoveryAction
    max_retries: int
    cooldown_seconds: float
    failure_description: str = ""


def create_default_policies(
    controller,
    *,
    nav2_timeout_sec: float = 60.0,
    gaden_timeout_sec: float = 5.0,
    amcl_timeout_sec: float = 10.0,
) -> list[RecoveryPolicy]:
    """Create the default set of recovery policies.

    Args:
        controller: SimulationController instance for action execution
        nav2_timeout_sec: Seconds without navigation before Nav2 timeout
        gaden_timeout_sec: Seconds without gas data before GADEN timeout
        amcl_timeout_sec: Seconds without pose updates before AMCL timeout

    Returns:
        List of RecoveryPolicy instances for standard failure types
    """
    from .actions import (
        ResetAmclPoseAction,
        RestartGadenPlayerAction,
        RestartLifecycleNodesAction,
        RestartSimulationAction,
    )

    # Track last known values for detection
    state = {
        "last_nav_activity": 0.0,
        "last_gas_update": 0.0,
        "last_amcl_update": 0.0,
        "simulation_running": False,
    }

    def detect_nav2_timeout() -> bool:
        """Detect Nav2 navigation timeout.

        Returns True if:
        - Simulation is running
        - Nav2 nodes are up
        - No navigation activity for nav2_timeout_sec
        """
        if not state.get("simulation_running", False):
            return False
        # Check metrics store for navigation staleness
        snapshot = controller.metrics_snapshot(limit=10)
        topic_health = snapshot.get("topic_health", {})
        nav_status = controller.status()
        if nav_status.get("state") != "running":
            return False

        # Check if Nav2 nodes are running but navigation is stale
        node_health = snapshot.get("node_health", {}).get("nodes", [])
        nav2_nodes = [
            n for n in node_health
            if n.get("name", "") in ["/controller_server", "/planner_server", "/bt_navigator"]
        ]
        if not nav2_nodes:
            return False
        nav2_up = all(n.get("up", False) for n in nav2_nodes)
        if not nav2_up:
            return False

        # Check navigation activity via current goal age
        nav_data = snapshot.get("nav", {})
        current_goal_age = nav_data.get("current_goal_age_sec")
        # If no current goal and no recent succeeded goals, might be stuck
        goal_succeeded = nav_data.get("goal_succeeded", 0)
        # More sophisticated: check if we're in SEEK mode but not moving
        mode = snapshot.get("mode", {}).get("current")
        if mode in ["SEEK_TRACK", "SEEK_CONFIRM"]:
            gas_stale = topic_health.get("/gas_concentration", {}).get("stale_sec", 0)
            if gas_stale > nav2_timeout_sec:
                return True
        return False

    def detect_gaden_not_publishing() -> bool:
        """Detect GADEN sensor not publishing.

        Returns True if:
        - Simulation is running with GADEN enabled
        - No gas data for gaden_timeout_sec
        """
        nav_status = controller.status()
        if nav_status.get("state") != "running":
            return False
        profile = nav_status.get("launch_profile", {})
        if profile.get("use_gaden", "true") != "true":
            return False

        snapshot = controller.metrics_snapshot(limit=10)
        topic_health = snapshot.get("topic_health", {})
        gas_stale = topic_health.get("/gas_concentration", {}).get("stale_sec", 0)
        raw_stale = topic_health.get("/gaden/sensor_reading", {}).get("stale_sec", 0)

        # Both topics stale indicates GADEN issue
        return gas_stale > gaden_timeout_sec or raw_stale > gaden_timeout_sec

    def detect_amcl_lost() -> bool:
        """Detect AMCL localization lost.

        Returns True if:
        - Simulation is running
        - No pose updates for amcl_timeout_sec
        """
        nav_status = controller.status()
        if nav_status.get("state") != "running":
            return False

        snapshot = controller.metrics_snapshot(limit=10)
        topic_health = snapshot.get("topic_health", {})
        odom_stale = topic_health.get("/odom", {}).get("stale_sec", 0)

        return odom_stale > amcl_timeout_sec

    def detect_simulation_crash() -> bool:
        """Detect simulation process crash.

        Returns True if:
        - Controller state shows error
        - Process exited unexpectedly
        """
        nav_status = controller.status()
        state = nav_status.get("state", "")
        last_error = nav_status.get("last_error", "")
        # Check for crash indicators
        if state == "error" and "exited with code" in last_error.lower():
            return True
        return False

    return [
        RecoveryPolicy(
            name="nav2_timeout",
            detection_func=detect_nav2_timeout,
            action=RestartLifecycleNodesAction(controller),
            max_retries=2,
            cooldown_seconds=30.0,
            failure_description="No navigation activity for 60 seconds",
        ),
        RecoveryPolicy(
            name="gaden_not_publishing",
            detection_func=detect_gaden_not_publishing,
            action=RestartGadenPlayerAction(controller),
            max_retries=1,
            cooldown_seconds=15.0,
            failure_description="No gas data for 5 seconds",
        ),
        RecoveryPolicy(
            name="amcl_lost",
            detection_func=detect_amcl_lost,
            action=ResetAmclPoseAction(controller),
            max_retries=1,
            cooldown_seconds=20.0,
            failure_description="No pose updates for 10 seconds",
        ),
        RecoveryPolicy(
            name="simulation_crash",
            detection_func=detect_simulation_crash,
            action=RestartSimulationAction(controller),
            max_retries=1,
            cooldown_seconds=10.0,
            failure_description="Simulation process exited unexpectedly",
        ),
    ]
