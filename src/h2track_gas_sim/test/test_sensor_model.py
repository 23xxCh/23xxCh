"""Tests for the realistic sensor model."""

from __future__ import annotations

import math
import random

import pytest

from h2track_gas_sim.gas_model import GasFieldModel, GasFieldParams
from h2track_gas_sim.sensor_model import SensorModel, SensorModelConfig
from h2track_gas_sim.wind_model import TimeVaryingWindModel, WindModelConfig
from h2track_utils.types import Pose2D


def _make_gas_model(source_x: float = 0.0, source_y: float = 0.0) -> GasFieldModel:
    params = GasFieldParams(
        source_x=source_x, source_y=source_y,
        source_strength=120.0, decay_rate=0.55,
        plume_stddev=1.2, wind_x=0.4, wind_y=0.0,
        noise_stddev=0.0, min_concentration=0.0, gas_type="H2",
    )
    return GasFieldModel(params, rng=random.Random(42))


class TestSensorModel:
    def test_sensor_tracks_gas_concentration(self):
        """Sensor reading should increase when entering a gas field."""
        gas_model = _make_gas_model(source_x=5.0, source_y=0.0)
        config = SensorModelConfig(
            response_tau=1.0, recovery_tau=2.0,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=0.0, baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(42))

        # Start far from source — near-zero
        for _ in range(10):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading < 5.0

        # Move to source — sensor rises gradually (not instant)
        for _ in range(30):
            sensor.update(Pose2D(5.0, 0.0), dt=0.1)
        assert sensor.reading > 50.0  # Approaching source_strength

    def test_response_delay(self):
        """Sensor should not reach steady-state instantly (first-order dynamics)."""
        gas_model = _make_gas_model(source_x=0.0, source_y=0.0)
        config = SensorModelConfig(
            response_tau=5.0, recovery_tau=10.0,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=0.0, baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(0))

        # One step: should not reach full concentration
        reading = sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        ideal = gas_model.concentration_at(Pose2D(0.0, 0.0))
        assert reading < ideal * 0.5  # Less than 50% of ideal after one step

    def test_recovery_slower_than_response(self):
        """Sensor should recover (fall) slower than it responds (rise)."""
        gas_model = _make_gas_model(source_x=0.0, source_y=0.0)
        config = SensorModelConfig(
            response_tau=1.0, recovery_tau=10.0,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=0.0, baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(0))

        # Rise: reach near steady state at source
        for _ in range(50):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        peak = sensor.reading

        # Fall: move away, check slow decay
        for _ in range(5):
            sensor.update(Pose2D(10.0, 10.0), dt=0.1)
        # After 0.5s with tau=10s, sensor should still be high
        assert sensor.reading > peak * 0.8

    def test_saturation(self):
        """Sensor reading should not exceed saturation limit."""
        gas_model = _make_gas_model(source_x=0.0, source_y=0.0)
        config = SensorModelConfig(
            response_tau=0.01,  # Very fast response
            recovery_tau=0.01,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=50.0,  # Cap at 50
            baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(0))

        for _ in range(50):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading <= 50.0

    def test_quantization(self):
        """Readings should be quantized to resolution."""
        gas_model = _make_gas_model(source_x=0.0, source_y=0.0)
        config = SensorModelConfig(
            response_tau=0.01, recovery_tau=0.01,
            noise_stddev=0.0, quantization_resolution=0.5,
            saturation=0.0, baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(0))

        for _ in range(50):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        # Reading should be a multiple of 0.5
        assert sensor.reading == pytest.approx(
            round(sensor.reading / 0.5) * 0.5, abs=1e-9
        )

    def test_baseline_drift_bounded(self):
        """Baseline drift should not exceed configured maximum."""
        gas_model = _make_gas_model(source_x=100.0, source_y=100.0)  # No gas
        config = SensorModelConfig(
            response_tau=1.0, recovery_tau=2.0,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=0.0,
            baseline_drift_rate=1.0,  # High drift rate
            baseline_drift_max=2.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(42))

        # Run for a long time
        for _ in range(1000):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        # Baseline drift should be bounded within ±2.0
        # (reading = smoothed + baseline + noise, smoothed≈0, noise=0)
        assert abs(sensor.reading) <= 2.0 + 0.01  # Small tolerance

    def test_fault_injection_stuck(self):
        """Stuck fault should force a fixed output."""
        gas_model = _make_gas_model()
        sensor = SensorModel(gas_model, SensorModelConfig(), rng=random.Random(0))
        sensor.inject_stuck(42.0)
        for _ in range(10):
            assert sensor.update(Pose2D(0.0, 0.0), dt=0.1) == 42.0

    def test_fault_injection_dropout(self):
        """Dropout fault should force zero output."""
        gas_model = _make_gas_model()
        sensor = SensorModel(gas_model, SensorModelConfig(), rng=random.Random(0))
        sensor.inject_dropout()
        for _ in range(10):
            assert sensor.update(Pose2D(0.0, 0.0), dt=0.1) == 0.0

    def test_fault_injection_spike(self):
        """Spike should add a transient offset that decays."""
        gas_model = _make_gas_model(source_x=100.0, source_y=100.0)
        config = SensorModelConfig(
            response_tau=0.01, recovery_tau=0.01,
            noise_stddev=0.0, quantization_resolution=0.0,
            saturation=0.0, baseline_drift_rate=0.0,
        )
        sensor = SensorModel(gas_model, config, rng=random.Random(0))

        # Baseline ~0
        for _ in range(10):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading < 1.0

        # Inject spike
        sensor.inject_spike(amplitude=50.0, duration=0.5)
        sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading > 40.0

        # Wait for spike to decay
        for _ in range(10):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading < 5.0

    def test_clear_faults(self):
        """clear_faults should restore normal sensor operation."""
        gas_model = _make_gas_model()
        sensor = SensorModel(gas_model, SensorModelConfig(), rng=random.Random(0))
        sensor.inject_stuck(42.0)
        assert sensor.has_fault
        sensor.clear_faults()
        assert not sensor.has_fault

    def test_reset_clears_state(self):
        """reset() should restore sensor to initial conditions."""
        gas_model = _make_gas_model(source_x=0.0, source_y=0.0)
        sensor = SensorModel(gas_model, SensorModelConfig(), rng=random.Random(0))

        # Build up state
        for _ in range(50):
            sensor.update(Pose2D(0.0, 0.0), dt=0.1)
        assert sensor.reading > 10.0

        # Reset
        sensor.reset()
        assert sensor.reading < 1.0


class TestTimeVaryingWindModel:
    def test_wind_starts_at_mean(self):
        """Wind should start at the configured mean direction."""
        config = WindModelConfig(
            mean_speed=0.5, mean_direction_deg=90.0, seed=42,
        )
        wind = TimeVaryingWindModel(config)
        # At 90°, wind_y should be positive, wind_x near zero
        assert wind.wind_x == pytest.approx(0.0, abs=0.01)
        assert wind.wind_y > 0.4

    def test_wind_direction_varies_over_time(self):
        """Wind direction should change over time (random walk)."""
        config = WindModelConfig(
            mean_speed=0.4, mean_direction_deg=0.0,
            direction_stddev_deg=30.0, seed=42,
        )
        wind = TimeVaryingWindModel(config)
        initial_dir = wind.direction_deg

        # Run for a while
        directions = []
        for _ in range(1000):
            wind.update(dt=0.1)
            directions.append(wind.direction_deg)

        # Direction should vary (not all equal to initial)
        direction_range = max(directions) - min(directions)
        assert direction_range > 5.0  # At least 5° of variation

    def test_gust_increases_speed(self):
        """When a gust is active, wind speed should increase."""
        config = WindModelConfig(
            mean_speed=0.3, gust_rate=1.0,  # High gust rate for testing
            gust_strength_factor=1.0, gust_duration=2.0,
            seed=42,
        )
        wind = TimeVaryingWindModel(config)
        base_speed = wind.speed

        # Run until gust occurs
        gust_detected = False
        for _ in range(500):
            wind.update(dt=0.1)
            if wind.gust_active:
                gust_detected = True
                assert wind.speed > base_speed * 1.2  # Gust boosts speed
                break

        assert gust_detected, "No gust detected in 50s with rate=1.0/s"

    def test_wind_returns_to_mean(self):
        """Wind direction should revert toward mean (O-U process)."""
        config = WindModelConfig(
            mean_speed=0.4, mean_direction_deg=0.0,
            direction_stddev_deg=45.0, seed=42,
        )
        wind = TimeVaryingWindModel(config)

        # Run for a long time
        for _ in range(10000):
            wind.update(dt=0.1)

        # Mean direction over last 100 samples should be close to 0°
        recent_dirs = []
        for _ in range(100):
            wind.update(dt=0.1)
            recent_dirs.append(wind.direction_deg)
        avg_dir = sum(d for d in recent_dirs) / len(recent_dirs)
        # Should be within 30° of mean (statistical, with seed=42)
        assert abs(avg_dir) < 30.0, f"Average direction {avg_dir:.1f}° too far from mean 0°"

    def test_reset(self):
        """reset() should restore wind to mean state."""
        config = WindModelConfig(mean_speed=0.4, mean_direction_deg=45.0, seed=42)
        wind = TimeVaryingWindModel(config)

        # Run for a while
        for _ in range(1000):
            wind.update(dt=0.1)

        # Reset
        wind.reset()
        assert wind.direction_deg == pytest.approx(45.0, abs=0.1)
        assert wind.speed == pytest.approx(0.4, abs=0.01)


class TestGasFieldModelSetWind:
    def test_set_wind_updates_concentration(self):
        """set_wind should change the plume direction."""
        params = GasFieldParams(
            source_x=0.0, source_y=0.0,
            source_strength=100.0, decay_rate=0.5,
            plume_stddev=1.0, wind_x=1.0, wind_y=0.0,
            noise_stddev=0.0, min_concentration=0.0, gas_type="H2",
        )
        model = GasFieldModel(params, rng=random.Random(0))

        # Robot downwind (+x) — high concentration
        c_downwind = model.concentration_at(Pose2D(2.0, 0.0))

        # Flip wind
        model.set_wind(-1.0, 0.0)
        c_after_flip = model.concentration_at(Pose2D(2.0, 0.0))

        # Now robot is upwind — lower concentration (for heavy gas) or
        # at least different (H2 has high upwind factor ~0.95)
        assert c_after_flip != pytest.approx(c_downwind, rel=0.01)
