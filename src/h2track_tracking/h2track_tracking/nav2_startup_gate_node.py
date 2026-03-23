"""ROS node that starts Nav2 only after odom TF and lifecycle service are ready."""

from __future__ import annotations

import time

from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.task import Future
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from .nav2_startup_gate import GateAction, Nav2StartupGateConfig, Nav2StartupGateState


class Nav2StartupGateNode(Node):
    def __init__(self) -> None:
        super().__init__("nav2_startup_gate_node")
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        self.declare_parameter("target_frame", "odom")
        self.declare_parameter("source_frame", "base_link")
        self.declare_parameter("lifecycle_manager_service", "/lifecycle_manager_navigation/manage_nodes")
        self.declare_parameter("timeout_sec", 30.0)
        self.declare_parameter("poll_period_sec", 0.5)
        self.declare_parameter("stable_ready_count", 2)
        self.declare_parameter("startup_retry_limit", 2)

        self._target_frame = str(self.get_parameter("target_frame").value)
        self._source_frame = str(self.get_parameter("source_frame").value)
        self._lifecycle_manager_service = str(self.get_parameter("lifecycle_manager_service").value)
        self._poll_period_sec = float(self.get_parameter("poll_period_sec").value)
        self._state = Nav2StartupGateState(
            Nav2StartupGateConfig(
                timeout_sec=float(self.get_parameter("timeout_sec").value),
                stable_ready_count=int(self.get_parameter("stable_ready_count").value),
                max_startup_retries=int(self.get_parameter("startup_retry_limit").value),
            )
        )
        self._started_at = time.monotonic()
        self._exit_code = 0
        self._startup_future: Future | None = None
        self._tf_buffer = Buffer(cache_time=Duration(seconds=30.0))
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._client = self.create_client(ManageLifecycleNodes, self._lifecycle_manager_service)
        self._navigate_action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._timer = self.create_timer(self._poll_period_sec, self._poll)

        self.get_logger().info(
            f"waiting for TF {self._target_frame} -> {self._source_frame} and service {self._lifecycle_manager_service} before starting Nav2"
        )

    @property
    def exit_code(self) -> int:
        return self._exit_code

    def _poll(self) -> None:
        if self._exit_code != 0:
            return

        startup_result = None
        if self._startup_future is not None:
            if self._startup_future.done():
                try:
                    response = self._startup_future.result()
                except Exception as exc:  # pragma: no cover - defensive runtime path
                    self._fail(f"Nav2 startup service call failed: {exc}")
                    return
                startup_result = bool(response and response.success)

        elapsed_sec = time.monotonic() - self._started_at
        tf_ready = self._tf_buffer.can_transform(
            self._target_frame,
            self._source_frame,
            Time(),
            timeout=Duration(seconds=0.0),
        )
        service_ready = self._client.wait_for_service(timeout_sec=0.0)
        nav_ready = self._navigate_action_client.server_is_ready()
        action = self._state.step(
            tf_ready=tf_ready,
            service_ready=service_ready,
            startup_result=startup_result,
            nav_ready=nav_ready,
            elapsed_sec=elapsed_sec,
        )

        if action in (GateAction.WAIT, GateAction.MONITOR):
            if startup_result is False and self._startup_future is not None and self._startup_future.done():
                self.get_logger().warn(
                    "Nav2 STARTUP request failed; retrying while gate timeout budget remains"
                )
                self._startup_future = None
            return
        if action is GateAction.STARTUP:
            self._send_startup_request()
            return
        if action is GateAction.COMPLETE:
            if startup_result is False and nav_ready:
                self.get_logger().warn(
                    "Nav2 STARTUP call returned failure, but navigate_to_pose is already ready; treating gate as complete"
                )
            self.get_logger().info("Nav2 startup gate completed successfully")
            if rclpy.ok():
                rclpy.shutdown()
            return
        if startup_result is False:
            self._fail("Nav2 lifecycle manager rejected the startup request")
            return
        self._fail(
            f"timed out after {elapsed_sec:.1f}s waiting for TF {self._target_frame} -> {self._source_frame} and service {self._lifecycle_manager_service}"
        )

    def _send_startup_request(self) -> None:
        request = ManageLifecycleNodes.Request()
        request.command = ManageLifecycleNodes.Request.STARTUP
        self.get_logger().info(
            f"TF and lifecycle service ready; sending STARTUP to {self._lifecycle_manager_service}"
        )
        self._startup_future = self._client.call_async(request)

    def _fail(self, message: str) -> None:
        if self._exit_code != 0:
            return
        self._exit_code = 1
        self.get_logger().error(message)
        if rclpy.ok():
            rclpy.shutdown()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = Nav2StartupGateNode()
    exit_code = 0
    try:
        rclpy.spin(node)
        exit_code = node.exit_code
    except KeyboardInterrupt:
        exit_code = node.exit_code
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(exit_code)
