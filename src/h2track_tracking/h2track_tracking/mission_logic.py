"""Mission state machine for patrol and hydrogen source tracking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
import math


class MissionMode(Enum):
    EXPLORE_MAPPING = auto()
    GAS_CONFIRM = auto()
    FREEZE_AND_RELOCALIZE = auto()
    PATROL = auto()
    SEEK_CONFIRM = auto()
    SEEK_TRACK = auto()
    SOURCE_FOUND = auto()


@dataclass(frozen=True)
class MissionConfig:
    patrol_points: list[tuple[float, float]]
    enter_threshold: float
    exit_threshold: float
    source_threshold: float
    confirm_samples: int
    source_radius: float
    source_hold_steps: int
    actual_source: tuple[float, float] | None = None


@dataclass(frozen=True)
class ExplorationMissionConfig:
    enter_threshold: float
    exit_threshold: float
    confirm_samples: int


class ExplorationMissionStateMachine:
    def __init__(self, config: ExplorationMissionConfig) -> None:
        self.config = config
        self.mode = MissionMode.EXPLORE_MAPPING
        self._recent_concentrations: deque[float] = deque(maxlen=max(1, config.confirm_samples))

    def update(self, concentration: float) -> MissionMode:
        self._recent_concentrations.append(concentration)
        recent_count = len(self._recent_concentrations)
        recent_values = list(self._recent_concentrations)

        if self.mode is MissionMode.EXPLORE_MAPPING:
            if (
                recent_count == self.config.confirm_samples
                and min(recent_values) >= self.config.enter_threshold
            ):
                self.mode = MissionMode.GAS_CONFIRM
        elif self.mode is MissionMode.GAS_CONFIRM:
            if (
                recent_count == self.config.confirm_samples
                and max(recent_values) < self.config.exit_threshold
            ):
                self.mode = MissionMode.EXPLORE_MAPPING
                self._recent_concentrations.clear()
            elif (
                recent_count == self.config.confirm_samples
                and min(recent_values) >= self.config.enter_threshold
            ):
                self.mode = MissionMode.FREEZE_AND_RELOCALIZE

        return self.mode


class MissionStateMachine:
    def __init__(self, config: MissionConfig) -> None:
        self.config = config
        self.mode = MissionMode.PATROL
        self._recent_observations: deque[tuple[tuple[float, float], float]] = deque(maxlen=max(1, config.confirm_samples))
        self._source_hits = 0
        self._current_patrol_index = 0
        self.source_estimate: tuple[float, float] | None = None

    @property
    def current_patrol_goal(self) -> tuple[float, float]:
        return self.config.patrol_points[self._current_patrol_index % len(self.config.patrol_points)]

    def advance_patrol(self) -> tuple[float, float]:
        self._current_patrol_index = (self._current_patrol_index + 1) % len(self.config.patrol_points)
        return self.current_patrol_goal

    def _is_near_actual_source(self, position: tuple[float, float]) -> bool:
        if self.config.actual_source is None:
            return True

        return math.hypot(
            position[0] - self.config.actual_source[0],
            position[1] - self.config.actual_source[1],
        ) <= self.config.source_radius

    def update(
        self,
        concentration: float,
        robot_position: tuple[float, float],
        goal_reached: bool,
    ) -> MissionMode:
        self._recent_observations.append((robot_position, concentration))

        recent_concentrations = [value for _, value in self._recent_observations]
        recent_count = len(self._recent_observations)

        if self.mode is MissionMode.PATROL:
            if goal_reached:
                self.advance_patrol()
            if (
                recent_count == self.config.confirm_samples
                and min(recent_concentrations) >= self.config.enter_threshold
            ):
                self.mode = MissionMode.SEEK_CONFIRM

        elif self.mode is MissionMode.SEEK_CONFIRM:
            if (
                recent_count == self.config.confirm_samples
                and max(recent_concentrations) < self.config.exit_threshold
            ):
                self.mode = MissionMode.PATROL
                self._recent_observations.clear()
            elif concentration >= self.config.enter_threshold:
                self.mode = MissionMode.SEEK_TRACK

        elif self.mode is MissionMode.SEEK_TRACK:
            if (
                recent_count == self.config.confirm_samples
                and max(recent_concentrations) < self.config.exit_threshold
            ):
                self.mode = MissionMode.PATROL
                self._source_hits = 0
                self.source_estimate = None
                self._recent_observations.clear()
            elif max(recent_concentrations) >= self.config.source_threshold:
                strongest_position, strongest_concentration = max(
                    self._recent_observations,
                    key=lambda observation: observation[1],
                )
                strongest_radius = math.hypot(
                    robot_position[0] - strongest_position[0],
                    robot_position[1] - strongest_position[1],
                )
                if strongest_radius <= self.config.source_radius:
                    if self.source_estimate is None:
                        self._source_hits = 1
                        self.source_estimate = strongest_position
                    else:
                        radius = math.hypot(
                            strongest_position[0] - self.source_estimate[0],
                            strongest_position[1] - self.source_estimate[1],
                        )
                        if radius <= self.config.source_radius:
                            self._source_hits += 1
                        else:
                            self._source_hits = 1
                        self.source_estimate = strongest_position
                    if self._source_hits >= self.config.source_hold_steps and self._is_near_actual_source(self.source_estimate):
                        self.mode = MissionMode.SOURCE_FOUND
                else:
                    self._source_hits = 0
            elif self.source_estimate is not None and concentration >= self.config.exit_threshold:
                radius = math.hypot(
                    robot_position[0] - self.source_estimate[0],
                    robot_position[1] - self.source_estimate[1],
                )
                if radius <= self.config.source_radius:
                    self._source_hits += 1
                    if self._source_hits >= self.config.source_hold_steps and self._is_near_actual_source(self.source_estimate):
                        self.mode = MissionMode.SOURCE_FOUND
                else:
                    self._source_hits = 0
            else:
                self._source_hits = 0

        return self.mode
