"""Tests for baseline algorithms."""

import math
import pytest

from h2track_tracking.tracking.baseline_algorithms import (
    GradientSearch,
    GradientSearchConfig,
    RandomWalk,
    RandomWalkConfig,
    SpiralSearch,
    SpiralSearchConfig,
)
from h2track_tracking.tracking.types import Pose2D


class TestGradientSearch:
    def test_init_default(self) -> None:
        algo = GradientSearch()
        assert algo.config.step_size == 0.5

    def test_update_returns_action(self) -> None:
        algo = GradientSearch()
        action = algo.update(concentration=1.0, robot_pose=Pose2D(0, 0), robot_yaw=0.0)
        assert action.target is not None

    def test_reset_clears_history(self) -> None:
        algo = GradientSearch()
        for i in range(5):
            algo.update(float(i), Pose2D(float(i), 0), 0.0)
        algo.reset()
        assert len(algo._history) == 0


class TestRandomWalk:
    def test_init_default(self) -> None:
        algo = RandomWalk()
        assert algo.config.step_size == 0.5

    def test_update_returns_action(self) -> None:
        algo = RandomWalk()
        action = algo.update(concentration=1.0, robot_pose=Pose2D(0, 0), robot_yaw=0.0)
        assert action.target is not None


class TestSpiralSearch:
    def test_init_default(self) -> None:
        algo = SpiralSearch()
        assert algo.config.initial_radius == 0.5

    def test_spiral_expands(self) -> None:
        algo = SpiralSearch()
        poses = []
        for i in range(10):
            action = algo.update(1.0, Pose2D(0, 0), 0.0)
            poses.append(action.target)
        # Radius should increase after full rotation
        assert algo._current_radius > algo.config.initial_radius

    def test_reset(self) -> None:
        algo = SpiralSearch()
        for i in range(10):
            algo.update(1.0, Pose2D(0, 0), 0.0)
        algo.reset()
        assert algo._current_radius == algo.config.initial_radius
