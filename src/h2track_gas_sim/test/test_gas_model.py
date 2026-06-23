"""Unit tests for gas_model.py — GasFieldModel and GasFieldParams."""

import math
import random

import pytest

from h2track_gas_sim.gas_model import GasFieldModel, GasFieldParams
from h2track_gas_sim.gas_types import GasType, get_gas_properties
from h2track_utils.types import Pose2D


def _default_params(**overrides) -> GasFieldParams:
    defaults = dict(
        source_x=0.0, source_y=0.0,
        source_strength=120.0, decay_rate=0.55,
        plume_stddev=1.2, wind_x=0.4, wind_y=0.0,
        noise_stddev=0.0, min_concentration=0.0,
        gas_type="H2",
    )
    defaults.update(overrides)
    return GasFieldParams(**defaults)


class TestGasFieldModel:
    def test_concentration_at_source(self):
        model = GasFieldModel(_default_params(), rng=random.Random(42))
        c = model.concentration_at(Pose2D(0.0, 0.0))
        assert c == pytest.approx(120.0)

    def test_concentration_decreases_with_distance(self):
        model = GasFieldModel(_default_params(), rng=random.Random(42))
        c_near = model.concentration_at(Pose2D(1.0, 0.0))
        c_far = model.concentration_at(Pose2D(5.0, 0.0))
        assert c_near > c_far

    def test_concentration_respects_min_concentration(self):
        model = GasFieldModel(_default_params(min_concentration=0.1), rng=random.Random(42))
        c = model.concentration_at(Pose2D(100.0, 100.0))
        assert c >= 0.1

    def test_downwind_higher_than_upwind(self):
        model = GasFieldModel(_default_params(), rng=random.Random(42))
        c_downwind = model.concentration_at(Pose2D(3.0, 0.0))
        c_upwind = model.concentration_at(Pose2D(-3.0, 0.0))
        assert c_downwind > c_upwind

    def test_no_wind_gives_isotropic_concentration(self):
        model = GasFieldModel(_default_params(wind_x=0.0, wind_y=0.0), rng=random.Random(42))
        c1 = model.concentration_at(Pose2D(3.0, 0.0))
        c2 = model.concentration_at(Pose2D(-3.0, 0.0))
        c3 = model.concentration_at(Pose2D(0.0, 3.0))
        # Without wind, all positions at same distance should have similar concentration
        assert c1 == pytest.approx(c2, rel=0.01)
        assert c1 == pytest.approx(c3, rel=0.01)

    def test_h2_has_higher_upwind_than_ch4(self):
        """H2 (lighter) should spread more upwind than CH4 (heavier)."""
        model_h2 = GasFieldModel(_default_params(gas_type="H2"), rng=random.Random(42))
        model_ch4 = GasFieldModel(_default_params(gas_type="CH4"), rng=random.Random(42))
        c_h2 = model_h2.concentration_at(Pose2D(-3.0, 0.0))
        c_ch4 = model_ch4.concentration_at(Pose2D(-3.0, 0.0))
        assert c_h2 > c_ch4

    def test_noise_adds_variability(self):
        model = GasFieldModel(_default_params(noise_stddev=1.0), rng=random.Random(42))
        # Multiple readings at same position should vary
        readings = [model.concentration_at(Pose2D(2.0, 0.0)) for _ in range(20)]
        assert max(readings) > min(readings)

    def test_buoyancy_smooth_across_gases(self):
        """Buoyancy factor should vary smoothly across different gas types."""
        upwind_concentrations = {}
        for gas_type in ["H2", "CH4", "CO", "C3H8"]:
            model = GasFieldModel(_default_params(gas_type=gas_type), rng=random.Random(42))
            c = model.concentration_at(Pose2D(-3.0, 0.0))
            upwind_concentrations[gas_type] = c

        # Upwind concentration should decrease with increasing density
        assert upwind_concentrations["H2"] > upwind_concentrations["CH4"]
        assert upwind_concentrations["CH4"] > upwind_concentrations["CO"]
        assert upwind_concentrations["CO"] > upwind_concentrations["C3H8"]

    def test_exponential_decay_formula(self):
        """Verify the core exponential decay formula: C = S * exp(-λ*d)."""
        params = _default_params(wind_x=0.0, wind_y=0.0)
        model = GasFieldModel(params, rng=random.Random(42))
        # At d=2.0 without wind: C = 120 * exp(-0.55 * 2)
        c = model.concentration_at(Pose2D(2.0, 0.0))
        expected = 120.0 * math.exp(-0.55 * 2.0)
        assert c == pytest.approx(expected, rel=0.01)


class TestGasFieldParams:
    def test_frozen_dataclass(self):
        params = _default_params()
        with pytest.raises(Exception):
            params.source_x = 5.0

    def test_gas_type_default(self):
        params = _default_params()
        assert params.gas_type == "H2"
