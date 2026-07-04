"""Mission state machine for patrol and hydrogen source tracking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
import math


class MissionMode(Enum):
    PATROL = auto()
    SEEK_CONFIRM = auto()
    SEEK_TRACK = auto()
    SOURCE_FOUND = auto()


@dataclass(frozen=True)
class MissionConfig:
    patrol_points: list[tuple[float, float]]
    enter_threshold: float = 4.0          # Gas concentration to trigger SEEK_CONFIRM
    exit_threshold: float = 1.5           # Below this, return to PATROL
    source_threshold: float = 8.0         # Concentration indicating source proximity
    confirm_samples: int = 3              # Consecutive readings to confirm a transition
    source_radius: float = 0.6            # Meters from source for SOURCE_FOUND
    source_hold_steps: int = 3            # Consecutive source detections needed
    track_exit_samples: int | None = None
    track_timeout_sec: float = 60.0       # Seconds stuck in SEEK_TRACK before fallback
    adaptive_source_ratio: float = 0.0    # 0=disabled; >0 triggers SOURCE_FOUND
                                          # when conc >= max_observed * ratio
    actual_source: tuple[float, float] | None = None
    dynamic_source_threshold: bool = False    # Enable plateau-based detection
    source_plateau_window: int = 10           # Samples to check (10 = 1s at 10Hz)
    source_plateau_ratio: float = 0.1         # Plateau tolerance (fraction of max_observed)


class MissionStateMachine:
    """Mission state machine — mutable by design.

    Unlike the frozen dataclass pattern used elsewhere, this class
    intentionally mutates internal state on each update() call:
    mode, source_estimate, _current_patrol_index, etc.

    Rationale: The state machine tracks real-time sensor observations
    and transitions mode on every tick. Making it immutable would
    require returning a new instance per tick, which is impractical
    for a 10 Hz loop that needs to maintain deque history and
    source-hit counters across calls.
    """
    def __init__(self, config: MissionConfig) -> None:
        if not config.patrol_points:
            raise ValueError("patrol_points must not be empty")
        self.config = config
        self.mode = MissionMode.PATROL
        # track_exit_samples must be >= 3 to prevent a single spurious
        # zero reading (DDS packet loss) from triggering SEEK_TRACK exit.
        self._track_exit_samples = max(3, int(config.track_exit_samples or config.confirm_samples))
        history_len = max(1, int(config.confirm_samples), self._track_exit_samples)
        self._recent_observations: deque[tuple[tuple[float, float], float]] = deque(maxlen=history_len)
        self._source_hits = 0
        self._current_patrol_index = 0
        self.source_estimate: tuple[float, float] | None = None
        self._seek_track_ticks = 0
        self._track_timeout_ticks = int(config.track_timeout_sec * 10)  # 10 Hz
        self._max_observed_concentration = 0.0
        self._plateau_window: deque[float] = deque(maxlen=max(1, int(config.source_plateau_window)))

    @property
    def current_patrol_goal(self) -> tuple[float, float]:
        return self.config.patrol_points[self._current_patrol_index % len(self.config.patrol_points)]

    def advance_patrol(self) -> tuple[float, float]:
        self._current_patrol_index = (self._current_patrol_index + 1) % len(self.config.patrol_points)
        return self.current_patrol_goal

    def _is_near_actual_source(self, position: tuple[float, float]) -> bool:
        """Check if the robot is near the known actual source.

        Returns False when actual_source is not configured (i.e., in
        simulation without a known ground-truth source position).
        """
        if self.config.actual_source is None:
            return False

        return math.hypot(
            position[0] - self.config.actual_source[0],
            position[1] - self.config.actual_source[1],
        ) <= self.config.source_radius

    def _is_concentration_plateaued(self) -> bool:
        """Check if concentration has stopped increasing (plateau detected)."""
        if len(self._plateau_window) < self._plateau_window.maxlen:
            return False
        if self._max_observed_concentration <= 0:
            return False
        spread = max(self._plateau_window) - min(self._plateau_window)
        return spread <= self._max_observed_concentration * self.config.source_plateau_ratio

    def _source_found_condition(self, confirm_concentrations: list[float]) -> bool:
        """Check if SOURCE_FOUND should trigger based on threshold mode.

        Uses max(confirm_concentrations) to preserve the original semantics
        where any reading in the confirm window above the threshold can
        trigger the source-found evaluation.
        """
        peak = max(confirm_concentrations) if confirm_concentrations else 0.0
        if self.config.dynamic_source_threshold:
            return (
                peak >= self.config.source_threshold
                and self._is_concentration_plateaued()
            )
        return peak >= self.config.source_threshold

    def update(
        self,
        concentration: float,
        robot_position: tuple[float, float],
        goal_reached: bool,
    ) -> MissionMode:
        self._recent_observations.append((robot_position, concentration))
        self._plateau_window.append(concentration)
        if concentration > self._max_observed_concentration:
            self._max_observed_concentration = concentration

        recent_count = len(self._recent_observations)
        confirm_window = list(self._recent_observations)[-self.config.confirm_samples :]
        confirm_concentrations = [value for _, value in confirm_window]
        track_exit_window = list(self._recent_observations)[-self._track_exit_samples :]
        track_exit_concentrations = [value for _, value in track_exit_window]

        if self.mode is MissionMode.PATROL:
            if goal_reached:
                self.advance_patrol()
            if (
                recent_count >= self.config.confirm_samples
                and min(confirm_concentrations) >= self.config.enter_threshold
            ):
                self.mode = MissionMode.SEEK_CONFIRM

        elif self.mode is MissionMode.SEEK_CONFIRM:
            if (
                recent_count >= self.config.confirm_samples
                and max(confirm_concentrations) < self.config.exit_threshold
            ):
                self.mode = MissionMode.PATROL
                self._recent_observations.clear()
            elif concentration >= self.config.enter_threshold:
                self.mode = MissionMode.SEEK_TRACK
                self._seek_track_ticks = 0

        elif self.mode is MissionMode.SEEK_TRACK:
            self._seek_track_ticks += 1
            if (
                self._seek_track_ticks >= self._track_timeout_ticks
                and self.config.track_timeout_sec > 0
            ):
                self.mode = MissionMode.PATROL
                self._source_hits = 0
                self.source_estimate = None
                self._seek_track_ticks = 0
                self._recent_observations.clear()
            elif (
                recent_count >= self._track_exit_samples
                and max(track_exit_concentrations) < self.config.exit_threshold
            ):
                self.mode = MissionMode.PATROL
                self._source_hits = 0
                self.source_estimate = None
                self._seek_track_ticks = 0
                self._recent_observations.clear()
            # Fast-path: if robot is physically near actual source with high
            # concentration, trigger SOURCE_FOUND immediately.  This handles
            # the edge case where SurgeCast oscillation moves the robot away
            # from the strongest_window position before _source_hits accumulates.
            elif (
                concentration >= self.config.source_threshold
                and self._is_near_actual_source(robot_position)
            ):
                self.source_estimate = robot_position
                self.mode = MissionMode.SOURCE_FOUND
            # Adaptive threshold: trigger SOURCE_FOUND when concentration
            # reaches a fraction of the observed maximum.
            elif (
                self.config.adaptive_source_ratio > 0
                and self._max_observed_concentration > 0
                and concentration
                >= self._max_observed_concentration * self.config.adaptive_source_ratio
                and self._seek_track_ticks >= self.config.confirm_samples
            ):
                self.source_estimate = robot_position
                self.mode = MissionMode.SOURCE_FOUND
            elif self._source_found_condition(confirm_concentrations):
                strongest_position, strongest_concentration = max(
                    confirm_window,
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
                    if self._source_hits >= self.config.source_hold_steps:
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
                    if self._source_hits >= self.config.source_hold_steps:
                        self.mode = MissionMode.SOURCE_FOUND
                else:
                    self._source_hits = 0
            else:
                self._source_hits = 0

        return self.mode
