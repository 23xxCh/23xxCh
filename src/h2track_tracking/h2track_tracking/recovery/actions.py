"""Recovery action implementations for automatic failure handling.

This module defines the RecoveryAction protocol and concrete implementations
for various failure types (Nav2, GADEN, AMCL, simulation crash).
"""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..web.simulation_controller import SimulationController


@dataclass(frozen=True)
class ActionResult:
    """Result of a recovery action execution.

    Attributes:
        success: Whether the action completed successfully
        message: Human-readable result message
        details: Additional details about the action taken
    """

    success: bool
    message: str
    details: dict[str, Any]


class RecoveryAction(ABC):
    """Abstract base class for recovery actions.

    All recovery actions must implement the execute() method.
    Actions should be idempotent and safe to retry.
    """

    @abstractmethod
    def execute(self) -> ActionResult:
        """Execute the recovery action.

        Returns:
            ActionResult indicating success/failure and details
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the action name for logging."""
        ...


class RestartLifecycleNodesAction(RecoveryAction):
    """Restart Nav2 lifecycle nodes to recover from navigation failures.

    This action restarts key Nav2 lifecycle nodes:
    - controller_server
    - planner_server
    - bt_navigator
    """

    def __init__(self, controller: "SimulationController") -> None:
        """Initialize with a reference to the simulation controller.

        Args:
            controller: SimulationController instance
        """
        self._controller = controller

    @property
    def name(self) -> str:
        return "restart_lifecycle_nodes"

    def execute(self) -> ActionResult:
        """Restart Nav2 lifecycle nodes.

        Returns:
            ActionResult with success status and details
        """
        nodes = [
            "/controller_server",
            "/planner_server",
            "/bt_navigator",
        ]
        results: dict[str, dict[str, Any]] = {}
        all_success = True

        for node in nodes:
            try:
                # Set node to inactive
                set_inactive = subprocess.run(
                    ["ros2", "lifecycle", "set", node, "inactive"],
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )
                time.sleep(0.5)

                # Set node to cleanup
                cleanup = subprocess.run(
                    ["ros2", "lifecycle", "set", node, "cleanup"],
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )
                time.sleep(0.5)

                # Set node to active
                set_active = subprocess.run(
                    ["ros2", "lifecycle", "set", node, "active"],
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )

                success = set_active.returncode == 0
                if not success:
                    all_success = False

                results[node] = {
                    "success": success,
                    "stderr": set_active.stderr or "",
                }
            except subprocess.TimeoutExpired:
                results[node] = {
                    "success": False,
                    "error": "Timeout during lifecycle operation",
                }
                all_success = False
            except Exception as e:
                results[node] = {
                    "success": False,
                    "error": str(e),
                }
                all_success = False

        if all_success:
            return ActionResult(
                success=True,
                message="Successfully restarted all Nav2 lifecycle nodes",
                details={"nodes": results},
            )
        return ActionResult(
            success=False,
            message="Failed to restart some Nav2 lifecycle nodes",
            details={"nodes": results},
        )


class RestartGadenPlayerAction(RecoveryAction):
    """Restart GADEN player to recover from gas simulation failures.

    This action restarts the GADEN player node to recover from
    situations where gas data stops publishing.
    """

    def __init__(self, controller: "SimulationController") -> None:
        """Initialize with a reference to the simulation controller.

        Args:
            controller: SimulationController instance
        """
        self._controller = controller

    @property
    def name(self) -> str:
        return "restart_gaden_player"

    def execute(self) -> ActionResult:
        """Restart GADEN player node.

        Returns:
            ActionResult with success status and details
        """
        try:
            # Kill existing gaden_player node
            kill_result = subprocess.run(
                ["ros2", "node", "kill", "/gaden_player"],
                capture_output=True,
                text=True,
                timeout=10.0,
            )

            # Give it time to restart (assuming it's managed by a lifecycle manager)
            time.sleep(2.0)

            # Check if node is back up
            list_result = subprocess.run(
                ["ros2", "node", "list"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if list_result.returncode == 0 and "/gaden_player" in list_result.stdout:
                return ActionResult(
                    success=True,
                    message="GADEN player restarted successfully",
                    details={
                        "kill_output": kill_result.stdout or "",
                        "node_list": list_result.stdout,
                    },
                )
            return ActionResult(
                success=False,
                message="GADEN player did not restart",
                details={
                    "kill_output": kill_result.stdout or "",
                    "kill_stderr": kill_result.stderr or "",
                },
            )
        except subprocess.TimeoutExpired:
            return ActionResult(
                success=False,
                message="Timeout while restarting GADEN player",
                details={},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error restarting GADEN player: {e}",
                details={"error": str(e)},
            )


class ResetAmclPoseAction(RecoveryAction):
    """Reset AMCL pose to recover from localization loss.

    This action resets the AMCL localization to a known initial pose,
    typically the starting position defined in the scene configuration.
    """

    def __init__(self, controller: "SimulationController") -> None:
        """Initialize with a reference to the simulation controller.

        Args:
            controller: SimulationController instance
        """
        self._controller = controller

    @property
    def name(self) -> str:
        return "reset_amcl_pose"

    def execute(self) -> ActionResult:
        """Reset AMCL pose to initial position.

        Returns:
            ActionResult with success status and details
        """
        try:
            # Get initial pose from launch profile or use defaults
            profile = self._controller.status().get("launch_profile", {})
            # Default initial pose (can be configured per scene)
            initial_x = 0.0
            initial_y = 0.0
            initial_yaw = 0.0

            # Publish initial pose
            result = subprocess.run(
                [
                    "ros2", "topic", "pub", "--once",
                    "/initialpose",
                    "geometry_msgs/msg/PoseWithCovarianceStamped",
                    (
                        "{"
                        f'"header": {{"frame_id": "map"}}, '
                        f'"pose": {{"pose": {{"position": {{"x": {initial_x}, "y": {initial_y}, "z": 0.0}}, '
                        f'"orientation": {{"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}}}}}'
                        "}"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10.0,
            )

            if result.returncode == 0:
                return ActionResult(
                    success=True,
                    message=f"AMCL pose reset to ({initial_x}, {initial_y})",
                    details={
                        "x": initial_x,
                        "y": initial_y,
                        "yaw": initial_yaw,
                        "output": result.stdout or "",
                    },
                )
            return ActionResult(
                success=False,
                message="Failed to publish initial pose",
                details={"stderr": result.stderr or ""},
            )
        except subprocess.TimeoutExpired:
            return ActionResult(
                success=False,
                message="Timeout while resetting AMCL pose",
                details={},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error resetting AMCL pose: {e}",
                details={"error": str(e)},
            )


class RestartSimulationAction(RecoveryAction):
    """Restart the entire simulation to recover from critical failures.

    This action stops and restarts the simulation when other recovery
    actions have failed or the simulation has crashed.
    """

    def __init__(self, controller: "SimulationController") -> None:
        """Initialize with a reference to the simulation controller.

        Args:
            controller: SimulationController instance
        """
        self._controller = controller

    @property
    def name(self) -> str:
        return "restart_simulation"

    def execute(self) -> ActionResult:
        """Restart the simulation.

        Returns:
            ActionResult with success status and details
        """
        try:
            # Get current profile before stopping
            profile = self._controller.status().get("launch_profile", {})

            # Stop current simulation
            stop_ok, stop_msg = self._controller.stop()

            if not stop_ok:
                # Try to stop anyway if simulation is not running
                pass

            # Wait for cleanup
            time.sleep(3.0)

            # Start with same profile
            start_ok, start_msg = self._controller.start_with_profile(profile)

            if start_ok:
                return ActionResult(
                    success=True,
                    message="Simulation restarted successfully",
                    details={
                        "stop_result": stop_msg,
                        "start_result": start_msg,
                    },
                )
            return ActionResult(
                success=False,
                message=f"Failed to restart simulation: {start_msg}",
                details={
                    "stop_result": stop_msg,
                    "start_result": start_msg,
                },
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error restarting simulation: {e}",
                details={"error": str(e)},
            )
