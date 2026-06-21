"""Time series storage for concentration grid snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import threading
from typing import Optional

from .grid import ConcentrationGrid


@dataclass(frozen=True)
class Snapshot:
    """Immutable snapshot of a concentration grid at a point in time."""

    timestamp: float
    grid_data: np.ndarray
    dimensions: tuple[int, int, int]
    origin: tuple[float, float, float]
    resolution: float

    def __post_init__(self) -> None:
        """Ensure grid_data is copied and immutable."""
        # Always make a copy to ensure data isolation from the original array
        if self.grid_data.flags.writeable:
            # Only copy if still writable (not already made read-only by previous call)
            object.__setattr__(self, "grid_data", self.grid_data.copy())
        # Make the array read-only
        self.grid_data.flags.writeable = False


class TimeSeriesStore:
    """Thread-safe time series storage for concentration grid snapshots.

    Uses a circular buffer for fixed memory usage, automatically discarding
    the oldest snapshots when the buffer is full.
    """

    def __init__(self, max_length: int = 1000) -> None:
        """Initialize the time series store.

        Args:
            max_length: Maximum number of snapshots to store (default: 1000)
        """
        self.max_length = max_length
        self._buffer: list[Snapshot] = []
        self._lock = threading.RLock()
        self._write_index: int = 0
        self._is_full: bool = False

    def __len__(self) -> int:
        """Return the current number of stored snapshots."""
        with self._lock:
            if self._is_full:
                return self.max_length
            return len(self._buffer)

    def save_snapshot(self, grid: ConcentrationGrid, timestamp: float) -> None:
        """Save the current state of a concentration grid.

        Creates a copy of the grid data for immutability.

        Args:
            grid: The concentration grid to snapshot
            timestamp: The timestamp for this snapshot
        """
        snapshot = Snapshot(
            timestamp=timestamp,
            grid_data=grid.data.copy(),
            dimensions=grid.dimensions,
            origin=grid.origin,
            resolution=grid.resolution,
        )

        with self._lock:
            if self._is_full:
                # Circular buffer: overwrite oldest entry
                self._buffer[self._write_index] = snapshot
                self._write_index = (self._write_index + 1) % self.max_length
            elif len(self._buffer) < self.max_length:
                # Still filling the buffer
                self._buffer.append(snapshot)
                self._write_index = len(self._buffer)
                if len(self._buffer) == self.max_length:
                    self._is_full = True
                    self._write_index = 0

    def query_range(
        self, start_time: float, end_time: float
    ) -> list[Snapshot]:
        """Query snapshots within a time range (inclusive).

        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)

        Returns:
            List of snapshots within the time range, sorted by timestamp
        """
        with self._lock:
            if not self._buffer:
                return []

            # Collect all snapshots in range
            results = [
                snap
                for snap in self._buffer
                if start_time <= snap.timestamp <= end_time
            ]

            # Sort by timestamp
            results.sort(key=lambda s: s.timestamp)
            return results

    def get_latest(self) -> Optional[Snapshot]:
        """Get the most recent snapshot.

        Returns:
            The latest snapshot, or None if store is empty
        """
        with self._lock:
            if not self._buffer:
                return None

            if self._is_full:
                # Latest is at (write_index - 1), handling wrap-around
                latest_idx = (self._write_index - 1) % self.max_length
                return self._buffer[latest_idx]
            else:
                # Latest is the last element
                return self._buffer[-1]

    def clear(self) -> None:
        """Clear all stored history."""
        with self._lock:
            self._buffer.clear()
            self._write_index = 0
            self._is_full = False
