"""Tests for particle filter observation model."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import ParticleFilterConfig
from h2track_tracking.particle_filter.observation_model import GaussianPlumeObservationModel


class TestGaussianPlumeObservationModel:
    def test_model_creation(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)
        assert model.plume_sigma == 2.0
        assert model.source_strength == 1.0

    def test_expected_concentration_at_source(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 机器人在源位置时浓度最高
        concentration = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([0.0, 0.0]),
        )
        assert concentration == pytest.approx(1.0, rel=0.01)

    def test_expected_concentration_far_from_source(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 机器人远离源时浓度较低
        concentration = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([10.0, 10.0]),
        )
        assert concentration < 0.1

    def test_likelihood_high_when_observation_matches(self):
        config = ParticleFilterConfig(
            plume_sigma=2.0,
            source_strength=1.0,
            observation_sigma=0.5,
        )
        model = GaussianPlumeObservationModel(config)

        # 观测值与期望值匹配时似然高
        likelihood = model.likelihood(
            source_hypothesis=np.array([0.0, 0.0]),
            robot_position=np.array([0.0, 0.0]),
            observed_concentration=1.0,
        )
        assert likelihood > 0.9

    def test_likelihood_low_when_observation_mismatched(self):
        config = ParticleFilterConfig(
            plume_sigma=2.0,
            source_strength=1.0,
            observation_sigma=0.5,
        )
        model = GaussianPlumeObservationModel(config)

        # 观测值与期望值不匹配时似然低
        likelihood = model.likelihood(
            source_hypothesis=np.array([10.0, 10.0]),
            robot_position=np.array([0.0, 0.0]),
            observed_concentration=1.0,
        )
        assert likelihood < 0.5

    def test_likelihood_symmetry(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 等距位置应有相同期望浓度
        c1 = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([1.0, 0.0]),
        )
        c2 = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([0.0, 1.0]),
        )
        assert c1 == pytest.approx(c2, rel=0.01)
