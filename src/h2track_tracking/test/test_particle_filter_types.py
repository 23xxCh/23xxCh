# src/h2track_tracking/test/test_particle_filter_types.py
"""Tests for particle filter type definitions."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import (
    Particle,
    ParticleFilterConfig,
    SourceEstimate,
)


class TestParticle:
    def test_particle_creation(self):
        particle = Particle(position=np.array([1.0, 2.0]), weight=0.5)
        assert particle.position.shape == (2,)
        assert particle.weight == 0.5

    def test_particle_weight_normalization(self):
        particle = Particle(position=np.array([0.0, 0.0]), weight=1.5)
        assert particle.weight == 1.5  # 不自动归一化

    def test_particle_copy(self):
        p1 = Particle(position=np.array([1.0, 2.0]), weight=0.5)
        p2 = Particle(position=p1.position.copy(), weight=p1.weight)
        p2.position[0] = 5.0
        assert p1.position[0] == 1.0


class TestParticleFilterConfig:
    def test_default_config(self):
        config = ParticleFilterConfig()
        assert config.num_particles == 500
        assert config.motion_sigma == 0.3
        assert config.observation_sigma == 0.5

    def test_custom_config(self):
        config = ParticleFilterConfig(
            num_particles=1000,
            motion_sigma=0.5,
            observation_sigma=0.3,
        )
        assert config.num_particles == 1000

    def test_frozen_config(self):
        config = ParticleFilterConfig()
        with pytest.raises(Exception):
            config.num_particles = 2000


class TestSourceEstimate:
    def test_source_estimate_creation(self):
        estimate = SourceEstimate(
            position=(3.6, -3.04),
            confidence=0.85,
            covariance=np.array([[0.1, 0.0], [0.0, 0.1]]),
            candidate_sources=[(3.5, -3.0, 0.3), (3.7, -3.1, 0.25)],
        )
        assert estimate.position == (3.6, -3.04)
        assert estimate.confidence == 0.85

    def test_source_estimate_covariance_shape(self):
        estimate = SourceEstimate(
            position=(0.0, 0.0),
            confidence=0.5,
            covariance=np.eye(2),
            candidate_sources=[],
        )
        assert estimate.covariance.shape == (2, 2)
