"""Nav2 client node for Behavior Tree.

Wraps the Nav2 ``navigate_to_pose`` action as a py_trees Behaviour.

Fix #2: Accepts action_server_name via constructor (no hardcoded topic).
Fix #4: Uses internal _nav_status instead of reading own blackboard writes.
"""

from __future__ import annotations

import math

import py_trees
from py_trees.common import Status
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.task import Future

from ...tracking.types import Pose2D


class Nav2ClientNode(py_trees.behaviour.Behaviour):
    """py_trees Behaviour: sends goal to Nav2, monitors progress.

    Writes terminal status (succeeded/failed) to blackboard at lifecycle end.
    Uses internal _nav_status during update to avoid circular reads.
    """

    def __init__(
        self,
        name: str,
        bb: "H2TrackBlackboard",
        node: Node,
        *,
        action_server_name: str = "/navigate_to_pose",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(name)
        self._bb = bb
        self._node = node
        self._action_server = action_server_name   # Fix #2: configurable
        self._timeout = timeout

        self._action_client: ActionClient | None = None
        self._goal_handle = None
        self._result_future: Future | None = None
        self._start_time_s: float | None = None
        self._nav_status = "idle"                    # Fix #4: internal state

    # -- py_trees lifecycle ---------------------------------------------------

    def setup(self, **kwargs: object) -> None:
        self._action_client = ActionClient(
            self._node, NavigateToPose, self._action_server
        )

    def initialise(self) -> None:
        target: Pose2D | None = self._bb.nav2.target_pose
        if target is None:
            self.feedback_message = "no target_pose on blackboard"
            return

        if self._action_client is None:
            self.feedback_message = "action client None"
            return

        yaw = self._bb.nav2.target_yaw or 0.0

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x = target.x
        goal.pose.pose.position.y = target.y
        goal.pose.pose.position.z = 0.0
        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)
        goal.pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=qz, w=qw)

        send_future = self._action_client.send_goal_async(goal)
        send_future.add_done_callback(self._on_goal_response)
        self._start_time_s = self._node.get_clock().now().nanoseconds / 1e9
        self._nav_status = "navigating"
        self._bb.nav2.status = "navigating"
        self.feedback_message = f"-> ({target.x:.2f}, {target.y:.2f})"

    def update(self) -> Status:
        # Fix #4: read internal status, not blackboard
        if self._nav_status == "idle":
            return Status.INVALID

        if self._nav_status == "navigating":
            if self._start_time_s is not None:
                elapsed = (
                    self._node.get_clock().now().nanoseconds / 1e9
                    - self._start_time_s
                )
                if elapsed > self._timeout:
                    self._nav_status = "failed"
                    self._bb.nav2.status = "failed"
                    self.feedback_message = "timeout"
                    return Status.FAILURE
            return Status.RUNNING

        if self._nav_status == "succeeded":
            self._bb.nav2.goal_reached_count = (
                self._bb.nav2.goal_reached_count or 0
            ) + 1
            self._bb.nav2.task_complete = True
            return Status.SUCCESS

        if self._nav_status == "failed":
            return Status.FAILURE

        return Status.RUNNING

    def terminate(self, new_status: Status) -> None:
        # Write terminal status to blackboard
        self._bb.nav2.status = self._nav_status
        if new_status == Status.INVALID and self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._nav_status = "cancelled"
        self._goal_handle = None
        self._result_future = None

    # -- action callbacks -----------------------------------------------------

    def _on_goal_response(self, future: Future) -> None:
        self._goal_handle = future.result()
        if self._goal_handle is None or not self._goal_handle.accepted:
            self._nav_status = "failed"
            self._bb.nav2.status = "failed"
            self.feedback_message = "goal rejected"
            return

        self._result_future = self._goal_handle.get_result_async()
        self._result_future.add_done_callback(self._on_result)

    def _on_result(self, future: Future) -> None:
        result = future.result()
        if result is not None and result.status == 4:  # SUCCEEDED
            self._nav_status = "succeeded"
            self._bb.nav2.status = "succeeded"
        else:
            self._nav_status = "failed"
            self._bb.nav2.status = "failed"
