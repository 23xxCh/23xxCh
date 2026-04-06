"""ROS node that manages patrol and hydrogen tracking goals."""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Bool, Float32, String
from tf2_ros import Buffer, TransformException, TransformListener

from .gas_model import GasFieldModel, GasFieldParams, Pose2D
from .mission_logic import MissionConfig, MissionMode, MissionStateMachine
from .navigation_executor import (
    coerce_patrol_points,
    determine_nav_action_on_result,
    map_pose_from_amcl,
    should_skip_patrol_goal,
)
from .tracking import (
    SurgeCastConfig,
    SurgeCastTracker,
    TrackingState,
    ParticleFilterIntegrator,
)


class MissionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("mission_manager_node")
        self.declare_parameter("initial_pose_x", 0.0)
        self.declare_parameter("initial_pose_y", 0.0)
        self.declare_parameter("initial_pose_yaw", 0.0)
        self.declare_parameter("patrol_points", "[3.0, 3.0, -3.0, 3.0, -3.0, -3.0, 3.0, -3.0]")
        self.declare_parameter("enter_threshold", 4.0)
        self.declare_parameter("exit_threshold", 1.5)
        self.declare_parameter("source_threshold", 8.0)
        self.declare_parameter("confirm_samples", 3)
        self.declare_parameter("track_exit_samples", 3)
        self.declare_parameter("source_radius", 0.6)
        self.declare_parameter("source_hold_steps", 3)
        self.declare_parameter("track_step", 0.7)
        self.declare_parameter("sweep_angle_deg", 30.0)
        self.declare_parameter("source_x", -3.5)
        self.declare_parameter("source_y", -3.5)
        self.declare_parameter("patrol_goal_timeout_sec", 45.0)
        self.declare_parameter("goal_reject_retry_sec", 2.0)
        self.declare_parameter("localizer_node", "amcl")
        self.declare_parameter("use_slam", False)
        self.declare_parameter("publish_initial_pose", True)
        self.declare_parameter("use_particle_filter_estimate", True)
        self.declare_parameter("particle_filter_min_confidence", 0.3)

        # Surge-Cast parameters
        self.declare_parameter("use_surge_cast", True)
        self.declare_parameter("plume_found_threshold", 5.0)
        self.declare_parameter("plume_lost_threshold", 2.0)
        self.declare_parameter("surge_step", 0.5)
        self.declare_parameter("cast_step", 0.3)
        self.declare_parameter("cast_distance_limit", 3.0)
        self.declare_parameter("wind_x", 0.4)
        self.declare_parameter("wind_y", 0.0)

        patrol_points = coerce_patrol_points(self.get_parameter("patrol_points").value)
        config = MissionConfig(
            patrol_points=patrol_points,
            enter_threshold=float(self.get_parameter("enter_threshold").value),
            exit_threshold=float(self.get_parameter("exit_threshold").value),
            source_threshold=float(self.get_parameter("source_threshold").value),
            confirm_samples=int(self.get_parameter("confirm_samples").value),
            track_exit_samples=int(self.get_parameter("track_exit_samples").value),
            source_radius=float(self.get_parameter("source_radius").value),
            source_hold_steps=int(self.get_parameter("source_hold_steps").value),
            actual_source=(
                float(self.get_parameter("source_x").value),
                float(self.get_parameter("source_y").value),
            ),
        )
        self._machine = MissionStateMachine(config)
        self._gas_model = GasFieldModel(
            GasFieldParams(
                source_x=float(self.get_parameter("source_x").value),
                source_y=float(self.get_parameter("source_y").value),
                source_strength=120.0,
                decay_rate=0.55,
                plume_stddev=1.2,
                wind_x=0.4,
                wind_y=0.0,
                noise_stddev=0.0,
                min_concentration=0.0,
            )
        )
        self._navigator = BasicNavigator()
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._initial_pose = Pose2D(
            float(self.get_parameter("initial_pose_x").value),
            float(self.get_parameter("initial_pose_y").value),
        )
        self._initial_yaw = float(self.get_parameter("initial_pose_yaw").value)
        self._localizer_node = str(self.get_parameter("localizer_node").value).strip().lower()
        self._use_slam = bool(self.get_parameter("use_slam").value)
        self._publish_initial_pose = bool(self.get_parameter("publish_initial_pose").value)
        self._patrol_goal_timeout_sec = float(self.get_parameter("patrol_goal_timeout_sec").value)
        self._goal_reject_retry_sec = float(self.get_parameter("goal_reject_retry_sec").value)
        if not self._localizer_node:
            self._localizer_node = "none" if self._use_slam else "amcl"
        self._current_pose = Pose2D(0.0, 0.0)
        self._current_yaw = 0.0
        self._current_concentration = 0.0
        self._history: list[tuple[Pose2D, float]] = []
        self._active_mode = None
        self._nav_ready = False
        self._initial_pose_sent = False
        self._current_goal_kind = None
        self._goal_started_at_sec: float | None = None
        self._retry_goal_kind: str | None = None
        self._retry_goal_at_sec: float | None = None
        self._source_announced = False
        self._use_particle_filter_estimate = bool(self.get_parameter("use_particle_filter_estimate").value)
        self._particle_filter_min_confidence = float(self.get_parameter("particle_filter_min_confidence").value)
        self._particle_filter_estimate: Pose2D | None = None
        self._particle_filter_confidence: float = 0.0

        # Surge-Cast tracker
        self._use_surge_cast = bool(self.get_parameter("use_surge_cast").value)
        self._surge_cast_config = SurgeCastConfig(
            plume_found_threshold=float(self.get_parameter("plume_found_threshold").value),
            plume_lost_threshold=float(self.get_parameter("plume_lost_threshold").value),
            source_threshold=float(self.get_parameter("source_threshold").value),
            surge_step=float(self.get_parameter("surge_step").value),
            cast_step=float(self.get_parameter("cast_step").value),
            cast_distance_limit=float(self.get_parameter("cast_distance_limit").value),
            wind_x=float(self.get_parameter("wind_x").value),
            wind_y=float(self.get_parameter("wind_y").value),
            use_particle_filter=self._use_particle_filter_estimate,
            min_pf_confidence=self._particle_filter_min_confidence,
            source_radius=float(self.get_parameter("source_radius").value),
            source_hold_steps=int(self.get_parameter("source_hold_steps").value),
        )
        self._surge_cast_tracker = SurgeCastTracker(self._surge_cast_config)
        self._pf_integrator = ParticleFilterIntegrator()

        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._amcl_pose_callback, 10)
        self.create_subscription(PoseWithCovarianceStamped, "/estimated_source", self._particle_filter_callback, 10)
        self.create_subscription(Float32, "/gas_concentration", self._concentration_callback, 10)
        self._mode_pub = self.create_publisher(String, "/robot_mode", 10)
        self._source_pub = self.create_publisher(Bool, "/source_found", 10)
        self._estimate_pub = self.create_publisher(PoseStamped, "/estimated_source_pose", 10)
        self.create_timer(1.0, self._control_loop)

    def _amcl_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        self._current_pose, self._current_yaw = map_pose_from_amcl(msg)

    def _concentration_callback(self, msg: Float32) -> None:
        self._current_concentration = float(msg.data)
        self._history.append((self._current_pose, self._current_concentration))
        self._history = self._history[-50:]  # Keep more history for better tracking

    def _particle_filter_callback(self, msg: PoseWithCovarianceStamped) -> None:
        """Handle particle filter source estimate."""
        self._particle_filter_estimate = Pose2D(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
        )
        # Extract confidence from covariance (inverse of variance)
        cov_x = msg.pose.covariance[0]
        cov_y = msg.pose.covariance[7]
        if cov_x > 0 and cov_y > 0:
            # Lower covariance = higher confidence
            self._particle_filter_confidence = min(1.0, 1.0 / (np.sqrt(cov_x * cov_y) + 0.1))
        else:
            self._particle_filter_confidence = 0.0

        # Update particle filter integrator
        self._pf_integrator.update(
            position=(msg.pose.pose.position.x, msg.pose.pose.position.y),
            confidence=self._particle_filter_confidence,
            covariance=(cov_x, cov_y, msg.pose.covariance[1], msg.pose.covariance[6]),
        )

    def _make_goal(self, x: float, y: float, yaw: float = 0.0) -> PoseStamped:
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        return goal

    def _send_patrol_goal(self) -> bool:
        goal_x, goal_y = self._machine.current_patrol_goal
        accepted = self._navigator.goToPose(self._make_goal(goal_x, goal_y))
        if not accepted:
            self.get_logger().warning(
                f"Patrol goal rejected; retrying in {self._goal_reject_retry_sec:.1f}s."
            )
            self._current_goal_kind = None
            self._goal_started_at_sec = None
            self._schedule_goal_retry("patrol")
            return False
        self._current_goal_kind = "patrol"
        self._goal_started_at_sec = self._now_sec()
        self._clear_goal_retry()
        return True

    def _send_tracking_goal(self) -> bool:
        # Use Surge-Cast algorithm if enabled
        if self._use_surge_cast:
            action = self._surge_cast_tracker.update(
                concentration=self._current_concentration,
                robot_pose=Pose2D(self._current_pose.x, self._current_pose.y),
                robot_yaw=self._current_yaw,
            )

            # Check for source found
            if action.state == TrackingState.SOURCE_FOUND:
                self.get_logger().info("Source found via Surge-Cast!")
                # Don't send new goal, let the state machine handle it
                return True

            target = action.target
            self.get_logger().info(
                f"Surge-Cast {action.state.name}: target=({target.x:.2f}, {target.y:.2f}), "
                f"conc={self._current_concentration:.2f}"
            )
        else:
            # Legacy tracking with particle filter integration
            use_pf = (
                self._use_particle_filter_estimate
                and self._particle_filter_estimate is not None
                and self._particle_filter_confidence >= self._particle_filter_min_confidence
            )

            if use_pf:
                # Navigate toward particle filter estimated source
                target_x = self._particle_filter_estimate.x
                target_y = self._particle_filter_estimate.y
                self.get_logger().info(
                    f"Using particle filter estimate: ({target_x:.2f}, {target_y:.2f}) "
                    f"confidence={self._particle_filter_confidence:.2f}"
                )
                target = Pose2D(target_x, target_y)
            else:
                # Fall back to gradient-based tracking
                target = self._gas_model.next_search_target(
                    current_pose=self._current_pose,
                    current_yaw=self._current_yaw,
                    history=self._history,
                    step_size=float(self.get_parameter("track_step").value),
                    sweep_angle=math.radians(float(self.get_parameter("sweep_angle_deg").value)),
                )

        accepted = self._navigator.goToPose(self._make_goal(target.x, target.y))
        if not accepted:
            self.get_logger().warning(
                f"Tracking goal rejected; retrying in {self._goal_reject_retry_sec:.1f}s."
            )
            self._current_goal_kind = None
            self._goal_started_at_sec = None
            self._schedule_goal_retry("track")
            return False
        self._current_goal_kind = "track"
        self._goal_started_at_sec = self._now_sec()
        self._clear_goal_retry()
        return True

    def _publish_source_estimate(self) -> None:
        if self._machine.source_estimate is None:
            return
        estimate = self._make_goal(self._machine.source_estimate[0], self._machine.source_estimate[1])
        self._estimate_pub.publish(estimate)

    def _refresh_pose_from_tf(self) -> bool:
        try:
            transform = self._tf_buffer.lookup_transform("map", "base_link", Time())
        except TransformException:
            return False
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z),
        )
        self._current_pose = Pose2D(translation.x, translation.y)
        self._current_yaw = yaw
        return True

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _schedule_goal_retry(self, goal_kind: str) -> None:
        retry_delay = max(0.2, self._goal_reject_retry_sec)
        self._retry_goal_kind = goal_kind
        self._retry_goal_at_sec = self._now_sec() + retry_delay

    def _clear_goal_retry(self) -> None:
        self._retry_goal_kind = None
        self._retry_goal_at_sec = None

    def _maybe_retry_rejected_goal(self, mode: MissionMode) -> bool:
        if self._retry_goal_kind is None or self._retry_goal_at_sec is None:
            return False
        if self._now_sec() < self._retry_goal_at_sec:
            return False

        if self._retry_goal_kind == "patrol":
            if mode is not MissionMode.PATROL:
                self._clear_goal_retry()
                return False
            self.get_logger().info("Retrying patrol goal after rejection.")
            self._send_patrol_goal()
            return True

        if self._retry_goal_kind == "track":
            if mode is not MissionMode.SEEK_TRACK:
                self._clear_goal_retry()
                return False
            self.get_logger().info("Retrying tracking goal after rejection.")
            self._send_tracking_goal()
            return True

        self._clear_goal_retry()
        return False

    def _control_loop(self) -> None:
        tf_ready = self._refresh_pose_from_tf()

        if not self._nav_ready:
            if self._publish_initial_pose and not self._initial_pose_sent:
                initial_pose = self._make_goal(self._initial_pose.x, self._initial_pose.y, self._initial_yaw)
                self._navigator.setInitialPose(initial_pose)
                self._initial_pose_sent = True
            if self._localizer_node in ("", "none", "slam_toolbox", "slam"):
                if not tf_ready:
                    return
                if not self._navigator.nav_to_pose_client.wait_for_server(timeout_sec=0.2):
                    return
                self._navigator._waitForNodeToActivate("bt_navigator")
                self._navigator.info("Nav2 is ready for use!")
            else:
                self._navigator.waitUntilNav2Active(localizer=self._localizer_node)
            self._nav_ready = True
            self._send_patrol_goal()
            return

        task_complete = self._navigator.isTaskComplete()
        nav_result = None
        if task_complete:
            nav_result = self._navigator.getResult()
        goal_reached = task_complete and nav_result == TaskResult.SUCCEEDED
        previous_mode = self._machine.mode

        mode = self._machine.update(
            concentration=self._current_concentration,
            robot_position=(self._current_pose.x, self._current_pose.y),
            goal_reached=goal_reached,
        )

        if mode is not self._active_mode:
            self._mode_pub.publish(String(data=mode.name))
            self._active_mode = mode

        if previous_mode is not mode:
            self._clear_goal_retry()
            self.get_logger().info(
                "Mode transition: %s -> %s (conc=%.3f, pose=(%.2f, %.2f))"
                % (
                    previous_mode.name,
                    mode.name,
                    self._current_concentration,
                    self._current_pose.x,
                    self._current_pose.y,
                )
            )
            if mode is MissionMode.SEEK_CONFIRM:
                self._navigator.cancelTask()
                self._current_goal_kind = None
                self._goal_started_at_sec = None
            elif mode is MissionMode.SEEK_TRACK:
                self._navigator.cancelTask()
                self._send_tracking_goal()
            elif mode is MissionMode.PATROL:
                self._send_patrol_goal()
            elif mode is MissionMode.SOURCE_FOUND:
                self._navigator.cancelTask()
                self._current_goal_kind = None
                self._goal_started_at_sec = None
                self._source_pub.publish(Bool(data=True))
                self._publish_source_estimate()
                self._source_announced = True
            return

        if self._maybe_retry_rejected_goal(mode):
            return

        if (
            mode is MissionMode.PATROL
            and self._current_goal_kind == "patrol"
            and not task_complete
            and self._goal_started_at_sec is not None
            and (self._now_sec() - self._goal_started_at_sec) > self._patrol_goal_timeout_sec
        ):
            self.get_logger().warning("Patrol goal timed out; skipping to next waypoint.")
            self._navigator.cancelTask()
            self._machine.advance_patrol()
            self._send_patrol_goal()
            return

        if mode is MissionMode.PATROL and task_complete:
            if nav_result == TaskResult.SUCCEEDED:
                self._send_patrol_goal()
            elif nav_result in (TaskResult.FAILED, TaskResult.CANCELED):
                self.get_logger().warning(
                    f"Patrol goal finished with result={nav_result}; skipping to next waypoint."
                )
                self._machine.advance_patrol()
                self._send_patrol_goal()
        elif mode is MissionMode.SEEK_TRACK and task_complete:
            if nav_result == TaskResult.SUCCEEDED:
                # Check for Surge-Cast source found
                if self._use_surge_cast and self._surge_cast_tracker.current_state == TrackingState.SOURCE_FOUND:
                    self.get_logger().info("Source confirmed by Surge-Cast!")
                    # Trigger source found
                    self._navigator.cancelTask()
                    self._source_pub.publish(Bool(data=True))
                    source_estimate = self._surge_cast_tracker.source_estimate
                    if source_estimate:
                        estimate_msg = self._make_goal(source_estimate.x, source_estimate.y)
                        self._estimate_pub.publish(estimate_msg)
                    self._source_announced = True
                    return
                self._send_tracking_goal()
            elif nav_result in (TaskResult.FAILED, TaskResult.CANCELED):
                if self._retry_goal_kind is None:
                    self.get_logger().warning(
                        f"Tracking goal finished with result={nav_result}; scheduling retry."
                    )
                    self._schedule_goal_retry("track")
        elif mode is MissionMode.SOURCE_FOUND and not self._source_announced:
            self._source_pub.publish(Bool(data=True))
            self._publish_source_estimate()
            self._source_announced = True


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MissionManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
