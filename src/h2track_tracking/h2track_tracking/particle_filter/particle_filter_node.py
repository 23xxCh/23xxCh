"""ROS 2 lifecycle node that wraps ParticleFilter for gas source localization.

Converted to LifecycleNode following ros2-engineering-skills pattern:
- on_configure: create filter, declare parameters, create subscriptions
- on_activate: create publishers, start timer
- on_deactivate: stop timer
- on_cleanup: reset filter
"""

from __future__ import annotations

import ast

from geometry_msgs.msg import Pose, PoseArray, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Float32

from .filter import ParticleFilter
from .types import ParticleFilterConfig


class ParticleFilterNode(LifecycleNode):
    """ROS 2 lifecycle node for probabilistic gas source localization.

    Subscribers:
        /gas_concentration (Float32): Gas sensor reading
        /odom (Odometry): Robot odometry for position

    Publishers (active only):
        /estimated_source (PoseWithCovarianceStamped): Estimated source position with covariance
        /particle_cloud (PoseArray): Particle positions for visualization
    """

    def __init__(self) -> None:
        super().__init__("particle_filter_node")

        # Declare parameters
        self.declare_parameter("num_particles", 500)
        self.declare_parameter("motion_sigma", 0.3)
        self.declare_parameter("observation_sigma", 0.5)
        self.declare_parameter("plume_sigma", 2.0)
        self.declare_parameter("source_strength", 1.0)
        self.declare_parameter("bounds", [-10.0, -10.0, 10.0, 10.0])
        self.declare_parameter("publish_rate", 2.0)
        self.declare_parameter("resample_threshold", 0.5)

        # State (initialized in on_configure)
        self._filter: ParticleFilter | None = None
        self._bounds: tuple[float, float, float, float] = (-10, -10, 10, 10)
        self._robot_position: tuple[float, float] = (0.0, 0.0)
        self._last_odom_position: tuple[float, float] | None = None
        self._estimate_pub = None
        self._particle_pub = None
        self._timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Create filter and subscriptions (no publishers or timers)."""
        num_particles = int(self.get_parameter("num_particles").value)
        motion_sigma = float(self.get_parameter("motion_sigma").value)
        observation_sigma = float(self.get_parameter("observation_sigma").value)
        plume_sigma = float(self.get_parameter("plume_sigma").value)
        source_strength = float(self.get_parameter("source_strength").value)
        resample_threshold = float(self.get_parameter("resample_threshold").value)

        # Parse bounds
        bounds_raw = self.get_parameter("bounds").value
        if isinstance(bounds_raw, str):
            try:
                bounds = ast.literal_eval(bounds_raw)
            except (ValueError, SyntaxError):
                self.get_logger().warning(f"Failed to parse bounds string: {bounds_raw}")
                bounds = [-10.0, -10.0, 10.0, 10.0]
        else:
            bounds = bounds_raw
        if not isinstance(bounds, (list, tuple)) or len(bounds) < 4:
            bounds = [-10.0, -10.0, 10.0, 10.0]
        self._bounds = (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))

        # Create and initialize filter
        config = ParticleFilterConfig(
            num_particles=num_particles,
            motion_sigma=motion_sigma,
            observation_sigma=observation_sigma,
            plume_sigma=plume_sigma,
            source_strength=source_strength,
            resample_threshold=resample_threshold,
        )
        self._filter = ParticleFilter(config)
        self._filter.initialize(self._bounds)

        # Create subscriptions (data flows even when inactive)
        self.create_subscription(Float32, "/gas_concentration", self._gas_concentration_callback, 10)
        self.create_subscription(Odometry, "/odom", self._odom_callback, 10)

        self.get_logger().info(
            f"ParticleFilterNode configured with {num_particles} particles, bounds={self._bounds}"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Create publishers and start timer."""
        state_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        vis_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._estimate_pub = self.create_publisher(PoseWithCovarianceStamped, "/estimated_source", state_qos)
        self._particle_pub = self.create_publisher(PoseArray, "/particle_cloud", vis_qos)

        publish_rate = float(self.get_parameter("publish_rate").value)
        if publish_rate > 0:
            self._timer = self.create_timer(1.0 / publish_rate, self._timer_callback)

        self.get_logger().info("ParticleFilterNode activated")
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Stop the timer."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.get_logger().info("ParticleFilterNode deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Reset filter and release resources."""
        self._filter = None
        self._estimate_pub = None
        self._particle_pub = None
        self._robot_position = (0.0, 0.0)
        self.get_logger().info("ParticleFilterNode cleaned up")
        return TransitionCallbackReturn.SUCCESS

    def _gas_concentration_callback(self, msg: Float32) -> None:
        """Handle gas concentration messages."""
        if self._filter is None:
            return
        concentration = float(msg.data)
        self._filter.update(self._robot_position, concentration)

        effective_count = self._filter.effective_particle_count()
        threshold_count = self._filter.config.resample_threshold * len(self._filter.particles)
        if effective_count < threshold_count:
            self._filter.resample()

    def _odom_callback(self, msg: Odometry) -> None:
        """Handle odometry messages."""
        if self._filter is None:
            return
        x = float(msg.pose.pose.position.x)
        y = float(msg.pose.pose.position.y)
        self._robot_position = (x, y)
        self._filter.predict(dt=1.0)

    def _timer_callback(self) -> None:
        """Periodic callback to publish estimates."""
        self._publish_estimate()
        self._publish_particle_cloud()

    def _publish_estimate(self) -> None:
        """Publish source estimate with covariance."""
        if self._filter is None or self._estimate_pub is None:
            return

        estimate = self._filter.estimate()
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = estimate.position[0]
        msg.pose.pose.position.y = estimate.position[1]
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.w = 1.0

        cov_2d = estimate.covariance
        cov_6d = np.zeros((6, 6))
        cov_6d[0, 0] = cov_2d[0, 0] if cov_2d.shape == (2, 2) else 1.0
        cov_6d[1, 1] = cov_2d[1, 1] if cov_2d.shape == (2, 2) else 1.0
        cov_6d[0, 1] = cov_2d[0, 1] if cov_2d.shape == (2, 2) else 0.0
        cov_6d[1, 0] = cov_2d[1, 0] if cov_2d.shape == (2, 2) else 0.0
        msg.pose.covariance = cov_6d.flatten().tolist()
        self._estimate_pub.publish(msg)

    def _publish_particle_cloud(self) -> None:
        """Publish particle positions for visualization."""
        if self._filter is None or self._particle_pub is None:
            return

        msg = PoseArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        for particle in self._filter.particles:
            pose = Pose()
            pose.position.x = float(particle.position[0])
            pose.position.y = float(particle.position[1])
            pose.position.z = 0.0
            pose.orientation.w = 1.0
            msg.poses.append(pose)

        self._particle_pub.publish(msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ParticleFilterNode()
    # Auto-transition for standalone usage (no lifecycle_manager)
    from rclpy.lifecycle import LifecycleState
    node.on_configure(LifecycleState(state_id=0, label="unconfigured"))
    node.on_activate(LifecycleState(state_id=1, label="inactive"))
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
