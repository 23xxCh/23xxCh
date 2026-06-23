"""Tracker node for Behavior Tree.

Wraps SurgeCastTracker + TrackingFusion + CostmapChecker as a single
py_trees Behaviour that outputs the next navigational target.
"""

from __future__ import annotations

import py_trees
from py_trees.common import Status

from ...tracking.types import Pose2D, SurgeCastConfig
from ...tracking.surge_cast import SurgeCastTracker
from ...tracking.fusion import TrackingFusion, FusionConfig
from ...tracking.costmap_checker import CostmapChecker


class TrackerNode(py_trees.behaviour.Behaviour):
    """py_trees Behaviour: compute next tracking target.

    Inputs (blackboard):
        sensor.concentration, sensor.robot_pose, sensor.robot_yaw,
        sensor.wind, sensor.pf_estimate, sensor.pf_confidence

    Outputs (blackboard):
        tracker.target, tracker.heading
    """

    def __init__(
        self,
        name: str,
        bb: "H2TrackBlackboard",
        surge_tracker: SurgeCastTracker,
        *,
        fusion: TrackingFusion | None = None,
        costmap_checker: CostmapChecker | None = None,
        use_fusion: bool = True,
        use_costmap: bool = True,
    ) -> None:
        super().__init__(name)
        self._bb = bb
        self._surge = surge_tracker          # DI: caller provides
        self._fusion = fusion                # DI
        self._costmap = costmap_checker      # DI
        self._use_fusion = use_fusion
        self._use_costmap = use_costmap

    def initialise(self) -> None:
        pass

    def update(self) -> Status:
        concentration = self._bb.sensor.concentration or 0.0
        robot_pose: Pose2D | None = self._bb.sensor.robot_pose
        robot_yaw: float = self._bb.sensor.robot_yaw or 0.0

        if robot_pose is None:
            self.feedback_message = "no robot pose"
            return Status.FAILURE

        # -- wind --------------------------------------------------------------
        wind = self._bb.sensor.wind or self._bb.tracker.wind_estimate

        # -- Surge-Cast update -------------------------------------------------
        sc_pose = Pose2D(robot_pose.x, robot_pose.y)
        action = self._surge.update(
            concentration=concentration,
            robot_pose=sc_pose,
            robot_yaw=robot_yaw,
            wind=wind,
        )
        pre_costmap_target = action.target

        # -- particle filter fusion --------------------------------------------
        if self._use_fusion and self._fusion is not None:
            pf_pos = self._bb.sensor.pf_estimate
            pf_conf = self._bb.sensor.pf_confidence or 0.0
            if pf_pos is not None:
                action = self._fusion.compute_fused_action(
                    surge_action=action,
                    pf_position=pf_pos,
                    pf_confidence=pf_conf,
                    concentration=concentration,
                    robot_pose=sc_pose,
                )

        # -- costmap guard -----------------------------------------------------
        if self._use_costmap and self._costmap is not None:
            action = self._costmap.safe_tracking_action(
                action, sc_pose, max_search_radius=2.0
            )

        # -- write outputs -----------------------------------------------------
        self._bb.tracker.target = action.target
        self._bb.tracker.heading = action.heading

        self.feedback_message = (
            f"{action.state.name} -> ({action.target.x:.2f}, {action.target.y:.2f})"
        )

        # Return FAILURE when tracker is in PATROL (lost plume) — this lets
        # the BT Selector fall back to the PATROL branch.  SURGE, CAST, and
        # SOURCE_FOUND all indicate the tracker is actively tracking.
        if action.state is TrackingState.PATROL:
            return Status.FAILURE

        return Status.SUCCESS

    def terminate(self, new_status: Status) -> None:
        pass

    def reset_tracker(self) -> None:
        self._surge.reset()
