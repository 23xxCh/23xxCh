from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
import math

try:
    from nav2_simple_commander.robot_navigator import TaskResult
except ImportError:
    class TaskResult(Enum):
        UNKNOWN = auto()
        SUCCEEDED = auto()
        CANCELED = auto()
        FAILED = auto()


@dataclass(frozen=True)
class FrontierGoal:
    x: float
    y: float


@dataclass(frozen=True)
class GridSnapshot:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    data: list[int]


def _index(width: int, x: int, y: int) -> int:
    return y * width + x


def _neighbors4(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _neighbors8(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return (
        (x + 1, y),
        (x - 1, y),
        (x, y + 1),
        (x, y - 1),
        (x + 1, y + 1),
        (x + 1, y - 1),
        (x - 1, y + 1),
        (x - 1, y - 1),
    )


def _in_bounds(grid: GridSnapshot, x: int, y: int) -> bool:
    return 0 <= x < grid.width and 0 <= y < grid.height


def _is_frontier_cell(grid: GridSnapshot, x: int, y: int) -> bool:
    if grid.data[_index(grid.width, x, y)] != 0:
        return False
    for nx, ny in _neighbors4(x, y):
        if _in_bounds(grid, nx, ny) and grid.data[_index(grid.width, nx, ny)] == -1:
            return True
    return False


def _cluster_frontiers(grid: GridSnapshot) -> list[list[tuple[int, int]]]:
    frontier_cells = {
        (x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if _is_frontier_cell(grid, x, y)
    }
    clusters: list[list[tuple[int, int]]] = []
    while frontier_cells:
        start = frontier_cells.pop()
        cluster = [start]
        queue = deque([start])
        while queue:
            cx, cy = queue.popleft()
            for nx, ny in _neighbors8(cx, cy):
                if (nx, ny) in frontier_cells:
                    frontier_cells.remove((nx, ny))
                    cluster.append((nx, ny))
                    queue.append((nx, ny))
        clusters.append(cluster)
    return clusters


def _cluster_centroid_world(grid: GridSnapshot, cluster: list[tuple[int, int]]) -> FrontierGoal:
    avg_x = sum(x + 0.5 for x, _ in cluster) / len(cluster)
    avg_y = sum(y + 0.5 for _, y in cluster) / len(cluster)
    return FrontierGoal(
        x=grid.origin_x + avg_x * grid.resolution,
        y=grid.origin_y + avg_y * grid.resolution,
    )


def select_frontier_goal(
    grid: GridSnapshot,
    robot_xy: tuple[float, float],
    *,
    min_frontier_cluster_size: int,
    min_goal_distance: float,
    min_goal_x: float = -1.0e9,
    max_goal_x: float = 1.0e9,
    min_goal_y: float = -1.0e9,
    max_goal_y: float = 1.0e9,
    blocked_goals: list[tuple[float, float, float]] | None = None,
) -> FrontierGoal | None:
    viable: list[FrontierGoal] = []
    robot_x, robot_y = robot_xy
    blocked = blocked_goals or []

    for cluster in _cluster_frontiers(grid):
        if len(cluster) < min_frontier_cluster_size:
            continue
        centroid = _cluster_centroid_world(grid, cluster)
        if math.dist((centroid.x, centroid.y), (robot_x, robot_y)) < min_goal_distance:
            continue
        if (
            centroid.x < min_goal_x
            or centroid.x > max_goal_x
            or centroid.y < min_goal_y
            or centroid.y > max_goal_y
        ):
            continue
        if any(
            math.dist((centroid.x, centroid.y), (blocked_x, blocked_y)) <= max(0.0, blocked_radius)
            for blocked_x, blocked_y, blocked_radius in blocked
        ):
            continue
        viable.append(centroid)

    if not viable:
        return None

    return min(viable, key=lambda goal: math.dist((goal.x, goal.y), (robot_x, robot_y)))


def navigation_state_allows_new_frontier(
    *,
    task_complete: bool,
    task_result: TaskResult | None,
) -> bool:
    if not task_complete:
        return False

    return task_result in (
        TaskResult.SUCCEEDED,
        TaskResult.CANCELED,
        TaskResult.FAILED,
        TaskResult.UNKNOWN,
        None,
    )


def goal_progress_stalled(
    *,
    task_complete: bool,
    active_goal_xy: tuple[float, float] | None,
    robot_xy: tuple[float, float],
    last_progress_xy: tuple[float, float] | None,
    last_progress_time_sec: float | None,
    now_sec: float,
    movement_epsilon: float,
    stall_timeout_sec: float,
    goal_tolerance: float,
) -> bool:
    if task_complete or active_goal_xy is None:
        return False
    if last_progress_xy is None or last_progress_time_sec is None:
        return False
    if math.dist(robot_xy, active_goal_xy) <= max(0.0, goal_tolerance):
        return False
    if math.dist(robot_xy, last_progress_xy) >= max(0.0, movement_epsilon):
        return False
    return (now_sec - last_progress_time_sec) >= max(0.0, stall_timeout_sec)
