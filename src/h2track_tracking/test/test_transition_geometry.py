import math

import pytest

from h2track_tracking.transition_manager_node import (
    freeze_gate_ready,
    resolve_tracking_source_point,
    transform_point_into_map_frame,
)


def test_transform_point_into_map_frame_applies_map_to_odom_translation_and_yaw():
    mapped = transform_point_into_map_frame(
        point_xy=(3.2, 2.6),
        translation_xy=(-2.0, 1.0),
        yaw=math.pi / 2.0,
    )

    assert mapped[0] == pytest.approx(-4.6)
    assert mapped[1] == pytest.approx(4.2)


def test_transform_point_into_map_frame_handles_identity_transform():
    mapped = transform_point_into_map_frame(
        point_xy=(-4.0, 1.95),
        translation_xy=(0.0, 0.0),
        yaw=0.0,
    )

    assert mapped == pytest.approx((-4.0, 1.95))


def test_freeze_gate_ready_requires_minimum_map_samples():
    assert not freeze_gate_ready(
        map_ready=False,
        valid_map_samples=1,
        first_valid_map_time_sec=2.0,
        now_sec=5.0,
        min_map_samples=2,
        min_map_age_sec=1.0,
    )


def test_freeze_gate_ready_requires_minimum_map_age():
    assert not freeze_gate_ready(
        map_ready=True,
        valid_map_samples=3,
        first_valid_map_time_sec=4.5,
        now_sec=5.0,
        min_map_samples=2,
        min_map_age_sec=1.0,
    )


def test_freeze_gate_ready_passes_when_map_samples_and_age_are_satisfied():
    assert freeze_gate_ready(
        map_ready=True,
        valid_map_samples=3,
        first_valid_map_time_sec=2.5,
        now_sec=5.0,
        min_map_samples=2,
        min_map_age_sec=1.0,
    )


def test_resolve_tracking_source_point_keeps_map_frame_source_unchanged():
    resolved = resolve_tracking_source_point(
        source_xy=(-4.0, 1.95),
        source_frame="map",
        map_to_odom_transform=((5.0, 3.0), 1.57),
    )

    assert resolved == pytest.approx((-4.0, 1.95))


def test_resolve_tracking_source_point_transforms_odom_frame_source_into_map():
    resolved = resolve_tracking_source_point(
        source_xy=(3.2, 2.6),
        source_frame="odom",
        map_to_odom_transform=((-2.0, 1.0), math.pi / 2.0),
    )

    assert resolved == pytest.approx((-4.6, 4.2))
