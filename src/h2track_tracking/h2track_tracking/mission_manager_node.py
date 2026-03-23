"""ROS node that manages patrol and hydrogen tracking goals."""

from __future__ import annotations

import ast
import math

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String

from .gas_model import GasFieldModel, GasFieldParams, Pose2D
from .mission_logic import MissionConfig, MissionMode, MissionStateMachine


def map_pose_from_amcl(msg: PoseWithCovarianceStamped) -> tuple[Pose2D, float]:
    position = msg.pose.pose.position
    orientation = msg.pose.pose.orientation
    yaw = math.atan2(
        2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z),
    )
    return Pose2D(position.x, position.y), yaw


def select_tracking_target(
    gas_model: GasFieldModel,
    current_pose: Pose2D,
    current_yaw: float,
    history: list[tuple[Pose2D, float]],
    step_size: float,
    sweep_angle: float,
    source_threshold: float,
) -> Pose2D:
    source_dx = gas_model.params.source_x - current_pose.x
    source_dy = gas_model.params.source_y - current_pose.y
    source_distance = math.hypot(source_dx, source_dy)

    def step_toward_model_source() -> Pose2D:
        if source_distance <= 1e-6:
            return current_pose
        scale = step_size / source_distance
        return Pose2D(
            x=current_pose.x + source_dx * scale,
            y=current_pose.y + source_dy * scale,
        )

    if history:
        strongest_index, (strongest_pose, strongest_concentration) = max(
            enumerate(history),
            key=lambda sample: sample[1][1],
        )
        strongest_radius = math.hypot(
            strongest_pose.x - current_pose.x,
            strongest_pose.y - current_pose.y,
        )
        if strongest_concentration >= source_threshold and strongest_index < len(history) - 1:
            if strongest_radius <= max(0.15, step_size * 0.5):
                return step_toward_model_source()
            return strongest_pose

    return gas_model.next_search_target(
        current_pose=current_pose,
        current_yaw=current_yaw,
        history=history,
        step_size=step_size,
        sweep_angle=sweep_angle,
    )


def _coerce_patrol_points(raw_value: object) -> list[tuple[float, float]]:
    if isinstance(raw_value, str):
        parsed = ast.literal_eval(raw_value)
    else:
        parsed = raw_value

    if not isinstance(parsed, list):
        raise ValueError(f"Unsupported patrol_points value: {parsed!r}")

    if parsed and isinstance(parsed[0], (list, tuple)):
        return [(float(x), float(y)) for x, y in parsed]

    flat_points = [float(v) for v in parsed]
    return list(zip(flat_points[0::2], flat_points[1::2]))


class MissionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("mission_manager_node")
        self.declare_parameter("start_in_tracking_mode", False)
        self.declare_parameter("tracking_only_mode", False)
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

        patrol_points = _coerce_patrol_points(self.get_parameter("patrol_points").value)
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
        self._start_in_tracking_mode = bool(self.get_parameter("start_in_tracking_mode").value)
        self._tracking_only_mode = bool(self.get_parameter("tracking_only_mode").value)
        self._initial_pose = Pose2D(
            float(self.get_parameter("initial_pose_x").value),
            float(self.get_parameter("initial_pose_y").value),
        )
        self._initial_yaw = float(self.get_parameter("initial_pose_yaw").value)
        self._current_pose = self._initial_pose
        self._current_yaw = self._initial_yaw
        self._current_concentration = 0.0
        self._history: list[tuple[Pose2D, float]] = []
        self._have_amcl_pose = False
        self._active_mode = None
        self._nav_ready = False
        self._current_goal_kind = None
        self._source_announced = False
        self._tracking_mode_start_consumed = False

        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._amcl_pose_callback, 10)
        self.create_subscription(Float32, "/gas_concentration", self._concentration_callback, 10)
        self._mode_pub = self.create_publisher(String, "/robot_mode", 10)
        self._source_pub = self.create_publisher(Bool, "/source_found", 10)
        self._estimate_pub = self.create_publisher(PoseStamped, "/estimated_source_pose", 10)
        self.create_timer(1.0, self._control_loop)

    def _amcl_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        self._current_pose, self._current_yaw = map_pose_from_amcl(msg)
        self._have_amcl_pose = True

    def _concentration_callback(self, msg: Float32) -> None:
        self._current_concentration = float(msg.data)
        self._history.append((self._current_pose, self._current_concentration))
        self._history = self._history[-8:]

    def _make_goal(self, x: float, y: float, yaw: float = 0.0) -> PoseStamped:
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        return goal

    def _send_patrol_goal(self) -> None:
        goal_x, goal_y = self._machine.current_patrol_goal
        self._navigator.goToPose(self._make_goal(goal_x, goal_y))
        self._current_goal_kind = "patrol"

    def _send_tracking_goal(self) -> None:
        next_target = select_tracking_target(
            gas_model=self._gas_model,
            current_pose=self._current_pose,
            current_yaw=self._current_yaw,
            history=self._history,
            step_size=float(self.get_parameter("track_step").value),
            sweep_angle=math.radians(float(self.get_parameter("sweep_angle_deg").value)),
            source_threshold=float(self.get_parameter("source_threshold").value),
        )
        self._navigator.goToPose(self._make_goal(next_target.x, next_target.y))
        self._current_goal_kind = "track"

    def _publish_source_estimate(self) -> None:
        if self._machine.source_estimate is None:
            return
        estimate = self._make_goal(self._machine.source_estimate[0], self._machine.source_estimate[1])
        self._estimate_pub.publish(estimate)

    def _enter_tracking_mode(self) -> None:
        self._machine.mode = MissionMode.SEEK_TRACK
        if self._active_mode is not MissionMode.SEEK_TRACK:
            self._mode_pub.publish(String(data=MissionMode.SEEK_TRACK.name))
            self._active_mode = MissionMode.SEEK_TRACK

    def _control_loop(self) -> None:
        if not self._nav_ready:
            initial_pose = self._make_goal(self._initial_pose.x, self._initial_pose.y, self._initial_yaw)
            self._navigator.setInitialPose(initial_pose)
            self._navigator.waitUntilNav2Active(localizer="amcl")
            self._nav_ready = True
            if self._start_in_tracking_mode and not self._tracking_mode_start_consumed:
                self._enter_tracking_mode()
                self._tracking_mode_start_consumed = True
                self._send_tracking_goal()
            else:
                self._send_patrol_goal()
            return

        task_complete = self._navigator.isTaskComplete()
        previous_mode = self._machine.mode

        mode = self._machine.update(
            concentration=self._current_concentration,
            robot_position=(self._current_pose.x, self._current_pose.y),
            goal_reached=task_complete,
        )
        if self._tracking_only_mode and mode is MissionMode.PATROL:
            self._machine.mode = MissionMode.SEEK_TRACK
            mode = MissionMode.SEEK_TRACK

        if mode is not self._active_mode:
            self._mode_pub.publish(String(data=mode.name))
            self._active_mode = mode

        if (
            self._start_in_tracking_mode
            and mode is MissionMode.SEEK_TRACK
            and self._current_goal_kind is None
        ):
            self._send_tracking_goal()
            return

        if previous_mode is not mode:
            if mode is MissionMode.SEEK_CONFIRM:
                self._navigator.cancelTask()
                self._current_goal_kind = None
            elif mode is MissionMode.SEEK_TRACK:
                self._navigator.cancelTask()
                self._send_tracking_goal()
            elif mode is MissionMode.PATROL:
                self._send_patrol_goal()
            elif mode is MissionMode.SOURCE_FOUND:
                self._navigator.cancelTask()
                self._current_goal_kind = None
                self._source_pub.publish(Bool(data=True))
                self._publish_source_estimate()
                self._source_announced = True
            return

        if mode is MissionMode.PATROL and task_complete:
            if self._navigator.getResult() in (TaskResult.SUCCEEDED, TaskResult.CANCELED, TaskResult.FAILED):
                self._send_patrol_goal()
        elif mode is MissionMode.SEEK_TRACK and task_complete:
            self._send_tracking_goal()
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
