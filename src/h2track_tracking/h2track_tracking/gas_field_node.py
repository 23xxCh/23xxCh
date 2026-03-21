"""ROS node that publishes a simplified hydrogen concentration signal."""

from __future__ import annotations

from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from visualization_msgs.msg import Marker

from .gas_model import GasFieldModel, GasFieldParams, Pose2D


class GasFieldNode(Node):
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
        self.declare_parameter("publish_rate_hz", 5.0)

        self._pose = Pose2D(0.0, 0.0)
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
        )
        self._model = GasFieldModel(params)

        self.create_subscription(Odometry, "/odom", self._odom_callback, 10)
        self._concentration_pub = self.create_publisher(Float32, "/gas_concentration", 10)
        self._marker_pub = self.create_publisher(Marker, "/gas_source_marker", 1)
        self.create_timer(1.0 / float(self.get_parameter("publish_rate_hz").value), self._publish)

    def _odom_callback(self, msg: Odometry) -> None:
        self._pose = Pose2D(msg.pose.pose.position.x, msg.pose.pose.position.y)

    def _publish(self) -> None:
        concentration = self._model.concentration_at(self._pose)
        self._concentration_pub.publish(Float32(data=float(concentration)))

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
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
