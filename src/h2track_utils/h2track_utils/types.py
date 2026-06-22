"""Canonical shared types for the h2track system.

Pose2D is defined here as the single source of truth. Other packages
should import from h2track_utils.types rather than defining their own.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pose2D:
    """2D pose (position + orientation)."""
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0

    def distance_to(self, other: Pose2D) -> float:
        """Calculate distance to another pose."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_dict(self) -> dict[str, float]:
        """Convert pose to dictionary representation."""
        return {"x": self.x, "y": self.y, "yaw": self.yaw}

    @classmethod
    def from_dict(cls, data: dict) -> Pose2D:
        """Create Pose2D from dictionary."""
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            yaw=float(data.get("yaw", 0.0)),
        )
