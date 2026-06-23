"""ROS lifecycle node that publishes a simplified hydrogen concentration signal.

Converted to LifecycleNode following ros2-engineering-skills pattern:
- on_configure: create model, declare parameters, create subscriptions
- on_activate: create publishers, start timer
- on_deactivate: stop timer
- on_cleanup: release resources

Sim2real features (opt-in via parameters):
- Realistic sensor model (response delay, baseline drift, noise, quantization)
- Time-varying wind (direction random walk + gusts → plume meandering)
"""

from __future__ import annotations

import random as _random

from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Float32
from visualization_msgs.msg import Marker

from .gas_model import GasFieldModel, GasFieldParams
from .sensor_model import SensorModel, SensorModelConfig
from .wind_model import TimeVaryingWindModel, WindModelConfig
from h2track_utils.types import Pose2D  # canonical definition


class GasFieldNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("gas_field_node")
        # --- Gas field parameters ---
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
        self.declare_parameter("seed", -1)  # -1 = use system entropy

        # --- Sim2real: realistic sensor model ---
        self.declare_parameter("use_realistic_sensor", False)
        self.declare_parameter("sensor_response_tau", 8.0)
        self.declare_parameter("sensor_recovery_tau", 20.0)
        self.declare_parameter("sensor_noise_stddev", 0.5)
        self.declare_parameter("sensor_quantization", 0.1)
        self.declare_parameter("sensor_saturation", 500.0)
        self.declare_parameter("sensor_baseline_drift_rate", 0.01)
        self.declare_parameter("sensor_baseline_drift_max", 2.0)

        # --- Sim2real: time-varying wind ---
        self.declare_parameter("use_time_varying_wind", False)
        self.declare_parameter("wind_mean_speed", 0.4)
        self.declare_parameter("wind_mean_direction_deg", 0.0)
        self.declare_parameter("wind_direction_stddev_deg", 15.0)
        self.declare_parameter("wind_gust_rate", 0.05)
        self.declare_parameter("wind_gust_strength_factor", 0.5)
        self.declare_parameter("wind_gust_duration", 3.0)

        self._pose = Pose2D(0.0, 0.0)
        self._model: GasFieldModel | None = None
        self._sensor: SensorModel | None = None
        self._wind_model: TimeVaryingWindModel | None = None
        self._concentration_pub = None
        self._marker_pub = None
        self._timer = None
        self._last_stamp: float | None = None

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

        seed = int(self.get_parameter("seed").value)
        rng = _random.Random(seed) if seed >= 0 else _random.Random()
        self._model = GasFieldModel(params, rng=rng)

        # Optional realistic sensor model
        if self.get_parameter("use_realistic_sensor").value:
            sensor_config = SensorModelConfig(
                response_tau=float(self.get_parameter("sensor_response_tau").value),
                recovery_tau=float(self.get_parameter("sensor_recovery_tau").value),
                noise_stddev=float(self.get_parameter("sensor_noise_stddev").value),
                quantization_resolution=float(self.get_parameter("sensor_quantization").value),
                saturation=float(self.get_parameter("sensor_saturation").value),
                baseline_drift_rate=float(self.get_parameter("sensor_baseline_drift_rate").value),
                baseline_drift_max=float(self.get_parameter("sensor_baseline_drift_max").value),
            )
            self._sensor = SensorModel(self._model, sensor_config, rng=_random.Random(seed))
            self.get_logger().info(
                f"Realistic sensor model enabled: tau={sensor_config.response_tau}s/"
                f"{sensor_config.recovery_tau}s"
            )

        # Optional time-varying wind
        if self.get_parameter("use_time_varying_wind").value:
            wind_config = WindModelConfig(
                mean_speed=float(self.get_parameter("wind_mean_speed").value),
                mean_direction_deg=float(self.get_parameter("wind_mean_direction_deg").value),
                direction_stddev_deg=float(self.get_parameter("wind_direction_stddev_deg").value),
                gust_rate=float(self.get_parameter("wind_gust_rate").value),
                gust_strength_factor=float(self.get_parameter("wind_gust_strength_factor").value),
                gust_duration=float(self.get_parameter("wind_gust_duration").value),
                seed=seed,
            )
            self._wind_model = TimeVaryingWindModel(wind_config)
            self.get_logger().info(
                f"Time-varying wind enabled: mean={wind_config.mean_speed} m/s "
                f"@ {wind_config.mean_direction_deg}°, "
                f"σ={wind_config.direction_stddev_deg}°"
            )

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
        self._sensor = None
        self._wind_model = None
        self._concentration_pub = None
        self._marker_pub = None
        self.get_logger().info("GasFieldNode cleaned up")
        return TransitionCallbackReturn.SUCCESS

    def _odom_callback(self, msg: Odometry) -> None:
        self._pose = Pose2D(msg.pose.pose.position.x, msg.pose.pose.position.y)

    def _publish(self) -> None:
        if self._model is None or self._concentration_pub is None:
            return

        # Compute dt from clock for accurate sensor dynamics
        now_sec = self.get_clock().now().nanoseconds * 1e-9
        if self._last_stamp is not None:
            dt = max(0.001, now_sec - self._last_stamp)
        else:
            dt = 0.1
        self._last_stamp = now_sec

        # Update time-varying wind and apply to gas model
        if self._wind_model is not None:
            wx, wy = self._wind_model.update(dt)
            self._model.set_wind(wx, wy)

        # Get concentration: realistic sensor (with dynamics) or ideal
        if self._sensor is not None:
            concentration = self._sensor.update(self._pose, dt=dt)
        else:
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
    # Auto-transition for standalone usage (no lifecycle_manager)
    from rclpy.lifecycle import LifecycleState
    node.on_configure(LifecycleState(state_id=0, label="unconfigured"))
    node.on_activate(LifecycleState(state_id=1, label="inactive"))
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
