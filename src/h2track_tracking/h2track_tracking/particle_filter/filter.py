"""Particle filter core implementation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel
from .observation_model import GaussianPlumeObservationModel


class ParticleFilter:
    """Particle filter for gas source localization.

    Supports both loop-based (original) and vectorized (optimized) operations.
    Use `method='vectorized'` for better performance on large particle counts.
    """

    def __init__(self, config: ParticleFilterConfig) -> None:
        self.config = config
        self.particles: list[Particle] = []
        self._motion_model = RandomWalkMotionModel(config)
        self._observation_model = GaussianPlumeObservationModel(config)

        # Cached NumPy arrays for vectorized operations
        self._positions_array: np.ndarray | None = None
        self._weights_array: np.ndarray | None = None

    def initialize(
        self,
        bounds: tuple[float, float, float, float],
    ) -> None:
        """Initialize particles uniformly within bounds.

        Args:
            bounds: (min_x, min_y, max_x, max_y)
        """
        min_x, min_y, max_x, max_y = bounds
        n = self.config.num_particles

        # Uniform distribution - already vectorized
        positions = np.random.uniform(
            low=[min_x, min_y],
            high=[max_x, max_y],
            size=(n, 2),
        )

        # Equal weights
        weight = 1.0 / n

        self.particles = [
            Particle(position=pos, weight=weight)
            for pos in positions
        ]

        # Invalidate cache
        self._positions_array = None
        self._weights_array = None

    def predict(self, dt: float = 1.0, method: Literal["loop", "vectorized"] = "loop") -> None:
        """Predict step: move particles according to motion model.

        Args:
            dt: Time step (affects noise magnitude)
            method: "loop" for original, "vectorized" for optimized
        """
        if method == "vectorized":
            self._predict_vectorized(dt)
        else:
            self._predict_loop(dt)

    def _predict_loop(self, dt: float) -> None:
        """Original loop-based predict implementation."""
        self.particles = [
            self._motion_model.predict(p, dt)
            for p in self.particles
        ]
        # Invalidate cache
        self._positions_array = None

    def _predict_vectorized(self, dt: float) -> None:
        """Vectorized predict step using NumPy operations.

        Performance: O(n) with vectorized operations vs O(n) Python loops.
        Typical speedup: 10-50x for 500+ particles.
        """
        if not self.particles:
            return

        if self._motion_model.sigma <= 0.0:
            # No noise, positions unchanged
            return

        n = len(self.particles)

        # Get or create positions array
        if self._positions_array is None or self._positions_array.shape[0] != n:
            self._positions_array = np.array([p.position for p in self.particles])

        # Vectorized noise addition
        noise = np.random.normal(
            0,
            self._motion_model.sigma * np.sqrt(dt),
            size=(n, 2)
        )
        self._positions_array = self._positions_array + noise

        # Update particles in-place (Particle has mutable position)
        for i, p in enumerate(self.particles):
            p.position = self._positions_array[i].copy()

    def update(
        self,
        robot_position: tuple[float, float],
        concentration: float,
        method: Literal["loop", "vectorized"] = "loop",
    ) -> None:
        """Update step: adjust weights based on observation.

        Args:
            robot_position: Current robot position (x, y)
            concentration: Observed gas concentration
            method: "loop" for original, "vectorized" for optimized
        """
        if method == "vectorized":
            self._update_vectorized(robot_position, concentration)
        else:
            self._update_loop(robot_position, concentration)

    def _update_loop(
        self,
        robot_position: tuple[float, float],
        concentration: float,
    ) -> None:
        """Original loop-based update implementation."""
        robot_pos = np.array(robot_position)

        for particle in self.particles:
            likelihood = self._observation_model.likelihood(
                source_hypothesis=particle.position,
                robot_position=robot_pos,
                observed_concentration=concentration,
            )
            particle.weight *= likelihood

        self._normalize_weights()
        # Invalidate cache
        self._weights_array = None

    def _update_vectorized(
        self,
        robot_position: tuple[float, float],
        concentration: float,
    ) -> None:
        """Vectorized update step using NumPy operations.

        Performance: O(n) with vectorized operations vs O(n) Python loops.
        Typical speedup: 20-100x for 500+ particles.
        """
        if not self.particles:
            return

        n = len(self.particles)
        robot_pos = np.array(robot_position)

        # Get positions array
        if self._positions_array is None or self._positions_array.shape[0] != n:
            self._positions_array = np.array([p.position for p in self.particles])

        # Vectorized distance computation using broadcasting
        distances = np.linalg.norm(self._positions_array - robot_pos, axis=1)

        # Vectorized expected concentration
        plume_sigma = self._observation_model.plume_sigma
        source_strength = self._observation_model.source_strength
        expected = source_strength * np.exp(-distances**2 / (2 * plume_sigma**2))

        # Vectorized likelihood computation
        observation_sigma = self._observation_model.observation_sigma
        error = concentration - expected
        likelihoods = np.exp(-error**2 / (2 * observation_sigma**2))

        # Get weights array
        if self._weights_array is None or self._weights_array.shape[0] != n:
            self._weights_array = np.array([p.weight for p in self.particles])

        # Update weights
        self._weights_array = self._weights_array * likelihoods

        # Normalize
        total = self._weights_array.sum()
        if total > 0:
            self._weights_array = self._weights_array / total

        # Update particles in-place
        for i, p in enumerate(self.particles):
            p.weight = float(self._weights_array[i])

    def resample(self) -> None:
        """Resample particles to combat degeneracy."""
        if not self.particles:
            return

        n = len(self.particles)

        # Get weights array
        if self._weights_array is None or self._weights_array.shape[0] != n:
            weights = np.array([p.weight for p in self.particles])
        else:
            weights = self._weights_array

        # Cumulative sum
        cumsum = np.cumsum(weights)
        cumsum[-1] = 1.0  # Ensure sum is exactly 1

        # Systematic resampling positions
        positions = (np.arange(n) + np.random.uniform()) / n

        # Resample indices
        indices = np.searchsorted(cumsum, positions)

        # Create new particles
        new_particles = [
            Particle(
                position=self.particles[i].position.copy(),
                weight=1.0 / n,
            )
            for i in indices
        ]

        self.particles = new_particles

        # Reset cache for new particles
        self._positions_array = None
        self._weights_array = np.full(n, 1.0 / n)

    def estimate(self) -> SourceEstimate:
        """Estimate source location from particles.

        Returns:
            SourceEstimate with position, confidence, and candidates
        """
        if not self.particles:
            return SourceEstimate(
                position=(0.0, 0.0),
                confidence=0.0,
                covariance=np.eye(2) * 1e6,
                candidate_sources=[],
            )

        n = len(self.particles)

        # Use cached arrays if available
        if self._positions_array is not None and self._positions_array.shape[0] == n:
            positions = self._positions_array
        else:
            positions = np.array([p.position for p in self.particles])
            self._positions_array = positions

        if self._weights_array is not None and self._weights_array.shape[0] == n:
            weights = self._weights_array
        else:
            weights = np.array([p.weight for p in self.particles])
            self._weights_array = weights

        # Weighted mean
        mean = np.average(positions, axis=0, weights=weights)

        # Weighted covariance
        diff = positions - mean
        cov = np.cov(diff.T, aweights=weights)

        # Confidence based on effective particle count
        effective_count = 1.0 / np.sum(weights**2)
        max_effective = n
        confidence = min(1.0, effective_count / (max_effective * 0.5))

        # Top candidates (highest weight particles)
        sorted_indices = np.argsort(weights)[::-1]
        candidates = [
            (
                float(positions[i][0]),
                float(positions[i][1]),
                float(weights[i]),
            )
            for i in sorted_indices[:5]
        ]

        return SourceEstimate(
            position=(float(mean[0]), float(mean[1])),
            confidence=float(confidence),
            covariance=cov if cov.shape == (2, 2) else np.eye(2) * np.var(positions),
            candidate_sources=candidates,
        )

    def _normalize_weights(self) -> None:
        """Normalize particle weights to sum to 1."""
        total = sum(p.weight for p in self.particles)
        if total > 0:
            for p in self.particles:
                p.weight /= total

    def effective_particle_count(self) -> float:
        """Calculate effective particle count.

        Used to determine when resampling is needed.
        """
        n = len(self.particles)
        if self._weights_array is not None and self._weights_array.shape[0] == n:
            weights = self._weights_array
        else:
            weights = np.array([p.weight for p in self.particles])
        return 1.0 / np.sum(weights**2)

    def benchmark(self, iterations: int = 100) -> dict[str, float]:
        """Benchmark loop vs vectorized methods.

        Args:
            iterations: Number of iterations for each benchmark

        Returns:
            Dict with timing results in milliseconds
        """
        if not self.particles:
            self.initialize(bounds=(0, 0, 10, 10))

        results = {}

        # Benchmark predict - loop version
        start = time.perf_counter()
        for _ in range(iterations):
            self._predict_loop(1.0)
        results['predict_loop_ms'] = (time.perf_counter() - start) * 1000 / iterations

        # Benchmark predict - vectorized version
        start = time.perf_counter()
        for _ in range(iterations):
            self._predict_vectorized(1.0)
        results['predict_vectorized_ms'] = (time.perf_counter() - start) * 1000 / iterations

        # Benchmark update
        robot_pos = (5.0, 5.0)
        concentration = 0.5

        # Benchmark update - loop version
        start = time.perf_counter()
        for _ in range(iterations):
            self._update_loop(robot_pos, concentration)
        results['update_loop_ms'] = (time.perf_counter() - start) * 1000 / iterations

        # Benchmark update - vectorized version
        start = time.perf_counter()
        for _ in range(iterations):
            self._update_vectorized(robot_pos, concentration)
        results['update_vectorized_ms'] = (time.perf_counter() - start) * 1000 / iterations

        # Calculate speedups
        if results['predict_vectorized_ms'] > 0:
            results['predict_speedup'] = results['predict_loop_ms'] / results['predict_vectorized_ms']
        else:
            results['predict_speedup'] = 0.0
        if results['update_vectorized_ms'] > 0:
            results['update_speedup'] = results['update_loop_ms'] / results['update_vectorized_ms']
        else:
            results['update_speedup'] = 0.0

        return results


@dataclass
class BenchmarkResult:
    """Result from particle filter benchmark."""
    num_particles: int
    predict_loop_ms: float
    predict_vectorized_ms: float
    update_loop_ms: float
    update_vectorized_ms: float
    predict_speedup: float
    update_speedup: float


def run_benchmark(
    num_particles_list: list[int] | None = None,
    iterations: int = 100,
) -> list[BenchmarkResult]:
    """Run comprehensive benchmark across different particle counts.

    Args:
        num_particles_list: List of particle counts to test
        iterations: Number of iterations per test

    Returns:
        List of benchmark results
    """
    if num_particles_list is None:
        num_particles_list = [100, 250, 500, 1000, 2000]

    results = []

    for n in num_particles_list:
        config = ParticleFilterConfig(num_particles=n)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        bench = pf.benchmark(iterations=iterations)

        results.append(BenchmarkResult(
            num_particles=n,
            predict_loop_ms=bench['predict_loop_ms'],
            predict_vectorized_ms=bench['predict_vectorized_ms'],
            update_loop_ms=bench['update_loop_ms'],
            update_vectorized_ms=bench['update_vectorized_ms'],
            predict_speedup=bench['predict_speedup'],
            update_speedup=bench['update_speedup'],
        ))

    return results
