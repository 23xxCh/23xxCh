"""Multi-robot coordinator for gas source localization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Pose2D
from std_msgs.msg import String

# Note: After building h2track_interfaces, import like:
# from h2track_interfaces.msg import RobotState, SourceEstimate, RoleAssignment


class Role(Enum):
    """Robot roles in multi-robot coordination."""
    TRACKER = "TRACKER"
    EXPLORER = "EXPLORER"
    VERIFIER = "VERIFIER"
    IDLE = "IDLE"


@dataclass
class RobotInfo:
    """Information about a single robot."""
    robot_id: int
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # x, y, yaw
    mode: str = "PATROL"
    concentration: float = 0.0
    role: Role = Role.EXPLORER
    source_estimate: Optional[Tuple[float, float, float]] = None  # x, y, confidence
    last_update: float = 0.0


class MultiRobotCoordinator(Node):
    """Coordinates multiple robots for gas source localization.

    Responsibilities:
    - Role assignment and reassignment
    - Information fusion from multiple robots
    - Conflict resolution
    - Global source estimation
    """

    def __init__(self) -> None:
        super().__init__("multi_robot_coordinator")

        # Declare parameters
        self.declare_parameter("num_robots", 3)
        self.declare_parameter("update_interval", 1.0)
        self.declare_parameter("fusion_threshold", 0.5)

        self._num_robots = int(self.get_parameter("num_robots").value)
        self._update_interval = float(self.get_parameter("update_interval").value)

        # Robot tracking
        self._robots: Dict[int, RobotInfo] = {
            i: RobotInfo(robot_id=i) for i in range(self._num_robots)
        }

        # Global estimate
        self._global_estimate: Optional[Tuple[float, float, float]] = None
        self._estimate_confidence: float = 0.0

        # Publishers (will be set up after message types are available)
        self._role_pub = self.create_publisher(String, "/coordinator/role_assignment", 10)
        self._estimate_pub = self.create_publisher(String, "/coordinator/global_estimate", 10)

        # Timer for periodic updates
        self._timer = self.create_timer(self._update_interval, self._coordination_loop)

        self.get_logger().info(f"Multi-robot coordinator started with {self._num_robots} robots")

    def _coordination_loop(self) -> None:
        """Main coordination loop called periodically."""
        # 1. Check for stale robot data
        self._check_robot_timeouts()

        # 2. Assign roles based on current state
        self._assign_roles()

        # 3. Fuse information from all robots
        self._fuse_information()

        # 4. Resolve conflicts
        self._resolve_conflicts()

        # 5. Publish updates
        self._publish_updates()

    def _check_robot_timeouts(self) -> None:
        """Check for robots that haven't updated recently."""
        import time
        current_time = time.time()
        timeout = self._update_interval * 5  # 5x update interval

        for robot_id, robot in self._robots.items():
            if current_time - robot.last_update > timeout:
                self.get_logger().warning(f"Robot {robot_id} timed out")
                robot.role = Role.IDLE

    def _assign_roles(self) -> None:
        """Assign roles to robots based on current state."""
        # Simple strategy: one tracker, others explore
        trackers = [r for r in self._robots.values() if r.role == Role.TRACKER]

        if not trackers:
            # Assign tracker to robot with highest concentration
            best_robot = max(self._robots.values(), key=lambda r: r.concentration)
            if best_robot.concentration > 0.5:
                best_robot.role = Role.TRACKER

        # Assign explorer roles to others
        for robot in self._robots.values():
            if robot.role == Role.TRACKER:
                continue
            elif robot.role == Role.IDLE:
                robot.role = Role.EXPLORER

        # Assign verifier if we have a good estimate
        if self._global_estimate and self._estimate_confidence > 0.7:
            # Find closest idle robot
            for robot in self._robots.values():
                if robot.role == Role.EXPLORER:
                    robot.role = Role.VERIFIER
                    break

    def _fuse_information(self) -> None:
        """Fuse source estimates from all robots."""
        estimates = []

        for robot in self._robots.values():
            if robot.source_estimate:
                estimates.append(robot.source_estimate)

        if len(estimates) >= 2:
            # Weighted average
            total_confidence = sum(e[2] for e in estimates)
            if total_confidence > 0:
                x = sum(e[0] * e[2] for e in estimates) / total_confidence
                y = sum(e[1] * e[2] for e in estimates) / total_confidence
                self._global_estimate = (x, y, total_confidence / len(estimates))
                self._estimate_confidence = total_confidence / len(estimates)

    def _resolve_conflicts(self) -> None:
        """Resolve conflicts between robots."""
        # Check for multiple trackers tracking same source
        tracker_positions = [
            (r.robot_id, r.position[:2])
            for r in self._robots.values()
            if r.role == Role.TRACKER
        ]

        if len(tracker_positions) > 1:
            # Keep best tracker, reassign others
            best_id = max(tracker_positions, key=lambda x: self._robots[x[0]].concentration)[0]
            for robot_id, _ in tracker_positions:
                if robot_id != best_id:
                    self._robots[robot_id].role = Role.EXPLORER
                    self.get_logger().info(f"Reassigned robot {robot_id} from TRACKER to EXPLORER")

    def _publish_updates(self) -> None:
        """Publish coordination updates."""
        # Publish role assignments
        for robot in self._robots.values():
            msg = String()
            msg.data = f"{robot.robot_id}:{robot.role.value}"
            self._role_pub.publish(msg)

        # Publish global estimate
        if self._global_estimate:
            msg = String()
            msg.data = f"{self._global_estimate[0]:.2f},{self._global_estimate[1]:.2f},{self._estimate_confidence:.2f}"
            self._estimate_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MultiRobotCoordinator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
