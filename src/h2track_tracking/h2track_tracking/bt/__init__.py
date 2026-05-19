"""Behavior Tree module for h2track_tracking.

Integrates MissionStateMachine, SurgeCastTracker, TrackingFusion, and Nav2
through a py_trees behavior tree for flexible orchestration.
"""

from .blackboard import H2TrackBlackboard
from .tree_factory import TreeFactory
from .nodes.nav2_client import Nav2ClientNode
from .nodes.tracker import TrackerNode
from .nodes.costmap_guard import CostmapGuardNode
from .nodes.state_machine import StateMachineNode
from .nodes.sensor_reader import SensorReaderNode

__all__ = [
    "H2TrackBlackboard",
    "TreeFactory",
    "Nav2ClientNode",
    "TrackerNode",
    "CostmapGuardNode",
    "StateMachineNode",
    "SensorReaderNode",
]
