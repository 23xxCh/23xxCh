"""Anemometer adapter — convert GADEN Anemometer readings to WindEstimate.

GADEN's simulated_anemometer (with use_map_ref_system:=true) publishes
wind_speed (m/s) and wind_direction (rad) in map frame, where
wind_direction = atan2(v, u) points in the direction wind blows TOWARDS.

This matches h2track's WindEstimate.wind_x/wind_y convention
(positive = blowing in +X direction).
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AnemometerReading:
    """Anemometer sensor reading (ROS-agnostic)."""

    wind_speed: float       # m/s
    wind_direction: float   # rad (direction wind blows TOWARDS)
    sensor_label: str
    timestamp: float


@dataclass(frozen=True)
class AnemometerAdapterConfig:
    """Configuration for anemometer → WindEstimate conversion."""

    noise_stddev: float = 0.0
    min_confidence: float = 0.0
    smoothing_alpha: float = 1.0
    max_wind_speed: float = 10.0


@dataclass(frozen=True)
class WindEstimate:
    """Wind estimate with confidence (matches tracking.wind_estimator)."""

    wind_x: float
    wind_y: float
    confidence: float
    timestamp: float


def convert_anemometer_to_wind_estimate(
    reading: AnemometerReading,
    config: AnemometerAdapterConfig,
    previous_estimate: WindEstimate | None = None,
) -> WindEstimate:
    """Convert anemometer reading to wind estimate.

    Args:
        reading: Anemometer reading (speed, direction in rad).
        config: Adapter configuration.
        previous_estimate: Optional previous estimate for smoothing.

    Returns:
        WindEstimate with wind_x, wind_y in m/s.
    """
    speed = reading.wind_speed
    # Clamp to max_wind_speed (preserves direction)
    if config.max_wind_speed > 0.0 and speed > config.max_wind_speed:
        speed = config.max_wind_speed
    direction = reading.wind_direction
    new_x = speed * math.cos(direction)
    new_y = speed * math.sin(direction)
    # Exponential smoothing when previous estimate supplied
    alpha = config.smoothing_alpha
    if previous_estimate is not None and 0.0 <= alpha < 1.0:
        wind_x = alpha * new_x + (1.0 - alpha) * previous_estimate.wind_x
        wind_y = alpha * new_y + (1.0 - alpha) * previous_estimate.wind_y
    else:
        wind_x = new_x
        wind_y = new_y
    return WindEstimate(
        wind_x=wind_x,
        wind_y=wind_y,
        confidence=1.0,
        timestamp=reading.timestamp,
    )
