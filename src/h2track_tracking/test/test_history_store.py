"""Tests for TimeSeriesStore (history store)."""

import pytest
import numpy as np
import time
import threading

from h2track_tracking.heatmap.grid import ConcentrationGrid, HeatmapConfig
from h2track_tracking.heatmap.history_store import TimeSeriesStore, Snapshot


class TestSnapshot:
    """Tests for Snapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a snapshot."""
        grid_data = np.zeros((10, 10, 5), dtype=np.float32)
        snapshot = Snapshot(
            timestamp=12345.0,
            grid_data=grid_data,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
            resolution=0.5,
        )

        assert snapshot.timestamp == 12345.0
        assert snapshot.dimensions == (10, 10, 5)
        assert snapshot.origin == (-5.0, -5.0, 0.0)
        assert snapshot.resolution == 0.5

    def test_snapshot_data_is_copy(self):
        """Test that snapshot stores a copy of grid data."""
        grid_data = np.ones((5, 5, 3), dtype=np.float32)
        original_value = grid_data[0, 0, 0]
        snapshot = Snapshot(
            timestamp=100.0,
            grid_data=grid_data,
            dimensions=(5, 5, 3),
            origin=(0.0, 0.0, 0.0),
            resolution=1.0,
        )

        # Snapshot should have the original value
        assert snapshot.grid_data[0, 0, 0] == original_value

        # Snapshot's data should be a separate array (not the same object)
        assert snapshot.grid_data is not grid_data

        # Snapshot data should be read-only
        assert not snapshot.grid_data.flags.writeable

    def test_snapshot_immutable(self):
        """Test that snapshot is frozen (immutable)."""
        grid_data = np.zeros((5, 5, 3), dtype=np.float32)
        snapshot = Snapshot(
            timestamp=100.0,
            grid_data=grid_data,
            dimensions=(5, 5, 3),
            origin=(0.0, 0.0, 0.0),
            resolution=1.0,
        )

        with pytest.raises(AttributeError):
            snapshot.timestamp = 200.0


class TestTimeSeriesStore:
    """Tests for TimeSeriesStore class."""

    def test_store_creation(self):
        """Test creating a time series store."""
        store = TimeSeriesStore(max_length=100)
        assert store.max_length == 100
        assert len(store) == 0

    def test_save_snapshot(self):
        """Test saving a snapshot."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore(max_length=100)
        timestamp = time.time()

        store.save_snapshot(grid, timestamp)

        assert len(store) == 1

    def test_save_snapshot_copies_data(self):
        """Test that save_snapshot copies grid data."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        timestamp = time.time()

        store.save_snapshot(grid, timestamp)

        # Modify grid after saving
        grid.update(
            position=(0.0, 0.0, 0.0),
            concentration=0.9,
            timestamp=time.time(),
        )

        # Saved snapshot should be unchanged
        snapshot = store.get_latest()
        assert snapshot is not None
        assert np.sum(snapshot.grid_data) == 0.0  # Original empty grid

    def test_get_latest_empty(self):
        """Test get_latest on empty store."""
        store = TimeSeriesStore()
        assert store.get_latest() is None

    def test_get_latest(self):
        """Test getting the latest snapshot."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        timestamps = [100.0, 200.0, 300.0]

        for ts in timestamps:
            store.save_snapshot(grid, ts)

        latest = store.get_latest()
        assert latest is not None
        assert latest.timestamp == 300.0

    def test_query_range(self):
        """Test querying snapshots by time range."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        timestamps = [100.0, 150.0, 200.0, 250.0, 300.0]

        for ts in timestamps:
            store.save_snapshot(grid, ts)

        # Query middle range
        results = store.query_range(150.0, 250.0)
        assert len(results) == 3
        assert [s.timestamp for s in results] == [150.0, 200.0, 250.0]

    def test_query_range_empty(self):
        """Test querying empty store."""
        store = TimeSeriesStore()
        results = store.query_range(0.0, 100.0)
        assert results == []

    def test_query_range_no_matches(self):
        """Test querying range with no matches."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        timestamps = [100.0, 200.0, 300.0]

        for ts in timestamps:
            store.save_snapshot(grid, ts)

        results = store.query_range(500.0, 600.0)
        assert results == []

    def test_query_range_inclusive(self):
        """Test that query_range is inclusive of boundaries."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        timestamps = [100.0, 200.0, 300.0]

        for ts in timestamps:
            store.save_snapshot(grid, ts)

        # Query exact boundary values
        results = store.query_range(100.0, 300.0)
        assert len(results) == 3

    def test_max_length_circular_buffer(self):
        """Test that store discards old snapshots when full."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        max_length = 5
        store = TimeSeriesStore(max_length=max_length)

        # Add more than max_length snapshots
        for i in range(10):
            store.save_snapshot(grid, float(i))

        # Should only keep last max_length
        assert len(store) == max_length

        # Oldest should be at index 5, not 0
        results = store.query_range(0.0, 10.0)
        assert results[0].timestamp == 5.0
        assert results[-1].timestamp == 9.0

    def test_clear(self):
        """Test clearing all history."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore()
        for i in range(5):
            store.save_snapshot(grid, float(i))

        store.clear()
        assert len(store) == 0
        assert store.get_latest() is None


class TestTimeSeriesStoreThreadSafety:
    """Thread safety tests for TimeSeriesStore."""

    def test_concurrent_saves(self):
        """Test concurrent save operations."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore(max_length=1000)
        num_threads = 10
        saves_per_thread = 100

        def save_snapshots(thread_id: int):
            for i in range(saves_per_thread):
                ts = float(thread_id * 1000 + i)
                store.save_snapshot(grid, ts)

        threads = [
            threading.Thread(target=save_snapshots, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(store) == num_threads * saves_per_thread

    def test_concurrent_read_write(self):
        """Test concurrent read and write operations."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore(max_length=500)
        errors = []

        def writer():
            for i in range(100):
                store.save_snapshot(grid, float(i))
                time.sleep(0.001)

        def reader():
            for i in range(100):
                try:
                    _ = store.get_latest()
                    _ = store.query_range(0.0, 100.0)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.001)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestTimeSeriesStoreIntegration:
    """Integration tests with ConcentrationGrid."""

    def test_full_workflow(self):
        """Test complete workflow: update grid, save snapshots, query history."""
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        store = TimeSeriesStore(max_length=100)
        base_time = time.time()

        # Simulate robot path with gas readings
        positions = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
        ]
        concentrations = [0.1, 0.3, 0.5, 0.7, 0.9]

        for i, (pos, conc) in enumerate(zip(positions, concentrations)):
            grid.update(pos, conc, base_time + i)
            store.save_snapshot(grid, base_time + i)

        # Query historical data
        history = store.query_range(base_time, base_time + 4)
        assert len(history) == 5

        # Check that each snapshot captures grid state at that time
        for i, snapshot in enumerate(history):
            ix, iy, iz = grid.world_to_grid(positions[i])
            # The snapshot should have the concentration from that time
            expected = concentrations[i]
            actual = snapshot.grid_data[ix, iy, iz]
            assert actual == pytest.approx(expected, rel=0.01)

    def test_snapshot_preserves_grid_metadata(self):
        """Test that snapshots preserve grid metadata."""
        config = HeatmapConfig(resolution=0.25)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(50, 50, 10),
            origin=(-10.0, -10.0, 1.0),
        )

        store = TimeSeriesStore()
        store.save_snapshot(grid, 12345.0)

        snapshot = store.get_latest()
        assert snapshot is not None
        assert snapshot.dimensions == (50, 50, 10)
        assert snapshot.origin == (-10.0, -10.0, 1.0)
        assert snapshot.resolution == 0.25
