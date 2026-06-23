"""Unit tests for anemometer_adapter — convert GADEN Anemometer to WindEstimate.

GADEN's simulated_anemometer (with use_map_ref_system:=true) publishes
wind_speed (m/s) and wind_direction (rad) in map frame, where
wind_direction = atan2(v, u) points in the direction wind blows TOWARDS.

This matches h2track's WindEstimate.wind_x/wind_y convention
(positive = blowing in +X direction).
"""

from __future__ import annotations

import math

import pytest

from h2track_gas_sim.anemometer_adapter import (
    AnemometerAdapterConfig,
    AnemometerReading,
    WindEstimate,
    convert_anemometer_to_wind_estimate,
)


def _reading(speed: float, direction: float, label: str = "anemometer") -> AnemometerReading:
    return AnemometerReading(
        wind_speed=speed,
        wind_direction=direction,
        sensor_label=label,
        timestamp=0.0,
    )


class TestConvertBasic:
    def test_east_wind_converts_to_positive_x(self) -> None:
        """Wind blowing east (direction=0) → wind_x = speed, wind_y = 0."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=1.0, direction=0.0),
            AnemometerAdapterConfig(),
        )
        assert result.wind_x == pytest.approx(1.0)
        assert result.wind_y == pytest.approx(0.0)

    def test_north_wind_converts_to_positive_y(self) -> None:
        """Wind blowing north (direction=π/2) → wind_y = speed, wind_x = 0."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=2.0, direction=math.pi / 2),
            AnemometerAdapterConfig(),
        )
        assert result.wind_x == pytest.approx(0.0, abs=1e-6)
        assert result.wind_y == pytest.approx(2.0)

    def test_west_wind_converts_to_negative_x(self) -> None:
        """Wind blowing west (direction=π) → wind_x = -speed."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=1.5, direction=math.pi),
            AnemometerAdapterConfig(),
        )
        assert result.wind_x == pytest.approx(-1.5)
        assert result.wind_y == pytest.approx(0.0, abs=1e-6)

    def test_south_wind_converts_to_negative_y(self) -> None:
        """Wind blowing south (direction=-π/2) → wind_y = -speed."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=0.8, direction=-math.pi / 2),
            AnemometerAdapterConfig(),
        )
        assert result.wind_x == pytest.approx(0.0, abs=1e-6)
        assert result.wind_y == pytest.approx(-0.8)


class TestEdgeCases:
    def test_zero_speed_returns_zero_estimate(self) -> None:
        """Zero wind speed → zero wind_x/y, confidence still 1.0 (truth)."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=0.0, direction=0.5),
            AnemometerAdapterConfig(),
        )
        assert result.wind_x == pytest.approx(0.0)
        assert result.wind_y == pytest.approx(0.0)
        assert result.confidence == pytest.approx(1.0)

    def test_confidence_is_one_for_ground_truth(self) -> None:
        """Anemometer is ground truth → confidence should be 1.0 by default."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=1.0, direction=0.0),
            AnemometerAdapterConfig(),
        )
        assert result.confidence == pytest.approx(1.0)

    def test_max_wind_speed_clamps_high_speeds(self) -> None:
        """Speeds above max_wind_speed are clamped."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=50.0, direction=0.0),
            AnemometerAdapterConfig(max_wind_speed=5.0),
        )
        assert result.wind_x == pytest.approx(5.0)
        assert result.wind_y == pytest.approx(0.0)


class TestSmoothing:
    def test_smoothing_blends_with_previous(self) -> None:
        """smoothing_alpha=0.3 → new = 30% new + 70% previous."""
        prev = WindEstimate(wind_x=1.0, wind_y=0.0, confidence=1.0, timestamp=0.0)
        # New reading: speed=2.0 east (wind_x=2.0)
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=2.0, direction=0.0),
            AnemometerAdapterConfig(smoothing_alpha=0.3),
            previous_estimate=prev,
        )
        # 0.3 * 2.0 + 0.7 * 1.0 = 0.6 + 0.7 = 1.3
        assert result.wind_x == pytest.approx(1.3)
        assert result.wind_y == pytest.approx(0.0)

    def test_smoothing_alpha_one_ignores_previous(self) -> None:
        """smoothing_alpha=1.0 (default) → no blending."""
        prev = WindEstimate(wind_x=10.0, wind_y=10.0, confidence=1.0, timestamp=0.0)
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=1.0, direction=0.0),
            AnemometerAdapterConfig(smoothing_alpha=1.0),
            previous_estimate=prev,
        )
        assert result.wind_x == pytest.approx(1.0)
        assert result.wind_y == pytest.approx(0.0)


class TestImmutability:
    def test_config_is_frozen(self) -> None:
        """Config should be immutable."""
        cfg = AnemometerAdapterConfig()
        with pytest.raises(AttributeError):
            cfg.noise_stddev = 0.5  # type: ignore[misc]

    def test_reading_is_frozen(self) -> None:
        """Reading should be immutable."""
        reading = AnemometerReading(
            wind_speed=1.0,
            wind_direction=0.0,
            sensor_label="test",
            timestamp=0.0,
        )
        with pytest.raises(AttributeError):
            reading.wind_speed = 2.0  # type: ignore[misc]

    def test_wind_estimate_is_frozen(self) -> None:
        """WindEstimate should be immutable."""
        result = convert_anemometer_to_wind_estimate(
            _reading(speed=1.0, direction=0.0),
            AnemometerAdapterConfig(),
        )
        with pytest.raises(AttributeError):
            result.wind_x = 99.0  # type: ignore[misc]
