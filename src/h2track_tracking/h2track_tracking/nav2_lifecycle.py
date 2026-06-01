"""Nav2 lifecycle management for BTNodeRunner.

Encapsulates BasicNavigator initialization, initial pose publishing,
and readiness polling.  Extracted from BTNodeRunner to separate
ROS I/O lifecycle from orchestration logic.
"""

from __future__ import annotations

from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
from rclpy.node import Node

from .tracking.types import Pose2D


class Nav2Lifecycle:
    """Manages Nav2 lifecycle: initial pose, readiness, activation."""

    def __init__(
        self,
        node: Node,
        initial_pose: Pose2D,
        initial_yaw: float,
        localizer_node: str,
        publish_initial_pose: bool = True,
    ) -> None:
        self._node = node
        self._initial_pose = initial_pose
        self._initial_yaw = initial_yaw
        self._localizer_node = localizer_node
        self._publish_initial_pose = publish_initial_pose

        self._navigator = BasicNavigator()
        self._initial_pose_sent = False
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def navigator(self) -> BasicNavigator:
        return self._navigator

    def check_ready(self) -> bool:
        """Poll until Nav2 is active.  Returns True once ready."""
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

        if self._localizer_node in ("", "none", "slam_toolbox", "slam"):
            if not self._navigator.nav_to_pose_client.wait_for_server(
                timeout_sec=0.2
            ):
                return False
            self._navigator._waitForNodeToActivate("bt_navigator")
        else:
            self._navigator.waitUntilNav2Active(localizer=self._localizer_node)

        self._ready = True
        return True


def _make_pose_stamped(node: Node, pose: Pose2D, yaw: float) -> PoseStamped:
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
