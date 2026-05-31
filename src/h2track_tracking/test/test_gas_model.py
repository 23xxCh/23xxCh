import math

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D


def test_concentration_is_higher_near_the_source():
    model = GasFieldModel(
        GasFieldParams(
            source_x=0.0,
            source_y=0.0,
            source_strength=120.0,
            decay_rate=0.7,
            plume_stddev=1.2,
            wind_x=0.5,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
    )

    near = model.concentration_at(Pose2D(0.4, 0.0))
    far = model.concentration_at(Pose2D(3.0, 0.0))

    assert near > far
    assert far >= 0.0


def test_concentration_prefers_downwind_samples():
    model = GasFieldModel(
        GasFieldParams(
            source_x=0.0,
            source_y=0.0,
            source_strength=80.0,
            decay_rate=0.5,
            plume_stddev=0.8,
            wind_x=1.0,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
    )

    upwind = model.concentration_at(Pose2D(-1.0, 0.0))
    downwind = model.concentration_at(Pose2D(1.0, 0.0))

    assert downwind > upwind


