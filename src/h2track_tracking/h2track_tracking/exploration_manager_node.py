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
    navigation_state_allows_new_frontier,
    select_frontier_goal,
)


class ExplorationManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("exploration_manager_node")
        self.declare_parameter("control_period_sec", 1.0)
        self.declare_parameter("frontier_min_cluster_size", 6)
        self.declare_parameter("min_goal_distance", 0.8)
        self.declare_parameter("target_frame", "map")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("exploration_enabled_topic", "/exploration_enabled")

        self._navigator = BasicNavigator()
        self._tf_buffer = Buffer(cache_time=Duration(seconds=10.0))
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._grid: GridSnapshot | None = None
        self._nav_ready = False
        self._exploration_enabled = True

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

    def _control_loop(self) -> None:
        if not self._nav_ready:
            self._navigator._waitForNodeToActivate('bt_navigator')
            self._navigator.info('Nav2 is ready for exploration use!')
            self._nav_ready = True
            return

        if self._grid is None:
            return

        if not self._exploration_enabled:
            return

        robot_xy = self._lookup_robot_xy()
        if robot_xy is None:
            return

        if not navigation_state_allows_new_frontier(
            task_complete=self._navigator.isTaskComplete(),
            task_result=self._navigator.getResult(),
        ):
            return

        goal = select_frontier_goal(
            self._grid,
            robot_xy=robot_xy,
            min_frontier_cluster_size=int(self.get_parameter("frontier_min_cluster_size").value),
            min_goal_distance=float(self.get_parameter("min_goal_distance").value),
        )
        if goal is None:
            self.get_logger().info("No frontier available; waiting for more map growth")
            return

        self.get_logger().info(f"Exploring frontier at ({goal.x:.2f}, {goal.y:.2f})")
        self._navigator.goToPose(self._make_goal(goal.x, goal.y))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ExplorationManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
