from nav2_simple_commander.robot_navigator import TaskResult

from h2track_tracking.exploration_logic import (
    GridSnapshot,
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
