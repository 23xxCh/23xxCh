"""Pure navigation helpers for mission management.

This module contains ROS-agnostic functions for navigation goal selection
and pose conversion. All functions are pure (no side effects) and testable
without ROS infrastructure.
"""

from __future__ import annotations

import ast
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gas_model import GasFieldModel, Pose2D


def map_pose_from_amcl(msg) -> tuple["Pose2D", float]:
    """Extract position and yaw from AMCL pose message.

    Args:
        msg: PoseWithCovarianceStamped message from AMCL.

    Returns:
        Tuple of (Pose2D position, yaw in radians).
    """
    from .gas_model import Pose2D

    position = msg.pose.pose.position
    orientation = msg.pose.pose.orientation
    yaw = math.atan2(
        2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z),
    )
    return Pose2D(position.x, position.y), yaw


def _gradient_search_target(
    current_pose: "Pose2D",
    current_yaw: float,
    history: list[tuple["Pose2D", float]],
    step_size: float,
    sweep_angle: float,
    wind_x: float,
    wind_y: float,
) -> "Pose2D":
    """Gradient-ascent target selection with upwind bias (pure function).

    Formerly part of gas_model.next_search_target.  Extracted here so that
    gas_model.py stays a pure physics module.
    """
    from .gas_model import Pose2D  # re-exported canonical type

    if not history:
        return Pose2D(
            x=current_pose.x + step_size * math.cos(current_yaw),
            y=current_pose.y + step_size * math.sin(current_yaw),
        )

    best_pose, best_conc = max(history, key=lambda h: h[1])
    current_conc = history[-1][1]

    wind_norm = math.hypot(wind_x, wind_y)
    upwind_x, upwind_y = 0.0, 0.0
    if wind_norm > 0.1:
        upwind_x = -wind_x / wind_norm
        upwind_y = -wind_y / wind_norm

    if best_conc > current_conc + 0.1:
        dx = best_pose.x - current_pose.x
        dy = best_pose.y - current_pose.y
        distance = math.hypot(dx, dy)
        if distance > step_size:
            heading = math.atan2(dy, dx)
            if wind_norm > 0.1:
                upwind_heading = math.atan2(upwind_y, upwind_x)
                upwind_weight = min(0.5, current_conc / 20.0)
                combined_x = (1 - upwind_weight) * math.cos(heading) + upwind_weight * math.cos(upwind_heading)
                combined_y = (1 - upwind_weight) * math.sin(heading) + upwind_weight * math.sin(upwind_heading)
                heading = math.atan2(combined_y, combined_x)
            return Pose2D(
                x=current_pose.x + step_size * math.cos(heading),
                y=current_pose.y + step_size * math.sin(heading),
            )
        else:
            explore_heading = current_yaw + sweep_angle
            if wind_norm > 0.1:
                upwind_heading = math.atan2(upwind_y, upwind_x)
                explore_heading = 0.5 * explore_heading + 0.5 * upwind_heading
            return Pose2D(
                x=current_pose.x + step_size * math.cos(explore_heading),
                y=current_pose.y + step_size * math.sin(explore_heading),
            )

    if len(history) >= 2:
        prev_pose, prev_conc = history[-2]
        curr_pose, curr_conc = history[-1]
        if curr_conc > prev_conc:
            dx = curr_pose.x - prev_pose.x
            dy = curr_pose.y - prev_pose.y
            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                heading = math.atan2(dy, dx)
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
            heading = current_yaw + sweep_angle
            if wind_norm > 0.1:
                upwind_heading = math.atan2(upwind_y, upwind_x)
                heading = 0.3 * heading + 0.7 * upwind_heading
            return Pose2D(
                x=current_pose.x + step_size * math.cos(heading),
                y=current_pose.y + step_size * math.sin(heading),
            )

    if wind_norm > 0.1:
        heading = math.atan2(upwind_y, upwind_x)
    else:
        heading = current_yaw + sweep_angle
    return Pose2D(
        x=current_pose.x + step_size * math.cos(heading),
        y=current_pose.y + step_size * math.sin(heading),
    )


def select_tracking_target(
    gas_model: "GasFieldModel",
    current_pose: "Pose2D",
    current_yaw: float,
    history: list[tuple["Pose2D", float]],
    step_size: float,
    sweep_angle: float,
    source_threshold: float,
) -> "Pose2D":
    """Select the next tracking target based on gas concentration history.

    When a strong source signal is detected in history but the current
    position shows lower concentration, returns the strongest position
    to guide the robot back toward the source.

    Args:
        gas_model: Gas field model for wind parameters.
        current_pose: Current robot position.
        current_yaw: Current robot heading in radians.
        history: Recent (position, concentration) samples.
        step_size: Distance to move toward target.
        sweep_angle: Angle to sweep when concentration decreases.
        source_threshold: Concentration threshold indicating source proximity.

    Returns:
        Target position for next navigation goal.
    """
    if history:
        strongest_index, (strongest_pose, strongest_concentration) = max(
            enumerate(history),
            key=lambda sample: sample[1][1],
        )
        if strongest_concentration >= source_threshold and strongest_index < len(history) - 1:
            return strongest_pose

    return _gradient_search_target(
        current_pose=current_pose,
        current_yaw=current_yaw,
        history=history,
        step_size=step_size,
        sweep_angle=sweep_angle,
        wind_x=gas_model.params.wind_x,
        wind_y=gas_model.params.wind_y,
    )


def coerce_patrol_points(raw_value: object) -> list[tuple[float, float]]:
    """Convert raw parameter value to list of patrol point coordinates.

    Handles multiple input formats:
    - String representation of list: "[x1, y1, x2, y2, ...]"
    - Flat list of floats: [x1, y1, x2, y2, ...]
    - List of coordinate pairs: [[x1, y1], [x2, y2], ...]

    Args:
        raw_value: Raw parameter value from ROS or config.

    Returns:
        List of (x, y) coordinate tuples.

    Raises:
        ValueError: If the input format is not supported.
    """
    if isinstance(raw_value, str):
        parsed = ast.literal_eval(raw_value)
    else:
        parsed = raw_value

    if not isinstance(parsed, list):
        raise ValueError(f"Unsupported patrol_points value: {parsed!r}")

    if parsed and isinstance(parsed[0], (list, tuple)):
        return [(float(x), float(y)) for x, y in parsed]

    flat_points = [float(v) for v in parsed]
    return list(zip(flat_points[0::2], flat_points[1::2]))


def should_skip_patrol_goal(
    current_goal_kind: str | None,
    goal_started_at_sec: float | None,
    current_time_sec: float,
    timeout_sec: float,
    task_complete: bool,
) -> bool:
    """Determine if current patrol goal should be skipped due to timeout.

    Args:
        current_goal_kind: Type of current goal ("patrol", "track", or None).
        goal_started_at_sec: Timestamp when goal was sent, or None.
        current_time_sec: Current time in seconds.
        timeout_sec: Maximum allowed time for patrol goal.
        task_complete: Whether navigation task has completed.

    Returns:
        True if the patrol goal should be cancelled and skipped.
    """
    if current_goal_kind != "patrol":
        return False
    if task_complete:
        return False
    if goal_started_at_sec is None:
        return False
    return (current_time_sec - goal_started_at_sec) > timeout_sec


def determine_nav_action_on_result(
    mode_name: str,
    nav_result: str | None,
    task_complete: bool,
) -> str | None:
    """Determine navigation action based on mode and navigation result.

    Args:
        mode_name: Current mission mode name ("PATROL", "SEEK_TRACK", etc.).
        nav_result: Navigation result ("SUCCEEDED", "FAILED", "CANCELED", or None).
        task_complete: Whether navigation task has completed.

    Returns:
        Action to take: "send_patrol", "send_track", "skip_patrol", "retry_track", or None.
    """
    if not task_complete:
        return None

    if mode_name == "PATROL":
        if nav_result == "SUCCEEDED":
            return "send_patrol"
        elif nav_result in ("FAILED", "CANCELED"):
            return "skip_patrol"

    elif mode_name == "SEEK_TRACK":
        if nav_result == "SUCCEEDED":
            return "send_track"
        elif nav_result in ("FAILED", "CANCELED"):
            return "retry_track"

    return None

