"""Pure gas field helpers used by the ROS node and tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float


@dataclass(frozen=True)
class GasFieldParams:
    source_x: float
    source_y: float
    source_strength: float
    decay_rate: float
    plume_stddev: float
    wind_x: float
    wind_y: float
    noise_stddev: float
    min_concentration: float


class GasFieldModel:
    """Simple 2D plume model with downwind bias and bounded noise."""

    def __init__(self, params: GasFieldParams, rng: random.Random | None = None) -> None:
        self.params = params
        self.rng = rng or random.Random(0)

    def concentration_at(self, pose: Pose2D) -> float:
        dx = pose.x - self.params.source_x
        dy = pose.y - self.params.source_y
        distance = math.hypot(dx, dy)

        wind_norm = math.hypot(self.params.wind_x, self.params.wind_y)
        if wind_norm > 1e-6:
            wind_dir = (self.params.wind_x / wind_norm, self.params.wind_y / wind_norm)
            projection = dx * wind_dir[0] + dy * wind_dir[1]
            lateral_sq = max(0.0, distance * distance - projection * projection)
            lateral = math.sqrt(lateral_sq)
            plume_bias = math.exp(-(lateral * lateral) / (2.0 * self.params.plume_stddev**2))
            if projection < 0.0:
                plume_bias *= 0.35
        else:
            plume_bias = 1.0

        baseline = self.params.source_strength * math.exp(-self.params.decay_rate * distance)
        noise = self.rng.gauss(0.0, self.params.noise_stddev) if self.params.noise_stddev > 0.0 else 0.0

        return max(self.params.min_concentration, baseline * plume_bias + noise)

    def next_search_target(
        self,
        current_pose: Pose2D,
        current_yaw: float,
        history: list[tuple[Pose2D, float]],
        step_size: float,
        sweep_angle: float,
    ) -> Pose2D:
        """Select next tracking target using concentration gradient and upwind bias.

        Uses the best position from history (highest concentration) as target
        when current concentration is lower, otherwise continues exploring.
        Adds upwind bias to move toward the gas source.
        """
        if not history:
            # No history, just go forward
            return Pose2D(
                x=current_pose.x + step_size * math.cos(current_yaw),
                y=current_pose.y + step_size * math.sin(current_yaw),
            )

        # Find position with highest concentration in history
        best_pose, best_conc = max(history, key=lambda h: h[1])
        current_conc = history[-1][1]

        # Calculate upwind direction (opposite to wind)
        wind_norm = math.hypot(self.params.wind_x, self.params.wind_y)
        upwind_x, upwind_y = 0.0, 0.0
        if wind_norm > 0.1:  # Significant wind
            upwind_x = -self.params.wind_x / wind_norm
            upwind_y = -self.params.wind_y / wind_norm

        # If we found a higher concentration elsewhere, go toward it with upwind bias
        if best_conc > current_conc + 0.1:  # 0.1 threshold to avoid oscillation
            dx = best_pose.x - current_pose.x
            dy = best_pose.y - current_pose.y
            distance = math.hypot(dx, dy)
            if distance > step_size:
                # Move toward the best position
                heading = math.atan2(dy, dx)
                # Add upwind bias to the heading
                if wind_norm > 0.1:
                    # Blend between toward-best and upwind (favor upwind when concentration is high)
                    upwind_heading = math.atan2(upwind_y, upwind_x)
                    # Weight upwind more when concentration is high
                    upwind_weight = min(0.5, current_conc / 20.0)
                    # Circular mean for angle blending
                    combined_x = (1 - upwind_weight) * math.cos(heading) + upwind_weight * math.cos(upwind_heading)
                    combined_y = (1 - upwind_weight) * math.sin(heading) + upwind_weight * math.sin(upwind_heading)
                    heading = math.atan2(combined_y, combined_x)

                return Pose2D(
                    x=current_pose.x + step_size * math.cos(heading),
                    y=current_pose.y + step_size * math.sin(heading),
                )
            else:
                # Already at best position, explore with upwind bias
                explore_heading = current_yaw + sweep_angle
                if wind_norm > 0.1:
                    upwind_heading = math.atan2(upwind_y, upwind_x)
                    explore_heading = 0.5 * explore_heading + 0.5 * upwind_heading
                return Pose2D(
                    x=current_pose.x + step_size * math.cos(explore_heading),
                    y=current_pose.y + step_size * math.sin(explore_heading),
                )

        # Concentration is increasing or stable - estimate gradient from history
        if len(history) >= 2:
            prev_pose, prev_conc = history[-2]
            curr_pose, curr_conc = history[-1]

            if curr_conc > prev_conc:
                # Moving in right direction, continue with upwind bias
                dx = curr_pose.x - prev_pose.x
                dy = curr_pose.y - prev_pose.y
                if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                    heading = math.atan2(dy, dx)
                    # Add upwind bias
                    if wind_norm > 0.1:
                        upwind_heading = math.atan2(upwind_y, upwind_x)
                        upwind_weight = min(0.4, current_conc / 30.0)
                        combined_x = (1 - upwind_weight) * math.cos(heading) + upwind_weight * math.cos(upwind_heading)
                        combined_y = (1 - upwind_weight) * math.sin(heading) + upwind_weight * math.sin(upwind_heading)
                        heading = math.atan2(combined_y, combined_x)

                    return Pose2D(
                        x=current_pose.x + step_size * math.cos(heading),
                        y=current_pose.y + step_size * math.sin(heading),
                    )
            else:
                # Concentration decreased, add sweep with upwind bias
                heading = current_yaw + sweep_angle
                if wind_norm > 0.1:
                    upwind_heading = math.atan2(upwind_y, upwind_x)
                    # More upwind bias when we're lost
                    heading = 0.3 * heading + 0.7 * upwind_heading
                return Pose2D(
                    x=current_pose.x + step_size * math.cos(heading),
                    y=current_pose.y + step_size * math.sin(heading),
                )

        # Default: explore with upwind bias
        if wind_norm > 0.1:
            heading = math.atan2(upwind_y, upwind_x)
        else:
            heading = current_yaw + sweep_angle
        return Pose2D(
            x=current_pose.x + step_size * math.cos(heading),
            y=current_pose.y + step_size * math.sin(heading),
        )
