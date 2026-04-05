"""Motion model for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .types import Particle, ParticleFilterConfig


@dataclass
class RandomWalkMotionModel:
    """Random walk motion model for particles."""

    config: ParticleFilterConfig

    @property
    def sigma(self) -> float:
        return self.config.motion_sigma

    def predict(self, particle: Particle, dt: float = 1.0) -> Particle:
        """Predict particle state using random walk.

        Args:
            particle: Current particle state
            dt: Time step (affects noise magnitude)

        Returns:
            New particle with updated position
        """
        if self.sigma <= 0.0:
            return Particle(
                position=particle.position.copy(),
                weight=particle.weight,
            )

        noise = np.random.normal(0, self.sigma * np.sqrt(dt), size=2)
        new_position = particle.position + noise

        return Particle(
            position=new_position,
            weight=particle.weight,
        )
