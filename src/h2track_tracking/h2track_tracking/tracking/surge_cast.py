"""Surge-Cast algorithm for gas source localization."""

from __future__ import annotations

from collections import deque
import math

from .types import Pose2D, SurgeCastConfig, TrackingAction, TrackingState
from .plume_detector import PlumeDetector


def _distance(pose1, pose2) -> float:
    """Calculate distance between two poses (can be any object with x, y attributes)."""
    return math.hypot(pose1.x - pose2.x, pose1.y - pose2.y)


class TrackingHistory:
    """Tracks position and concentration history."""

    def __init__(self, maxlen: int = 50) -> None:
        self.positions: deque[tuple[Pose2D, float]] = deque(maxlen=maxlen)

    def add(self, pose, concentration: float) -> None:
        """Add a new observation."""
        # Convert to internal Pose2D if needed
        if isinstance(pose, Pose2D):
            self.positions.append((pose, concentration))
        else:
            self.positions.append((Pose2D(pose.x, pose.y), concentration))

    def get_best_position(self) -> tuple[Pose2D, float] | None:
        """Get position with highest concentration."""
        if not self.positions:
            return None
        return max(self.positions, key=lambda p: p[1])

    def get_recent_average(self, n: int = 5) -> float:
        """Get average concentration of recent n samples."""
        if not self.positions:
            return 0.0
        recent = list(self.positions)[-n:]
        return sum(c for _, c in recent) / len(recent)

    def clear(self) -> None:
        """Clear history."""
        self.positions.clear()


class SurgeCastTracker:
    """Surge-Cast algorithm for gas source localization.

    The algorithm has two main states:
    - SURGE: Move upwind when in plume
    - CAST: Lateral search when plume is lost

    State transitions:
    - PATROL -> SURGE: When plume is detected (high concentration)
    - SURGE -> CAST: When plume is lost (low concentration)
    - SURGE -> SOURCE_FOUND: When source threshold reached
    - CAST -> SURGE: When plume is found again
    """

    def __init__(self, config: SurgeCastConfig) -> None:
        self.config = config
        self.state = TrackingState.PATROL
        self._plume_detector = PlumeDetector()
        self._history = TrackingHistory()
        self._cast_direction = 1  # +1 or -1 for left/right
        self._cast_start_pose: Pose2D | None = None
        self._cast_distance = 0.0
        self._source_hits = 0
        self._source_estimate: Pose2D | None = None
        # Confirm-sample buffers for robust state transitions
        self._plume_lost_count = 0  # consecutive low-concentration samples
        self._plume_found_count = 0  # consecutive high-concentration samples

    def _adaptive_step_size(self, concentration: float) -> float:
        """Adjust step size based on concentration.
        
        Higher concentration = smaller steps for precision.
        Lower concentration = larger steps for exploration.
        """
        if not self.config.adaptive_step:
            return self.config.surge_step
        
        if concentration >= self.config.concentration_threshold_high:
            # Near source: small steps for precision
            return self.config.min_step
        elif concentration <= self.config.concentration_threshold_low:
            # Far from source: large steps for exploration
            return self.config.max_step
        else:
            # Linear interpolation
            ratio = (concentration - self.config.concentration_threshold_low) / \
                    (self.config.concentration_threshold_high - self.config.concentration_threshold_low)
            return self.config.max_step - ratio * (self.config.max_step - self.config.min_step)

    def update(
        self,
        concentration: float,
        robot_pose: Pose2D,
        robot_yaw: float,
        wind: tuple[float, float] | None = None,
    ) -> TrackingAction:
        """Update tracker with new observation and get next action.

        Args:
            concentration: Current gas concentration.
            robot_pose: Current robot position.
            robot_yaw: Current robot heading (radians).
            wind: Optional wind vector (wind_x, wind_y). Uses config if not provided.

        Returns:
            TrackingAction with target position and state.
        """
        # Update history
        self._history.add(robot_pose, concentration)

        # Update plume detector
        self._plume_detector.update(concentration, (robot_pose.x, robot_pose.y))

        # Use provided wind or config
        wind_x = wind[0] if wind else self.config.wind_x
        wind_y = wind[1] if wind else self.config.wind_y

        # Process state transitions
        self._process_transitions(concentration, robot_pose)

        # Generate action based on current state
        return self._generate_action(robot_pose, robot_yaw, wind_x, wind_y, concentration)

    def _process_transitions(
        self,
        concentration: float,
        robot_pose: Pose2D,
    ) -> None:
        """Process state transitions based on concentration.

        Uses confirm-sample counting to avoid spurious transitions
        from single-sample noise spikes.
        """
        prev_state = self.state
        n_confirm = self.config.plume_confirm_samples

        if self.state == TrackingState.PATROL:
            # Transition to SURGE when plume is detected
            if self._plume_detector.in_plume:
                avg_conc = self._plume_detector.average_concentration
                if avg_conc >= self.config.plume_found_threshold:
                    self._plume_found_count += 1
                    if self._plume_found_count >= n_confirm:
                        self.state = TrackingState.SURGE
                        self._plume_found_count = 0
                else:
                    self._plume_found_count = 0
            else:
                self._plume_found_count = 0

        elif self.state == TrackingState.SURGE:
            # Check for source found
            if concentration >= self.config.source_threshold:
                best = self._history.get_best_position()
                if best:
                    best_pose, best_conc = best
                    dist = _distance(robot_pose, best_pose)
                    if dist <= self.config.source_radius:
                        self._source_hits += 1
                        if self._source_hits >= self.config.source_hold_steps:
                            self.state = TrackingState.SOURCE_FOUND
                            self._source_estimate = best_pose
                    else:
                        self._source_hits = 0

            # Check for plume lost (with confirm samples)
            elif concentration < self.config.plume_lost_threshold:
                self._plume_lost_count += 1
                if self._plume_lost_count >= n_confirm:
                    self.state = TrackingState.CAST
                    self._cast_start_pose = robot_pose
                    self._cast_distance = 0.0
                    self._plume_lost_count = 0
                    # Choose cast direction perpendicular to upwind
                    wind_norm = math.hypot(self.config.wind_x, self.config.wind_y)
                    if wind_norm > 0.1:
                        self._cast_direction *= -1
            else:
                self._plume_lost_count = 0

        elif self.state == TrackingState.CAST:
            # Check for plume found (with confirm samples)
            if concentration >= self.config.plume_found_threshold:
                self._plume_found_count += 1
                if self._plume_found_count >= n_confirm:
                    self.state = TrackingState.SURGE
                    self._source_hits = 0
                    self._plume_found_count = 0
            else:
                self._plume_found_count = 0

            # Check if cast distance exceeded
            if self._cast_start_pose:
                self._cast_distance = _distance(robot_pose, self._cast_start_pose)
                if self._cast_distance >= self.config.cast_distance_limit:
                    # Reverse cast direction
                    self._cast_direction *= -1
                    self._cast_start_pose = robot_pose
                    self._cast_distance = 0.0

        elif self.state == TrackingState.SOURCE_FOUND:
            # Stay in source found state
            pass

    def _generate_action(
        self,
        robot_pose: Pose2D,
        robot_yaw: float,
        wind_x: float,
        wind_y: float,
        concentration: float = 0.0,
    ) -> TrackingAction:
        """Generate tracking action based on current state."""
        if self.state == TrackingState.PATROL:
            # During patrol, just continue forward
            return TrackingAction(
                target=Pose2D(
                    robot_pose.x + self.config.surge_step * math.cos(robot_yaw),
                    robot_pose.y + self.config.surge_step * math.sin(robot_yaw),
                ),
                state=self.state,
                heading=robot_yaw,
                step_size=self.config.surge_step,
                use_particle_filter=False,
            )

        elif self.state == TrackingState.SURGE:
            # Determine primary heading
            wind_norm = math.hypot(wind_x, wind_y)
            best = self._history.get_best_position()

            if best:
                best_pose, best_conc = best
                dx = best_pose.x - robot_pose.x
                dy = best_pose.y - robot_pose.y
                dist_to_best = math.hypot(dx, dy)

                if dist_to_best > 0.05 and best_conc > self._plume_detector.current_concentration:
                    # Gradient toward best position
                    gradient_heading = math.atan2(dy, dx)
                else:
                    gradient_heading = None
            else:
                gradient_heading = None

            if wind_norm > 0.1:
                upwind_heading = math.atan2(-wind_y, -wind_x)
                if gradient_heading is not None:
                    # Blend upwind with gradient
                    upwind_weight = min(0.8, wind_norm)
                    combined_x = upwind_weight * math.cos(upwind_heading) + (1 - upwind_weight) * math.cos(gradient_heading)
                    combined_y = upwind_weight * math.sin(upwind_heading) + (1 - upwind_weight) * math.sin(gradient_heading)
                    upwind_heading = math.atan2(combined_y, combined_x)
            elif gradient_heading is not None:
                upwind_heading = gradient_heading
            else:
                upwind_heading = robot_yaw

            step = self._adaptive_step_size(concentration)
            target = Pose2D(
                robot_pose.x + step * math.cos(upwind_heading),
                robot_pose.y + step * math.sin(upwind_heading),
            )

            return TrackingAction(
                target=target,
                state=self.state,
                heading=upwind_heading,
                step_size=step,
                use_particle_filter=self.config.use_particle_filter,
            )

        elif self.state == TrackingState.CAST:
            # Move perpendicular to wind, but bias toward best historical position
            wind_norm = math.hypot(wind_x, wind_y)
            if wind_norm > 0.1:
                # Cast perpendicular to wind direction
                wind_heading = math.atan2(wind_y, wind_x)
                cast_heading = wind_heading + math.pi / 2 * self._cast_direction
            else:
                # No wind, cast perpendicular to current heading
                cast_heading = robot_yaw + math.pi / 2 * self._cast_direction

            # Bias toward best historical position if available
            best = self._history.get_best_position()
            if best and best[1] > 0:
                best_pose = best[0]
                dx = best_pose.x - robot_pose.x
                dy = best_pose.y - robot_pose.y
                dist = math.hypot(dx, dy)
                if dist > 0.5:  # Only bias if significantly far
                    best_heading = math.atan2(dy, dx)
                    # Blend cast heading with direction to best position
                    # using unit vectors to handle angle wraparound correctly
                    bx = 0.6 * math.cos(cast_heading) + 0.4 * math.cos(best_heading)
                    by = 0.6 * math.sin(cast_heading) + 0.4 * math.sin(best_heading)
                    cast_heading = math.atan2(by, bx)

            target = Pose2D(
                robot_pose.x + self.config.cast_step * math.cos(cast_heading),
                robot_pose.y + self.config.cast_step * math.sin(cast_heading),
            )

            return TrackingAction(
                target=target,
                state=self.state,
                heading=cast_heading,
                step_size=self.config.cast_step,
                use_particle_filter=False,
            )

        elif self.state == TrackingState.SOURCE_FOUND:
            # Stay at current position
            return TrackingAction(
                target=robot_pose,
                state=self.state,
                heading=robot_yaw,
                step_size=0.0,
                use_particle_filter=False,
            )

        # Default fallback
        return TrackingAction(
            target=robot_pose,
            state=self.state,
            heading=robot_yaw,
            step_size=0.0,
            use_particle_filter=False,
        )

    @property
    def current_state(self) -> TrackingState:
        """Current tracking state."""
        return self.state

    @property
    def source_estimate(self) -> Pose2D | None:
        """Estimated source position if found."""
        return self._source_estimate

    def reset(self) -> None:
        """Reset tracker to initial state."""
        self.state = TrackingState.PATROL
        self._plume_detector.reset()
        self._history.clear()
        self._cast_direction = 1
        self._cast_start_pose = None
        self._cast_distance = 0.0
        self._source_hits = 0
        self._source_estimate = None
        self._plume_lost_count = 0
        self._plume_found_count = 0
