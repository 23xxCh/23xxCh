"""ROS 2 node that wraps ParticleFilter for gas source localization."""

from __future__ import annotations

from geometry_msgs.msg import Pose, PoseArray, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

from .filter import ParticleFilter
from .types import ParticleFilterConfig


class ParticleFilterNode(Node):
    """ROS 2 node for probabilistic gas source localization using particle filter.

    Subscribers:
        /gas_concentration (Float32): Gas sensor reading
        /odom (Odometry): Robot odometry for position

    Publishers:
        /estimated_source (PoseWithCovarianceStamped): Estimated source position with covariance
        /particle_cloud (PoseArray): Particle positions for visualization

    Parameters:
        num_particles (int): Number of particles (default: 500)
        motion_sigma (float): Motion noise standard deviation in meters (default: 0.3)
        observation_sigma (float): Observation noise standard deviation (default: 0.5)
        plume_sigma (float): Plume dispersion parameter (default: 2.0)
        source_strength (float): Source strength parameter (default: 1.0)
        bounds (double[]): Bounds as [min_x, min_y, max_x, max_y] (default: [-10, -10, 10, 10])
        publish_rate (float): Publishing rate in Hz (default: 2.0)
        resample_threshold (float): Effective particle ratio threshold for resampling (default: 0.5)
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

        # Get parameters
        num_particles = int(self.get_parameter("num_particles").value)
        motion_sigma = float(self.get_parameter("motion_sigma").value)
        observation_sigma = float(self.get_parameter("observation_sigma").value)
        plume_sigma = float(self.get_parameter("plume_sigma").value)
        source_strength = float(self.get_parameter("source_strength").value)
        bounds = self.get_parameter("bounds").value
        publish_rate = float(self.get_parameter("publish_rate").value)
        resample_threshold = float(self.get_parameter("resample_threshold").value)

        # Validate bounds
        if len(bounds) < 4:
            self.get_logger().warning("Invalid bounds parameter, using defaults")
            bounds = [-10.0, -10.0, 10.0, 10.0]

        self._bounds = (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))

        # Create filter config
        config = ParticleFilterConfig(
            num_particles=num_particles,
            motion_sigma=motion_sigma,
            observation_sigma=observation_sigma,
            plume_sigma=plume_sigma,
            source_strength=source_strength,
            resample_threshold=resample_threshold,
        )

        # Initialize filter
        self._filter = ParticleFilter(config)
        self._filter.initialize(self._bounds)

        # Robot state
        self._robot_position: tuple[float, float] = (0.0, 0.0)
        self._last_odom_position: tuple[float, float] | None = None

        # Create publishers
        self._estimate_pub = self.create_publisher(
            PoseWithCovarianceStamped,
            "/estimated_source",
            10
        )
        self._particle_pub = self.create_publisher(
            PoseArray,
            "/particle_cloud",
            10
        )

        # Create subscriptions
        self.create_subscription(
            Float32,
            "/gas_concentration",
            self._gas_concentration_callback,
            10
        )
        self.create_subscription(
            Odometry,
            "/odom",
            self._odom_callback,
            10
        )

        # Create timer for periodic publishing
        if publish_rate > 0:
            timer_period = 1.0 / publish_rate
            self._timer = self.create_timer(timer_period, self._timer_callback)
        else:
            self._timer = None

        self.get_logger().info(
            f"ParticleFilterNode initialized with {num_particles} particles, "
            f"bounds={self._bounds}, publish_rate={publish_rate}Hz"
        )

    def _gas_concentration_callback(self, msg: Float32) -> None:
        """Handle gas concentration messages.

        Updates particle weights based on the observation.
        """
        concentration = float(msg.data)

        # Update filter with observation
        self._filter.update(self._robot_position, concentration)

        # Check if resampling is needed
        effective_count = self._filter.effective_particle_count()
        threshold_count = self._filter.config.resample_threshold * len(self._filter.particles)

        if effective_count < threshold_count:
            self.get_logger().debug(
                f"Resampling: effective_count={effective_count:.1f}, threshold={threshold_count:.1f}"
            )
            self._filter.resample()

    def _odom_callback(self, msg: Odometry) -> None:
        """Handle odometry messages.

        Updates robot position and triggers predict step.
        """
        x = float(msg.pose.pose.position.x)
        y = float(msg.pose.pose.position.y)
        self._robot_position = (x, y)

        # Trigger predict step with small dt
        # (motion model adds noise to particle positions)
        self._filter.predict(dt=1.0)

    def _timer_callback(self) -> None:
        """Periodic callback to publish estimates."""
        self._publish_estimate()
        self._publish_particle_cloud()

    def _publish_estimate(self) -> None:
        """Publish source estimate with covariance."""
        estimate = self._filter.estimate()

        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        # Position
        msg.pose.pose.position.x = estimate.position[0]
        msg.pose.pose.position.y = estimate.position[1]
        msg.pose.pose.position.z = 0.0

        # Orientation (identity - no orientation information)
        msg.pose.pose.orientation.w = 1.0

        # Covariance (6x6 matrix stored as 36-element array)
        # Position x, y covariance from filter estimate
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
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
