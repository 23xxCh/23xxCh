"""Behavior Tree factory for h2track_tracking.

Constructs the py_trees BehaviourTree that orchestrates:
  - MissionStateMachine (ticked in runner, BT reads mission.mode)
  - SurgeCastTracker + TrackingFusion
  - Nav2 navigation
  - Costmap-based safety guards

All domain objects injected via constructor (DI).
"""

from __future__ import annotations

import py_trees
from rclpy.node import Node

from .blackboard import H2TrackBlackboard
from .nodes import (
    Nav2ClientNode,
    TrackerNode,
    CostmapGuardNode,
)
from .nodes.conditions import CheckMissionMode
from ..tracking.surge_cast import SurgeCastTracker
from ..tracking.fusion import TrackingFusion
from ..tracking.costmap_checker import CostmapChecker
from ..mission_logic import MissionMode


class TreeFactory:
    """Builds the main mission behavior tree. All deps injected."""

    def __init__(
        self,
        bb: H2TrackBlackboard,
        node: Node,
        *,
        surge_tracker: SurgeCastTracker,
        fusion: TrackingFusion | None,
        costmap_checker: CostmapChecker,
        action_server: str = "/navigate_to_pose",
    ) -> None:
        self._bb = bb
        self._node = node

        # Domain objects (DI)
        self._surge_tracker = surge_tracker
        self._fusion = fusion
        self._costmap_checker = costmap_checker
        self._action_server = action_server

    def create_tree(self) -> py_trees.BehaviourTree:
        """Assemble and return the complete mission BT.

        Tree structure:
          MissionRoot (Selector)
          ├── SourceFound    → CheckMissionMode(SOURCE_FOUND)
          ├── SeekTrack      → CheckMissionMode + CostmapGuard + Tracker + Nav2Client
          ├── SeekConfirm    → CheckMissionMode(SEEK_CONFIRM)
          └── Patrol         → CheckMissionMode + CostmapGuard + Nav2Client
        """

        tracker_node = TrackerNode(
            name="Tracker",
            bb=self._bb,
            surge_tracker=self._surge_tracker,
            fusion=self._fusion,
            costmap_checker=self._costmap_checker,
        )

        root = py_trees.composites.Selector(
            name="MissionRoot",
            memory=False,
            children=[
                self._make_source_found_branch(),
                self._make_seek_track_branch(tracker_node),
                self._make_seek_confirm_branch(),
                self._make_patrol_branch(),
            ],
        )

        tree = py_trees.trees.BehaviourTree(root)
        tree.setup(timeout=15)
        return tree

    # ------------------------------------------------------------------
    # Branch builders
    # ------------------------------------------------------------------

    def _make_patrol_branch(self) -> py_trees.composites.Sequence:
        return py_trees.composites.Sequence(
            name="Patrol",
            memory=True,
            children=[
                CheckMissionMode("CheckPatrol", self._bb, MissionMode.PATROL),
                CostmapGuardNode(
                    "PatrolGuard", self._bb, costmap_checker=self._costmap_checker
                ),
                Nav2ClientNode(
                    "PatrolNav", self._bb, self._node,
                    action_server_name=self._action_server, timeout=30.0,
                ),
            ],
        )

    def _make_seek_confirm_branch(self) -> py_trees.composites.Sequence:
        return py_trees.composites.Sequence(
            name="SeekConfirm",
            memory=True,
            children=[
                CheckMissionMode("CheckSeekConfirm", self._bb, MissionMode.SEEK_CONFIRM),
            ],
        )

    def _make_seek_track_branch(
        self,
        tracker_node: TrackerNode,
    ) -> py_trees.composites.Sequence:
        return py_trees.composites.Sequence(
            name="SeekTrack",
            memory=True,
            children=[
                CheckMissionMode("CheckSeekTrack", self._bb, MissionMode.SEEK_TRACK),
                CostmapGuardNode(
                    "TrackGuard", self._bb, costmap_checker=self._costmap_checker
                ),
                tracker_node,
                Nav2ClientNode(
                    "TrackNav", self._bb, self._node,
                    action_server_name=self._action_server, timeout=30.0,
                ),
            ],
        )

    def _make_source_found_branch(self) -> py_trees.composites.Sequence:
        return py_trees.composites.Sequence(
            name="SourceFound",
            memory=True,
            children=[
                CheckMissionMode("CheckSourceFound", self._bb, MissionMode.SOURCE_FOUND),
                py_trees.behaviours.Success(name="SourceFoundDone"),
            ],
        )
