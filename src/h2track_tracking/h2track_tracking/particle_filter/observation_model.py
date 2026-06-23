"""Observation model for particle filter.

Uses an exponential-decay plume model that matches GasFieldModel's
concentration_at() output:  C = S * exp(-λ·d) * plume_bias + noise.

This replaces the old Gaussian-blob model (exp(-d²/2σ²)) which produced
fundamentally different concentration profiles, causing weight collapse
when real gas-field concentrations were fed into the particle filter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .types import ParticleFilterConfig


@dataclass
class GaussianPlumeObservationModel:
    """Exponential-decay plume observation model for gas concentration.

    The expected concentration follows the same formula as GasFieldModel:
        C(d) = source_strength * exp(-decay_rate * d) * plume_bias

    where plume_bias accounts for lateral Gaussian spread and upwind penalty
    (including gas-type-dependent buoyancy from density_ratio).

    Wind components are mutable so they can be updated at runtime from
    /estimated_wind without rebuilding the frozen ParticleFilterConfig.
    """

    config: ParticleFilterConfig
    # Mutable wind state (overrides config defaults when set via set_wind)
    _wind_x: float | None = None
    _wind_y: float | None = None

    def __post_init__(self) -> None:
        # Initialise mutable wind from config so that wind_x/wind_y properties
        # always return a concrete value.
        self._wind_x = self.config.wind_x
        self._wind_y = self.config.wind_y

    def set_wind(self, wind_x: float, wind_y: float) -> None:
        """Update wind components at runtime (e.g. from /estimated_wind)."""
        self._wind_x = float(wind_x)
        self._wind_y = float(wind_y)

    def _get_density_ratio(self) -> float:
        """Look up density_ratio for the configured gas type."""
        try:
            from h2track_gas_sim.gas_types import GasType, get_gas_properties
            gas_enum = GasType(self.config.gas_type)
            return get_gas_properties(gas_enum).density_ratio
        except (ImportError, ValueError):
            return 0.069  # Default to H2

    @property
    def plume_sigma(self) -> float:
        return self.config.plume_sigma

    @property
    def source_strength(self) -> float:
        return self.config.source_strength

    @property
    def observation_sigma(self) -> float:
        return self.config.observation_sigma

    @property
    def decay_rate(self) -> float:
        return self.config.decay_rate

    @property
    def wind_x(self) -> float:
        return self._wind_x if self._wind_x is not None else self.config.wind_x

    @property
    def wind_y(self) -> float:
        return self._wind_y if self._wind_y is not None else self.config.wind_y

    def expected_concentration(
        self,
        source_pos: np.ndarray,
        robot_pos: np.ndarray,
    ) -> float:
        """Calculate expected concentration at robot position.

        Uses exponential-decay plume model matching GasFieldModel:
            C = S * exp(-λ·d) * plume_bias

        plume_bias incorporates:
        - Lateral Gaussian spread: exp(-lateral² / (2σ²))
        - Upwind penalty when robot is upwind of hypothesized source

        Args:
            source_pos: Hypothesized source position [x, y]
            robot_pos: Robot position [x, y]

        Returns:
            Expected concentration at robot position
        """
        dx = float(robot_pos[0] - source_pos[0])
        dy = float(robot_pos[1] - source_pos[1])
        distance = math.hypot(dx, dy)

        if distance < 1e-6:
            return self.source_strength

        # Plume bias: lateral Gaussian spread + upwind penalty
        wind_norm = math.hypot(self.wind_x, self.wind_y)
        if wind_norm > 1e-6:
            wind_dir = (self.wind_x / wind_norm, self.wind_y / wind_norm)
            projection = dx * wind_dir[0] + dy * wind_dir[1]
            lateral_sq = max(0.0, distance * distance - projection * projection)
            plume_bias = math.exp(-lateral_sq / (2.0 * self.plume_sigma**2))
            if projection < 0.0:
                # Upwind penalty using same buoyancy formula as GasFieldModel:
                #   upwind_factor = 0.35 / (density_ratio + 0.3), capped at 0.95
                density_ratio = self._get_density_ratio()
                upwind_factor = 0.35 / (density_ratio + 0.3)
                plume_bias *= min(upwind_factor, 0.95)
        else:
            plume_bias = 1.0

        return self.source_strength * math.exp(-self.decay_rate * distance) * plume_bias

    def likelihood(
        self,
        source_hypothesis: np.ndarray,
        robot_position: np.ndarray,
        observed_concentration: float,
    ) -> float:
        """Calculate observation likelihood.

        Uses a robust likelihood that handles the wide dynamic range of
        gas concentrations.  High observed concentrations strongly
        favour hypotheses that predict high concentrations nearby;
        near-zero observations weakly penalise distant hypotheses.

        Args:
            source_hypothesis: Hypothesized source position [x, y]
            robot_position: Current robot position [x, y]
            observed_concentration: Measured concentration

        Returns:
            Likelihood value [0, 1]
        """
        expected = self.expected_concentration(source_hypothesis, robot_position)

        if observed_concentration < 1e-6:
            # No gas detected — mild preference for distant hypotheses
            # (nearby source would likely produce detectable gas)
            return max(0.01, 1.0 - expected / (self.source_strength + 1.0))

        # Scale observation sigma with expected concentration to handle
        # the wide dynamic range (concentrations span 0–120+)
        sigma = self.observation_sigma * (1.0 + expected)
        error = observed_concentration - expected

        return float(np.exp(-error**2 / (2.0 * sigma**2)))
