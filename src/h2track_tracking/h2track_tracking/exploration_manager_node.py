from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool
from tf2_ros import Buffer, TransformListener, TransformException

from .exploration_logic import (
    GridSnapshot,
    goal_progress_stalled,
    navigation_state_allows_new_frontier,
    select_frontier_goal,
    FrontierGoal,
)


class ExplorationManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("exploration_manager_node")
        self.declare_parameter("control_period_sec", 1.0)
        self.declare_parameter("frontier_min_cluster_size", 6)
        self.declare_parameter("min_goal_distance", 0.8)
        self.declare_parameter("no_frontier_relaxed_after_cycles", 8)
        self.declare_parameter("no_frontier_relaxed_cluster_size", 1)
        self.declare_parameter("no_frontier_relaxed_min_goal_distance", 0.35)
        self.declare_parameter("min_goal_x", -1.0e9)
        self.declare_parameter("max_goal_x", 1.0e9)
        self.declare_parameter("min_goal_y", -1.0e9)
        self.declare_parameter("max_goal_y", 1.0e9)
        self.declare_parameter("stuck_timeout_sec", 15.0)
        self.declare_parameter("stuck_movement_epsilon", 0.08)
        self.declare_parameter("stuck_goal_tolerance", 0.45)
        self.declare_parameter("blocked_goal_ttl_sec", 60.0)
        self.declare_parameter("blocked_goal_radius", 0.9)
        self.declare_parameter("target_frame", "map")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("exploration_enabled_topic", "/exploration_enabled")

        self._navigator = BasicNavigator()
        self._tf_buffer = Buffer(cache_time=Duration(seconds=10.0))
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._grid: GridSnapshot | None = None
        self._nav_ready = False
        self._exploration_enabled = True
        self._no_frontier_cycles = 0
        self._active_goal: FrontierGoal | None = None
        self._last_progress_xy: tuple[float, float] | None = None
        self._last_progress_time_sec: float | None = None
        self._blocked_goals: list[tuple[float, float, float, float]] = []

        map_qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.create_subscription(OccupancyGrid, "/map", self._map_callback, map_qos)
        self.create_subscription(
            Bool,
            str(self.get_parameter("exploration_enabled_topic").value),
            self._exploration_enabled_callback,
            10,
        )
        self.create_timer(float(self.get_parameter("control_period_sec").value), self._control_loop)

    def _map_callback(self, msg: OccupancyGrid) -> None:
        self._grid = GridSnapshot(
            width=msg.info.width,
            height=msg.info.height,
            resolution=msg.info.resolution,
            origin_x=msg.info.origin.position.x,
            origin_y=msg.info.origin.position.y,
            data=list(msg.data),
        )

    def _exploration_enabled_callback(self, msg: Bool) -> None:
        self._exploration_enabled = bool(msg.data)
        if not self._exploration_enabled and not self._navigator.isTaskComplete():
            self._navigator.cancelTask()

    def _lookup_robot_xy(self) -> tuple[float, float] | None:
        target_frame = str(self.get_parameter("target_frame").value)
        robot_frame = str(self.get_parameter("robot_frame").value)
        try:
            transform = self._tf_buffer.lookup_transform(
                target_frame,
                robot_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException:
            return None
        return (
            transform.transform.translation.x,
            transform.transform.translation.y,
        )

    def _make_goal(self, x: float, y: float) -> PoseStamped:
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.w = 1.0
        return goal

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _prune_blocked_goals(self, now_sec: float) -> None:
        self._blocked_goals = [
            item for item in self._blocked_goals
            if item[3] > now_sec
        ]

    def _blocked_goal_regions(self, now_sec: float) -> list[tuple[float, float, float]]:
        self._prune_blocked_goals(now_sec)
        return [(x, y, radius) for x, y, radius, _ in self._blocked_goals]

    def _mark_active_goal_blocked(self, now_sec: float) -> None:
        if self._active_goal is None:
            return
        ttl_sec = max(0.0, float(self.get_parameter("blocked_goal_ttl_sec").value))
        radius = max(0.0, float(self.get_parameter("blocked_goal_radius").value))
        expires_at = now_sec + ttl_sec
        self._blocked_goals.append((self._active_goal.x, self._active_goal.y, radius, expires_at))
        self.get_logger().warn(
            "Exploration goal stalled; temporarily blocking frontier around "
            f"({self._active_goal.x:.2f}, {self._active_goal.y:.2f}) for {ttl_sec:.1f}s"
        )
        self._active_goal = None
        self._last_progress_xy = None
        self._last_progress_time_sec = None

    def _control_loop(self) -> None:
        if not self._nav_ready:
            self._navigator._waitForNodeToActivate('bt_navigator')
            self._navigator.info('Nav2 is ready for exploration use!')
            self._nav_ready = True
            return

        if self._grid is None:
            return

        if not self._exploration_enabled:
            self._no_frontier_cycles = 0
            self._active_goal = None
            self._last_progress_xy = None
            self._last_progress_time_sec = None
            return

        robot_xy = self._lookup_robot_xy()
        if robot_xy is None:
            return

        now_sec = self._now_sec()

        if self._active_goal is not None and self._last_progress_xy is not None:
            movement_epsilon = float(self.get_parameter("stuck_movement_epsilon").value)
            if math.dist(robot_xy, self._last_progress_xy) >= max(0.0, movement_epsilon):
                self._last_progress_xy = robot_xy
                self._last_progress_time_sec = now_sec

        if not navigation_state_allows_new_frontier(
            task_complete=self._navigator.isTaskComplete(),
            task_result=self._navigator.getResult(),
        ):
            if goal_progress_stalled(
                task_complete=self._navigator.isTaskComplete(),
                active_goal_xy=(
                    (self._active_goal.x, self._active_goal.y) if self._active_goal is not None else None
                ),
                robot_xy=robot_xy,
                last_progress_xy=self._last_progress_xy,
                last_progress_time_sec=self._last_progress_time_sec,
                now_sec=now_sec,
                movement_epsilon=float(self.get_parameter("stuck_movement_epsilon").value),
                stall_timeout_sec=float(self.get_parameter("stuck_timeout_sec").value),
                goal_tolerance=float(self.get_parameter("stuck_goal_tolerance").value),
            ):
                self._navigator.cancelTask()
                self._mark_active_goal_blocked(now_sec)
            return

        self._active_goal = None
        self._last_progress_xy = None
        self._last_progress_time_sec = None

        goal = select_frontier_goal(
            self._grid,
            robot_xy=robot_xy,
            min_frontier_cluster_size=int(self.get_parameter("frontier_min_cluster_size").value),
            min_goal_distance=float(self.get_parameter("min_goal_distance").value),
            min_goal_x=float(self.get_parameter("min_goal_x").value),
            max_goal_x=float(self.get_parameter("max_goal_x").value),
            min_goal_y=float(self.get_parameter("min_goal_y").value),
            max_goal_y=float(self.get_parameter("max_goal_y").value),
            blocked_goals=self._blocked_goal_regions(now_sec),
        )
        if goal is None:
            self._no_frontier_cycles += 1
            relaxed_after_cycles = int(
                self.get_parameter("no_frontier_relaxed_after_cycles").value
            )
            relaxed_cluster_size = int(
                self.get_parameter("no_frontier_relaxed_cluster_size").value
            )
            relaxed_min_goal_distance = float(
                self.get_parameter("no_frontier_relaxed_min_goal_distance").value
            )

            if self._no_frontier_cycles >= relaxed_after_cycles:
                goal = select_frontier_goal(
                    self._grid,
                    robot_xy=robot_xy,
                    min_frontier_cluster_size=relaxed_cluster_size,
                    min_goal_distance=relaxed_min_goal_distance,
                    min_goal_x=float(self.get_parameter("min_goal_x").value),
                    max_goal_x=float(self.get_parameter("max_goal_x").value),
                    min_goal_y=float(self.get_parameter("min_goal_y").value),
                    max_goal_y=float(self.get_parameter("max_goal_y").value),
                )
                if goal is not None:
                    self.get_logger().info(
                        "No strict frontier after "
                        f"{self._no_frontier_cycles} cycles; using relaxed frontier at "
                        f"({goal.x:.2f}, {goal.y:.2f})"
                    )
                    self._no_frontier_cycles = 0
                else:
                    self.get_logger().info("No frontier available; waiting for more map growth")
                    return
            else:
                self.get_logger().info("No frontier available; waiting for more map growth")
                return

        self._no_frontier_cycles = 0
        self.get_logger().info(f"Exploring frontier at ({goal.x:.2f}, {goal.y:.2f})")
        self._navigator.goToPose(self._make_goal(goal.x, goal.y))
        self._active_goal = goal
        self._last_progress_xy = robot_xy
        self._last_progress_time_sec = now_sec


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ExplorationManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
