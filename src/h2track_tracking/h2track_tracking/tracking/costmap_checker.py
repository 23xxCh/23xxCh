"""Costmap validation for tracking targets.

Ensures tracking targets are in free space before sending to Nav2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union
import math

import numpy as np

if TYPE_CHECKING:
    from nav_msgs.msg import OccupancyGrid
    from nav2_msgs.msg import Costmap

from .types import Pose2D, TrackingAction


@dataclass(frozen=True)
class SafetyAssessment:
    """Immutable result of safety evaluation.

    Attributes:
        obstacle_detected: True if target is in obstacle or robot is stuck.
        suggested_action: One of "continue", "replan", "wait".
        alternative_target: Projected free-space target, or None.
    """
    obstacle_detected: bool = False
    suggested_action: str = "continue"
    alternative_target: Pose2D | None = None


@dataclass(frozen=True)
class CostmapConfig:
    """Configuration for costmap validation.

    Attributes:
        inflation_radius: Robot inflation radius for safety margin
        lethal_cost_threshold: Cost value considered lethal (Nav2 uses 254)
        free_threshold: Cost values below this are considered free space
        unknown_cost_value: Cost value for unknown cells (typically -1 for occupancy grid)
    """
    inflation_radius: float = 0.5
    lethal_cost_threshold: int = 254
    free_threshold: int = 1
    unknown_cost_value: int = -1


class CostmapChecker:
    """Check tracking targets against Nav2 costmap.

    Validates that tracking targets are in free space and projects
    invalid targets to the nearest valid position.

    Supports both nav_msgs/OccupancyGrid (int8, -128 to 127) and
    nav2_msgs/Costmap (uint8, 0 to 255) message types.

    Example:
        >>> checker = CostmapChecker()
        >>> # After receiving Costmap message
        >>> checker.update_costmap(msg)
        >>> if not checker.is_valid_target(target):
        ...     projected = checker.project_to_free_space(target, robot_pose)
    """

    def __init__(self, config: CostmapConfig | None = None) -> None:
        """Initialize the costmap checker.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or CostmapConfig()
        self._costmap: np.ndarray | None = None
        self._resolution: float = 0.05
        self._origin_x: float = 0.0
        self._origin_y: float = 0.0
        self._width: int = 0
        self._height: int = 0
        self._frame_id: str = "map"

    def update_costmap(self, msg: Union["OccupancyGrid", "Costmap"]) -> None:
        """Update internal costmap from ROS message.

        Supports both nav_msgs/OccupancyGrid and nav2_msgs/Costmap.

        Args:
            msg: Costmap message from Nav2 or occupancy grid from SLAM.
        """
        # Check message type based on available attributes
        if hasattr(msg, 'metadata'):
            # nav2_msgs/Costmap
            self._resolution = msg.metadata.resolution
            self._origin_x = msg.metadata.origin.position.x
            self._origin_y = msg.metadata.origin.position.y
            self._width = msg.metadata.size_x
            self._height = msg.metadata.size_y
            # uint8 array, values 0-255
            self._costmap = np.array(list(msg.data), dtype=np.uint8).reshape(
                (self._height, self._width)
            )
        else:
            # nav_msgs/OccupancyGrid
            self._resolution = msg.info.resolution
            self._origin_x = msg.info.origin.position.x
            self._origin_y = msg.info.origin.position.y
            self._width = msg.info.width
            self._height = msg.info.height
            # int8 array, values -128 to 127
            # OccupancyGrid uses -1 for unknown, 0-100 for probability
            self._costmap = np.array(list(msg.data), dtype=np.int16).reshape(
                (self._height, self._width)
            )

        self._frame_id = msg.header.frame_id

    def _world_to_grid(self, x: float, y: float) -> tuple[int, int] | None:
        """Convert world coordinates to grid indices.

        Args:
            x: World X coordinate
            y: World Y coordinate

        Returns:
            Tuple of (row, col) indices, or None if outside costmap bounds.
        """
        if self._costmap is None:
            return None

        col = int((x - self._origin_x) / self._resolution)
        row = int((y - self._origin_y) / self._resolution)

        if 0 <= row < self._height and 0 <= col < self._width:
            return (row, col)
        return None

    def _grid_to_world(self, row: int, col: int) -> tuple[float, float]:
        """Convert grid indices to world coordinates.

        Args:
            row: Grid row index
            col: Grid column index

        Returns:
            Tuple of (x, y) world coordinates at cell center.
        """
        x = self._origin_x + (col + 0.5) * self._resolution
        y = self._origin_y + (row + 0.5) * self._resolution
        return (x, y)

    def is_valid_target(self, target: Pose2D) -> bool:
        """Check if target is in free space.

        Args:
            target: Target position to check

        Returns:
            True if:
            - Costmap not available (allow by default)
            - Target is within costmap bounds and cost < lethal_threshold
            False if target is in obstacle or outside costmap bounds.
        """
        if self._costmap is None:
            return True  # No costmap, allow by default

        indices = self._world_to_grid(target.x, target.y)
        if indices is None:
            return False  # Outside costmap bounds

        row, col = indices
        cost = int(self._costmap[row, col])

        # Nav2 Costmap uses 255 for NO_INFORMATION (unknown), which is
        # traversable when the global planner has allow_unknown: true.
        # 254 is LETHAL_OBSTACLE.  OccupancyGrid uses -1 for unknown.
        if cost == 255 or cost == self.config.unknown_cost_value:
            return True
        # Free (0) or low cost are valid
        return cost < self.config.free_threshold

    def get_cost_at(self, target: Pose2D) -> int:
        """Get cost value at target position.

        Args:
            target: Position to query

        Returns:
            Cost value (0-254), or lethal_cost_threshold if outside costmap,
            or 0 if no costmap available.
        """
        if self._costmap is None:
            return 0

        indices = self._world_to_grid(target.x, target.y)
        if indices is None:
            return self.config.lethal_cost_threshold  # Outside = lethal

        return int(self._costmap[indices[0], indices[1]])

    def project_to_free_space(
        self,
        target: Pose2D,
        source: Pose2D,
        max_search_radius: float = 2.0,
        step_size: float | None = None,
    ) -> Pose2D | None:
        """Project target to nearest free space along source->target direction.

        Algorithm:
        1. If target is already valid, return it
        2. Search backward along source->target line for free space
        3. If not found on line, search in expanding circles around target

        Args:
            target: Target position to project
            source: Source position (typically robot pose)
            max_search_radius: Maximum distance to search for free space
            step_size: Step size for search. Defaults to 2x resolution.

        Returns:
            Projected Pose2D in free space, or None if no free space found.
        """
        if self.is_valid_target(target):
            return target

        if self._costmap is None:
            return target  # No costmap, return original

        # Direction from source to target
        dx = target.x - source.x
        dy = target.y - source.y
        dist = math.hypot(dx, dy)

        if dist < 1e-6:
            # Source and target are same point, search nearby
            return self._find_nearest_free(target, max_search_radius)

        # Normalize direction
        dir_x = dx / dist
        dir_y = dy / dist

        if step_size is None:
            step_size = self._resolution * 2

        # Search backward along the line (toward source)
        for d in np.arange(0, min(dist, max_search_radius), step_size):
            # Point closer to source
            test_x = target.x - dir_x * d
            test_y = target.y - dir_y * d
            test_pose = Pose2D(test_x, test_y)

            if self.is_valid_target(test_pose):
                return test_pose

        # If not found on line, search in circles around target
        return self._find_nearest_free(target, max_search_radius)

    def _find_nearest_free(
        self,
        center: Pose2D,
        max_radius: float,
    ) -> Pose2D | None:
        """Find nearest free space in expanding circles around center.

        Args:
            center: Center position to search around
            max_radius: Maximum search radius

        Returns:
            Nearest Pose2D in free space, or None if not found.
        """
        if self._costmap is None:
            return None

        step = self._resolution * 2
        best_dist = float('inf')
        best_pose: Pose2D | None = None

        for radius in np.arange(step, max_radius, step):
            # Check points on circle
            num_points = max(8, int(2 * math.pi * radius / step))
            for i in range(num_points):
                angle = 2 * math.pi * i / num_points
                test_x = center.x + radius * math.cos(angle)
                test_y = center.y + radius * math.sin(angle)
                test_pose = Pose2D(test_x, test_y)

                if self.is_valid_target(test_pose):
                    dist = math.hypot(test_x - center.x, test_y - center.y)
                    if dist < best_dist:
                        best_dist = dist
                        best_pose = test_pose

            if best_pose is not None:
                return best_pose

        return None

    def safe_tracking_action(
        self,
        action: TrackingAction,
        robot_pose: Pose2D,
        max_search_radius: float = 2.0,
    ) -> TrackingAction:
        """Validate and correct tracking action.

        If target is in obstacle:
        1. Project to nearest free space along robot->target direction
        2. If projection fails, return action with target set to robot pose

        Args:
            action: Original tracking action
            robot_pose: Current robot position
            max_search_radius: Maximum distance to search for free space

        Returns:
            Corrected TrackingAction with valid target.
        """
        if self.is_valid_target(action.target):
            return action

        projected = self.project_to_free_space(
            action.target,
            robot_pose,
            max_search_radius
        )

        if projected is not None:
            return TrackingAction(
                target=projected,
                state=action.state,
                heading=action.heading,
                step_size=action.step_size,
                use_particle_filter=action.use_particle_filter,
            )

        # No valid projection, stay in place
        return TrackingAction(
            target=robot_pose,
            state=action.state,
            heading=action.heading,
            step_size=0.0,
            use_particle_filter=False,
        )

    def evaluate_safety(
        self,
        target: Pose2D,
        robot_pose: Pose2D,
        *,
        nav_status: str = "idle",
        path_deviation: float = 0.0,
        max_deviation: float = 2.0,
    ) -> SafetyAssessment:
        """Evaluate safety of a navigation target.

        Encapsulates the domain logic for obstacle/stuck detection previously
        spread across CostmapGuardNode.

        Args:
            target: Navigation target to evaluate.
            robot_pose: Current robot position.
            nav_status: Nav2 status string (idle/navigating/succeeded/failed).
            path_deviation: Current path deviation from Nav2.
            max_deviation: Threshold beyond which the robot is considered stuck.

        Returns:
            SafetyAssessment with obstacle/stuck verdict and suggested action.
        """
        is_valid = self.is_valid_target(target)
        is_stuck = nav_status == "navigating" and path_deviation > max_deviation

        alternative_target = None
        suggested_action = "continue"

        if is_stuck:
            projected = self.project_to_free_space(
                target, robot_pose, max_search_radius=3.0
            )
            if projected is None:
                suggested_action = "wait"
            else:
                suggested_action = "replan"
                alternative_target = projected
        elif not is_valid:
            suggested_action = "replan"

        return SafetyAssessment(
            obstacle_detected=(not is_valid) or is_stuck,
            suggested_action=suggested_action,
            alternative_target=alternative_target,
        )

    @property
    def has_costmap(self) -> bool:
        """Check if costmap data is available."""
        return self._costmap is not None

    @property
    def frame_id(self) -> str:
        """Get the costmap frame ID."""
        return self._frame_id
