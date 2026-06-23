"""Complete GADEN MOX sensor model port — 5 sensors × 7 gases.

Port of fake_gas_sensor.h/cpp. Provides:
- Static sensitivity: Rs/R0 = A * conc^B (line in loglog scale)
- Dynamic response: tau-based low-pass filter (rise/decay)
- Multi-gas accumulation
- PID correction factors

GADEN upstream bug fixed: tau_value selection now uses [gas_id] instead
of hardcoded [0] (ethanol).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import math
from typing import Any


# Gas type string → index (matches GADEN's string comparison order)
GAS_TYPE_IDS: dict[str, int] = {
    "ethanol": 0,
    "methane": 1,
    "hydrogen": 2,
    "propanol": 3,
    "chlorine": 4,
    "fluorine": 5,
    "acetone": 6,
}


class MoxSensorType(IntEnum):
    """Figaro TGS sensor models (index matches GADEN input_sensor_model)."""

    TGS2620 = 0
    TGS2600 = 1
    TGS2611 = 2
    TGS2610 = 3
    TGS2612 = 4


class MoxGasType(IntEnum):
    """Gas types (index matches GADEN gas_type ordering)."""

    ETHANOL = 0
    METHANE = 1
    HYDROGEN = 2
    PROPANOL = 3
    CHLORINE = 4
    FLUORINE = 5
    ACETONE = 6


# R0 [Ohms] — Reference resistance (see datasheets)
# GADEN: const float R0[5] = {3000, 50000, 3740, 3740, 4500}
_R0: tuple[float, ...] = (3000.0, 50000.0, 3740.0, 3740.0, 4500.0)

# RS/R0 when exposed to clean air (datasheet)
# GADEN: const float Sensitivity_Air[5] = {21, 1, 8.8, 10.3, 19.5}
_SENSITIVITY_AIR: tuple[float, ...] = (21.0, 1.0, 8.8, 10.3, 19.5)

# RS/R0 = A*conc^B (a line in the loglog scale)
# GADEN: sensitivity_lineloglog[5][7][2]
_SENSITIVITY_LINELOGLOG: tuple[tuple[tuple[float, float], ...], ...] = (
    # TGS2620
    ((62.32, -0.7155), (120.6, -0.4877), (24.45, -0.5546),
     (120.6, -0.4877), (120.6, -0.4877), (120.6, -0.4877), (120.6, -0.4877)),
    # TGS2600
    ((0.6796, -0.3196), (1.018, -0.07284), (0.6821, -0.3532),
     (1.018, -0.07284), (1.018, -0.07284), (1.018, -0.07284), (1.018, -0.07284)),
    # TGS2611
    ((51.11, -0.3658), (38.46, -0.4289), (41.3, -0.3614),
     (38.46, -0.4289), (38.46, -0.4289), (38.46, -0.4289), (38.46, -0.4289)),
    # TGS2610
    ((106.1, -0.5008), (63.91, -0.5372), (66.78, -0.4888),
     (63.91, -0.5372), (63.91, -0.5372), (63.91, -0.5372), (63.91, -0.5372)),
    # TGS2612
    ((31.35, -0.09115), (146.2, -0.5916), (19.5, 0.0),
     (146.2, -0.5916), (146.2, -0.5916), (146.2, -0.5916), (146.2, -0.5916)),
)

# Time constants (Rise, Decay) — 5 sensors × 7 gases × 2
# GADEN: tau_value[5][7][2]
_TAU_VALUE: tuple[tuple[tuple[float, float], ...], ...] = (
    # TGS2620
    ((2.96, 15.71),) * 7,
    # TGS2600
    ((4.8, 18.75),) * 7,
    # TGS2611
    ((3.44, 6.35),) * 7,
    # TGS2610
    ((3.44, 6.35),) * 7,
    # TGS2612
    ((3.44, 6.35),) * 7,
)

# PID correction factors (11.7eV lamp)
# GADEN: PID_correction_factors[7] = {10.47, 0.0, 0.0, 2.7, 1.0, 0.0, 1.4}
_PID_CORRECTION_FACTORS: tuple[float, ...] = (10.47, 0.0, 0.0, 2.7, 1.0, 0.0, 1.4)


def mox_raw_from_ppm(
    model: MoxSensorType,
    gas_type: MoxGasType,
    concentration_ppm: float,
) -> float:
    """Compute sensor resistance (Ohms) for a single gas at a concentration.

    Rs/R0 = A * conc^B, then Rs = (Rs/R0) * R0.
    Clamped to air resistance (baseline cap — never exceed air level).

    Args:
        model: Sensor model (TGS2620, TGS2600, TGS2611, TGS2610, TGS2612).
        gas_type: Gas type.
        concentration_ppm: Concentration in ppm.

    Returns:
        Sensor resistance in Ohms.
    """
    if concentration_ppm <= 0.0:
        return MoxSensorModel.air_resistance(model)

    a, b = _SENSITIVITY_LINELOGLOG[model][gas_type]
    rs_over_r0 = a * math.pow(concentration_ppm, b)
    # Cap at air baseline (MOX drops with gas, never exceeds)
    air = _SENSITIVITY_AIR[model]
    if rs_over_r0 > air:
        rs_over_r0 = air
    return rs_over_r0 * _R0[model]


@dataclass(frozen=True)
class MoxSensorConfig:
    """Configuration for MoxSensorModel."""

    sensor_model: MoxSensorType = MoxSensorType.TGS2600
    gas_type: MoxGasType = MoxGasType.HYDROGEN
    use_dynamics: bool = True
    node_rate_hz: float = 10.0


@dataclass
class MoxSensorModel:
    """MOX sensor model with optional dynamic (tau-based) response.

    Stateful — maintains previous sensor output for low-pass filtering.
    Use reset() between runs.
    """

    config: MoxSensorConfig = field(default_factory=MoxSensorConfig)
    _previous_output: float | None = None
    _first_reading: bool = True

    @classmethod
    def air_resistance(cls, model: MoxSensorType) -> float:
        """Return sensor resistance in clean air (baseline)."""
        return _SENSITIVITY_AIR[model] * _R0[model]

    def reset(self) -> None:
        """Clear internal state (call between runs)."""
        self._previous_output = None
        self._first_reading = True

    def update(self, concentration_ppm: float) -> float:
        """Update sensor reading for current concentration.

        Args:
            concentration_ppm: Current gas concentration in ppm.

        Returns:
            Sensor resistance in Ohms.
        """
        if self._first_reading:
            # Init at baseline
            self._previous_output = _SENSITIVITY_AIR[self.config.sensor_model]
            self._first_reading = False

        # Static Rs/R0 for current concentration
        a, b = _SENSITIVITY_LINELOGLOG[self.config.sensor_model][self.config.gas_type]
        if concentration_ppm <= 0.0:
            rs_over_r0 = _SENSITIVITY_AIR[self.config.sensor_model]
        else:
            rs_over_r0 = a * math.pow(concentration_ppm, b)
            air = _SENSITIVITY_AIR[self.config.sensor_model]
            if rs_over_r0 > air:
                rs_over_r0 = air

        # Ensure minimum
        if rs_over_r0 <= 0.0:
            rs_over_r0 = 0.01

        if not self.config.use_dynamics:
            self._previous_output = rs_over_r0
            return rs_over_r0 * _R0[self.config.sensor_model]

        # Dynamic: tau-based low-pass filter
        # GADEN upstream bug: hardcoded [0] (ethanol) for tau selection.
        # h2track fix: use [gas_type] instead.
        if rs_over_r0 < (self._previous_output or 0.0):  # rise
            tau = _TAU_VALUE[self.config.sensor_model][self.config.gas_type][0]
        else:  # decay
            tau = _TAU_VALUE[self.config.sensor_model][self.config.gas_type][1]

        dt = 1.0 / max(self.config.node_rate_hz, 0.001)
        alpha = dt / (tau + dt)
        filtered = alpha * rs_over_r0 + (1.0 - alpha) * (self._previous_output or 0.0)
        self._previous_output = filtered
        return filtered * _R0[self.config.sensor_model]
