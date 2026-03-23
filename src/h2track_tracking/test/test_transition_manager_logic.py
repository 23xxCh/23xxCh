import math

from h2track_tracking.transition_manager_node import clamp_tracking_source_seed


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
