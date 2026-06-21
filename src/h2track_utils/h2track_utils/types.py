"""Shared types for the h2track_utils package."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pose2D:
    """2D pose (position + optional orientation)."""
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0

    def distance_to(self, other: Pose2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)
