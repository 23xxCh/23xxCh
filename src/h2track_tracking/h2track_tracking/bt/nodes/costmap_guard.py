"""Costmap guard node for Behavior Tree.

Monitors Nav2 costmap and path deviation to detect obstacles.

Reads ``nav2.target_pose`` (common target for both Patrol and SeekTrack branches).
Domain logic (stuck detection, projection, action selection) lives in
``CostmapChecker.evaluate_safety()``.
"""

from __future__ import annotations

import py_trees
from py_trees.common import Status

from ...tracking.types import Pose2D
from ...tracking.costmap_checker import CostmapChecker


class CostmapGuardNode(py_trees.behaviour.Behaviour):
    """py_trees Behaviour: dynamic safety guard based on costmap.

    Delegates domain logic to CostmapChecker.evaluate_safety().
    Keeps only tick-counting state and blackboard I/O.

    Inputs (blackboard):
        nav2.target_pose, sensor.robot_pose,
        nav2.status, nav2.path_deviation

    Outputs (blackboard):
        safety.obstacle_detected, safety.suggested_action,
        safety.alternative_target, safety.stuck_duration
    """

    def __init__(
        self,
        name: str,
        bb: "H2TrackBlackboard",
        costmap_checker: CostmapChecker,
        *,
        max_deviation: float = 2.0,
    ) -> None:
        super().__init__(name)
        self._bb = bb
        self._checker = costmap_checker
        self._max_dev = max_deviation
        self._stuck_count = 0

    def update(self) -> Status:
        target: Pose2D | None = self._bb.nav2.target_pose
        robot_pose: Pose2D | None = self._bb.sensor.robot_pose

        if target is None or robot_pose is None:
            return Status.SUCCESS

        assessment = self._checker.evaluate_safety(
            target,
            robot_pose,
            nav_status=self._bb.nav2.status or "idle",
            path_deviation=self._bb.nav2.path_deviation or 0.0,
            max_deviation=self._max_dev,
        )

        if assessment.obstacle_detected:
            self._stuck_count += 1
        else:
            self._stuck_count = 0

        self._bb.safety.obstacle_detected = assessment.obstacle_detected
        self._bb.safety.suggested_action = assessment.suggested_action
        self._bb.safety.alternative_target = assessment.alternative_target
        self._bb.safety.stuck_duration = self._stuck_count

        return Status.SUCCESS

    def terminate(self, new_status: Status) -> None:
        pass
