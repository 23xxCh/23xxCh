#!/usr/bin/env python3
"""Behavior Tree node runner — LifecycleNode variant.

Full replacement for the legacy MissionManagerNode.  All ROS I/O stays here;
the py_trees BehaviourTree handles orchestration decisions.

Converted to LifecycleNode following ros2-engineering-skills pattern:
- on_configure: build configs, create domain objects, blackboard, BT tree, Nav2, TF
- on_activate: create subscriptions, publishers, start tick timer
- on_deactivate: stop timer, cancel navigation goals
- on_cleanup: release resources
"""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from h2track_interfaces.msg import WindEstimate as WindEstimateMsg
from nav2_msgs.msg import Costmap
import numpy as np
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from std_msgs.msg import Bool, Float32, String
from tf2_ros import Buffer, TransformException, TransformListener

from h2track_tracking.bt.blackboard import H2TrackBlackboard
from h2track_tracking.bt.tree_factory import TreeFactory
from h2track_tracking.tracking.types import Pose2D
from h2track_tracking.tracking.surge_cast import SurgeCastTracker
from h2track_tracking.tracking.fusion import TrackingFusion
from h2track_tracking.tracking.costmap_checker import CostmapChecker
from h2track_tracking.tracking.wind_estimator import WindEstimator, WindEstimatorConfig
from h2track_utils.navigation_executor import map_pose_from_amcl
from h2track_tracking.mission_logic import MissionMode, MissionStateMachine
from h2track_utils.nav2_lifecycle import Nav2Lifecycle, _make_pose_stamped

from .param_bridge import (
    declare_parameters,
    build_mission_config,
    build_surge_config,
    build_fusion_config,
)


class BTNodeRunner(LifecycleNode):
    """Lifecycle-enabled BT orchestrator.  BT tree handles orchestration;
    this node handles all ROS I/O, Nav2 lifecycle, and parameter management."""

    def __init__(self) -> None:
        super().__init__("bt_node_runner")

        # -- ROS parameters (declared immediately, used in on_configure) --------
        declare_parameters(self)

        # -- placeholders (initialized in on_configure / on_activate) -----------
        self._bb: H2TrackBlackboard | None = None
        self._tree = None
        self._nav2: Nav2Lifecycle | None = None
        self._costmap_checker: CostmapChecker | None = None
        self._state_machine: MissionStateMachine | None = None
        self._wind_estimator: WindEstimator | None = None

        self._tf_buffer = Buffer()
        self._tf_listener: TransformListener | None = None

        self._current_pose = Pose2D(0.0, 0.0)
        self._current_yaw = 0.0
        self._current_concentration = 0.0
        self._history: list[tuple[Pose2D, float]] = []
        self._particle_filter_estimate: Pose2D | None = None
        self._particle_filter_confidence: float = 0.0
        self._estimated_wind: tuple[float, float] | None = None
        self._wind_confidence: float = 0.5
        # estimate_wind: "gradient" (WindEstimator) | "anemometer" (GADEN truth)
        # | "off" (no wind estimation, /estimated_wind not published by runner).
        # "anemometer" mode expects anemometer_adapter_node to publish directly
        # to /estimated_wind (avoids double-publish).
        # Backward compat: True/"true" → "gradient", False/"false" → "off".
        raw = self.get_parameter("estimate_wind").value
        raw_str = str(raw).strip().lower()
        if raw_str in ("gradient", "anemometer", "off"):
            self._estimate_wind = raw_str
        elif raw_str in ("true", "1", "yes"):
            self._estimate_wind = "gradient"
        else:
            self._estimate_wind = "off"

        self._mode_pub = None
        self._source_pub = None
        self._estimate_pub = None
        self._wind_pub = None
        self._last_mode: MissionMode | None = None
        self._source_announced = False
        self._tick_count = 0
        self._timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Build configs, create domain objects, blackboard, BT tree, Nav2, TF."""
        # -- mission config --------------------------------------------------
        mission_cfg = build_mission_config(self)

        # -- surge-cast config -----------------------------------------------
        surge_cfg = build_surge_config(self)

        # -- domain objects --------------------------------------------------
        surge_tracker = SurgeCastTracker(surge_cfg)
        fusion = TrackingFusion(build_fusion_config(self))
        self._costmap_checker = CostmapChecker()
        self._state_machine = MissionStateMachine(mission_cfg)

        # -- wind estimator --------------------------------------------------
        self._wind_estimator = WindEstimator(WindEstimatorConfig(
            min_samples_for_estimate=int(self.get_parameter("wind_estimation_min_samples").value),
        ))

        # -- blackboard & tree -----------------------------------------------
        self._bb = H2TrackBlackboard()
        self._tree_factory = TreeFactory(
            bb=self._bb,
            node=self,
            surge_tracker=surge_tracker,
            fusion=fusion,
            costmap_checker=self._costmap_checker,
        )
        self._tree = self._tree_factory.create_tree()

        # -- Nav2 lifecycle --------------------------------------------------
        localizer = str(self.get_parameter("localizer_node").value).strip().lower()
        use_slam = bool(self.get_parameter("use_slam").value)
        if not localizer:
            localizer = "none" if use_slam else "amcl"

        self._nav2 = Nav2Lifecycle(
            node=self,
            initial_pose=Pose2D(self._pf("initial_pose_x"), self._pf("initial_pose_y")),
            initial_yaw=self._pf("initial_pose_yaw"),
            localizer_node=localizer,
            publish_initial_pose=bool(self.get_parameter("publish_initial_pose").value),
        )
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)

        self.get_logger().info("BTNodeRunner configured")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Create subscriptions, publishers, start tick timer."""
        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        state_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)

        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, state_qos)
        self.create_subscription(PoseWithCovarianceStamped, "/estimated_source", self._on_pf, state_qos)
        self.create_subscription(Float32, "/gas_concentration", self._on_concentration, sensor_qos)
        self.create_subscription(Costmap, "/global_costmap/costmap", self._on_costmap, 10)

        self._mode_pub = self.create_publisher(String, "/robot_mode", state_qos)
        self._source_pub = self.create_publisher(Bool, "/source_found", state_qos)
        self._estimate_pub = self.create_publisher(PoseStamped, "/estimated_source_pose", state_qos)
        # In anemometer mode, anemometer_adapter_node publishes /estimated_wind
        # (CFD ground truth). We subscribe to update blackboard instead of
        # publishing. In gradient/off mode, runner is the publisher.
        if self._estimate_wind == "anemometer":
            self.create_subscription(
                WindEstimateMsg, "/estimated_wind", self._on_wind_estimate, sensor_qos
            )
            self._wind_pub = None
        else:
            self._wind_pub = self.create_publisher(
                WindEstimateMsg, "/estimated_wind", sensor_qos
            )

        self._timer = self.create_timer(0.1, self._tick)

        self.get_logger().info("BTNodeRunner activated")
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Stop timer."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.get_logger().info("BTNodeRunner deactivated")
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Release resources."""
        self._tree = None
        self._bb = None
        self._nav2 = None
        self._costmap_checker = None
        self._state_machine = None
        self._wind_estimator = None
        self._tf_listener = None
        self._mode_pub = None
        self._source_pub = None
        self._estimate_pub = None
        self._wind_pub = None
        self.get_logger().info("BTNodeRunner cleaned up")
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------
    # parameter helpers
    # ------------------------------------------------------------------

    def _pf(self, name: str) -> float:
        return float(self.get_parameter(name).value)

    def _pi(self, name: str) -> int:
        return int(self.get_parameter(name).value)

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        try:
            if self._nav2 is None or self._bb is None or self._tree is None:
                return

            # ensure Nav2 is ready
            if not self._nav2.ready:
                if not self._nav2.check_ready():
                    return
                self.get_logger().info("Nav2 ready, starting main loop")

            self._tick_count += 1
            self._log_diagnostics()

            self._sync_sensor_to_blackboard()
            self._update_state_machine()
            self._tree.tick()
            self._sync_targets_to_blackboard()
            self._publish_state()
        except Exception:
            self.get_logger().error("Unhandled exception in _tick()", exc_info=True)

    def _log_diagnostics(self) -> None:
        if self._tick_count % 50 == 1 and self._bb is not None:
            self.get_logger().info(
                f"tick #{self._tick_count} mode={self._last_mode} "
                f"pose=({self._current_pose.x:.2f},{self._current_pose.y:.2f}) "
                f"conc={self._current_concentration:.3f}"
            )
            tp = self._bb.nav2.target_pose
            self.get_logger().info(
                f"nav2 target=({tp.x:.2f},{tp.y:.2f})" if tp else "nav2 target=None"
            )

    def _sync_sensor_to_blackboard(self) -> None:
        if self._bb is None:
            return
        bb = self._bb
        bb.sensor.concentration = self._current_concentration
        bb.sensor.robot_pose = self._current_pose
        bb.sensor.robot_yaw = self._current_yaw
        bb.sensor.pf_estimate = self._particle_filter_estimate
        bb.sensor.pf_confidence = self._particle_filter_confidence
        bb.sensor.wind = self._estimated_wind

    def _update_state_machine(self) -> None:
        if self._bb is None or self._state_machine is None or self._nav2 is None:
            return
        bb = self._bb
        mode = self._state_machine.update(
            concentration=self._current_concentration,
            robot_position=(self._current_pose.x, self._current_pose.y),
            goal_reached=bool(bb.nav2.goal_reached_count),
        )
        bb.mission.mode = mode
        bb.mission.source_estimate = self._state_machine.source_estimate
        bb.nav2.goal_reached_count = 0

        goal = self._state_machine.current_patrol_goal
        bb.mission.patrol_target = Pose2D(goal[0], goal[1])
        bb.nav2.nav_ready = self._nav2.ready

    def _sync_targets_to_blackboard(self) -> None:
        if self._bb is None:
            return
        bb = self._bb
        mode = bb.mission.mode

        if mode == MissionMode.SEEK_TRACK and bb.tracker.target is not None:
            bb.nav2.target_pose = bb.tracker.target
            bb.nav2.target_yaw = bb.tracker.heading
        elif mode in (MissionMode.PATROL, MissionMode.SEEK_CONFIRM):
            patrol = bb.mission.patrol_target
            if patrol is not None:
                bb.nav2.target_pose = patrol
                dx = patrol.x - self._current_pose.x
                dy = patrol.y - self._current_pose.y
                bb.nav2.target_yaw = math.atan2(dy, dx)

    def _publish_state(self) -> None:
        if self._bb is None:
            return
        bb = self._bb
        mode = bb.mission.mode

        # Publish mode on change OR periodically when in SOURCE_FOUND
        # (SOURCE_FOUND is terminal — ensure subscribers see it even if
        # they connect after the transition event)
        should_publish = (
            mode is not None and mode != self._last_mode
        ) or (
            mode is MissionMode.SOURCE_FOUND
            and self._tick_count % 50 == 0
        )
        if should_publish and self._mode_pub is not None:
            self._mode_pub.publish(String(data=mode.name))
            if mode != self._last_mode:
                self.get_logger().info(f"Mode change: {self._last_mode} -> {mode}")
            self._last_mode = mode

        if bb.mission.mode is not None and bb.mission.mode.name == "SOURCE_FOUND":
            if not self._source_announced:
                if self._source_pub is not None:
                    self._source_pub.publish(Bool(data=True))
                est = bb.mission.source_estimate
                if est is not None and self._estimate_pub is not None:
                    self._estimate_pub.publish(_make_pose_stamped(
                        self, Pose2D(est[0], est[1]), 0.0
                    ))
                self._source_announced = True
        else:
            self._source_announced = False

        # Publish /estimated_wind only in gradient mode — anemometer mode
        # has anemometer_adapter_node publishing directly (avoids conflicts),
        # and "off" mode publishes nothing.
        if (
            self._estimate_wind == "gradient"
            and self._estimated_wind is not None
            and self._wind_pub is not None
        ):
            wx, wy = self._estimated_wind
            wind_msg = WindEstimateMsg(
                wind_x=wx, wind_y=wy, confidence=self._wind_confidence
            )
            wind_msg.header.stamp = self.get_clock().now().to_msg()
            wind_msg.header.frame_id = "map"
            self._wind_pub.publish(wind_msg)

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._current_pose, self._current_yaw = map_pose_from_amcl(msg)

    def _on_concentration(self, msg: Float32) -> None:
        self._current_concentration = float(msg.data)
        self._history.append((self._current_pose, self._current_concentration))
        self._history = self._history[-50:]
        # Only run gradient-based WindEstimator when estimate_wind == "gradient".
        # "anemometer" mode: anemometer_adapter_node publishes /estimated_wind
        # directly (CFD ground truth); runner subscribes via _on_wind_estimate.
        # "off" mode: no wind estimation at all.
        if self._estimate_wind == "gradient" and self._wind_estimator is not None:
            wind_est = self._wind_estimator.update(
                self._current_pose, self._current_concentration
            )
            if wind_est is not None and wind_est.confidence > 0.3:
                self._estimated_wind = (wind_est.wind_x, wind_est.wind_y)
                self._wind_confidence = wind_est.confidence

    def _on_wind_estimate(self, msg: WindEstimateMsg) -> None:
        """Receive wind estimate from anemometer_adapter_node (anemometer mode)."""
        self._estimated_wind = (float(msg.wind_x), float(msg.wind_y))
        self._wind_confidence = float(msg.confidence)

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
        if self._costmap_checker is not None:
            self._costmap_checker.update_costmap(msg)


def main(args=None):
    rclpy.init(args=args)
    node = BTNodeRunner()
    # Auto-transition for standalone usage (no lifecycle_manager)
    from rclpy.lifecycle import LifecycleState
    node.on_configure(LifecycleState(state_id=0, label="unconfigured"))
    node.on_activate(LifecycleState(state_id=1, label="inactive"))
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
