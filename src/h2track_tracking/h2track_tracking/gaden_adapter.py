"""GasSensor-to-concentration adapter for the GADEN playback path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import math


class GasSensorUnits(IntEnum):
    UNKNOWN = 0
    VOLT = 1
    AMP = 2
    PPM = 3
    PPB = 4
    OHM = 5
    PPMXM = 6
    CENTIGRADE = 100
    RELATIVEHUMIDITY = 101
    NOT_VALID = 255


class HydrogenSensorModel(IntEnum):
    TGS2620 = 0
    TGS2600 = 1
    TGS2611 = 2
    TGS2610 = 3
    TGS2612 = 4

    @classmethod
    def from_mpn(cls, mpn: int | str | None) -> "HydrogenSensorModel | None":
        mapping = {
            50: cls.TGS2620,
            51: cls.TGS2600,
            52: cls.TGS2611,
            53: cls.TGS2610,
            54: cls.TGS2612,
        }
        if mpn is None:
            return None
        try:
            return mapping.get(int(mpn))
        except (TypeError, ValueError):
            return None

    @classmethod
    def air_resistance(cls, model: "HydrogenSensorModel") -> float:
        return _SENSITIVITY_AIR[model] * _R0[model]

    @classmethod
    def mox_raw_from_ppm(cls, model: "HydrogenSensorModel", concentration_ppm: float) -> float:
        if concentration_ppm <= 0.0:
            return cls.air_resistance(model)

        coeff_a, coeff_b = _HYDROGEN_COEFFICIENTS[model]
        rs_over_r0 = coeff_a * math.pow(concentration_ppm, coeff_b)
        rs_over_r0 = min(rs_over_r0, _SENSITIVITY_AIR[model])
        return rs_over_r0 * _R0[model]


@dataclass(frozen=True)
class GasSensorSample:
    raw: float
    raw_units: GasSensorUnits
    raw_air: float = 0.0
    calib_a: float = 0.0
    calib_b: float = 0.0
    technology: int | None = None
    manufacturer: int | str | None = None
    mpn: int | str | None = None


@dataclass(frozen=True)
class GasSensorAdapterConfig:
    sensor_model: HydrogenSensorModel | None = HydrogenSensorModel.TGS2600
    fallback_ohm_scale: float = 0.0
    voltage_scale: float = 1.0
    minimum_concentration_ppm: float = 0.0
    maximum_concentration_ppm: float | None = None


_R0 = {
    HydrogenSensorModel.TGS2620: 3000.0,
    HydrogenSensorModel.TGS2600: 50000.0,
    HydrogenSensorModel.TGS2611: 3740.0,
    HydrogenSensorModel.TGS2610: 3740.0,
    HydrogenSensorModel.TGS2612: 4500.0,
}

_SENSITIVITY_AIR = {
    HydrogenSensorModel.TGS2620: 21.0,
    HydrogenSensorModel.TGS2600: 1.0,
    HydrogenSensorModel.TGS2611: 8.8,
    HydrogenSensorModel.TGS2610: 10.3,
    HydrogenSensorModel.TGS2612: 19.5,
}

_HYDROGEN_COEFFICIENTS = {
    HydrogenSensorModel.TGS2620: (24.45, -0.5546),
    HydrogenSensorModel.TGS2600: (0.6821, -0.3532),
    HydrogenSensorModel.TGS2611: (41.3, -0.3614),
    HydrogenSensorModel.TGS2610: (66.78, -0.4888),
    HydrogenSensorModel.TGS2612: (19.5, 0.0),
}


def convert_gas_sensor_sample(sample: GasSensorSample, config: GasSensorAdapterConfig) -> float:
    if sample.raw_units == GasSensorUnits.PPM:
        concentration = sample.raw
    elif sample.raw_units == GasSensorUnits.PPB:
        concentration = sample.raw / 1000.0
    elif sample.raw_units == GasSensorUnits.VOLT:
        concentration = sample.raw * config.voltage_scale
    elif sample.raw_units == GasSensorUnits.OHM:
        concentration = _convert_ohms_to_ppm(sample, config)
    else:
        concentration = 0.0

    concentration = max(config.minimum_concentration_ppm, concentration)
    if config.maximum_concentration_ppm is not None:
        concentration = min(config.maximum_concentration_ppm, concentration)
    return concentration


def _convert_ohms_to_ppm(sample: GasSensorSample, config: GasSensorAdapterConfig) -> float:
    sensor_model = _resolve_sensor_model(sample, config)
    if sensor_model is None:
        return _fallback_ohm_proxy(sample, config)

    coeff_a, coeff_b = _HYDROGEN_COEFFICIENTS[sensor_model]
    if coeff_b == 0.0:
        return _fallback_ohm_proxy(sample, config)

    raw_air = sample.raw_air or HydrogenSensorModel.air_resistance(sensor_model)
    if raw_air <= 0.0:
        return _fallback_ohm_proxy(sample, config)

    rs_over_r0 = sample.raw * _SENSITIVITY_AIR[sensor_model] / raw_air
    rs_over_r0 = max(rs_over_r0, 1e-9)
    concentration = math.pow(rs_over_r0 / coeff_a, 1.0 / coeff_b)
    if not math.isfinite(concentration):
        return _fallback_ohm_proxy(sample, config)
    return concentration


def _resolve_sensor_model(sample: GasSensorSample, config: GasSensorAdapterConfig) -> HydrogenSensorModel | None:
    inferred = HydrogenSensorModel.from_mpn(sample.mpn)
    return inferred or config.sensor_model


def _fallback_ohm_proxy(sample: GasSensorSample, config: GasSensorAdapterConfig) -> float:
    if config.fallback_ohm_scale <= 0.0:
        return 0.0
    raw_air = sample.raw_air
    if raw_air <= 0.0:
        return sample.raw * config.fallback_ohm_scale
    return max(0.0, (raw_air - sample.raw) * config.fallback_ohm_scale)
