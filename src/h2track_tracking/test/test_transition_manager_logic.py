import math

from nav_msgs.msg import OccupancyGrid

from h2track_tracking.transition_manager_node import (
    clamp_tracking_source_seed,
    snap_tracking_source_to_free_space,
)


def test_clamp_tracking_source_seed_keeps_source_when_within_max_distance():
    source = (1.0, 2.0)
    current = (0.2, 1.4)
    clamped = clamp_tracking_source_seed(source, current, max_distance=2.0)
    assert clamped == source


def test_clamp_tracking_source_seed_limits_distance_when_source_is_far():
    source = (-1.55, 3.1)
    current = (2.5, -3.4)
    clamped = clamp_tracking_source_seed(source, current, max_distance=2.0)
    dx = clamped[0] - current[0]
    dy = clamped[1] - current[1]
    assert math.isclose(math.hypot(dx, dy), 2.0, rel_tol=1e-6, abs_tol=1e-6)
    direction_x = source[0] - current[0]
    direction_y = source[1] - current[1]
    assert dx * direction_x + dy * direction_y > 0.0


def _make_grid(
    *,
    width: int,
    height: int,
    resolution: float,
    origin_x: float,
    origin_y: float,
    data: list[int],
) -> OccupancyGrid:
    grid = OccupancyGrid()
    grid.info.width = width
    grid.info.height = height
    grid.info.resolution = resolution
    grid.info.origin.position.x = origin_x
    grid.info.origin.position.y = origin_y
    grid.data = data
    return grid


def test_snap_tracking_source_to_free_space_keeps_point_when_cell_is_free():
    grid = _make_grid(
        width=5,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[0] * 25,
    )
    source = (2.5, 2.5)
    snapped = snap_tracking_source_to_free_space(source, grid, max_search_cells=5)
    assert snapped == source


def test_snap_tracking_source_to_free_space_moves_to_nearest_free_cell():
    data = [100] * 25
    # free cell at gx=1, gy=2 -> world (1.5, 2.5)
    data[2 * 5 + 1] = 0
    grid = _make_grid(
        width=5,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=data,
    )
    source = (2.5, 2.5)
    snapped = snap_tracking_source_to_free_space(source, grid, max_search_cells=5)
    assert snapped == (1.5, 2.5)


def test_snap_tracking_source_to_free_space_falls_back_to_original_when_no_free_cell():
    data = [100] * 25
    grid = _make_grid(
        width=5,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=data,
    )
    source = (2.5, 2.5)
    snapped = snap_tracking_source_to_free_space(source, grid, max_search_cells=3)
    assert snapped == source
