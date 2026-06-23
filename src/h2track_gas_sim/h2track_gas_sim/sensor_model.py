"""Realistic gas sensor model for sim2real.

Wraps the ideal GasFieldModel concentration with real sensor effects:
- First-order response dynamics (response/recovery time constant)
- Baseline drift (slow random walk + temperature dependence)
- Measurement noise (ADC quantization + Gaussian)
- Saturation (sensor max reading)
- Optional fault injection (dropout, stuck-at, spike)

This module is pure Python (no ROS dependencies) so it can be
unit-tested in isolation and composed with any gas field model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .gas_model import GasFieldModel
from h2track_utils.types import Pose2D


@dataclass(frozen=True)
class SensorModelConfig:
    """Configuration for realistic gas sensor behaviour.

    Attributes:
        response_tau: Response time constant (seconds). Real H2 sensors
            (MQ-8, electrochemical) typically have τ = 5-30s.
        recovery_tau: Recovery time constant (seconds). Usually 2-5x
            slower than response_tau (sensor desorbs slower than it adsorbs).
        noise_stddev: Gaussian measurement noise (ppm).
        quantization_resolution: ADC resolution (ppm). 0 = disabled.
        saturation: Maximum sensor reading (ppm). 0 = disabled.
        baseline_drift_rate: Stddev of baseline random walk per second (ppm/sqrt(s)).
        baseline_drift_max: Maximum baseline drift magnitude (ppm).
        temperature_coeff: ppm/°C (positive = reading increases with temperature).
        reference_temperature: Temperature at which baseline = 0 (°C).
        cross_sensitivity: Dict mapping gas name to sensitivity (0-1).
            E.g. {"H2": 1.0, "CO": 0.15} means sensor responds to H2 at 100%
            and CO at 15%.
    """
    response_tau: float = 8.0       # seconds
    recovery_tau: float = 20.0     # seconds (slower than response)
    noise_stddev: float = 0.5      # ppm
    quantization_resolution: float = 0.1  # ppm
    saturation: float = 500.0      # ppm
    baseline_drift_rate: float = 0.01  # ppm/sqrt(s)
    baseline_drift_max: float = 2.0     # ppm
    temperature_coeff: float = 0.0      # ppm/°C
    reference_temperature: float = 20.0  # °C
    cross_sensitivity: dict = None  # type: ignore[assignment]


class SensorModel:
    """Realistic gas sensor with first-order dynamics and noise.

    Usage:
        model = GasFieldModel(params)
        sensor = SensorModel(model, SensorModelConfig(response_tau=10.0))
        sensor.update(pose, dt=0.1)
        reading = sensor.reading  # realistic sensor output

    The sensor maintains internal state (baseline drift, smoothed
    concentration) and must be called with consistent dt for accurate
    dynamics.
    """

    def __init__(
        self,
        gas_model: GasFieldModel,
        config: SensorModelConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.gas_model = gas_model
        self.config = config or SensorModelConfig()
        self.rng = rng or random.Random(0)

        # Internal state
        self._smoothed_concentration: float = 0.0  # after first-order dynamics
        self._baseline: float = 0.0                # baseline drift
        self._temperature: float = self.config.reference_temperature
        self._elapsed: float = 0.0                 # total simulated time

        # Fault injection state
        self._fault_stuck: bool = False
        self._fault_stuck_value: float = 0.0
        self._fault_dropout: bool = False
        self._spike_remaining: float = 0.0
        self._spike_amplitude: float = 0.0

    @property
    def reading(self) -> float:
        """Current realistic sensor reading (ppm)."""
        if self._fault_dropout:
            return 0.0
        if self._fault_stuck:
            return self._fault_stuck_value

        # Smoothed concentration + baseline drift + temperature effect
        temp_offset = self.config.temperature_coeff * (
            self._temperature - self.config.reference_temperature
        )
        raw = self._smoothed_concentration + self._baseline + temp_offset

        # Add measurement noise
        if self.config.noise_stddev > 0:
            raw += self.rng.gauss(0.0, self.config.noise_stddev)

        # Add transient spike if active
        if self._spike_remaining > 0:
            raw += self._spike_amplitude

        # Quantization (ADC resolution)
        if self.config.quantization_resolution > 0:
            raw = round(raw / self.config.quantization_resolution) * \
                self.config.quantization_resolution

        # Saturation
        if self.config.saturation > 0:
            raw = min(raw, self.config.saturation)

        return max(0.0, raw)

    def update(
        self,
        pose: Pose2D,
        dt: float = 0.1,
        temperature: float | None = None,
    ) -> float:
        """Advance sensor by dt and return current reading.

        Args:
            pose: Robot pose (position where sensor samples gas field).
            dt: Time step in seconds.
            temperature: Optional ambient temperature (°C). If None,
                keeps previous temperature.

        Returns:
            Realistic sensor reading (ppm).
        """
        if dt <= 0:
            return self.reading

        self._elapsed += dt
        if temperature is not None:
            self._temperature = temperature

        # Sample ideal gas concentration at current pose
        ideal = self.gas_model.concentration_at(pose)

        # Apply cross-sensitivity (if configured)
        # For simplicity, the gas_model already accounts for the primary
        # gas type; cross_sensitivity would matter in multi-gas scenarios.
        # Left as extension point for future multi-gas fields.

        # First-order response dynamics
        # Rising (concentration increasing): use response_tau
        # Falling (concentration decreasing): use recovery_tau (slower)
        if ideal > self._smoothed_concentration:
            tau = self.config.response_tau
        else:
            tau = self.config.recovery_tau
        alpha = 1.0 - math.exp(-dt / tau) if tau > 0 else 1.0
        self._smoothed_concentration += alpha * (ideal - self._smoothed_concentration)

        # Baseline drift: Brownian random walk, bounded
        if self.config.baseline_drift_rate > 0:
            drift_step = self.rng.gauss(0.0, self.config.baseline_drift_rate * math.sqrt(dt))
            self._baseline += drift_step
            # Clamp to max drift
            self._baseline = max(
                -self.config.baseline_drift_max,
                min(self.config.baseline_drift_max, self._baseline)
            )

        # Advance spike fault
        if self._spike_remaining > 0:
            self._spike_remaining -= dt
            if self._spike_remaining <= 0:
                self._spike_amplitude = 0.0
                self._spike_remaining = 0.0

        return self.reading

    # ------------------------------------------------------------------
    # Fault injection (for robustness testing)
    # ------------------------------------------------------------------

    def inject_stuck(self, value: float) -> None:
        """Force sensor to output a fixed value until cleared."""
        self._fault_stuck = True
        self._fault_stuck_value = value

    def inject_dropout(self) -> None:
        """Force sensor to output 0 until cleared."""
        self._fault_dropout = True

    def inject_spike(self, amplitude: float, duration: float) -> None:
        """Add a transient spike of given amplitude for given duration."""
        self._spike_amplitude = amplitude
        self._spike_remaining = duration

    def clear_faults(self) -> None:
        """Clear all injected faults."""
        self._fault_stuck = False
        self._fault_dropout = False
        self._spike_remaining = 0.0
        self._spike_amplitude = 0.0

    @property
    def has_fault(self) -> bool:
        """Whether any fault is currently active."""
        return self._fault_stuck or self._fault_dropout or self._spike_remaining > 0

    def reset(self) -> None:
        """Reset sensor state to initial conditions."""
        self._smoothed_concentration = 0.0
        self._baseline = 0.0
        self._temperature = self.config.reference_temperature
        self._elapsed = 0.0
        self.clear_faults()
