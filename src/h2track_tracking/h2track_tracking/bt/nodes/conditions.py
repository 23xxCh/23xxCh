"""Condition nodes for the BT pipeline.

These are simple py_trees Behaviours that gate tree branches based on
blackboard state. They read from the custom H2TrackBlackboard (not
py_trees' own blackboard), so they are specific to this project.
"""

from __future__ import annotations

import py_trees
from py_trees.common import Status

from ...mission_logic import MissionMode


class CheckMissionMode(py_trees.behaviour.Behaviour):
    """Gate: succeed when ``mission.mode`` is one of the expected modes.

    Inputs (blackboard):
        mission.mode

    Returns:
        SUCCESS if mode matches any accepted mode, FAILURE otherwise.
    """

    def __init__(self, name: str, bb: "H2TrackBlackboard", *modes: MissionMode) -> None:
        super().__init__(name)
        self._bb = bb
        self._modes = modes

    def update(self) -> Status:
        current = self._bb.mission.mode
        if current in self._modes:
            return Status.SUCCESS
        expected = "|".join(m.name for m in self._modes)
        self.feedback_message = f"mode is {current}, expected {expected}"
        return Status.FAILURE
