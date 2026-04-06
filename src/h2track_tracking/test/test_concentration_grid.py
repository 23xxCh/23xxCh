"""Tests for concentration grid."""

import pytest
import numpy as np
import time

from h2track_tracking.heatmap.grid import ConcentrationGrid, HeatmapConfig


class TestHeatmapConfig:
    def test_default_config(self):
        config = HeatmapConfig()
        assert config.resolution == 0.5
        assert config.decay_rate == 0.95

    def test_custom_config(self):
        config = HeatmapConfig(resolution=0.25, decay_rate=0.9)
        assert config.resolution == 0.25


class TestConcentrationGrid:
    def test_grid_creation(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        assert grid.dimensions == (20, 20, 5)
        assert grid.resolution == 0.5

    def test_world_to_grid_conversion(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        # Origin should map to (0, 0, 0)
        ix, iy, iz = grid.world_to_grid((-5.0, -5.0, 0.0))
        assert (ix, iy, iz) == (0, 0, 0)

        # (0, 0, 0) world should map to (10, 10, 0)
        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert (ix, iy, iz) == (10, 10, 0)

    def test_grid_to_world_conversion(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        x, y, z = grid.grid_to_world(0, 0, 0)
        assert (x, y, z) == pytest.approx((-5.0, -5.0, 0.0))

    def test_update_concentration(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        grid.update(
            position=(0.0, 0.0, 0.0),
            concentration=0.8,
            timestamp=time.time(),
        )

        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert grid.data[ix, iy, iz] == pytest.approx(0.8, rel=0.01)

    def test_decay(self):
        config = HeatmapConfig(resolution=0.5, decay_rate=0.9)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        grid.update(
            position=(0.0, 0.0, 0.0),
            concentration=1.0,
            timestamp=time.time(),
        )

        grid.decay()

        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert grid.data[ix, iy, iz] == pytest.approx(0.9, rel=0.01)

    def test_to_dict_serialization(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 3),
            origin=(-5.0, -5.0, 0.0),
        )

        data = grid.to_dict()

        assert data["resolution"] == 0.5
        assert data["dimensions"] == (10, 10, 3)
        assert data["origin"] == (-5.0, -5.0, 0.0)
        assert "data" in data

    def test_out_of_bounds_handling(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        # Should not raise for out of bounds
        grid.update(
            position=(100.0, 100.0, 100.0),
            concentration=0.5,
            timestamp=time.time(),
        )

        # Data should remain unchanged
        assert np.sum(grid.data) == 0.0
