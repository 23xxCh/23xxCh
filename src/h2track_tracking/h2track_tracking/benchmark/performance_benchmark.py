"""Performance benchmark for gas source localization algorithms.

Benchmarks:
- Surge-Cast execution time
- Particle filter update time
- Wind estimation time
- Fusion computation time
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Tuple
import statistics

logger = logging.getLogger(__name__)

from ..tracking import (
    SurgeCastTracker,
    SurgeCastConfig,
    WindEstimator,
    WindEstimatorConfig,
    TrackingFusion,
    FusionConfig,
)
from ..tracking.types import Pose2D


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float


def benchmark_surge_cast(iterations: int = 1000) -> BenchmarkResult:
    """Benchmark Surge-Cast algorithm."""
    config = SurgeCastConfig()
    tracker = SurgeCastTracker(config)
    
    times = []
    for i in range(iterations):
        start = time.perf_counter()
        tracker.update(
            concentration=2.0 + (i % 10) * 0.5,
            robot_pose=Pose2D(float(i % 100) * 0.1, float(i % 100) * 0.1),
            robot_yaw=0.0,
            wind=(0.4, 0.0),
        )
        times.append((time.perf_counter() - start) * 1000)
    
    return BenchmarkResult(
        name="Surge-Cast",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        std_dev_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
    )


def benchmark_wind_estimator(iterations: int = 1000) -> BenchmarkResult:
    """Benchmark wind estimation."""
    config = WindEstimatorConfig(min_samples_for_estimate=10)
    estimator = WindEstimator(config)
    
    # Pre-populate with enough samples
    for i in range(20):
        estimator.update(Pose2D(float(i), 0.0), float(i % 10), float(i))
    
    times = []
    for i in range(iterations):
        start = time.perf_counter()
        estimator.update(Pose2D(float(i), float(i)), float(i % 10), float(i))
        times.append((time.perf_counter() - start) * 1000)
    
    return BenchmarkResult(
        name="Wind Estimator",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        std_dev_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
    )


def benchmark_fusion(iterations: int = 1000) -> BenchmarkResult:
    """Benchmark tracking fusion."""
    config = FusionConfig()
    fusion = TrackingFusion(config)
    
    from ..tracking.types import TrackingAction, TrackingState
    
    surge_action = TrackingAction(
        target=Pose2D(1.0, 1.0),
        state=TrackingState.SURGE,
        heading=0.0,
        step_size=0.5,
        use_particle_filter=False,
    )
    
    times = []
    for i in range(iterations):
        start = time.perf_counter()
        fusion.compute_fused_action(
            surge_action=surge_action,
            pf_position=Pose2D(3.0, 3.0),
            pf_confidence=0.8,
            concentration=5.0,
            robot_pose=Pose2D(0.0, 0.0),
        )
        times.append((time.perf_counter() - start) * 1000)
    
    return BenchmarkResult(
        name="Tracking Fusion",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        std_dev_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
    )


def run_all_benchmarks(iterations: int = 1000) -> List[BenchmarkResult]:
    """Run all benchmarks and return results."""
    results = []
    
    logger.info("Running benchmarks...")
    logger.info("%-20s %-12s %-12s %-12s %-12s", "Algorithm", "Avg (ms)", "Min (ms)", "Max (ms)", "Std (ms)")
    logger.info("-" * 68)

    for benchmark_fn in [benchmark_surge_cast, benchmark_wind_estimator, benchmark_fusion]:
        result = benchmark_fn(iterations)
        results.append(result)
        logger.info("%-20s %-12.4f %-12.4f %-12.4f %-12.4f", result.name, result.avg_time_ms, result.min_time_ms, result.max_time_ms, result.std_dev_ms)
    
    return results


if __name__ == "__main__":
    run_all_benchmarks(1000)
