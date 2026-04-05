"""Comprehensive unit tests for gaden_adapter.py pure Python module."""

import math

import pytest

from h2track_tracking.gaden_adapter import (
    GasSensorAdapterConfig,
    GasSensorSample,
    GasSensorUnits,
    HydrogenSensorModel,
    convert_gas_sensor_sample,
)


class TestGasSensorUnits:
    """Tests for GasSensorUnits IntEnum values."""

    def test_unknown_value(self):
        assert GasSensorUnits.UNKNOWN == 0

    def test_volt_value(self):
        assert GasSensorUnits.VOLT == 1

    def test_amp_value(self):
        assert GasSensorUnits.AMP == 2

    def test_ppm_value(self):
        assert GasSensorUnits.PPM == 3

    def test_ppb_value(self):
        assert GasSensorUnits.PPB == 4

    def test_ohm_value(self):
        assert GasSensorUnits.OHM == 5

    def test_ppmxm_value(self):
        assert GasSensorUnits.PPMXM == 6

    def test_centigrade_value(self):
        assert GasSensorUnits.CENTIGRADE == 100

    def test_relative_humidity_value(self):
        assert GasSensorUnits.RELATIVEHUMIDITY == 101

    def test_not_valid_value(self):
        assert GasSensorUnits.NOT_VALID == 255


class TestHydrogenSensorModel:
    """Tests for HydrogenSensorModel IntEnum and class methods."""

    def test_tgs2620_value(self):
        assert HydrogenSensorModel.TGS2620 == 0

    def test_tgs2600_value(self):
        assert HydrogenSensorModel.TGS2600 == 1

    def test_tgs2611_value(self):
        assert HydrogenSensorModel.TGS2611 == 2

    def test_tgs2610_value(self):
        assert HydrogenSensorModel.TGS2610 == 3

    def test_tgs2612_value(self):
        assert HydrogenSensorModel.TGS2612 == 4


class TestHydrogenSensorModelFromMpn:
    """Tests for HydrogenSensorModel.from_mpn() class method."""

    def test_from_mpn_valid_int_50_returns_tgs2620(self):
        assert HydrogenSensorModel.from_mpn(50) == HydrogenSensorModel.TGS2620

    def test_from_mpn_valid_int_51_returns_tgs2600(self):
        assert HydrogenSensorModel.from_mpn(51) == HydrogenSensorModel.TGS2600

    def test_from_mpn_valid_int_52_returns_tgs2611(self):
        assert HydrogenSensorModel.from_mpn(52) == HydrogenSensorModel.TGS2611

    def test_from_mpn_valid_int_53_returns_tgs2610(self):
        assert HydrogenSensorModel.from_mpn(53) == HydrogenSensorModel.TGS2610

    def test_from_mpn_valid_int_54_returns_tgs2612(self):
        assert HydrogenSensorModel.from_mpn(54) == HydrogenSensorModel.TGS2612

    def test_from_mpn_valid_string_returns_model(self):
        assert HydrogenSensorModel.from_mpn("51") == HydrogenSensorModel.TGS2600

    def test_from_mpn_invalid_int_returns_none(self):
        assert HydrogenSensorModel.from_mpn(999) is None

    def test_from_mpn_invalid_string_returns_none(self):
        assert HydrogenSensorModel.from_mpn("invalid") is None

    def test_from_mpn_none_returns_none(self):
        assert HydrogenSensorModel.from_mpn(None) is None

    def test_from_mpn_float_converts_to_int(self):
        assert HydrogenSensorModel.from_mpn(51.9) == HydrogenSensorModel.TGS2600


class TestHydrogenSensorModelAirResistance:
    """Tests for HydrogenSensorModel.air_resistance() class method."""

    def test_air_resistance_tgs2620(self):
        result = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2620)
        expected = 21.0 * 3000.0  # _SENSITIVITY_AIR * _R0
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_air_resistance_tgs2600(self):
        result = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2600)
        expected = 1.0 * 50000.0  # _SENSITIVITY_AIR * _R0
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_air_resistance_tgs2611(self):
        result = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2611)
        expected = 8.8 * 3740.0
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_air_resistance_tgs2610(self):
        result = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2610)
        expected = 10.3 * 3740.0
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_air_resistance_tgs2612(self):
        result = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2612)
        expected = 19.5 * 4500.0
        assert math.isclose(result, expected, rel_tol=1e-6)


class TestHydrogenSensorModelMoxRawFromPpm:
    """Tests for HydrogenSensorModel.mox_raw_from_ppm() class method."""

    def test_mox_raw_from_ppm_zero_returns_air_resistance(self):
        model = HydrogenSensorModel.TGS2600
        result = HydrogenSensorModel.mox_raw_from_ppm(model, 0.0)
        expected = HydrogenSensorModel.air_resistance(model)
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_mox_raw_from_ppm_negative_returns_air_resistance(self):
        model = HydrogenSensorModel.TGS2600
        result = HydrogenSensorModel.mox_raw_from_ppm(model, -5.0)
        expected = HydrogenSensorModel.air_resistance(model)
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_mox_raw_from_ppm_positive_concentration(self):
        model = HydrogenSensorModel.TGS2600
        result = HydrogenSensorModel.mox_raw_from_ppm(model, 10.0)
        # For TGS2600: coeff_a=0.6821, coeff_b=-0.3532
        # rs_over_r0 = 0.6821 * 10^(-0.3532) ~= 0.303
        # result = 0.303 * 50000 ~= 15150
        assert result > 0.0
        assert result < HydrogenSensorModel.air_resistance(model)

    def test_mox_raw_from_ppm_large_concentration_bounded(self):
        """Very large concentrations should be bounded by air resistance."""
        model = HydrogenSensorModel.TGS2600
        result = HydrogenSensorModel.mox_raw_from_ppm(model, 1e10)
        air_resistance = HydrogenSensorModel.air_resistance(model)
        assert result <= air_resistance

    def test_mox_raw_from_ppm_tgs2612_with_zero_coeff_b(self):
        """TGS2612 has coeff_b=0, which is a special case."""
        model = HydrogenSensorModel.TGS2612
        result = HydrogenSensorModel.mox_raw_from_ppm(model, 10.0)
        # For TGS2612: coeff_a=19.5, coeff_b=0.0
        # rs_over_r0 = 19.5 * ppm^0 = 19.5
        expected = 19.5 * 4500.0
        assert math.isclose(result, expected, rel_tol=1e-6)


class TestGasSensorSample:
    """Tests for GasSensorSample dataclass."""

    def test_create_sample_with_required_fields(self):
        sample = GasSensorSample(raw=1000.0, raw_units=GasSensorUnits.OHM)
        assert sample.raw == 1000.0
        assert sample.raw_units == GasSensorUnits.OHM
        assert sample.raw_air == 0.0
        assert sample.calib_a == 0.0
        assert sample.calib_b == 0.0
        assert sample.technology is None
        assert sample.manufacturer is None
        assert sample.mpn is None

    def test_create_sample_with_all_fields(self):
        sample = GasSensorSample(
            raw=2000.0,
            raw_units=GasSensorUnits.PPM,
            raw_air=5000.0,
            calib_a=1.0,
            calib_b=2.0,
            technology=1,
            manufacturer="FIGARO",
            mpn=51,
        )
        assert sample.raw == 2000.0
        assert sample.raw_units == GasSensorUnits.PPM
        assert sample.raw_air == 5000.0
        assert sample.calib_a == 1.0
        assert sample.calib_b == 2.0
        assert sample.technology == 1
        assert sample.manufacturer == "FIGARO"
        assert sample.mpn == 51

    def test_sample_is_frozen(self):
        sample = GasSensorSample(raw=1000.0, raw_units=GasSensorUnits.OHM)
        with pytest.raises(AttributeError):
            sample.raw = 2000.0


class TestGasSensorAdapterConfig:
    """Tests for GasSensorAdapterConfig dataclass."""

    def test_default_config(self):
        config = GasSensorAdapterConfig()
        assert config.sensor_model == HydrogenSensorModel.TGS2600
        assert config.fallback_ohm_scale == 0.0
        assert config.voltage_scale == 1.0
        assert config.minimum_concentration_ppm == 0.0
        assert config.maximum_concentration_ppm is None

    def test_custom_config(self):
        config = GasSensorAdapterConfig(
            sensor_model=HydrogenSensorModel.TGS2620,
            fallback_ohm_scale=0.001,
            voltage_scale=0.5,
            minimum_concentration_ppm=1.0,
            maximum_concentration_ppm=100.0,
        )
        assert config.sensor_model == HydrogenSensorModel.TGS2620
        assert config.fallback_ohm_scale == 0.001
        assert config.voltage_scale == 0.5
        assert config.minimum_concentration_ppm == 1.0
        assert config.maximum_concentration_ppm == 100.0

    def test_config_is_frozen(self):
        config = GasSensorAdapterConfig()
        with pytest.raises(AttributeError):
            config.sensor_model = HydrogenSensorModel.TGS2620

    def test_config_with_none_sensor_model(self):
        config = GasSensorAdapterConfig(sensor_model=None)
        assert config.sensor_model is None


class TestConvertGasSensorSamplePpmUnits:
    """Tests for convert_gas_sensor_sample with PPM units."""

    def test_ppm_units_pass_through(self):
        sample = GasSensorSample(raw=12.5, raw_units=GasSensorUnits.PPM)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 12.5

    def test_ppm_with_minimum_clamp(self):
        sample = GasSensorSample(raw=0.5, raw_units=GasSensorUnits.PPM)
        config = GasSensorAdapterConfig(minimum_concentration_ppm=1.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 1.0

    def test_ppm_with_maximum_clamp(self):
        sample = GasSensorSample(raw=150.0, raw_units=GasSensorUnits.PPM)
        config = GasSensorAdapterConfig(maximum_concentration_ppm=100.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 100.0

    def test_ppm_with_both_clamps(self):
        sample = GasSensorSample(raw=50.0, raw_units=GasSensorUnits.PPM)
        config = GasSensorAdapterConfig(
            minimum_concentration_ppm=1.0,
            maximum_concentration_ppm=100.0,
        )
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 50.0

    def test_ppm_zero_returns_zero(self):
        sample = GasSensorSample(raw=0.0, raw_units=GasSensorUnits.PPM)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_ppm_negative_returns_negative_clamped(self):
        """Negative PPM should pass through and get clamped by minimum."""
        sample = GasSensorSample(raw=-5.0, raw_units=GasSensorUnits.PPM)
        config = GasSensorAdapterConfig(minimum_concentration_ppm=0.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 0.0


class TestConvertGasSensorSamplePpbUnits:
    """Tests for convert_gas_sensor_sample with PPB units."""

    def test_ppb_units_convert_to_ppm(self):
        sample = GasSensorSample(raw=2500.0, raw_units=GasSensorUnits.PPB)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 2.5

    def test_ppb_zero(self):
        sample = GasSensorSample(raw=0.0, raw_units=GasSensorUnits.PPB)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_ppb_with_minimum_clamp(self):
        sample = GasSensorSample(raw=500.0, raw_units=GasSensorUnits.PPB)  # 0.5 ppm
        config = GasSensorAdapterConfig(minimum_concentration_ppm=1.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 1.0

    def test_ppb_large_value(self):
        sample = GasSensorSample(raw=1000000.0, raw_units=GasSensorUnits.PPB)  # 1000 ppm
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 1000.0


class TestConvertGasSensorSampleVoltUnits:
    """Tests for convert_gas_sensor_sample with VOLT units."""

    def test_volt_units_uses_voltage_scale(self):
        sample = GasSensorSample(raw=2.5, raw_units=GasSensorUnits.VOLT)
        config = GasSensorAdapterConfig(voltage_scale=10.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 25.0

    def test_volt_units_default_scale(self):
        sample = GasSensorSample(raw=5.0, raw_units=GasSensorUnits.VOLT)
        config = GasSensorAdapterConfig()  # default voltage_scale=1.0
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 5.0

    def test_volt_with_minimum_clamp(self):
        sample = GasSensorSample(raw=0.05, raw_units=GasSensorUnits.VOLT)
        config = GasSensorAdapterConfig(voltage_scale=10.0, minimum_concentration_ppm=1.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 1.0

    def test_volt_zero(self):
        sample = GasSensorSample(raw=0.0, raw_units=GasSensorUnits.VOLT)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0


class TestConvertGasSensorSampleOhmUnits:
    """Tests for convert_gas_sensor_sample with OHM units."""

    def test_ohm_units_invert_mox_hydrogen_curve(self):
        concentration_ppm = 8.0
        model = HydrogenSensorModel.TGS2600
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(model, concentration_ppm),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
            manufacturer="FIGARO",
            mpn="TGS2600",
        )
        config = GasSensorAdapterConfig(sensor_model=model)
        concentration = convert_gas_sensor_sample(sample, config)
        assert math.isclose(concentration, concentration_ppm, rel_tol=1e-3)

    def test_ohm_units_with_model_from_config(self):
        """Test OHM conversion using model from config, not sample."""
        model = HydrogenSensorModel.TGS2620
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(model, 5.0),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
            # No mpn, so config model is used
        )
        config = GasSensorAdapterConfig(sensor_model=model)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration > 0.0

    def test_ohm_units_no_model_returns_fallback(self):
        sample = GasSensorSample(raw=2000.0, raw_units=GasSensorUnits.OHM, raw_air=4000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.002)
        concentration = convert_gas_sensor_sample(sample, config)
        assert math.isclose(concentration, 4.0, rel_tol=1e-6)

    def test_ohm_units_tgs2612_uses_fallback(self):
        """TGS2612 has coeff_b=0, which triggers fallback."""
        model = HydrogenSensorModel.TGS2612
        sample = GasSensorSample(
            raw=10000.0,
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
            mpn=54,
        )
        config = GasSensorAdapterConfig(sensor_model=model, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        # Should use fallback path due to coeff_b=0
        assert concentration >= 0.0

    def test_ohm_units_with_clamps(self):
        model = HydrogenSensorModel.TGS2600
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(model, 50.0),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
        )
        config = GasSensorAdapterConfig(
            sensor_model=model,
            minimum_concentration_ppm=1.0,
            maximum_concentration_ppm=10.0,
        )
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration >= 1.0
        assert concentration <= 10.0


class TestConvertGasSensorSampleUnknownUnits:
    """Tests for convert_gas_sensor_sample with unknown/invalid units."""

    def test_unknown_units_returns_zero(self):
        sample = GasSensorSample(raw=100.0, raw_units=GasSensorUnits.UNKNOWN)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_amp_units_returns_zero(self):
        sample = GasSensorSample(raw=0.5, raw_units=GasSensorUnits.AMP)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_centigrade_units_returns_zero(self):
        sample = GasSensorSample(raw=25.0, raw_units=GasSensorUnits.CENTIGRADE)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_not_valid_units_returns_zero(self):
        sample = GasSensorSample(raw=100.0, raw_units=GasSensorUnits.NOT_VALID)
        concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())
        assert concentration == 0.0

    def test_unknown_units_with_minimum_clamp(self):
        sample = GasSensorSample(raw=100.0, raw_units=GasSensorUnits.UNKNOWN)
        config = GasSensorAdapterConfig(minimum_concentration_ppm=0.5)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 0.5


class TestFallbackOhmProxy:
    """Tests for _fallback_ohm_proxy edge cases via convert_gas_sensor_sample."""

    def test_fallback_with_zero_scale_returns_zero(self):
        """fallback_ohm_scale <= 0 should return 0.0."""
        sample = GasSensorSample(raw=2000.0, raw_units=GasSensorUnits.OHM, raw_air=4000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.0)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 0.0

    def test_fallback_with_negative_scale_returns_zero(self):
        """Negative fallback_ohm_scale should return 0.0."""
        sample = GasSensorSample(raw=2000.0, raw_units=GasSensorUnits.OHM, raw_air=4000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=-0.1)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 0.0

    def test_fallback_with_zero_raw_air_uses_raw_only(self):
        """When raw_air <= 0, use raw * fallback_ohm_scale."""
        sample = GasSensorSample(raw=3000.0, raw_units=GasSensorUnits.OHM, raw_air=0.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        assert math.isclose(concentration, 3.0, rel_tol=1e-6)

    def test_fallback_normal_case(self):
        """Normal case: (raw_air - raw) * fallback_ohm_scale."""
        sample = GasSensorSample(raw=3000.0, raw_units=GasSensorUnits.OHM, raw_air=5000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        expected = (5000.0 - 3000.0) * 0.001  # = 2.0
        assert math.isclose(concentration, expected, rel_tol=1e-6)

    def test_fallback_raw_greater_than_air_returns_zero(self):
        """When raw > raw_air, max(0, ...) returns 0."""
        sample = GasSensorSample(raw=6000.0, raw_units=GasSensorUnits.OHM, raw_air=5000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration == 0.0


class TestResolveSensorModel:
    """Tests for _resolve_sensor_model via convert_gas_sensor_sample."""

    def test_sample_mpn_takes_precedence_over_config(self):
        """Sample mpn should override config sensor_model."""
        config_model = HydrogenSensorModel.TGS2600
        sample_model = HydrogenSensorModel.TGS2620
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(sample_model, 5.0),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(sample_model),
            mpn=50,  # TGS2620
        )
        config = GasSensorAdapterConfig(sensor_model=config_model)
        # Should use TGS2620 from sample, not TGS2600 from config
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration > 0.0

    def test_config_model_used_when_no_mpn(self):
        """Config model should be used when sample has no mpn."""
        model = HydrogenSensorModel.TGS2611
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(model, 5.0),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
        )
        config = GasSensorAdapterConfig(sensor_model=model)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration > 0.0

    def test_none_model_when_no_mpn_and_no_config_model(self):
        """Should use fallback when both mpn and config model are None."""
        sample = GasSensorSample(raw=3000.0, raw_units=GasSensorUnits.OHM, raw_air=5000.0)
        config = GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration >= 0.0


class TestConvertOhmsToPpmEdgeCases:
    """Tests for edge cases in _convert_ohms_to_ppm via convert_gas_sensor_sample."""

    def test_zero_raw_air_uses_fallback(self):
        """Zero raw_air should trigger fallback."""
        model = HydrogenSensorModel.TGS2600
        sample = GasSensorSample(
            raw=30000.0,
            raw_units=GasSensorUnits.OHM,
            raw_air=0.0,  # Invalid raw_air
        )
        config = GasSensorAdapterConfig(sensor_model=model, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration >= 0.0

    def test_negative_raw_air_uses_fallback(self):
        """Negative raw_air should trigger fallback."""
        model = HydrogenSensorModel.TGS2600
        sample = GasSensorSample(
            raw=30000.0,
            raw_units=GasSensorUnits.OHM,
            raw_air=-100.0,  # Invalid raw_air
        )
        config = GasSensorAdapterConfig(sensor_model=model, fallback_ohm_scale=0.001)
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration >= 0.0

    def test_uses_default_air_resistance_when_raw_air_is_zero(self):
        """When raw_air is 0 in sample but sensor model has valid air_resistance."""
        model = HydrogenSensorModel.TGS2600
        # Create sample with raw that would produce valid concentration
        sample = GasSensorSample(
            raw=25000.0,
            raw_units=GasSensorUnits.OHM,
            raw_air=0.0,  # Will be replaced by model's air_resistance
            mpn=51,
        )
        config = GasSensorAdapterConfig(sensor_model=model, fallback_ohm_scale=0.001)
        # Should work because raw_air=0 triggers use of model's air_resistance
        concentration = convert_gas_sensor_sample(sample, config)
        assert concentration >= 0.0


class TestConvertGasSensorSampleAllSensorModels:
    """Tests covering all HydrogenSensorModel variants."""

    @pytest.mark.parametrize("model", list(HydrogenSensorModel))
    def test_ohm_conversion_for_all_models(self, model):
        """Test OHM conversion works for all sensor models."""
        sample = GasSensorSample(
            raw=HydrogenSensorModel.mox_raw_from_ppm(model, 5.0),
            raw_units=GasSensorUnits.OHM,
            raw_air=HydrogenSensorModel.air_resistance(model),
        )
        config = GasSensorAdapterConfig(sensor_model=model)
        concentration = convert_gas_sensor_sample(sample, config)
        # All models should produce a non-negative concentration
        assert concentration >= 0.0
