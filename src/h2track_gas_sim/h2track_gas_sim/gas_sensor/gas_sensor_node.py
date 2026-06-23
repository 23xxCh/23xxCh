"""Gas sensor node for real hardware integration.

Provides:
- Gas concentration reading (from simulation or hardware)
- Wind speed/direction estimation (passthrough)
- Sensor calibration
- Alarm threshold monitoring
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Float32MultiArray

from h2track_gas_sim.gas_types import GasType, get_gas_properties


class GasSensorNode(Node):
    """ROS2 node for gas sensor integration.

    Supports:
    - MQ series sensors (MQ-2, MQ-4, MQ-8, etc.)
    - Digital gas sensors via I2C
    - Simulation mode: subscribes to /gas_concentration from gas_field_node
    """

    def __init__(self) -> None:
        super().__init__("gas_sensor_node")

        # Declare parameters
        self.declare_parameter("gas_type", "H2")
        self.declare_parameter("simulation_mode", True)
        self.declare_parameter("publish_rate", 10.0)
        self.declare_parameter("sensor_port", "/dev/ttyUSB0")
        self.declare_parameter("alarm_threshold", -1.0)  # -1 = use gas default

        self._gas_type = GasType(self.get_parameter("gas_type").value)
        self._simulation_mode = self.get_parameter("simulation_mode").value
        self._publish_rate = float(self.get_parameter("publish_rate").value)

        # Alarm threshold (use gas default if not overridden)
        alarm_param = float(self.get_parameter("alarm_threshold").value)
        if alarm_param > 0:
            self._alarm_threshold = alarm_param
        else:
            self._alarm_props = get_gas_properties(self._gas_type)
            self._alarm_threshold = self._alarm_props.alarm_threshold

        # Publisher for sensor readings (re-publishes with alarm monitoring)
        self._concentration_pub = self.create_publisher(
            Float32, "/gas_concentration", 10
        )
        self._wind_pub = self.create_publisher(
            Float32MultiArray, "/wind_estimate", 10
        )
        self._sensor_status_pub = self.create_publisher(
            Float32MultiArray, "/sensor_status", 10
        )

        # Internal state (updated by subscription or hardware read)
        self._current_concentration = 0.0
        self._sim_wind_x = 0.0
        self._sim_wind_y = 0.0

        if self._simulation_mode:
            # In simulation, subscribe to gas_field_node's output and
            # re-publish with alarm monitoring. We use a remap-friendly
            # internal topic to avoid a feedback loop.
            self.create_subscription(
                Float32,
                "/gas_concentration_sim",
                self._sim_concentration_callback,
                10,
            )
            self.get_logger().info(
                f"Gas sensor in SIMULATION mode — "
                f"remap /gas_concentration_sim:=/gas_concentration"
            )

        # Timer for periodic publishing + alarm check
        self._timer = self.create_timer(
            1.0 / self._publish_rate, self._read_and_publish
        )

        self.get_logger().info(
            f"Gas sensor node started for {self._gas_type.value} "
            f"(simulation: {self._simulation_mode}, "
            f"alarm_threshold: {self._alarm_threshold})"
        )

    def _sim_concentration_callback(self, msg: Float32) -> None:
        """Receive concentration from gas_field_node in simulation mode."""
        self._current_concentration = float(msg.data)

    def _read_and_publish(self) -> None:
        """Read sensor and publish data."""
        if not self._simulation_mode:
            self._current_concentration = self._read_hardware()

        # Publish concentration
        msg = Float32()
        msg.data = self._current_concentration
        self._concentration_pub.publish(msg)

        # Publish wind estimate (if available)
        wind_msg = Float32MultiArray()
        wind_msg.data = [self._sim_wind_x, self._sim_wind_y]
        self._wind_pub.publish(wind_msg)

        # Publish sensor status: [concentration, alarm_flag, 0.0]
        status_msg = Float32MultiArray()
        alarm = 1.0 if self._current_concentration >= self._alarm_threshold else 0.0
        status_msg.data = [self._current_concentration, alarm, 0.0]
        self._sensor_status_pub.publish(status_msg)

        # Check alarm threshold
        if self._current_concentration >= self._alarm_threshold:
            self.get_logger().warning(
                f"ALARM: {self._gas_type.value} concentration "
                f"{self._current_concentration:.1f} exceeds threshold "
                f"{self._alarm_threshold}"
            )

    def _read_hardware(self) -> float:
        """Read from actual hardware sensor.

        Placeholder for hardware integration:
        - Serial communication (MQ sensors via ADC)
        - I2C communication (digital sensors)
        - ADC reading (analog sensors)

        Returns:
            Concentration in ppm.
        """
        self.get_logger().warning(
            "Hardware reading not implemented, returning 0.0", throttle_duration_sec=5.0
        )
        return 0.0


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GasSensorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
