from h2track_tracking.exploration_logic import (
    GridSnapshot,
    TaskResult,
    goal_progress_stalled,
    navigation_state_allows_new_frontier,
    select_frontier_goal,
)


def test_select_frontier_goal_returns_centroid_of_nearest_frontier_cluster():
    grid = GridSnapshot(
        width=6,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[
            100, 100, 100, 100, 100, 100,
            100,   0,   0,  -1,  -1, 100,
            100,   0,   0,  -1,  -1, 100,
            100,   0,   0,   0,   0, 100,
            100, 100, 100, 100, 100, 100,
        ],
    )

    goal = select_frontier_goal(
        grid,
        robot_xy=(1.5, 3.5),
        min_frontier_cluster_size=2,
        min_goal_distance=0.5,
    )

    assert goal is not None
    assert goal.x > 2.0
    assert 1.0 < goal.y < 4.5


def test_select_frontier_goal_returns_none_when_only_tiny_frontiers_exist():
    grid = GridSnapshot(
        width=5,
        height=5,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[
            100, 100, 100, 100, 100,
            100,   0,   0, 100, 100,
            100,   0,  -1, 100, 100,
            100, 100, 100, 100, 100,
            100, 100, 100, 100, 100,
        ],
    )

    goal = select_frontier_goal(
        grid,
        robot_xy=(1.5, 1.5),
        min_frontier_cluster_size=3,
        min_goal_distance=0.5,
    )

    assert goal is None


def test_select_frontier_goal_skips_frontiers_too_close_to_robot():
    grid = GridSnapshot(
        width=8,
        height=6,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[
            100, 100, 100, 100, 100, 100, 100, 100,
            100,   0,  -1, 100, 100, 100, 100, 100,
            100,   0,   0, 100,   0,   0,  -1, 100,
            100, 100, 100, 100,   0,   0,  -1, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
        ],
    )

    goal = select_frontier_goal(
        grid,
        robot_xy=(1.5, 1.5),
        min_frontier_cluster_size=2,
        min_goal_distance=2.0,
    )

    assert goal is not None
    assert goal.x >= 5.0


def test_navigation_state_allows_dispatch_when_no_goal_has_been_sent_yet():
    assert navigation_state_allows_new_frontier(
        task_complete=True,
        task_result=TaskResult.UNKNOWN,
    )


def test_navigation_state_blocks_dispatch_while_goal_is_still_running():
    assert not navigation_state_allows_new_frontier(
        task_complete=False,
        task_result=TaskResult.UNKNOWN,
    )


def test_select_frontier_goal_respects_optional_world_bounds():
    grid = GridSnapshot(
        width=8,
        height=6,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[
            100, 100, 100, 100, 100, 100, 100, 100,
            100,   0,  -1, 100, 100, 100, 100, 100,
            100,   0,   0, 100,   0,   0,  -1, 100,
            100, 100, 100, 100,   0,   0,  -1, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
        ],
    )

    goal = select_frontier_goal(
        grid,
        robot_xy=(1.5, 1.5),
        min_frontier_cluster_size=2,
        min_goal_distance=0.5,
        min_goal_x=0.0,
        max_goal_x=3.0,
        min_goal_y=0.0,
        max_goal_y=5.0,
    )

    assert goal is not None
    assert goal.x <= 3.0


def test_select_frontier_goal_skips_temporarily_blocked_frontier_regions():
    grid = GridSnapshot(
        width=8,
        height=6,
        resolution=1.0,
        origin_x=0.0,
        origin_y=0.0,
        data=[
            100, 100, 100, 100, 100, 100, 100, 100,
            100,   0,  -1, 100, 100, 100, 100, 100,
            100,   0,   0, 100,   0,   0,  -1, 100,
            100, 100, 100, 100,   0,   0,  -1, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
            100, 100, 100, 100, 100, 100, 100, 100,
        ],
    )

    goal = select_frontier_goal(
        grid,
        robot_xy=(1.5, 1.5),
        min_frontier_cluster_size=2,
        min_goal_distance=0.5,
        blocked_goals=[(1.5, 1.5, 2.0)],
    )

    assert goal is not None
    assert goal.x >= 5.0


def test_goal_progress_stalled_requires_timeout_without_meaningful_motion():
    assert goal_progress_stalled(
        task_complete=False,
        active_goal_xy=(4.0, 4.0),
        robot_xy=(0.1, 0.2),
        last_progress_xy=(0.1, 0.2),
        last_progress_time_sec=10.0,
        now_sec=26.0,
        movement_epsilon=0.08,
        stall_timeout_sec=15.0,
        goal_tolerance=0.4,
    )


def test_goal_progress_stalled_returns_false_when_robot_moved_since_last_progress_mark():
    assert not goal_progress_stalled(
        task_complete=False,
        active_goal_xy=(4.0, 4.0),
        robot_xy=(0.4, 0.2),
        last_progress_xy=(0.1, 0.2),
        last_progress_time_sec=10.0,
        now_sec=26.0,
        movement_epsilon=0.08,
        stall_timeout_sec=15.0,
        goal_tolerance=0.4,
    )


def test_goal_progress_stalled_returns_false_when_already_near_goal():
    assert not goal_progress_stalled(
        task_complete=False,
        active_goal_xy=(0.25, 0.2),
        robot_xy=(0.1, 0.2),
        last_progress_xy=(0.1, 0.2),
        last_progress_time_sec=10.0,
        now_sec=26.0,
        movement_epsilon=0.08,
        stall_timeout_sec=15.0,
        goal_tolerance=0.4,
    )
