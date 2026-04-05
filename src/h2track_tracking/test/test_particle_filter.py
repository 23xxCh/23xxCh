"""Tests for particle filter core."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import ParticleFilterConfig
from h2track_tracking.particle_filter.filter import ParticleFilter


class TestParticleFilter:
    def test_initialization(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(-5, -5, 5, 5))

        assert len(pf.particles) == 100
        assert all(0 <= p.weight <= 1 for p in pf.particles)

    def test_weight_normalization(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(-5, -5, 5, 5))

        total_weight = sum(p.weight for p in pf.particles)
        assert total_weight == pytest.approx(1.0, rel=0.01)

    def test_particles_within_bounds(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        for p in pf.particles:
            assert 0 <= p.position[0] <= 10
            assert 0 <= p.position[1] <= 10

    def test_predict_moves_particles(self):
        config = ParticleFilterConfig(num_particles=100, motion_sigma=0.5)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        old_positions = [p.position.copy() for p in pf.particles]
        pf.predict(dt=1.0)

        # 至少有一些粒子移动了
        moved = sum(
            1 for old, p in zip(old_positions, pf.particles)
            if not np.allclose(old, p.position)
        )
        assert moved > 0

    def test_update_changes_weights(self):
        config = ParticleFilterConfig(num_particles=100, observation_sigma=0.5)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        old_weights = [p.weight for p in pf.particles]
        pf.update(robot_position=(5.0, 5.0), concentration=0.5)

        # 权重应该改变
        new_weights = [p.weight for p in pf.particles]
        assert old_weights != new_weights

    def test_resample_maintains_particle_count(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        # 人为设置权重差异
        for i, p in enumerate(pf.particles):
            p.weight = 1.0 if i == 0 else 0.001
        pf._normalize_weights()

        pf.resample()
        assert len(pf.particles) == 100

    def test_estimate_returns_result(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        estimate = pf.estimate()

        assert estimate.position is not None
        assert 0 <= estimate.confidence <= 1
        assert estimate.covariance.shape == (2, 2)

    def test_convergence_to_source(self):
        """Test that filter converges to true source location."""
        config = ParticleFilterConfig(
            num_particles=500,
            plume_sigma=2.0,
            observation_sigma=0.3,
        )
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        true_source = np.array([5.0, 5.0])

        # Simulate observations near the source
        np.random.seed(42)
        for _ in range(50):
            # Robot moves randomly
            robot_pos = np.random.uniform(0, 10, 2)
            distance = np.linalg.norm(robot_pos - true_source)
            concentration = np.exp(-distance**2 / (2 * config.plume_sigma**2))
            concentration += np.random.normal(0, 0.05)  # noise
            concentration = max(0, concentration)

            pf.update(tuple(robot_pos), concentration)
            pf.predict(dt=0.1)

        estimate = pf.estimate()
        error = np.linalg.norm(np.array(estimate.position) - true_source)

        # Should converge within 2 meters
        assert error < 2.0
