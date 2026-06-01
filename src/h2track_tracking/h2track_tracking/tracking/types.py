"""Data types for Surge-Cast gas tracking algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import math


class TrackingState(Enum):
    """Tracking state machine states."""
    PATROL = auto()       # Normal patrol mode
    SURGE = auto()        # Moving upwind toward source
    CAST = auto()         # Lateral search when plume is lost
    SOURCE_FOUND = auto() # Source located


@dataclass(frozen=True)
class Pose2D:
    """2D pose (position + optional orientation)."""
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


@dataclass(frozen=True)
class TrackingAction:
    """Action returned by the tracking algorithm."""
    target: Pose2D
    state: TrackingState
    heading: float  # Direction to move (radians)
    step_size: float  # Distance to move
    use_particle_filter: bool  # Whether to use PF estimate


@dataclass(frozen=True)
class SurgeCastConfig:
    """Configuration for Surge-Cast algorithm.

    Thresholds should match the mission_manager's enter/exit/source thresholds.
    """
    # Plume detection thresholds (should match mission config)
    plume_found_threshold: float = 5.0  # Concentration to enter SURGE (enter_threshold)
    plume_lost_threshold: float = 2.0   # Concentration to enter CAST (exit_threshold)
    source_threshold: float = 20.0      # Concentration to confirm source

    # Movement parameters
    surge_step: float = 0.5             # Step size during SURGE (meters)
    cast_step: float = 0.3              # Step size during CAST (meters)
    cast_distance_limit: float = 3.0    # Max distance per CAST phase (meters)

    # Particle filter integration
    use_particle_filter: bool = True
    min_pf_confidence: float = 0.3      # Minimum PF confidence to use estimate

    # Wind parameters (m/s)
    wind_x: float = 0.4                 # Wind X component
    wind_y: float = 0.0                 # Wind Y component

    # History parameters
    history_size: int = 50              # Number of samples to keep
    plume_confirm_samples: int = 3      # Samples to confirm plume state

    # Source confirmation
    source_radius: float = 1.0          # Distance to confirm source (meters)
    source_hold_steps: int = 2          # Consecutive detections needed

    # Adaptive step size parameters
    adaptive_step: bool = True          # Enable adaptive step size
    min_step: float = 0.2               # Minimum step size (meters)
    max_step: float = 1.0               # Maximum step size (meters)
    concentration_threshold_high: float = 5.0  # High concentration threshold
    concentration_threshold_low: float = 1.0   # Low concentration threshold

    @property
    def upwind_direction(self) -> float:
        """Direction to move upwind (opposite to wind)."""
        wind_norm = math.hypot(self.wind_x, self.wind_y)
        if wind_norm < 1e-6:
            return 0.0
        return math.atan2(-self.wind_y, -self.wind_x)

    @property
    def wind_direction(self) -> float:
        """Current wind direction (where wind is blowing to)."""
        wind_norm = math.hypot(self.wind_x, self.wind_y)
        if wind_norm < 1e-6:
            return 0.0
        return math.atan2(self.wind_y, self.wind_x)

    @property
    def has_wind(self) -> bool:
        """Check if there's significant wind."""
        return math.hypot(self.wind_x, self.wind_y) > 0.1


@dataclass
class PlumeState:
    """Current plume detection state."""
    in_plume: bool = False
    confidence: float = 0.0
    average_concentration: float = 0.0
    trend: str = "stable"  # "increasing", "decreasing", "stable"
