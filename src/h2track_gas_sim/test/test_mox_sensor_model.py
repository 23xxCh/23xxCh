"""Tests for mox_sensor_model — complete GADEN MOX sensor model port.

Tests cover:
- Constants (R0, Sensitivity_Air, sensitivity_lineloglog, tau_value, PID factors)
- Static conversion: ppm → Rs/R0 → Ohms
- Dynamic response: tau-based low-pass filter
- Gas type lookup
- Reset clears state
"""

from __future__ import annotations

import math

import pytest

from h2track_gas_sim.mox_sensor_model import (
    GAS_TYPE_IDS,
    MoxGasType,
    MoxSensorConfig,
    MoxSensorModel,
    MoxSensorType,
    mox_raw_from_ppm,
)


class TestConstants:
    """Golden-value tests — values must match GADEN fake_gas_sensor.h exactly."""

    def test_r0_values_match_gaden(self) -> None:
        """R0 [Ohms] must match GADEN header: {3000, 50000, 3740, 3740, 4500}."""
        # air_resistance returns Rs in clean air = Sensitivity_Air * R0
        # GADEN: TGS2620 → 21 * 3000 = 63000
        #        TGS2600 → 1 * 50000 = 50000
        #        TGS2611 → 8.8 * 3740 = 32912
        #        TGS2610 → 10.3 * 3740 = 38522
        #        TGS2612 → 19.5 * 4500 = 87750
        assert MoxSensorModel.air_resistance(MoxSensorType.TGS2620) == pytest.approx(63000.0)
        assert MoxSensorModel.air_resistance(MoxSensorType.TGS2600) == pytest.approx(50000.0)
        assert MoxSensorModel.air_resistance(MoxSensorType.TGS2611) == pytest.approx(32912.0)
        assert MoxSensorModel.air_resistance(MoxSensorType.TGS2610) == pytest.approx(38522.0)
        assert MoxSensorModel.air_resistance(MoxSensorType.TGS2612) == pytest.approx(87750.0)


class TestStaticConversion:
    """Test static Rs/R0 = A * conc^B conversion."""

    def test_zero_concentration_returns_air_resistance(self) -> None:
        """At 0 ppm, Rs = air resistance (baseline)."""
        rs_ohms = mox_raw_from_ppm(MoxSensorType.TGS2600, MoxGasType.HYDROGEN, 0.0)
        # air_resistance = Sensitivity_Air * R0 = 1 * 50000 = 50000
        assert rs_ohms == pytest.approx(50000.0)

    def test_high_concentration_reduces_resistance(self) -> None:
        """At high ppm, Rs should be below air resistance (MOX drops)."""
        rs_ohms = mox_raw_from_ppm(MoxSensorType.TGS2600, MoxGasType.HYDROGEN, 100.0)
        assert rs_ohms < 50000.0


class TestGasTypeLookup:
    def test_gas_type_ids_match_gaden(self) -> None:
        """Gas type ID mapping must match GADEN string→index."""
        assert GAS_TYPE_IDS["ethanol"] == 0
        assert GAS_TYPE_IDS["methane"] == 1
        assert GAS_TYPE_IDS["hydrogen"] == 2
        assert GAS_TYPE_IDS["propanol"] == 3
        assert GAS_TYPE_IDS["chlorine"] == 4
        assert GAS_TYPE_IDS["fluorine"] == 5
        assert GAS_TYPE_IDS["acetone"] == 6


class TestDynamicResponse:
    """Test tau-based low-pass filter (rise/decay)."""

    def test_first_reading_returns_air_resistance(self) -> None:
        """First update() should return baseline (air resistance)."""
        model = MoxSensorModel(MoxSensorConfig(
            sensor_model=MoxSensorType.TGS2600,
            gas_type=MoxGasType.HYDROGEN,
            use_dynamics=True,
        ))
        # First call sets previous_output but uses baseline
        result = model.update(0.0)
        assert result == pytest.approx(50000.0)  # air for TGS2600

    def test_dynamic_response_slower_than_static(self) -> None:
        """With dynamics, response to step should lag behind static."""
        model = MoxSensorModel(MoxSensorConfig(
            sensor_model=MoxSensorType.TGS2600,
            gas_type=MoxGasType.HYDROGEN,
            use_dynamics=True,
            node_rate_hz=10.0,
        ))
        # Prime with baseline
        model.update(0.0)
        # Step to 100 ppm
        dynamic_result = model.update(100.0)
        # Compare to static (no dynamics)
        static_result = mox_raw_from_ppm(MoxSensorType.TGS2600, MoxGasType.HYDROGEN, 100.0)
        # Dynamic should be between air (50000) and static (lower)
        assert dynamic_result < 50000.0
        assert dynamic_result > static_result  # lagging behind

    def test_no_dynamics_returns_static(self) -> None:
        """With use_dynamics=False, update() returns static resistance immediately."""
        model = MoxSensorModel(MoxSensorConfig(
            sensor_model=MoxSensorType.TGS2600,
            gas_type=MoxGasType.HYDROGEN,
            use_dynamics=False,
        ))
        model.update(0.0)  # prime
        result = model.update(100.0)
        static = mox_raw_from_ppm(MoxSensorType.TGS2600, MoxGasType.HYDROGEN, 100.0)
        assert result == pytest.approx(static)

    def test_reset_clears_state(self) -> None:
        """After reset(), first update returns baseline again."""
        model = MoxSensorModel(MoxSensorConfig(
            sensor_model=MoxSensorType.TGS2600,
            gas_type=MoxGasType.HYDROGEN,
            use_dynamics=True,
        ))
        model.update(0.0)
        model.update(100.0)
        model.reset()
        # Next update should be first_reading again
        result = model.update(0.0)
        assert result == pytest.approx(50000.0)  # air baseline


class TestConfigImmutability:
    def test_config_is_frozen(self) -> None:
        """MoxSensorConfig should be immutable."""
        cfg = MoxSensorConfig()
        with pytest.raises(AttributeError):
            cfg.use_dynamics = False  # type: ignore[misc]


# Parametrize golden value tests over all 5 sensors × 7 gases
_SENSORS = list(MoxSensorType)
_GASES = list(MoxGasType)


class TestSensitivityGoldenValues:
    """Verify sensitivity_lineloglog constants match GADEN header exactly."""

    @pytest.mark.parametrize("sensor", _SENSORS)
    @pytest.mark.parametrize("gas", _GASES)
    def test_sensitivity_a_matches_gaden(self, sensor: MoxSensorType, gas: MoxGasType) -> None:
        """A coefficient must match GADEN sensitivity_lineloglog[sensor][gas][0]."""
        # These are the exact values from fake_gas_sensor.h
        expected_a = {
            (MoxSensorType.TGS2620, MoxGasType.ETHANOL): 62.32,
            (MoxSensorType.TGS2620, MoxGasType.METHANE): 120.6,
            (MoxSensorType.TGS2620, MoxGasType.HYDROGEN): 24.45,
            (MoxSensorType.TGS2600, MoxGasType.ETHANOL): 0.6796,
            (MoxSensorType.TGS2600, MoxGasType.HYDROGEN): 0.6821,
            (MoxSensorType.TGS2611, MoxGasType.HYDROGEN): 41.3,
            (MoxSensorType.TGS2612, MoxGasType.HYDROGEN): 19.5,
        }
        if (sensor, gas) in expected_a:
            a, _ = _get_sensitivity(sensor, gas)
            assert a == pytest.approx(expected_a[(sensor, gas)])


def _get_sensitivity(sensor: MoxSensorType, gas: MoxGasType) -> tuple[float, float]:
    """Helper: access internal sensitivity table for golden-value tests."""
    from h2track_gas_sim.mox_sensor_model import _SENSITIVITY_LINELOGLOG
    return _SENSITIVITY_LINELOGLOG[sensor][gas]


class TestTauGoldenValues:
    """Verify tau_value constants match GADEN header."""

    @pytest.mark.parametrize("sensor", _SENSORS)
    def test_tau_rise_and_decay_match_gaden(self, sensor: MoxSensorType) -> None:
        """Tau (rise, decay) must match GADEN tau_value[sensor][*][0,1]."""
        from h2track_gas_sim.mox_sensor_model import _TAU_VALUE
        # GADEN values (all gases share same tau per sensor)
        expected = {
            MoxSensorType.TGS2620: (2.96, 15.71),
            MoxSensorType.TGS2600: (4.8, 18.75),
            MoxSensorType.TGS2611: (3.44, 6.35),
            MoxSensorType.TGS2610: (3.44, 6.35),
            MoxSensorType.TGS2612: (3.44, 6.35),
        }
        rise, decay = _TAU_VALUE[sensor][0]
        assert rise == pytest.approx(expected[sensor][0])
        assert decay == pytest.approx(expected[sensor][1])


class TestPIDCorrectionFactors:
    def test_pid_factors_match_gaden(self) -> None:
        """PID correction factors must match GADEN header."""
        from h2track_gas_sim.mox_sensor_model import _PID_CORRECTION_FACTORS
        # GADEN: {10.47, 0.0, 0.0, 2.7, 1.0, 0.0, 1.4}
        assert _PID_CORRECTION_FACTORS == (
            10.47, 0.0, 0.0, 2.7, 1.0, 0.0, 1.4
        )

    def test_pid_factor_for_hydrogen_is_zero(self) -> None:
        """H2 PID factor = 0 → PID insensitive to hydrogen (matches GADEN)."""
        from h2track_gas_sim.mox_sensor_model import _PID_CORRECTION_FACTORS
        assert _PID_CORRECTION_FACTORS[MoxGasType.HYDROGEN] == 0.0
