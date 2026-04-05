"""Data types for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from typing import NamedTuple


@dataclass
class Particle:
    """Single particle representing a gas source position hypothesis."""

    position: np.ndarray  # shape: (2,) - [x, y]
    weight: float  # normalized weight [0, 1]


@dataclass(frozen=True)
class ParticleFilterConfig:
    """Configuration for particle filter."""

    num_particles: int = 500
    motion_sigma: float = 0.3  # motion noise std (meters)
    observation_sigma: float = 0.5  # observation noise std
    resample_threshold: float = 0.5  # effective particle ratio threshold
    plume_sigma: float = 2.0  # plume dispersion parameter
    source_strength: float = 1.0  # source strength


@dataclass
class SourceEstimate:
    """Gas source position estimate result."""

    position: tuple[float, float]
    confidence: float  # [0, 1]
    covariance: np.ndarray  # shape: (2, 2)
    candidate_sources: list[tuple[float, float, float]]  # [(x, y, weight), ...]
