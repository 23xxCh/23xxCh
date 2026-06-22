"""Nav2 lifecycle management for BTNodeRunner.

Encapsulates BasicNavigator initialization, initial pose publishing,
and readiness polling.  Extracted from BTNodeRunner to separate
ROS I/O lifecycle from orchestration logic.
"""

from __future__ import annotations

from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
from rclpy.node import Node

from .types import Pose2D


class Nav2Lifecycle:
    """Manages Nav2 lifecycle: initial pose, readiness, activation.

    Retries the readiness check up to *max_retries* times with
    *retry_delay_sec* between attempts to handle transient DDS issues.
    """

    def __init__(
        self,
        node: Node,
        initial_pose: Pose2D,
        initial_yaw: float,
        localizer_node: str,
        publish_initial_pose: bool = True,
        max_retries: int = 3,
        retry_delay_sec: float = 5.0,
    ) -> None:
        self._node = node
        self._initial_pose = initial_pose
        self._initial_yaw = initial_yaw
        self._localizer_node = localizer_node
        self._publish_initial_pose = publish_initial_pose
        self._max_retries = max_retries
        self._retry_delay_sec = retry_delay_sec

        self._navigator = BasicNavigator()
        self._initial_pose_sent = False
        self._ready = False
        self._attempt = 0
        self._retry_timer = None

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def navigator(self) -> BasicNavigator:
        return self._navigator

    def check_ready(self) -> bool:
        """Poll until Nav2 is active.  Returns True once ready.

        On failure, schedules a retry after *retry_delay_sec* seconds
        up to *max_retries* attempts.
        """
        if self._ready:
            return True

        if not self._publish_initial_pose and self._initial_pose_sent:
            self._ready = True
            return True

        initial = _make_pose_stamped(
            self._node, self._initial_pose, self._initial_yaw
        )
        self._navigator.setInitialPose(initial)
        self._initial_pose_sent = True

        try:
            # Non-blocking readiness check: poll key services with short timeouts
            # instead of blocking the entire executor with waitUntilNav2Active
            if not self._navigator.nav_to_pose_client.wait_for_server(
                timeout_sec=0.2
            ):
                self._schedule_retry()
                return False
            self._navigator._waitForNodeToActivate("bt_navigator")
        except Exception:
            self._schedule_retry()
            return False

        self._ready = True
        return True

    def _schedule_retry(self) -> None:
        """Schedule a retry after delay, up to max_retries."""
        self._attempt += 1
        if self._attempt >= self._max_retries:
            self._node.get_logger().error(
                f"Nav2 startup failed after {self._max_retries} attempts"
            )
            return
        self._node.get_logger().warn(
            f"Nav2 startup attempt {self._attempt} failed, "
            f"retrying in {self._retry_delay_sec}s..."
        )
        if self._retry_timer is None:
            self._retry_timer = self._node.create_timer(
                self._retry_delay_sec, self._on_retry
            )
        else:
            self._retry_timer.reset()

    def _on_retry(self) -> None:
        """Timer callback: cancel timer and re-attempt check_ready."""
        self._retry_timer.cancel()
        self._retry_timer = None
        self._node.get_logger().info(
            f"Nav2 retry attempt {self._attempt + 1}/{self._max_retries}"
        )
        self.check_ready()


def _make_pose_stamped(node: Node, pose: Pose2D, yaw: float = 0.0) -> PoseStamped:
    """Create a PoseStamped message from a Pose2D."""
    import math

    goal = PoseStamped()
    goal.header.frame_id = "map"
    goal.header.stamp = node.get_clock().now().to_msg()
    goal.pose.position.x = pose.x
    goal.pose.position.y = pose.y
    goal.pose.orientation.z = math.sin(yaw / 2.0)
    goal.pose.orientation.w = math.cos(yaw / 2.0)
    return goal
