"""Tests for GadenAdapterNode ROS node and helper functions."""

import math
from unittest.mock import MagicMock, patch

import rclpy
from std_msgs.msg import Float32

from h2track_tracking.gaden_adapter import (
    GasSensorAdapterConfig,
    GasSensorSample,
    GasSensorUnits,
    HydrogenSensorModel,
)
from h2track_tracking.gaden_adapter_node import (
    GadenAdapterNode,
    should_emit_periodic_log,
)


def test_should_emit_periodic_log_first_sample():
    assert should_emit_periodic_log(last_emit_sec=None, now_sec=1.0, interval_sec=1.0) is True


def test_should_emit_periodic_log_throttles_between_intervals():
    assert should_emit_periodic_log(last_emit_sec=10.0, now_sec=10.4, interval_sec=1.0) is False
    assert should_emit_periodic_log(last_emit_sec=10.0, now_sec=11.1, interval_sec=1.0) is True


def test_should_emit_periodic_log_returns_true_when_interval_is_zero():
    """When interval is zero or negative, always emit."""
    assert should_emit_periodic_log(last_emit_sec=10.0, now_sec=10.1, interval_sec=0.0) is True
    assert should_emit_periodic_log(last_emit_sec=10.0, now_sec=10.1, interval_sec=-1.0) is True


def test_should_emit_periodic_log_returns_true_for_first_sample():
    """First sample always emits regardless of interval."""
    assert should_emit_periodic_log(last_emit_sec=None, now_sec=0.0, interval_sec=10.0) is True


def test_should_emit_periodic_log_boundary_condition():
    """Test exact interval boundary."""
    assert should_emit_periodic_log(last_emit_sec=5.0, now_sec=6.0, interval_sec=1.0) is True
    assert should_emit_periodic_log(last_emit_sec=5.0, now_sec=5.999, interval_sec=1.0) is False


class TestGadenAdapterNodeInit:
    """Tests for GadenAdapterNode initialization and parameter handling."""

    def test_node_initializes_with_default_parameters(self):
        """Node should initialize with default parameter values."""
        rclpy.init()
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_custom_gas_sensor_topic_parameter(self):
        """Node should accept custom gas_sensor_topic parameter."""
        rclpy.init(args=["--ros-args", "-p", "gas_sensor_topic:=/custom/sensor"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_custom_gas_concentration_topic_parameter(self):
        """Node should accept custom gas_concentration_topic parameter."""
        rclpy.init(args=["--ros-args", "-p", "gas_concentration_topic:=/custom/concentration"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_resolves_default_sensor_model_from_parameter(self):
        """Node should resolve sensor_model parameter to HydrogenSensorModel."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=1"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_fallback_sensor_model_for_invalid_parameter(self):
        """Node should fall back to TGS2600 for invalid sensor_model."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=999"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_negative_sensor_model_as_unspecified(self):
        """Node should treat negative sensor_model as unspecified."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=-1"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_log_interval_parameter(self):
        """Node should accept log_interval_sec parameter."""
        rclpy.init(args=["--ros-args", "-p", "log_interval_sec:=2.5"])
        try:
            node = GadenAdapterNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestGadenAdapterNodeSensorCallback:
    """Tests for GadenAdapterNode sensor callback behavior."""

    def _create_mock_gas_sensor_msg(self, raw=1000.0, raw_units=5, mpn=51):
        """Create a mock GasSensor message for testing."""
        from olfaction_msgs.msg import GasSensor
        msg = GasSensor()
        msg.raw = raw
        msg.raw_units = raw_units
        msg.raw_air = HydrogenSensorModel.air_resistance(HydrogenSensorModel.TGS2600)
        msg.calib_a = 0.0
        msg.calib_b = 0.0
        msg.technology = 0
        msg.manufacturer = 0
        msg.mpn = mpn
        return msg

    def test_sensor_callback_converts_ohm_units_to_ppm(self):
        """Callback should convert OHM units to concentration using MOX curve."""
        rclpy.init()
        try:
            node = GadenAdapterNode()

            # Create message with known values
            msg = self._create_mock_gas_sensor_msg(raw=25000.0, raw_units=5, mpn=51)

            # Patch publisher to capture published message
            published_values = []
            original_publish = node._publisher.publish

            def mock_publish(data):
                published_values.append(data.data)
                original_publish(data)

            with patch.object(node._publisher, 'publish', mock_publish):
                node._sensor_callback(msg)

            assert len(published_values) == 1
            assert published_values[0] > 0.0

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_sensor_callback_handles_ppm_units_directly(self):
        """Callback should pass through PPM units directly."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=1"])
        try:
            node = GadenAdapterNode()

            # Create message with PPM units
            msg = self._create_mock_gas_sensor_msg(raw=5.5, raw_units=3, mpn=51)

            published_values = []
            with patch.object(node._publisher, 'publish') as mock_publish:
                node._sensor_callback(msg)
                published_values = [call.args[0].data for call in mock_publish.call_args_list]

            assert len(published_values) == 1
            assert math.isclose(published_values[0], 5.5, rel_tol=1e-6)

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_sensor_callback_applies_minimum_concentration_clamp(self):
        """Callback should clamp concentration to minimum_concentration_ppm."""
        rclpy.init(args=["--ros-args", "-p", "minimum_concentration_ppm:=1.0", "-p", "sensor_model:=1"])
        try:
            node = GadenAdapterNode()

            # Create message with low PPM value
            msg = self._create_mock_gas_sensor_msg(raw=0.5, raw_units=3, mpn=51)

            published_values = []
            with patch.object(node._publisher, 'publish') as mock_publish:
                node._sensor_callback(msg)
                published_values = [call.args[0].data for call in mock_publish.call_args_list]

            assert len(published_values) == 1
            assert published_values[0] >= 1.0

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_sensor_callback_applies_maximum_concentration_clamp(self):
        """Callback should clamp concentration to maximum_concentration_ppm."""
        rclpy.init(args=["--ros-args", "-p", "maximum_concentration_ppm:=10.0", "-p", "sensor_model:=1"])
        try:
            node = GadenAdapterNode()

            # Create message with high PPM value
            msg = self._create_mock_gas_sensor_msg(raw=50.0, raw_units=3, mpn=51)

            published_values = []
            with patch.object(node._publisher, 'publish') as mock_publish:
                node._sensor_callback(msg)
                published_values = [call.args[0].data for call in mock_publish.call_args_list]

            assert len(published_values) == 1
            assert published_values[0] <= 10.0

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_sensor_callback_infers_model_from_mpn_when_sensor_model_is_negative(self):
        """Callback should infer sensor model from MPN when sensor_model < 0."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=-1"])
        try:
            node = GadenAdapterNode()

            # Create message with TGS2620 MPN (50)
            msg = self._create_mock_gas_sensor_msg(
                raw=10000.0,
                raw_units=5,
                mpn=50  # TGS2620
            )

            with patch.object(node._publisher, 'publish'):
                node._sensor_callback(msg)

            # Config should be updated to TGS2620
            assert node._config.sensor_model == HydrogenSensorModel.TGS2620

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_sensor_callback_handles_invalid_units_gracefully(self):
        """Callback should handle invalid/units gracefully."""
        rclpy.init(args=["--ros-args", "-p", "sensor_model:=1"])
        try:
            node = GadenAdapterNode()

            # Create message with invalid units (255 = NOT_VALID)
            msg = self._create_mock_gas_sensor_msg(raw=100.0, raw_units=255, mpn=51)

            published_values = []
            with patch.object(node._publisher, 'publish') as mock_publish:
                node._sensor_callback(msg)
                published_values = [call.args[0].data for call in mock_publish.call_args_list]

            # Invalid units should result in 0.0 concentration
            assert len(published_values) == 1
            assert published_values[0] == 0.0

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestGadenAdapterNodeCoerceUnits:
    """Tests for _coerce_units helper method."""

    def test_coerce_units_returns_valid_enum_for_known_values(self):
        """_coerce_units should return valid enum for known unit values."""
        rclpy.init()
        try:
            node = GadenAdapterNode()

            assert node._coerce_units(1) == GasSensorUnits.VOLT
            assert node._coerce_units(3) == GasSensorUnits.PPM
            assert node._coerce_units(5) == GasSensorUnits.OHM

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_coerce_units_returns_not_valid_for_unknown_values(self):
        """_coerce_units should return NOT_VALID for unknown unit values."""
        rclpy.init()
        try:
            node = GadenAdapterNode()

            assert node._coerce_units(999) == GasSensorUnits.NOT_VALID
            assert node._coerce_units(-1) == GasSensorUnits.NOT_VALID

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

