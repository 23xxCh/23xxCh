import os
from pathlib import Path


_GADEN_WS = Path(os.environ.get("GADEN_WS", "/home/user/gaden_ws"))
GAS_SENSOR_SOURCE = _GADEN_WS / "src" / "gaden" / "simulated_gas_sensor" / "src" / "fake_gas_sensor.cpp"


def test_simulated_gas_sensor_spins_callbacks_before_tf_lookup():
    text = GAS_SENSOR_SOURCE.read_text(encoding="utf-8")

    # The lookupTransform call now includes a timeout parameter
    lookup_pos = text.index("lookupTransform(")
    # Find the spin_some that happens in the wait loops before the main loop
    spin_pos = text.index("rclcpp::spin_some(shared_this);")

    assert spin_pos < lookup_pos


def test_simulated_gas_sensor_waits_for_tf_before_lookup():
    text = GAS_SENSOR_SOURCE.read_text(encoding="utf-8")

    can_transform_pos = text.index("canTransform(")
    # The lookupTransform call now includes a timeout parameter
    lookup_pos = text.index("lookupTransform(")

    assert can_transform_pos < lookup_pos

def test_simulated_gas_sensor_waits_for_frame_registration_before_tf_query():
    text = GAS_SENSOR_SOURCE.read_text(encoding="utf-8")

    fixed_frame_exists_pos = text.index('_frameExists(input_fixed_frame)')
    sensor_frame_exists_pos = text.index('_frameExists(input_sensor_frame)')
    can_transform_pos = text.index("canTransform(")

    assert fixed_frame_exists_pos < can_transform_pos
    assert sensor_frame_exists_pos < can_transform_pos

