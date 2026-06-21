"""ROS lifecycle node that publishes a simplified hydrogen concentration signal.

Converted to LifecycleNode following ros2-engineering-skills pattern:
- on_configure: create model, declare parameters, create subscriptions
- on_activate: create publishers, start timer
- on_deactivate: stop timer
- on_cleanup: release resources
"""

from __future__ import annotations

from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Float32
from visualization_msgs.msg import Marker

from .gas_model import GasFieldModel, GasFieldParams, Pose2D


class GasFieldNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("gas_field_node")
        self.declare_parameter("source_x", -3.5)
        self.declare_parameter("source_y", -3.5)
        self.declare_parameter("source_strength", 120.0)
        self.declare_parameter("decay_rate", 0.55)
        self.declare_parameter("plume_stddev", 1.2)
        self.declare_parameter("wind_x", 0.4)
        self.declare_parameter("wind_y", 0.0)
        self.declare_parameter("noise_stddev", 0.05)
        self.declare_parameter("gas_type", "H2")
        self.declare_parameter("publish_rate_hz", 5.0)

        self._pose = Pose2D(0.0, 0.0)
        self._model: GasFieldModel | None = None
        self._concentration_pub = None
        self._marker_pub = None
        self._timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Create model and subscriptions (no publishers or timers yet)."""
        params = GasFieldParams(
            source_x=float(self.get_parameter("source_x").value),
            source_y=float(self.get_parameter("source_y").value),
            source_strength=float(self.get_parameter("source_strength").value),
            decay_rate=float(self.get_parameter("decay_rate").value),
            plume_stddev=float(self.get_parameter("plume_stddev").value),
            wind_x=float(self.get_parameter("wind_x").value),
            wind_y=float(self.get_parameter("wind_y").value),
            noise_stddev=float(self.get_parameter("noise_stddev").value),
            min_concentration=0.0,
            gas_type=str(self.get_parameter("gas_type").value),
        )
        self._model = GasFieldModel(params)
        self.create_subscription(Odometry, "/odom", self._odom_callback, 10)
        self.get_logger().info("GasFieldNode configured")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Create publishers and start the publishing timer."""
        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._concentration_pub = self.create_publisher(Float32, "/gas_concentration", sensor_qos)
        self._marker_pub = self.create_publisher(Marker, "/gas_source_marker", 1)
        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        self._timer = self.create_timer(1.0 / rate_hz, self._publish)
        self.get_logger().info("GasFieldNode activated")
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Stop the publishing timer."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.get_logger().info("GasFieldNode deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Release all resources."""
        self._model = None
        self._concentration_pub = None
        self._marker_pub = None
        self.get_logger().info("GasFieldNode cleaned up")
        return TransitionCallbackReturn.SUCCESS

    def _odom_callback(self, msg: Odometry) -> None:
        self._pose = Pose2D(msg.pose.pose.position.x, msg.pose.pose.position.y)

    def _publish(self) -> None:
        if self._model is None or self._concentration_pub is None:
            return
        concentration = self._model.concentration_at(self._pose)
        self._concentration_pub.publish(Float32(data=float(concentration)))

        if self._marker_pub is not None:
            marker = Marker()
            marker.header.frame_id = "map"
            marker.ns = "hydrogen_source"
            marker.id = 1
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose.position = Point(
                x=self._model.params.source_x,
                y=self._model.params.source_y,
                z=0.2,
            )
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.25
            marker.scale.y = 0.25
            marker.scale.z = 0.25
            marker.color.a = 0.85
            marker.color.r = 0.95
            marker.color.g = 0.85
            marker.color.b = 0.1
            self._marker_pub.publish(marker)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GasFieldNode()
    # Lifecycle nodes need a lifecycle manager to transition them,
    # but for standalone usage, auto-configure and activate
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
