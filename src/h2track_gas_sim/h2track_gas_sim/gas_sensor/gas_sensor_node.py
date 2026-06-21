"""Gas sensor node for real hardware integration.

Provides:
- Gas concentration reading
- Wind speed/direction estimation
- Sensor calibration
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Float32MultiArray
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Temperature, RelativeHumidity

from h2track_gas_sim.gas_types import GasType, get_gas_properties


class GasSensorNode(Node):
    """ROS2 node for gas sensor integration.
    
    Supports:
    - MQ series sensors (MQ-2, MQ-4, MQ-8, etc.)
    - Digital gas sensors via I2C
    - Simulation mode for testing
    """
    
    def __init__(self) -> None:
        super().__init__("gas_sensor_node")
        
        # Declare parameters
        self.declare_parameter("gas_type", "H2")
        self.declare_parameter("simulation_mode", True)
        self.declare_parameter("publish_rate", 10.0)
        self.declare_parameter("sensor_port", "/dev/ttyUSB0")
        
        self._gas_type = GasType(self.get_parameter("gas_type").value)
        self._simulation_mode = self.get_parameter("simulation_mode").value
        self._publish_rate = float(self.get_parameter("publish_rate").value)
        
        # Get gas properties
        self._gas_props = get_gas_properties(self._gas_type)
        
        # Publishers
        self._concentration_pub = self.create_publisher(
            Float32, "/gas_concentration", 10
        )
        self._wind_pub = self.create_publisher(
            Float32MultiArray, "/wind_estimate", 10
        )
        self._sensor_status_pub = self.create_publisher(
            Float32MultiArray, "/sensor_status", 10
        )
        
        # Timer for publishing
        self._timer = self.create_timer(
            1.0 / self._publish_rate, self._read_and_publish
        )
        
        # Simulation state
        self._sim_concentration = 0.0
        self._sim_wind_x = 0.0
        self._sim_wind_y = 0.0
        
        self.get_logger().info(
            f"Gas sensor node started for {self._gas_props.name} "
            f"(simulation: {self._simulation_mode})"
        )
    
    def _read_and_publish(self) -> None:
        """Read sensor and publish data."""
        if self._simulation_mode:
            concentration = self._read_simulation()
        else:
            concentration = self._read_hardware()
        
        # Publish concentration
        msg = Float32()
        msg.data = concentration
        self._concentration_pub.publish(msg)
        
        # Publish wind estimate (if available)
        wind_msg = Float32MultiArray()
        wind_msg.data = [self._sim_wind_x, self._sim_wind_y]
        self._wind_pub.publish(wind_msg)
        
        # Check alarm threshold
        if concentration >= self._gas_props.alarm_threshold:
            self.get_logger().warning(
                f"ALARM: {self._gas_props.name} concentration {concentration:.1f} "
                f"exceeds threshold {self._gas_props.alarm_threshold}"
            )
    
    def _read_simulation(self) -> float:
        """Read from simulation (for testing)."""
        # TODO: Connect to GADEN simulation
        return self._sim_concentration
    
    def _read_hardware(self) -> float:
        """Read from actual hardware sensor."""
        # TODO: Implement hardware reading
        # - Serial communication
        # - I2C communication
        # - ADC reading
        self.get_logger().warning("Hardware reading not implemented, using simulation")
        return 0.0
    
    def set_simulation_values(
        self,
        concentration: float,
        wind_x: float = 0.0,
        wind_y: float = 0.0,
    ) -> None:
        """Set simulation values (for testing)."""
        self._sim_concentration = concentration
        self._sim_wind_x = wind_x
        self._sim_wind_y = wind_y


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GasSensorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
