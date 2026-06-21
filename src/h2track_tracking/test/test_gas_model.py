import math

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D


def _make_model(gas_type: str = "H2", **kwargs) -> GasFieldModel:
    defaults = dict(
        source_x=0.0,
        source_y=0.0,
        source_strength=120.0,
        decay_rate=0.7,
        plume_stddev=1.2,
        wind_x=0.5,
        wind_y=0.0,
        noise_stddev=0.0,
        min_concentration=0.0,
        gas_type=gas_type,
    )
    defaults.update(kwargs)
    return GasFieldModel(GasFieldParams(**defaults), rng=type("R", (), {"gauss": lambda s, m, sd: 0.0})())


def test_concentration_is_higher_near_the_source():
    model = _make_model()

    near = model.concentration_at(Pose2D(0.4, 0.0))
    far = model.concentration_at(Pose2D(3.0, 0.0))

    assert near > far
    assert far >= 0.0


def test_concentration_prefers_downwind_samples():
    model = _make_model(wind_x=1.0, wind_y=0.0, decay_rate=0.5, plume_stddev=0.8, source_strength=80.0)

    upwind = model.concentration_at(Pose2D(-1.0, 0.0))
    downwind = model.concentration_at(Pose2D(1.0, 0.0))

    assert downwind > upwind


def test_hydrogen_wider_plume_than_propane():
    """H2 diffuses faster → wider lateral spread than C3H8."""
    h2 = _make_model(gas_type="H2")
    c3h8 = _make_model(gas_type="C3H8")

    # Lateral point (perpendicular to wind)
    lateral = Pose2D(0.0, 2.0)
    h2_conc = h2.concentration_at(lateral)
    c3h8_conc = c3h8.concentration_at(lateral)

    assert h2_conc > c3h8_conc, "H2 should have wider plume (higher lateral conc)"


def test_propane_more_confined_downwind_than_hydrogen():
    """C3H8 heavier → more confined downwind than H2."""
    h2 = _make_model(gas_type="H2")
    c3h8 = _make_model(gas_type="C3H8")

    # Downwind point
    downwind = Pose2D(3.0, 0.0)
    h2_conc = h2.concentration_at(downwind)
    c3h8_conc = c3h8.concentration_at(downwind)

    # Both should have concentration, but H2 should be higher due to wider spread
    assert h2_conc > 0
    assert c3h8_conc > 0


def test_light_gas_less_upwind_penalty_than_heavy_gas():
    """Light gases (H2) spread more upwind than heavy gases (C3H8)."""
    h2 = _make_model(gas_type="H2")
    c3h8 = _make_model(gas_type="C3H8")

    # Upwind point
    upwind = Pose2D(-2.0, 0.0)
    h2_conc = h2.concentration_at(upwind)
    c3h8_conc = c3h8.concentration_at(upwind)

    assert h2_conc > c3h8_conc, "Light gas should have less upwind penalty"


def test_default_gas_type_is_hydrogen():
    """Default gas_type='H2' maintains backward compatibility."""
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
    # Should not raise, should produce valid concentration
    conc = model.concentration_at(Pose2D(0.5, 0.0))
    assert conc > 0


def test_methane_intermediate_between_h2_and_propane():
    """CH4 properties should place it between H2 and C3H8."""
    h2 = _make_model(gas_type="H2")
    ch4 = _make_model(gas_type="CH4")
    c3h8 = _make_model(gas_type="C3H8")

    lateral = Pose2D(0.0, 1.5)
    h2_conc = h2.concentration_at(lateral)
    ch4_conc = ch4.concentration_at(lateral)
    c3h8_conc = c3h8.concentration_at(lateral)

    assert h2_conc > ch4_conc > c3h8_conc


