"""Particle filter core implementation."""

from __future__ import annotations

import numpy as np

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel
from .observation_model import GaussianPlumeObservationModel


class ParticleFilter:
    """Particle filter for gas source localization."""

    def __init__(self, config: ParticleFilterConfig) -> None:
        self.config = config
        self.particles: list[Particle] = []
        self._motion_model = RandomWalkMotionModel(config)
        self._observation_model = GaussianPlumeObservationModel(config)

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

        # Uniform distribution
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

    def predict(self, dt: float = 1.0) -> None:
        """Predict step: move particles according to motion model."""
        self.particles = [
            self._motion_model.predict(p, dt)
            for p in self.particles
        ]

    def update(
        self,
        robot_position: tuple[float, float],
        concentration: float,
    ) -> None:
        """Update step: adjust weights based on observation.

        Args:
            robot_position: Current robot position (x, y)
            concentration: Observed gas concentration
        """
        robot_pos = np.array(robot_position)

        for particle in self.particles:
            likelihood = self._observation_model.likelihood(
                source_hypothesis=particle.position,
                robot_position=robot_pos,
                observed_concentration=concentration,
            )
            particle.weight *= likelihood

        self._normalize_weights()

    def resample(self) -> None:
        """Resample particles to combat degeneracy."""
        if not self.particles:
            return

        # Systematic resampling
        weights = np.array([p.weight for p in self.particles])
        n = len(self.particles)

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

        # Weighted mean
        positions = np.array([p.position for p in self.particles])
        weights = np.array([p.weight for p in self.particles])

        mean = np.average(positions, axis=0, weights=weights)

        # Weighted covariance
        diff = positions - mean
        cov = np.cov(diff.T, aweights=weights)

        # Confidence based on effective particle count
        effective_count = 1.0 / np.sum(weights**2)
        max_effective = len(self.particles)
        confidence = min(1.0, effective_count / (max_effective * 0.5))

        # Top candidates (highest weight particles)
        sorted_indices = np.argsort(weights)[::-1]
        candidates = [
            (
                float(self.particles[i].position[0]),
                float(self.particles[i].position[1]),
                float(self.particles[i].weight),
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
        weights = np.array([p.weight for p in self.particles])
        return 1.0 / np.sum(weights**2)
