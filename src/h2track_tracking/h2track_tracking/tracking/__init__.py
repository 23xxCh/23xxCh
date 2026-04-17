"""Surge-Cast gas tracking algorithm module."""

from .types import (
    Pose2D,
    PlumeState,
    SurgeCastConfig,
    TrackingAction,
    TrackingState,
)
from .plume_detector import PlumeDetector
from .surge_cast import SurgeCastTracker
from .pf_integrator import ParticleFilterIntegrator
from .costmap_checker import CostmapChecker, CostmapConfig
from .wind_estimator import WindEstimator, WindEstimatorConfig, WindEstimate
from .fusion import TrackingFusion, FusionConfig, FusionState
from .baseline_algorithms import (
    GradientSearch,
    GradientSearchConfig,
    RandomWalk,
    RandomWalkConfig,
    SpiralSearch,
    SpiralSearchConfig,
)

__all__ = [
    "Pose2D",
    "PlumeState",
    "SurgeCastConfig",
    "TrackingAction",
    "TrackingState",
    "PlumeDetector",
    "SurgeCastTracker",
    "ParticleFilterIntegrator",
    "CostmapChecker",
    "CostmapConfig",
    "WindEstimator",
    "WindEstimatorConfig",
    "WindEstimate",
    "TrackingFusion",
    "FusionConfig",
    "FusionState",
    "GradientSearch",
    "GradientSearchConfig",
    "RandomWalk",
    "RandomWalkConfig",
    "SpiralSearch",
    "SpiralSearchConfig",
]
