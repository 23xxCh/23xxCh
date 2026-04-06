"""Observation model for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .types import ParticleFilterConfig


@dataclass
class GaussianPlumeObservationModel:
    """Gaussian plume observation model for gas concentration."""

    config: ParticleFilterConfig

    @property
    def plume_sigma(self) -> float:
        return self.config.plume_sigma

    @property
    def source_strength(self) -> float:
        return self.config.source_strength

    @property
    def observation_sigma(self) -> float:
        return self.config.observation_sigma

    def expected_concentration(
        self,
        source_pos: np.ndarray,
        robot_pos: np.ndarray,
    ) -> float:
        """Calculate expected concentration at robot position.

        Uses Gaussian plume model: C = Q * exp(-d² / (2 * σ²))

        Args:
            source_pos: Hypothesized source position [x, y]
            robot_pos: Robot position [x, y]

        Returns:
            Expected concentration at robot position
        """
        distance = np.linalg.norm(robot_pos - source_pos)
        if distance < 1e-6:
            return self.source_strength

        return self.source_strength * np.exp(
            -distance**2 / (2 * self.plume_sigma**2)
        )

    def likelihood(
        self,
        source_hypothesis: np.ndarray,
        robot_position: np.ndarray,
        observed_concentration: float,
    ) -> float:
        """Calculate observation likelihood.

        Args:
            source_hypothesis: Hypothesized source position [x, y]
            robot_position: Current robot position [x, y]
            observed_concentration: Measured concentration

        Returns:
            Likelihood value [0, 1]
        """
        expected = self.expected_concentration(source_hypothesis, robot_position)
        error = observed_concentration - expected

        # Gaussian likelihood
        return np.exp(-error**2 / (2 * self.observation_sigma**2))
