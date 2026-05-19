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
    """Gate: succeed only when ``mission.mode`` matches the expected mode.

    Inputs (blackboard):
        mission.mode

    Returns:
        SUCCESS if mode matches, FAILURE otherwise.
    """

    def __init__(self, name: str, bb: "H2TrackBlackboard", mode: MissionMode) -> None:
        super().__init__(name)
        self._bb = bb
        self._mode = mode

    def update(self) -> Status:
        current = self._bb.mission.mode
        if current == self._mode:
            return Status.SUCCESS
        self.feedback_message = f"mode is {current}, expected {self._mode}"
        return Status.FAILURE
