"""Benchmark module."""

from .performance_benchmark import (
    BenchmarkResult,
    benchmark_surge_cast,
    benchmark_wind_estimator,
    benchmark_fusion,
    run_all_benchmarks,
)

__all__ = [
    "BenchmarkResult",
    "benchmark_surge_cast",
    "benchmark_wind_estimator",
    "benchmark_fusion",
    "run_all_benchmarks",
]
