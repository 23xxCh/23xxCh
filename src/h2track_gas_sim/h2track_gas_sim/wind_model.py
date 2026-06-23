"""Time-varying wind field model for realistic simulation.

Real wind is not constant — it has:
- Slow direction variation (Gaussian random walk on bearing)
- Gust fluctuations (intermittent speed spikes)
- Optional spatial variation (uniform + shear)

This module generates time-varying wind vectors that can be fed
to GasFieldModel via periodic parameter updates, enabling more
realistic sim2real testing where the plume meanders over time.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class WindModelConfig:
    """Configuration for time-varying wind.

    Attributes:
        mean_speed: Mean wind speed (m/s).
        mean_direction_deg: Mean wind direction in degrees (0 = +X, 90 = +Y).
        direction_stddev_deg: Stddev of direction fluctuations (degrees).
        gust_rate: Expected gust events per second (Poisson process).
        gust_strength_factor: Gust amplitude as fraction of mean speed.
        gust_duration: Mean gust duration (seconds, exponential).
        direction_smoothing: Exponential smoothing factor (0-1).
            Higher = faster response to new wind samples.
        seed: Random seed (-1 = system entropy).
    """
    mean_speed: float = 0.4
    mean_direction_deg: float = 0.0
    direction_stddev_deg: float = 15.0
    gust_rate: float = 0.05         # ~1 gust every 20s
    gust_strength_factor: float = 0.5
    gust_duration: float = 3.0     # seconds
    direction_smoothing: float = 0.1
    seed: int = -1


class TimeVaryingWindModel:
    """Generates time-varying wind vectors for realistic plume meandering.

    Usage:
        wind_model = TimeVaryingWindModel(WindModelConfig(mean_speed=0.4))
        wind_model.update(dt=0.1)
        wx, wy = wind_model.wind_x, wind_model.wind_y

    The model uses:
    - Gaussian random walk on wind direction (O-U process)
    - Poisson gust events with exponential duration
    - Exponential smoothing for continuity

    Integration with GasFieldModel: periodically call
    `gas_model.params = replace(gas_model.params, wind_x=wx, wind_y=wy)`
    or update the node's parameters via set_parameter.
    """

    def __init__(self, config: WindModelConfig | None = None) -> None:
        self.config = config or WindModelConfig()
        seed = self.config.seed if self.config.seed >= 0 else None
        self.rng = random.Random(seed)

        # Current state
        mean_rad = math.radians(self.config.mean_direction_deg)
        self._direction = mean_rad
        self._speed = self.config.mean_speed
        self._gust_remaining = 0.0
        self._gust_amplitude = 0.0
        self._elapsed = 0.0

    @property
    def wind_x(self) -> float:
        """Current wind X component (m/s)."""
        return self._speed * math.cos(self._direction) + self._gust_amplitude * math.cos(self._direction)

    @property
    def wind_y(self) -> float:
        """Current wind Y component (m/s)."""
        return self._speed * math.sin(self._direction) + self._gust_amplitude * math.sin(self._direction)

    @property
    def speed(self) -> float:
        """Current total wind speed (m/s)."""
        return math.hypot(self.wind_x, self.wind_y)

    @property
    def direction_deg(self) -> float:
        """Current wind direction in degrees."""
        return math.degrees(math.atan2(self.wind_y, self.wind_x))

    @property
    def gust_active(self) -> bool:
        """Whether a gust is currently active."""
        return self._gust_remaining > 0

    @property
    def elapsed(self) -> float:
        """Elapsed simulated time (seconds)."""
        return self._elapsed

    def update(self, dt: float) -> tuple[float, float]:
        """Advance wind model by dt seconds.

        Args:
            dt: Time step in seconds.

        Returns:
            (wind_x, wind_y) tuple at current time.
        """
        if dt <= 0:
            return self.wind_x, self.wind_y

        self._elapsed += dt

        # Direction random walk (Ornstein-Uhlenbeck process toward mean)
        mean_rad = math.radians(self.config.mean_direction_deg)
        sigma = math.radians(self.config.direction_stddev_deg)
        # O-U process: dθ = -κ(θ - θ_mean)dt + σ dW
        # κ controls how strongly wind reverts to mean direction.
        # Stationary std-dev = σ / sqrt(2κ). With κ=0.5, σ=45° → std=45°/√1.0=45°.
        # The average of N samples has std 45°/sqrt(N), so averages converge to mean.
        kappa = 0.5  # 1/s — reversion timescale ~2s
        drift = -kappa * (self._direction - mean_rad) * dt
        noise = self.rng.gauss(0.0, sigma * math.sqrt(dt))
        self._direction += drift + noise

        # Speed: mild fluctuation around mean
        speed_noise = self.rng.gauss(0.0, 0.02 * self.config.mean_speed * math.sqrt(dt))
        self._speed = max(0.0, self._speed + speed_noise)
        # Pull toward mean speed
        self._speed += 0.01 * (self.config.mean_speed - self._speed) * dt

        # Gust events (Poisson process)
        if self._gust_remaining <= 0:
            # Check for new gust
            p_gust = self.config.gust_rate * dt
            if self.rng.random() < p_gust:
                self._gust_remaining = self.rng.expovariate(1.0 / self.config.gust_duration)
                self._gust_amplitude = (
                    self.config.mean_speed * self.config.gust_strength_factor
                    * self.rng.uniform(0.5, 1.5)
                )
        else:
            # Decay gust
            self._gust_remaining -= dt
            if self._gust_remaining <= 0:
                self._gust_amplitude = 0.0
                self._gust_remaining = 0.0

        return self.wind_x, self.wind_y

    def reset(self) -> None:
        """Reset wind model to initial mean state."""
        mean_rad = math.radians(self.config.mean_direction_deg)
        self._direction = mean_rad
        self._speed = self.config.mean_speed
        self._gust_remaining = 0.0
        self._gust_amplitude = 0.0
        self._elapsed = 0.0
