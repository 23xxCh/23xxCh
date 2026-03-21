import math

from h2track_tracking.gaden_adapter import (
    GasSensorAdapterConfig,
    GasSensorSample,
    GasSensorUnits,
    HydrogenSensorModel,
    convert_gas_sensor_sample,
)


def test_ppm_units_pass_through():
    sample = GasSensorSample(raw=12.5, raw_units=GasSensorUnits.PPM)

    concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())

    assert concentration == 12.5


def test_ppb_units_convert_to_ppm():
    sample = GasSensorSample(raw=2500.0, raw_units=GasSensorUnits.PPB)

    concentration = convert_gas_sensor_sample(sample, GasSensorAdapterConfig())

    assert concentration == 2.5


def test_ohm_units_invert_mox_hydrogen_curve():
    concentration_ppm = 8.0
    model = HydrogenSensorModel.TGS2600
    sample = GasSensorSample(
        raw=HydrogenSensorModel.mox_raw_from_ppm(model, concentration_ppm),
        raw_units=GasSensorUnits.OHM,
        raw_air=HydrogenSensorModel.air_resistance(model),
        manufacturer="FIGARO",
        mpn="TGS2600",
    )

    concentration = convert_gas_sensor_sample(
        sample,
        GasSensorAdapterConfig(sensor_model=model),
    )

    assert math.isclose(concentration, concentration_ppm, rel_tol=1e-3)


def test_unsupported_ohm_units_fall_back_to_scale():
    sample = GasSensorSample(raw=2000.0, raw_units=GasSensorUnits.OHM, raw_air=4000.0)

    concentration = convert_gas_sensor_sample(
        sample,
        GasSensorAdapterConfig(sensor_model=None, fallback_ohm_scale=0.002),
    )

    assert math.isclose(concentration, 4.0, rel_tol=1e-6)
