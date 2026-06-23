"""ROS adapter that converts GADEN Anemometer readings to /estimated_wind.

Subscribes to olfaction_msgs/Anemometer (published by simulated_anemometer
with use_map_ref_system:=true) and republishes as
h2track_interfaces/msg/WindEstimate on /estimated_wind.

This is the "ground truth" wind path: GADEN's CFD wind field sampled at
the robot's position with configurable Gaussian noise.
"""

from __future__ import annotations

from olfaction_msgs.msg import Anemometer
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from h2track_interfaces.msg import WindEstimate as WindEstimateMsg

from .anemometer_adapter import (
    AnemometerAdapterConfig,
    AnemometerReading,
    WindEstimate,
    convert_anemometer_to_wind_estimate,
)


class AnemometerAdapterNode(Node):
    """Bridge GADEN Anemometer → h2track WindEstimate."""

    def __init__(self) -> None:
        super().__init__("anemometer_adapter_node")

        self.declare_parameter("anemometer_topic", "/simulated_anemometer/WindSensor_reading")
        self.declare_parameter("wind_topic", "/estimated_wind")
        self.declare_parameter("smoothing_alpha", 1.0)
        self.declare_parameter("max_wind_speed", 10.0)
        self.declare_parameter("log_interval_sec", 1.0)

        self._config = AnemometerAdapterConfig(
            smoothing_alpha=float(self.get_parameter("smoothing_alpha").value),
            max_wind_speed=float(self.get_parameter("max_wind_speed").value),
        )
        self._previous_estimate: WindEstimate | None = None
        self._log_interval_sec = max(0.0, float(self.get_parameter("log_interval_sec").value))
        self._last_log_sec: float | None = None

        anemometer_topic = str(self.get_parameter("anemometer_topic").value)
        wind_topic = str(self.get_parameter("wind_topic").value)

        # Anemometer is a sensor stream → BEST_EFFORT matches publisher.
        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._publisher = self.create_publisher(WindEstimateMsg, wind_topic, sensor_qos)
        self.create_subscription(Anemometer, anemometer_topic, self._on_anemometer, sensor_qos)

        self.get_logger().info(
            f"anemometer_adapter listening on {anemometer_topic}, republishing {wind_topic}"
        )

    def _on_anemometer(self, msg: Anemometer) -> None:
        """Convert Anemometer msg to WindEstimate msg and publish."""
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        reading = AnemometerReading(
            wind_speed=float(msg.wind_speed),
            wind_direction=float(msg.wind_direction),
            sensor_label=str(msg.sensor_label),
            timestamp=stamp,
        )
        estimate = convert_anemometer_to_wind_estimate(
            reading, self._config, self._previous_estimate
        )
        self._previous_estimate = estimate

        wind_msg = WindEstimateMsg(
            wind_x=float(estimate.wind_x),
            wind_y=float(estimate.wind_y),
            confidence=float(estimate.confidence),
        )
        wind_msg.header.stamp = msg.header.stamp
        wind_msg.header.frame_id = "map"
        self._publisher.publish(wind_msg)

        import time as _time
        now_sec = _time.monotonic()
        if self._should_log(now_sec):
            self._last_log_sec = now_sec
            self.get_logger().info(
                f"wind=({estimate.wind_x:.2f},{estimate.wind_y:.2f}) m/s"
            )

    def _should_log(self, now_sec: float) -> bool:
        if self._log_interval_sec <= 0.0:
            return True
        if self._last_log_sec is None:
            return True
        return (now_sec - self._last_log_sec) >= self._log_interval_sec


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = AnemometerAdapterNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
