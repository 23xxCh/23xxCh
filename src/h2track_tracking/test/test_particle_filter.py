"""Tests for particle filter core."""

import math
import random

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
        """Test that filter converges to true source location.

        Uses exponential-decay plume model matching GasFieldModel:
            C = S * exp(-decay_rate * d) * plume_bias
        """
        config = ParticleFilterConfig(
            num_particles=500,
            plume_sigma=2.0,
            observation_sigma=0.3,
            source_strength=120.0,
            decay_rate=0.55,
            wind_x=0.4,
            wind_y=0.0,
        )
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        true_source = np.array([5.0, 5.0])

        # Simulate observations using the same model as the PF observation model
        import math
        np.random.seed(42)
        for _ in range(50):
            robot_pos = np.random.uniform(0, 10, 2)
            dx = robot_pos[0] - true_source[0]
            dy = robot_pos[1] - true_source[1]
            distance = math.hypot(dx, dy)

            # Exponential decay + plume bias (matching observation model)
            baseline = config.source_strength * math.exp(-config.decay_rate * distance)
            wind_norm = math.hypot(config.wind_x, config.wind_y)
            plume_bias = 1.0
            if wind_norm > 1e-6:
                wind_dir = (config.wind_x / wind_norm, config.wind_y / wind_norm)
                projection = dx * wind_dir[0] + dy * wind_dir[1]
                lateral_sq = max(0.0, distance**2 - projection**2)
                plume_bias = math.exp(-lateral_sq / (2.0 * config.plume_sigma**2))
                if projection < 0.0:
                    plume_bias *= 0.35

            concentration = baseline * plume_bias
            concentration += np.random.normal(0, 0.5)
            concentration = max(0, concentration)

            pf.update(tuple(robot_pos), concentration)
            pf.predict(dt=0.1)

        estimate = pf.estimate()
        error = np.linalg.norm(np.array(estimate.position) - true_source)

        # Should converge within 2 meters
        assert error < 2.0


class TestPFGasModelIntegration:
    """Integration tests: PF observation model vs GasFieldModel output.

    Verifies that the PF observation model can correctly weight particles
    when fed real GasFieldModel concentration values — the core fix for
    the weight-collapse bug.
    """

    def test_observation_model_matches_gas_model(self):
        """PF expected_concentration should match GasFieldModel output."""
        from h2track_tracking.particle_filter.observation_model import GaussianPlumeObservationModel

        config = ParticleFilterConfig(
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
        )
        model = GaussianPlumeObservationModel(config)

        # Source at origin, robot at various positions
        source_pos = np.array([0.0, 0.0])

        # At source: should return source_strength
        assert model.expected_concentration(source_pos, source_pos) == pytest.approx(120.0)

        # Downwind (positive x): should have high concentration
        robot_downwind = np.array([2.0, 0.0])
        c_downwind = model.expected_concentration(source_pos, robot_downwind)
        assert c_downwind > 0
        # At d=2, C = 120 * exp(-0.55*2) * 1.0 ≈ 39.9
        assert c_downwind == pytest.approx(120.0 * math.exp(-0.55 * 2.0), rel=0.01)

        # Upwind (negative x): buoyancy-corrected penalty for H2 (light gas)
        # H2 density_ratio=0.069 → upwind_factor = 0.35/(0.069+0.3) ≈ 0.95
        # So upwind concentration is ~95% of downwind — light gas spreads widely
        robot_upwind = np.array([-2.0, 0.0])
        c_upwind = model.expected_concentration(source_pos, robot_upwind)
        assert c_upwind > c_downwind * 0.5  # H2 spreads far upwind

        # Crosswind: should have lateral Gaussian suppression
        robot_cross = np.array([0.0, 3.0])
        c_cross = model.expected_concentration(source_pos, robot_cross)
        # lateral=3, plume_bias = exp(-9/(2*1.44)) ≈ exp(-3.125) ≈ 0.044
        assert c_cross < c_downwind * 0.1

    def test_no_weight_collapse_with_gas_model_concentrations(self):
        """PF should NOT collapse all weights to near-zero when fed
        real GasFieldModel concentrations.

        This is the core regression test for the weight-collapse bug:
        the old Gaussian-blob model (source_strength=1.0) would produce
        expected_concentration ≈ 0.0 for all particles when real
        concentrations were 50-120, causing all likelihoods to vanish.
        """
        from h2track_gas_sim.gas_model import GasFieldModel, GasFieldParams
        from h2track_utils.types import Pose2D

        # Create gas field matching PF config
        gf_params = GasFieldParams(
            source_x=5.0, source_y=5.0,
            source_strength=120.0, decay_rate=0.55,
            plume_stddev=1.2, wind_x=0.4, wind_y=0.0,
            noise_stddev=0.0, min_concentration=0.0,
            gas_type="H2",
        )
        gas_model = GasFieldModel(gf_params, rng=random.Random(42))

        pf_config = ParticleFilterConfig(
            num_particles=200,
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
            observation_sigma=0.5,
        )
        pf = ParticleFilter(pf_config)
        pf.initialize(bounds=(0, 0, 10, 10))

        # Simulate robot moving through the gas field
        np.random.seed(42)
        effective_counts = []
        for _ in range(20):
            robot_x = np.random.uniform(2, 8)
            robot_y = np.random.uniform(2, 8)
            pose = Pose2D(robot_x, robot_y)
            concentration = gas_model.concentration_at(pose)

            pf.update((robot_x, robot_y), concentration)
            pf.predict(dt=0.1)

            effective = pf.effective_particle_count()
            effective_counts.append(effective)

            # Resample when needed (same as particle_filter_node)
            if effective < pf.config.resample_threshold * len(pf.particles):
                pf.resample()

        # Average effective count should be healthy (not collapsed to 1)
        avg_effective = sum(effective_counts) / len(effective_counts)
        assert avg_effective > 10.0, (
            f"Weight collapse detected: avg_effective_count={avg_effective:.1f} "
            f"(should be > 10.0)"
        )

    def test_vectorized_matches_loop(self):
        """Vectorized and loop update should produce same weights."""
        config = ParticleFilterConfig(
            num_particles=100,
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
            observation_sigma=0.5,
        )

        pf_loop = ParticleFilter(config)
        pf_loop.initialize(bounds=(0, 0, 10, 10))

        pf_vec = ParticleFilter(config)
        pf_vec.initialize(bounds=(0, 0, 10, 10))
        # Copy particle positions
        for i, p in enumerate(pf_loop.particles):
            pf_vec.particles[i].position = p.position.copy()

        # Update with same observation
        pf_loop.update(robot_position=(5.0, 5.0), concentration=30.0, method="loop")
        pf_vec.update(robot_position=(5.0, 5.0), concentration=30.0, method="vectorized")

        # Weights should be close
        for p_loop, p_vec in zip(pf_loop.particles, pf_vec.particles):
            assert p_loop.weight == pytest.approx(p_vec.weight, rel=0.01)


class TestPFRuntimeWindUpdate:
    """Tests for runtime wind updates via set_wind()."""

    def test_set_wind_updates_observation_model(self):
        """set_wind() should update wind components used by the observation model."""
        config = ParticleFilterConfig(
            num_particles=50,
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
        )
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        # Initial wind from config
        assert pf._observation_model.wind_x == pytest.approx(0.4)
        assert pf._observation_model.wind_y == pytest.approx(0.0)

        # Runtime update
        pf.set_wind(-0.8, 0.6)
        assert pf._observation_model.wind_x == pytest.approx(-0.8)
        assert pf._observation_model.wind_y == pytest.approx(0.6)

    def test_set_wind_affects_expected_concentration(self):
        """Changing wind direction should change expected concentrations."""
        from h2track_tracking.particle_filter.observation_model import GaussianPlumeObservationModel

        config = ParticleFilterConfig(
            source_strength=120.0,
            decay_rate=0.55,
            plume_sigma=1.2,
            wind_x=0.4,
            wind_y=0.0,
        )
        model = GaussianPlumeObservationModel(config)

        source = np.array([0.0, 0.0])
        robot = np.array([2.0, 0.0])  # downwind of source initially

        c_before = model.expected_concentration(source, robot)

        # Flip wind so robot is now upwind
        model.set_wind(-0.4, 0.0)
        c_after = model.expected_concentration(source, robot)

        # Concentration should change when wind direction flips
        assert c_after != pytest.approx(c_before, rel=0.01)
