"""ROS node that waits for TF connectivity before launching the GADEN sensor process."""

from __future__ import annotations

import os
import subprocess
import time

from ament_index_python.packages import PackageNotFoundError, get_package_prefix
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from .gaden_sensor_gate import GateAction, SensorGateConfig, SensorGateState, build_sensor_process_command


class GadenSensorGateNode(Node):
    def __init__(self) -> None:
        super().__init__("gaden_sensor_gate_node")
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        self.declare_parameter("fixed_frame", "gaden_map")
        self.declare_parameter("sensor_frame", "base_link")
        self.declare_parameter("timeout_sec", 30.0)
        self.declare_parameter("poll_period_sec", 0.5)
        self.declare_parameter("stable_ready_count", 3)
        self.declare_parameter("sensor_executable_path", "")
        self.declare_parameter("sensor_node_name", "gaden_pid_sensor")
        self.declare_parameter("topic", "/gaden/sensor_reading")
        self.declare_parameter("sensor_model", 30)
        self.declare_parameter("rate", 5.0)
        self.declare_parameter("use_pid_correction_factors", False)

        self._fixed_frame = str(self.get_parameter("fixed_frame").value)
        self._sensor_frame = str(self.get_parameter("sensor_frame").value)
        self._state = SensorGateState(
            SensorGateConfig(
                timeout_sec=float(self.get_parameter("timeout_sec").value),
                poll_period_sec=float(self.get_parameter("poll_period_sec").value),
                stable_ready_count=int(self.get_parameter("stable_ready_count").value),
            )
        )
        self._poll_period_sec = float(self.get_parameter("poll_period_sec").value)
        self._started_at = time.monotonic()
        self._process: subprocess.Popen[bytes] | None = None
        self._exit_code = 0
        self._shutting_down = False
        self._tf_buffer = Buffer(cache_time=Duration(seconds=30.0))
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._timer = self.create_timer(self._poll_period_sec, self._poll)

        self.get_logger().info(
            f"waiting for TF {self._fixed_frame} -> {self._sensor_frame} before launching simulated_gas_sensor"
        )

    @property
    def exit_code(self) -> int:
        return self._exit_code

    def _poll(self) -> None:
        if self._process is not None:
            return_code = self._process.poll()
            if return_code is not None and not self._shutting_down:
                self._fail(f"simulated_gas_sensor exited unexpectedly with code {return_code}")
            return

        elapsed_sec = time.monotonic() - self._started_at
        has_transform = self._tf_buffer.can_transform(
            self._fixed_frame,
            self._sensor_frame,
            Time(),
            timeout=Duration(seconds=0.0),
        )
        action = self._state.step(has_transform=has_transform, elapsed_sec=elapsed_sec)
        if action is GateAction.WAIT:
            return
        if action is GateAction.FAIL:
            self._fail(
                f"timed out after {elapsed_sec:.1f}s waiting for TF {self._fixed_frame} -> {self._sensor_frame}"
            )
            return
        if action is GateAction.LAUNCH:
            self._launch_sensor_process()

    def _launch_sensor_process(self) -> None:
        executable_path = self._resolve_sensor_executable_path()
        command = build_sensor_process_command(
            executable_path=executable_path,
            use_sim_time=bool(self.get_parameter("use_sim_time").value),
            topic=str(self.get_parameter("topic").value),
            fixed_frame=self._fixed_frame,
            sensor_frame=self._sensor_frame,
            sensor_model=int(self.get_parameter("sensor_model").value),
            rate=float(self.get_parameter("rate").value),
            use_pid_correction_factors=bool(self.get_parameter("use_pid_correction_factors").value),
            sensor_node_name=str(self.get_parameter("sensor_node_name").value),
        )
        self.get_logger().info(f"TF ready; launching simulated_gas_sensor: {executable_path}")
        self._process = subprocess.Popen(command)

    def _resolve_sensor_executable_path(self) -> str:
        override = str(self.get_parameter("sensor_executable_path").value)
        if override:
            return override
        try:
            prefix = get_package_prefix("simulated_gas_sensor")
        except PackageNotFoundError as exc:
            raise RuntimeError("simulated_gas_sensor package is not available in the current environment") from exc
        executable_path = os.path.join(prefix, "lib", "simulated_gas_sensor", "simulated_gas_sensor")
        if not os.path.exists(executable_path):
            raise RuntimeError(f"simulated_gas_sensor executable not found at {executable_path}")
        return executable_path

    def _fail(self, message: str) -> None:
        if self._exit_code != 0:
            return
        self._exit_code = 1
        self.get_logger().error(message)
        self._shutting_down = True
        self._terminate_child()
        if rclpy.ok():
            rclpy.shutdown()

    def _terminate_child(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is not None:
            self._process = None
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5.0)
        self._process = None

    def shutdown(self) -> None:
        self._shutting_down = True
        self._terminate_child()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GadenSensorGateNode()
    exit_code = 0
    try:
        rclpy.spin(node)
        exit_code = node.exit_code
    except KeyboardInterrupt:
        exit_code = node.exit_code
    finally:
        node.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(exit_code)
