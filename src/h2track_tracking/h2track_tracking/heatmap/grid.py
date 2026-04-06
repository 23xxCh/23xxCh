"""3D concentration grid for heatmap visualization."""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import numpy as np
import time


@dataclass(frozen=True)
class HeatmapConfig:
    """Configuration for concentration heatmap."""

    resolution: float = 0.5  # meters per cell
    decay_rate: float = 0.95  # time decay factor
    publish_rate: float = 2.0  # Hz
    history_length: int = 1000  # number of snapshots to keep


@dataclass
class ConcentrationGrid:
    """3D grid for storing gas concentration values."""

    config: HeatmapConfig
    dimensions: tuple[int, int, int]  # (nx, ny, nz)
    origin: tuple[float, float, float]  # (x0, y0, z0)
    data: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 1), dtype=np.float32))
    timestamps: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 1), dtype=np.float64))

    def __post_init__(self) -> None:
        nx, ny, nz = self.dimensions
        if self.data.shape != (nx, ny, nz):
            object.__setattr__(self, 'data', np.zeros((nx, ny, nz), dtype=np.float32))
        if self.timestamps.shape != (nx, ny, nz):
            object.__setattr__(self, 'timestamps', np.zeros((nx, ny, nz), dtype=np.float64))

    @property
    def resolution(self) -> float:
        return self.config.resolution

    def world_to_grid(
        self,
        position: tuple[float, float, float],
    ) -> tuple[int, int, int]:
        """Convert world coordinates to grid indices."""
        x, y, z = position
        x0, y0, z0 = self.origin
        res = self.resolution

        ix = int((x - x0) / res)
        iy = int((y - y0) / res)
        iz = int((z - z0) / res)

        return (ix, iy, iz)

    def grid_to_world(
        self,
        ix: int,
        iy: int,
        iz: int,
    ) -> tuple[float, float, float]:
        """Convert grid indices to world coordinates.

        Returns the corner position of the cell (origin-aligned).
        """
        x0, y0, z0 = self.origin
        res = self.resolution

        x = x0 + ix * res
        y = y0 + iy * res
        z = z0 + iz * res

        return (x, y, z)

    def update(
        self,
        position: tuple[float, float, float],
        concentration: float,
        timestamp: float,
    ) -> None:
        """Update concentration at a position."""
        ix, iy, iz = self.world_to_grid(position)

        # Check bounds
        nx, ny, nz = self.dimensions
        if not (0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz):
            return

        self.data[ix, iy, iz] = concentration
        self.timestamps[ix, iy, iz] = timestamp

    def decay(self) -> None:
        """Apply time decay to all values."""
        self.data *= self.config.decay_rate

    def to_dict(self) -> dict:
        """Serialize grid to dictionary for JSON/WebSocket."""
        # Encode data as base64 for efficient transfer
        data_bytes = self.data.tobytes()
        data_b64 = base64.b64encode(data_bytes).decode('ascii')

        return {
            "resolution": self.resolution,
            "dimensions": self.dimensions,
            "origin": self.origin,
            "data": data_b64,
            "dtype": "float32",
        }

    def clear(self) -> None:
        """Reset all concentration values to zero."""
        self.data.fill(0.0)
        self.timestamps.fill(0.0)
