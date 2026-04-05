"""Thread-safe registry for multi-robot state tracking.

This module provides the RobotRegistry class for managing:
- Robot registration and unregistration
- Robot state updates (pose, mode, gas reading)
- Fleet-wide state queries

All operations are thread-safe for use in concurrent ROS environments.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class Pose2D:
    """2D pose representation for robot position and orientation.

    Attributes:
        x: X coordinate in meters
        y: Y coordinate in meters
        yaw: Orientation in radians
    """

    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert pose to dictionary representation."""
        return {"x": self.x, "y": self.y, "yaw": self.yaw}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pose2D:
        """Create Pose2D from dictionary."""
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            yaw=float(data.get("yaw", 0.0)),
        )


@dataclass(frozen=True)
class RobotState:
    """Immutable snapshot of a robot's state.

    This dataclass captures all relevant state for a single robot
    at a point in time. Being frozen ensures thread-safe reads
    and prevents accidental mutation.

    Attributes:
        robot_id: Unique identifier for the robot
        namespace: ROS namespace the robot operates in
        mode: Current mission mode (PATROL, SEEK_CONFIRM, SEEK_TRACK, SOURCE_FOUND)
        pose: 2D position and orientation
        gas_reading: Current gas concentration reading (normalized 0.0-1.0)
        last_updated: UTC timestamp of last state update
    """

    robot_id: str
    namespace: str
    mode: str
    pose: Pose2D
    gas_reading: float
    last_updated: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary representation for serialization."""
        return {
            "robot_id": self.robot_id,
            "namespace": self.namespace,
            "mode": self.mode,
            "pose": self.pose.to_dict(),
            "gas_reading": self.gas_reading,
            "last_updated": self.last_updated.isoformat(),
        }


class RobotRegistry:
    """Thread-safe registry for tracking multiple robots.

    This class manages the state of multiple robots in the system.
    All operations are protected by an internal lock for thread safety.

    Usage:
        registry = RobotRegistry()

        # Register a new robot
        registry.register("robot_1", "/robot_1")

        # Update robot state
        state = RobotState(
            robot_id="robot_1",
            namespace="/robot_1",
            mode="PATROL",
            pose=Pose2D(x=1.0, y=2.0, yaw=0.5),
            gas_reading=0.42,
            last_updated=_now_utc(),
        )
        registry.update_state("robot_1", state)

        # Query robot state
        current = registry.get_state("robot_1")

        # List all robots
        all_robots = registry.list_robots()

        # Unregister when done
        registry.unregister("robot_1")
    """

    def __init__(self) -> None:
        """Initialize an empty robot registry."""
        self._lock = threading.Lock()
        self._robots: dict[str, RobotState] = {}
        self._namespaces: dict[str, str] = {}  # robot_id -> namespace mapping
        self._updated_at = _now_utc()

    def _touch(self) -> None:
        """Update the last modification timestamp."""
        self._updated_at = _now_utc()

    def register(self, robot_id: str, namespace: str) -> None:
        """Register a new robot in the registry.

        Creates an initial state for the robot with default values.
        If the robot is already registered, this is a no-op.

        Args:
            robot_id: Unique identifier for the robot
            namespace: ROS namespace for the robot (e.g., "/robot_1")
        """
        if not robot_id or not robot_id.strip():
            raise ValueError("robot_id cannot be empty")
        if not namespace or not namespace.strip():
            raise ValueError("namespace cannot be empty")

        robot_id = robot_id.strip()
        namespace = namespace.strip()

        with self._lock:
            if robot_id in self._robots:
                return  # Already registered, no-op

            initial_state = RobotState(
                robot_id=robot_id,
                namespace=namespace,
                mode="INIT",
                pose=Pose2D(),
                gas_reading=0.0,
                last_updated=_now_utc(),
            )
            self._robots[robot_id] = initial_state
            self._namespaces[robot_id] = namespace
            self._touch()

    def unregister(self, robot_id: str) -> bool:
        """Remove a robot from the registry.

        Args:
            robot_id: Unique identifier of the robot to remove

        Returns:
            True if the robot was removed, False if it wasn't registered
        """
        with self._lock:
            if robot_id not in self._robots:
                return False

            del self._robots[robot_id]
            del self._namespaces[robot_id]
            self._touch()
            return True

    def update_state(self, robot_id: str, state: RobotState) -> None:
        """Update the state of a registered robot.

        The state's robot_id must match the provided robot_id.

        Args:
            robot_id: Unique identifier of the robot to update
            state: New state for the robot

        Raises:
            KeyError: If the robot is not registered
            ValueError: If state.robot_id doesn't match robot_id
        """
        with self._lock:
            if robot_id not in self._robots:
                raise KeyError(f"Robot '{robot_id}' is not registered")

            if state.robot_id != robot_id:
                raise ValueError(
                    f"State robot_id '{state.robot_id}' doesn't match "
                    f"provided robot_id '{robot_id}'"
                )

            self._robots[robot_id] = state
            self._touch()

    def update_pose(self, robot_id: str, pose: Pose2D) -> None:
        """Update only the pose of a registered robot.

        Convenience method for updating pose without constructing
        a full RobotState object.

        Args:
            robot_id: Unique identifier of the robot to update
            pose: New pose for the robot

        Raises:
            KeyError: If the robot is not registered
        """
        with self._lock:
            if robot_id not in self._robots:
                raise KeyError(f"Robot '{robot_id}' is not registered")

            current = self._robots[robot_id]
            updated = RobotState(
                robot_id=current.robot_id,
                namespace=current.namespace,
                mode=current.mode,
                pose=pose,
                gas_reading=current.gas_reading,
                last_updated=_now_utc(),
            )
            self._robots[robot_id] = updated
            self._touch()

    def update_mode(self, robot_id: str, mode: str) -> None:
        """Update only the mode of a registered robot.

        Args:
            robot_id: Unique identifier of the robot to update
            mode: New mission mode

        Raises:
            KeyError: If the robot is not registered
        """
        with self._lock:
            if robot_id not in self._robots:
                raise KeyError(f"Robot '{robot_id}' is not registered")

            current = self._robots[robot_id]
            updated = RobotState(
                robot_id=current.robot_id,
                namespace=current.namespace,
                mode=mode,
                pose=current.pose,
                gas_reading=current.gas_reading,
                last_updated=_now_utc(),
            )
            self._robots[robot_id] = updated
            self._touch()

    def update_gas_reading(self, robot_id: str, gas_reading: float) -> None:
        """Update only the gas reading of a registered robot.

        Args:
            robot_id: Unique identifier of the robot to update
            gas_reading: New gas concentration reading

        Raises:
            KeyError: If the robot is not registered
        """
        with self._lock:
            if robot_id not in self._robots:
                raise KeyError(f"Robot '{robot_id}' is not registered")

            current = self._robots[robot_id]
            updated = RobotState(
                robot_id=current.robot_id,
                namespace=current.namespace,
                mode=current.mode,
                pose=current.pose,
                gas_reading=gas_reading,
                last_updated=_now_utc(),
            )
            self._robots[robot_id] = updated
            self._touch()

    def get_state(self, robot_id: str) -> RobotState | None:
        """Get the current state of a robot.

        Args:
            robot_id: Unique identifier of the robot

        Returns:
            Current RobotState, or None if robot is not registered
        """
        with self._lock:
            return self._robots.get(robot_id)

    def get_namespace(self, robot_id: str) -> str | None:
        """Get the ROS namespace of a robot.

        Args:
            robot_id: Unique identifier of the robot

        Returns:
            Namespace string, or None if robot is not registered
        """
        with self._lock:
            return self._namespaces.get(robot_id)

    def list_robots(self) -> list[RobotState]:
        """Get a list of all registered robots and their states.

        Returns:
            List of RobotState objects for all registered robots
        """
        with self._lock:
            return list(self._robots.values())

    def list_robot_ids(self) -> list[str]:
        """Get a list of all registered robot IDs.

        Returns:
            List of robot_id strings
        """
        with self._lock:
            return list(self._robots.keys())

    def count(self) -> int:
        """Get the number of registered robots.

        Returns:
            Number of robots currently registered
        """
        with self._lock:
            return len(self._robots)

    def is_registered(self, robot_id: str) -> bool:
        """Check if a robot is registered.

        Args:
            robot_id: Unique identifier to check

        Returns:
            True if robot is registered, False otherwise
        """
        with self._lock:
            return robot_id in self._robots

    def clear(self) -> None:
        """Remove all robots from the registry."""
        with self._lock:
            self._robots.clear()
            self._namespaces.clear()
            self._touch()

    @property
    def updated_at(self) -> datetime:
        """Get the timestamp of the last modification."""
        with self._lock:
            return self._updated_at

    def snapshot(self) -> dict[str, Any]:
        """Generate a snapshot of the registry state.

        Returns:
            Dictionary containing all robots and their states,
            suitable for JSON serialization.
        """
        with self._lock:
            return {
                "robots": {
                    robot_id: state.to_dict()
                    for robot_id, state in self._robots.items()
                },
                "robot_ids": list(self._robots.keys()),
                "count": len(self._robots),
                "updated_at": self._updated_at.isoformat(),
            }
