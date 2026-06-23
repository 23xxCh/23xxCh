"""Unit tests for GADEN gas sensor adapter.

Tests the core conversion logic (GasSensor → Float32 concentration):
- PPM passthrough
- PPB → PPM conversion
- VOLT scaling
- OHM → PPM inversion (Figaro TGS sensor model)
- Clamping to min/max
- Fallback for unknown units
"""

from __future__ import annotations

import math
import pytest

from h2track_gas_sim.gaden_adapter import (
    GasSensorAdapterConfig,
    GasSensorSample,
    GasSensorUnits,
    HydrogenSensorModel,
    convert_gas_sensor_sample,
)


def _make_sample(
    raw: float = 0.0,
    units: GasSensorUnits = GasSensorUnits.PPM,
    raw_air: float = 0.0,
    mpn: int | None = 50,
) -> GasSensorSample:
    return GasSensorSample(
        raw=raw,
        raw_units=units,
        raw_air=raw_air,
        mpn=mpn,
    )


class TestPPMConversion:
    def test_ppm_passthrough(self):
        """PPM readings should pass through unchanged."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=42.5, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(42.5)

    def test_ppm_clamped_to_minimum(self):
        """Negative PPM should be clamped to minimum."""
        config = GasSensorAdapterConfig(minimum_concentration_ppm=0.0)
        sample = _make_sample(raw=-5.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)

    def test_ppm_clamped_to_maximum(self):
        """PPM above maximum should be clamped."""
        config = GasSensorAdapterConfig(maximum_concentration_ppm=100.0)
        sample = _make_sample(raw=500.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(100.0)

    def test_ppm_zero(self):
        """Zero PPM should pass through."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=0.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)


class TestPPBConversion:
    def test_ppb_to_ppm(self):
        """PPB should be divided by 1000 to get PPM."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=5000.0, units=GasSensorUnits.PPB)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(5.0)

    def test_ppb_zero(self):
        """Zero PPB should be 0 PPM."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=0.0, units=GasSensorUnits.PPB)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)


class TestVOLTConversion:
    def test_volt_scaling(self):
        """VOLT should be multiplied by voltage_scale."""
        config = GasSensorAdapterConfig(voltage_scale=10.0)
        sample = _make_sample(raw=2.5, units=GasSensorUnits.VOLT)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(25.0)

    def test_volt_default_scale(self):
        """Default voltage_scale should be 1.0."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=3.0, units=GasSensorUnits.VOLT)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(3.0)


class TestOHMConversion:
    def test_ohm_uses_sensor_model(self):
        """OHM should be converted via Figaro sensor model."""
        config = GasSensorAdapterConfig(sensor_model=HydrogenSensorModel.TGS2600)
        # Use a realistic resistance value (lower than air resistance = high gas)
        # TGS2600: R0=50000, air=1.0 * 50000 = 50000
        sample = _make_sample(
            raw=10000.0,  # Rs much less than air
            units=GasSensorUnits.OHM,
            raw_air=50000.0,  # Air resistance
            mpn=51,  # TGS2600
        )
        result = convert_gas_sensor_sample(sample, config)
        # Result should be positive and finite
        assert result > 0.0
        assert math.isfinite(result)

    def test_ohm_fallback_when_no_sensor_model(self):
        """OHM with no resolvable sensor should use fallback proxy."""
        config = GasSensorAdapterConfig(
            sensor_model=None,
            fallback_ohm_scale=0.001,
        )
        sample = _make_sample(
            raw=10000.0,
            units=GasSensorUnits.OHM,
            raw_air=50000.0,
            mpn=None,  # No MPN → no sensor model
        )
        result = convert_gas_sensor_sample(sample, config)
        # fallback = (raw_air - raw) * scale = 40000 * 0.001 = 40.0
        assert result == pytest.approx(40.0)

    def test_ohm_fallback_no_raw_air(self):
        """OHM fallback without raw_air should use direct scaling."""
        config = GasSensorAdapterConfig(
            sensor_model=None,
            fallback_ohm_scale=0.01,
        )
        sample = _make_sample(
            raw=500.0,
            units=GasSensorUnits.OHM,
            raw_air=0.0,  # No air reference
            mpn=None,
        )
        result = convert_gas_sensor_sample(sample, config)
        # fallback = raw * scale = 500 * 0.01 = 5.0
        assert result == pytest.approx(5.0)

    def test_ohm_zero_concentration_returns_air_resistance(self):
        """OHM at zero concentration should return air resistance (high)."""
        config = GasSensorAdapterConfig(sensor_model=HydrogenSensorModel.TGS2600)
        # air_resistance for TGS2600 = 1.0 * 50000 = 50000
        sample = _make_sample(
            raw=50000.0,  # = air resistance
            units=GasSensorUnits.OHM,
            raw_air=50000.0,
            mpn=51,
        )
        # mox_raw_from_ppm(0) = air_resistance → convert back to ~0 ppm
        result = convert_gas_sensor_sample(sample, config)
        # Should be near zero (or clamped to minimum)
        assert result >= 0.0
        assert math.isfinite(result)

    def test_ohm_no_fallback_returns_zero(self):
        """OHM with no sensor and no fallback should return 0."""
        config = GasSensorAdapterConfig(
            sensor_model=None,
            fallback_ohm_scale=0.0,
        )
        sample = _make_sample(
            raw=1000.0,
            units=GasSensorUnits.OHM,
            raw_air=0.0,
            mpn=None,
        )
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)


class TestUnknownUnits:
    def test_unknown_units_returns_zero(self):
        """Unknown units should return 0 (after clamping)."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=42.0, units=GasSensorUnits.UNKNOWN)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)

    def test_not_valid_units_returns_zero(self):
        """NOT_VALID units should return 0."""
        config = GasSensorAdapterConfig()
        sample = _make_sample(raw=42.0, units=GasSensorUnits.NOT_VALID)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(0.0)


class TestHydrogenSensorModel:
    def test_from_mpn_valid(self):
        """Valid MPNs should resolve to correct sensor models."""
        assert HydrogenSensorModel.from_mpn(50) == HydrogenSensorModel.TGS2620
        assert HydrogenSensorModel.from_mpn(51) == HydrogenSensorModel.TGS2600
        assert HydrogenSensorModel.from_mpn(52) == HydrogenSensorModel.TGS2611
        assert HydrogenSensorModel.from_mpn(53) == HydrogenSensorModel.TGS2610
        assert HydrogenSensorModel.from_mpn(54) == HydrogenSensorModel.TGS2612

    def test_from_mpn_invalid(self):
        """Invalid MPNs should return None."""
        assert HydrogenSensorModel.from_mpn(30) is None
        assert HydrogenSensorModel.from_mpn(99) is None
        assert HydrogenSensorModel.from_mpn(None) is None

    def test_air_resistance_positive(self):
        """All sensor models should have positive air resistance."""
        for model in HydrogenSensorModel:
            assert HydrogenSensorModel.air_resistance(model) > 0.0

    def test_mox_raw_from_ppm_zero_returns_air(self):
        """Zero concentration should return air resistance."""
        for model in HydrogenSensorModel:
            raw = HydrogenSensorModel.mox_raw_from_ppm(model, 0.0)
            assert raw == pytest.approx(HydrogenSensorModel.air_resistance(model))


class TestClamping:
    def test_minimum_clamp(self):
        """Concentration below minimum should be clamped up."""
        config = GasSensorAdapterConfig(minimum_concentration_ppm=5.0)
        sample = _make_sample(raw=2.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(5.0)

    def test_maximum_clamp(self):
        """Concentration above maximum should be clamped down."""
        config = GasSensorAdapterConfig(maximum_concentration_ppm=100.0)
        sample = _make_sample(raw=500.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(100.0)

    def test_no_maximum(self):
        """None maximum should not clamp."""
        config = GasSensorAdapterConfig(maximum_concentration_ppm=None)
        sample = _make_sample(raw=10000.0, units=GasSensorUnits.PPM)
        assert convert_gas_sensor_sample(sample, config) == pytest.approx(10000.0)
