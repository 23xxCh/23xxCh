"""Tests for particle filter motion model."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import Particle, ParticleFilterConfig
from h2track_tracking.particle_filter.motion_model import RandomWalkMotionModel


class TestRandomWalkMotionModel:
    def test_motion_model_creation(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        assert model.sigma == 0.5

    def test_predict_moves_particle(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([0.0, 0.0]), weight=1.0)

        np.random.seed(42)
        new_particle = model.predict(particle, dt=1.0)

        # Particle should have moved
        assert not np.allclose(new_particle.position, particle.position)

    def test_predict_preserves_weight(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([0.0, 0.0]), weight=0.5)

        new_particle = model.predict(particle, dt=1.0)

        assert new_particle.weight == 0.5

    def test_predict_with_zero_sigma(self):
        config = ParticleFilterConfig(motion_sigma=0.0)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([1.0, 2.0]), weight=1.0)

        new_particle = model.predict(particle, dt=1.0)

        # With sigma=0, particle should not move
        assert np.allclose(new_particle.position, particle.position)

    def test_predict_multiple_particles(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particles = [
            Particle(position=np.array([0.0, 0.0]), weight=0.5),
            Particle(position=np.array([1.0, 1.0]), weight=0.5),
        ]

        new_particles = [model.predict(p, dt=1.0) for p in particles]

        assert len(new_particles) == 2
        assert new_particles[0].weight == 0.5
        assert new_particles[1].weight == 0.5
