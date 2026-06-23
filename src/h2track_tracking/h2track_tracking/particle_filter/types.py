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
    """Configuration for particle filter.

    decay_rate, wind_x, wind_y, plume_sigma, gas_type must match
    GasFieldParams so the observation model produces concentration
    profiles compatible with the gas simulation.
    """

    num_particles: int = 500
    motion_sigma: float = 0.3  # motion noise std (meters)
    observation_sigma: float = 0.5  # observation noise std (relative scale)
    resample_threshold: float = 0.5  # effective particle ratio threshold
    plume_sigma: float = 1.2  # lateral plume dispersion — must match gas_field.plume_stddev
    source_strength: float = 120.0  # source strength — must match gas_field.source_strength
    decay_rate: float = 0.55  # exponential decay rate — must match gas_field.decay_rate
    wind_x: float = 0.0  # wind x component — must match gas_field.wind_x
    wind_y: float = 0.0  # wind y component — must match gas_field.wind_y
    gas_type: str = "H2"  # gas type — used for buoyancy-corrected upwind penalty


@dataclass
class SourceEstimate:
    """Gas source position estimate result."""

    position: tuple[float, float]
    confidence: float  # [0, 1]
    covariance: np.ndarray  # shape: (2, 2)
    candidate_sources: list[tuple[float, float, float]]  # [(x, y, weight), ...]
