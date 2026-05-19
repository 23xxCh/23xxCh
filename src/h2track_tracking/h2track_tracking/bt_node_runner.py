#!/usr/bin/env python3
"""Behavior Tree node runner.

Full replacement for the legacy MissionManagerNode.  All ROS I/O stays here;
the py_trees BehaviourTree handles orchestration decisions.
"""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.msg import Costmap
from nav2_simple_commander.robot_navigator import BasicNavigator
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Bool, Float32, String
from tf2_ros import Buffer, TransformException, TransformListener


from h2track_tracking.bt.blackboard import H2TrackBlackboard
from h2track_tracking.bt.tree_factory import TreeFactory
from h2track_tracking.tracking.types import Pose2D, SurgeCastConfig
from h2track_tracking.tracking.surge_cast import SurgeCastTracker
from h2track_tracking.tracking.fusion import TrackingFusion, FusionConfig
from h2track_tracking.tracking.costmap_checker import CostmapChecker
from h2track_tracking.tracking.wind_estimator import WindEstimator, WindEstimatorConfig
from h2track_tracking.navigation_executor import (
    coerce_patrol_points,
    map_pose_from_amcl,
    should_skip_patrol_goal,
)
from h2track_tracking.mission_logic import MissionConfig, MissionMode, MissionStateMachine


class BTNodeRunner(Node):
    """Full-featured ROS node.  BT tree handles orchestration; this node
    handles all ROS I/O, Nav2 lifecycle, and parameter management."""

    def __init__(self) -> None:
        super().__init__("bt_node_runner")

        # -- canonical defaults from dataclasses (single source of truth) -----
        _mc = MissionConfig(patrol_points=[])
        _sc = SurgeCastConfig()

        # -- ROS parameters --------------------------------------------------
        self.declare_parameter("initial_pose_x", 0.0)
        self.declare_parameter("initial_pose_y", 0.0)
        self.declare_parameter("initial_pose_yaw", 0.0)
        self.declare_parameter("patrol_points", _DEFAULT_PATROL)
        self.declare_parameter("enter_threshold", _mc.enter_threshold)
        self.declare_parameter("exit_threshold", _mc.exit_threshold)
        self.declare_parameter("source_threshold", _mc.source_threshold)
        self.declare_parameter("confirm_samples", _mc.confirm_samples)
        self.declare_parameter("track_exit_samples", _mc.track_exit_samples or _mc.confirm_samples)
        self.declare_parameter("source_radius", _mc.source_radius)
        self.declare_parameter("source_hold_steps", _mc.source_hold_steps)
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
        self.declare_parameter("particle_filter_min_confidence", _sc.min_pf_confidence)
        self.declare_parameter("use_surge_cast", True)
        self.declare_parameter("surge_step", _sc.surge_step)
        self.declare_parameter("cast_step", _sc.cast_step)
        self.declare_parameter("cast_distance_limit", _sc.cast_distance_limit)
        self.declare_parameter("wind_x", _sc.wind_x)
        self.declare_parameter("wind_y", _sc.wind_y)
        self.declare_parameter("estimate_wind", True)
        self.declare_parameter("wind_estimation_min_samples", 10)
        self.declare_parameter("use_fusion", True)
        self.declare_parameter("fusion_mode", "weighted")
        self.declare_parameter("fusion_pf_weight", 0.3)
        self.declare_parameter("fusion_surge_weight", 0.7)

        # -- mission config --------------------------------------------------
        patrol_points = coerce_patrol_points(self.get_parameter("patrol_points").value)
        mission_cfg = MissionConfig(
            patrol_points=patrol_points,
            enter_threshold=self._pf("enter_threshold"),
            exit_threshold=self._pf("exit_threshold"),
            source_threshold=self._pf("source_threshold"),
            confirm_samples=self._pi("confirm_samples"),
            track_exit_samples=self._pi("track_exit_samples"),
            source_radius=self._pf("source_radius"),
            source_hold_steps=self._pi("source_hold_steps"),
            actual_source=(self._pf("source_x"), self._pf("source_y")),
        )

        # -- surge-cast config -----------------------------------------------
        surge_cfg = SurgeCastConfig(
            plume_found_threshold=self._pf("enter_threshold"),
            plume_lost_threshold=self._pf("exit_threshold"),
            source_threshold=self._pf("source_threshold"),
            surge_step=self._pf("surge_step"),
            cast_step=self._pf("cast_step"),
            cast_distance_limit=self._pf("cast_distance_limit"),
            wind_x=self._pf("wind_x"),
            wind_y=self._pf("wind_y"),
            source_radius=self._pf("source_radius"),
            source_hold_steps=self._pi("source_hold_steps"),
        )

        # -- domain objects --------------------------------------------------
        surge_tracker = SurgeCastTracker(surge_cfg)
        fusion = TrackingFusion(FusionConfig(
            blending_mode=str(self.get_parameter("fusion_mode").value),
            pf_weight_base=self._pf("fusion_pf_weight"),
            surge_weight=self._pf("fusion_surge_weight"),
            pf_confidence_threshold=self._pf("particle_filter_min_confidence"),
        ))
        costmap = CostmapChecker()
        self._state_machine = MissionStateMachine(mission_cfg)

        # -- blackboard & tree -----------------------------------------------
        self._bb = H2TrackBlackboard()
        self._tree_factory = TreeFactory(
            bb=self._bb,
            node=self,
            surge_tracker=surge_tracker,
            fusion=fusion,
            costmap_checker=costmap,
        )
        self._tree = self._tree_factory.create_tree()

        # -- Nav2 lifecycle --------------------------------------------------
        self._navigator = BasicNavigator()
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._initial_pose = Pose2D(self._pf("initial_pose_x"), self._pf("initial_pose_y"))
        self._initial_yaw = self._pf("initial_pose_yaw")
        self._localizer_node = str(self.get_parameter("localizer_node").value).strip().lower()
        self._use_slam = bool(self.get_parameter("use_slam").value)
        self._publish_initial_pose = bool(self.get_parameter("publish_initial_pose").value)
        self._nav_ready = False
        self._initial_pose_sent = False
        if not self._localizer_node:
            self._localizer_node = "none" if self._use_slam else "amcl"

        # -- ROS I/O ---------------------------------------------------------
        self._current_pose = Pose2D(0.0, 0.0)
        self._current_yaw = 0.0
        self._current_concentration = 0.0
        self._history: list[tuple[Pose2D, float]] = []
        self._particle_filter_estimate: Pose2D | None = None
        self._particle_filter_confidence: float = 0.0

        # wind estimator
        self._estimate_wind = bool(self.get_parameter("estimate_wind").value)
        self._wind_estimator = WindEstimator(WindEstimatorConfig(
            min_samples_for_estimate=self._pi("wind_estimation_min_samples"),
        ))
        self._estimated_wind: tuple[float, float] | None = None

        # subscriptions
        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, 10)
        self.create_subscription(PoseWithCovarianceStamped, "/estimated_source", self._on_pf, 10)
        self.create_subscription(Float32, "/gas_concentration", self._on_concentration, 10)
        self.create_subscription(Costmap, "/global_costmap/costmap", self._on_costmap, 10)

        # publishers
        self._mode_pub = self.create_publisher(String, "/robot_mode", 10)
        self._source_pub = self.create_publisher(Bool, "/source_found", 10)
        self._estimate_pub = self.create_publisher(PoseStamped, "/estimated_source_pose", 10)
        self._wind_pub = self.create_publisher(String, "/estimated_wind", 10)
        self._fusion_pub = self.create_publisher(String, "/fusion_state", 10)

        self._last_mode: MissionMode | None = None
        self._source_announced = False
        self._active_mode = None

        # -- main loop (10 Hz) -----------------------------------------------
        self.create_timer(0.1, self._tick)
        self.get_logger().info("BT Node Runner initialized (full replacement)")

    # ------------------------------------------------------------------
    # parameter helpers
    # ------------------------------------------------------------------

    def _pf(self, name: str) -> float:
        return float(self.get_parameter(name).value)

    def _pi(self, name: str) -> int:
        return int(self.get_parameter(name).value)

    # ------------------------------------------------------------------
    # Nav2 lifecycle
    # ------------------------------------------------------------------

    def _nav2_ready(self) -> bool:
        if not self._publish_initial_pose and self._initial_pose_sent:
            return True
        initial = self._make_pose_stamped(self._initial_pose, self._initial_yaw)
        self._navigator.setInitialPose(initial)
        self._initial_pose_sent = True
        if self._localizer_node in ("", "none", "slam_toolbox", "slam"):
            if not self._nav_to_pose_client_ready():
                return False
            self._navigator._waitForNodeToActivate("bt_navigator")
        else:
            self._navigator.waitUntilNav2Active(localizer=self._localizer_node)
        return True

    def _nav_to_pose_client_ready(self) -> bool:
        return self._navigator.nav_to_pose_client.wait_for_server(timeout_sec=0.2)

    # ------------------------------------------------------------------
    # blackboard sync helpers
    # ------------------------------------------------------------------

    def _sync_to_blackboard(self) -> None:
        """Route tracking/patrol targets to nav2 based on current mission mode."""
        bb = self._bb
        mode = bb.mission.mode

        if mode == MissionMode.SEEK_TRACK and bb.tracker.target is not None:
            bb.nav2.target_pose = bb.tracker.target
            bb.nav2.target_yaw = bb.tracker.heading
        elif mode in (MissionMode.PATROL, MissionMode.SEEK_CONFIRM):
            patrol = bb.mission.patrol_target
            if patrol is not None:
                bb.nav2.target_pose = patrol
                # Compute yaw toward patrol target from current pose
                dx = patrol.x - self._current_pose.x
                dy = patrol.y - self._current_pose.y
                bb.nav2.target_yaw = math.atan2(dy, dx)

    def _sync_from_blackboard(self) -> None:
        """Push BT outputs to ROS topics."""
        bb = self._bb
        # mode publication
        mode = bb.mission.mode
        if mode is not None and mode != self._last_mode:
            self.get_logger().info(f"Mode change: {self._last_mode} -> {mode}")
            self._mode_pub.publish(String(data=mode.name))
            self._last_mode = mode

        # source found
        if bb.mission.mode is not None and bb.mission.mode.name == "SOURCE_FOUND":
            if not self._source_announced:
                self._source_pub.publish(Bool(data=True))
                est = bb.mission.source_estimate
                if est is not None:
                    self._estimate_pub.publish(self._make_pose_stamped(
                        Pose2D(est[0], est[1]), 0.0
                    ))
                self._source_announced = True
        else:
            self._source_announced = False

        # wind estimate
        if self._estimated_wind is not None:
            wx, wy = self._estimated_wind
            self._wind_pub.publish(String(data=f"{wx:.3f},{wy:.3f},{0.5:.2f}"))

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        # ensure Nav2 is ready
        if not self._nav_ready:
            if not self._nav2_ready():
                return
            self._nav_ready = True
            self.get_logger().info("Nav2 ready, starting main loop")

        # - diagnostic: log every 50 ticks (~5s)
        self._tick_count = getattr(self, '_tick_count', 0) + 1
        if self._tick_count % 50 == 1:
            self.get_logger().info(
                f"tick #{self._tick_count} mode={self._last_mode} "
                f"pose=({self._current_pose.x:.2f},{self._current_pose.y:.2f}) "
                f"conc={self._current_concentration:.3f}"
            )

        # -- push sensor data to blackboard (was SensorReaderNode) ----------
        bb = self._bb
        bb.sensor.concentration = self._current_concentration
        bb.sensor.robot_pose = self._current_pose
        bb.sensor.robot_yaw = self._current_yaw
        bb.sensor.pf_estimate = self._particle_filter_estimate
        bb.sensor.pf_confidence = self._particle_filter_confidence
        bb.sensor.wind = self._estimated_wind

        # -- update mission state machine (was StateMachineNode) ------------
        mode = self._state_machine.update(
            concentration=self._current_concentration,
            robot_position=(self._current_pose.x, self._current_pose.y),
            goal_reached=bool(bb.nav2.goal_reached_count),
        )
        if bb.mission.mode != mode:
            bb.mission.mode_changed = True
            bb.mission.new_mode = mode
        else:
            bb.mission.mode_changed = False
        bb.mission.mode = mode
        bb.mission.source_estimate = self._state_machine.source_estimate

        # Consume accumulated goal completions (edge-triggered counter)
        bb.nav2.goal_reached_count = 0

        # -- patrol target (from state machine) -----------------------------
        goal = self._state_machine.current_patrol_goal
        bb.mission.patrol_target = Pose2D(goal[0], goal[1])

        # -- route targets to nav2 (mode-aware) -----------------------------
        self._sync_to_blackboard()
        bb.nav2.nav_ready = self._nav_ready

        # diagnostic
        if self._tick_count % 50 == 1:
            tp = bb.nav2.target_pose
            self.get_logger().info(
                f"nav2 target=({tp.x:.2f},{tp.y:.2f})" if tp else "nav2 target=None"
            )

        # tick the behavior tree
        self._tree.tick()

        # publish results to ROS topics
        self._sync_from_blackboard()

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._current_pose, self._current_yaw = map_pose_from_amcl(msg)

    def _on_concentration(self, msg: Float32) -> None:
        self._current_concentration = float(msg.data)
        self._history.append((self._current_pose, self._current_concentration))
        self._history = self._history[-50:]
        if self._estimate_wind:
            wind_est = self._wind_estimator.update(
                self._current_pose, self._current_concentration
            )
            if wind_est is not None and wind_est.confidence > 0.3:
                self._estimated_wind = (wind_est.wind_x, wind_est.wind_y)

    def _on_pf(self, msg: PoseWithCovarianceStamped) -> None:
        p = msg.pose.pose.position
        self._particle_filter_estimate = Pose2D(p.x, p.y)
        cov = msg.pose.covariance
        if cov[0] > 0 and cov[7] > 0:
            self._particle_filter_confidence = min(
                1.0, 1.0 / (np.sqrt(cov[0] * cov[7]) + 0.1)
            )
        else:
            self._particle_filter_confidence = 0.0

    def _on_costmap(self, msg: Costmap) -> None:
        pass  # handled by CostmapChecker via blackboard

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _make_pose_stamped(self, pose: Pose2D, yaw: float = 0.0) -> PoseStamped:
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = pose.x
        goal.pose.position.y = pose.y
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        return goal


_DEFAULT_PATROL = "[3.0, 3.0, -3.0, 3.0, -3.0, -3.0, 3.0, -3.0]"


def main(args=None):
    rclpy.init(args=args)
    node = BTNodeRunner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
