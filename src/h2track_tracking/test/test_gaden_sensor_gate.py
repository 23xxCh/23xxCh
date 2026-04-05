"""Tests for GADEN sensor gate logic and ROS node."""

import subprocess
from unittest.mock import MagicMock, patch

import rclpy

from h2track_tracking.gaden_sensor_gate import (
    GateAction,
    SensorGateConfig,
    SensorGateState,
    build_sensor_process_command,
)


def test_gate_waits_until_transform_is_available():
    gate = SensorGateState(SensorGateConfig(timeout_sec=20.0, poll_period_sec=0.5))

    action = gate.step(has_transform=False, elapsed_sec=5.0)

    assert action is GateAction.WAIT


def test_gate_launches_once_after_transform_becomes_available():
    gate = SensorGateState(SensorGateConfig(timeout_sec=20.0, poll_period_sec=0.5))

    assert gate.step(has_transform=False, elapsed_sec=2.0) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=3.0) is GateAction.LAUNCH
    assert gate.step(has_transform=True, elapsed_sec=4.0) is GateAction.RUNNING


def test_gate_requires_multiple_ready_checks_before_launch():
    gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, poll_period_sec=0.5, stable_ready_count=3))

    assert gate.step(has_transform=True, elapsed_sec=1.0) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=1.5) is GateAction.WAIT
    assert gate.step(has_transform=True, elapsed_sec=2.0) is GateAction.LAUNCH


def test_gate_times_out_if_transform_never_appears():
    gate = SensorGateState(SensorGateConfig(timeout_sec=12.0, poll_period_sec=0.5))

    action = gate.step(has_transform=False, elapsed_sec=12.1)

    assert action is GateAction.FAIL


def test_sensor_process_command_preserves_sensor_parameters():
    command = build_sensor_process_command(
        executable_path='/opt/ros/humble/lib/simulated_gas_sensor/simulated_gas_sensor',
        use_sim_time=True,
        topic='/gaden/sensor_reading',
        fixed_frame='gaden_map',
        sensor_frame='base_link',
        sensor_model=30,
        rate=5.0,
        use_pid_correction_factors=False,
        sensor_node_name='gaden_pid_sensor',
    )

    assert command[:2] == [
        '/opt/ros/humble/lib/simulated_gas_sensor/simulated_gas_sensor',
        '--ros-args',
    ]
    assert '-r' in command
    assert '__node:=gaden_pid_sensor' in command
    assert 'use_sim_time:=true' in command
    assert 'topic:=/gaden/sensor_reading' in command
    assert 'fixed_frame:=gaden_map' in command
    assert 'sensor_frame:=base_link' in command
    assert 'sensor_model:=30' in command
    assert 'rate:=5.0' in command
    assert 'use_PID_correction_factors:=false' in command


class TestSensorGateStateEdgeCases:
    """Additional edge case tests for SensorGateState."""

    def test_gate_resets_ready_count_when_transform_disappears(self):
        """Ready count should reset if transform becomes unavailable."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, stable_ready_count=2))

        # First transform available
        assert gate.step(has_transform=True, elapsed_sec=1.0) is GateAction.WAIT
        # Transform disappears
        assert gate.step(has_transform=False, elapsed_sec=1.5) is GateAction.WAIT
        # Transform appears again - count should restart
        assert gate.step(has_transform=True, elapsed_sec=2.0) is GateAction.WAIT
        # Second consecutive ready
        assert gate.step(has_transform=True, elapsed_sec=2.5) is GateAction.LAUNCH

    def test_gate_returns_fail_after_timeout_regardless_of_previous_state(self):
        """Once timed out, gate should continue returning FAIL."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=5.0))

        assert gate.step(has_transform=False, elapsed_sec=5.1) is GateAction.FAIL
        assert gate.step(has_transform=True, elapsed_sec=6.0) is GateAction.FAIL

    def test_gate_returns_running_after_launch(self):
        """After launch, gate should continue returning RUNNING."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, stable_ready_count=1))

        assert gate.step(has_transform=True, elapsed_sec=1.0) is GateAction.LAUNCH
        assert gate.step(has_transform=True, elapsed_sec=2.0) is GateAction.RUNNING
        assert gate.step(has_transform=False, elapsed_sec=3.0) is GateAction.RUNNING

    def test_gate_with_zero_stable_ready_count(self):
        """Gate with stable_ready_count=0 should launch immediately on first ready."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, stable_ready_count=0))

        # With zero count, should still require at least one ready
        assert gate.step(has_transform=True, elapsed_sec=1.0) is GateAction.LAUNCH

    def test_gate_with_high_stable_ready_count(self):
        """Gate should require exact number of consecutive ready samples."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=30.0, stable_ready_count=5))

        for i in range(4):
            assert gate.step(has_transform=True, elapsed_sec=i * 0.5) is GateAction.WAIT
        assert gate.step(has_transform=True, elapsed_sec=2.0) is GateAction.LAUNCH

    def test_gate_timeout_at_exact_boundary(self):
        """Gate should fail exactly at timeout boundary."""
        gate = SensorGateState(SensorGateConfig(timeout_sec=10.0))

        assert gate.step(has_transform=False, elapsed_sec=9.9) is GateAction.WAIT
        assert gate.step(has_transform=False, elapsed_sec=10.0) is GateAction.FAIL


class TestBuildSensorProcessCommand:
    """Tests for build_sensor_process_command edge cases."""

    def test_command_with_use_sim_time_false(self):
        """Command should include use_sim_time:=false when disabled."""
        command = build_sensor_process_command(
            executable_path='/path/to/sensor',
            use_sim_time=False,
            topic='/topic',
            fixed_frame='map',
            sensor_frame='base',
            sensor_model=1,
            rate=10.0,
            use_pid_correction_factors=True,
            sensor_node_name='test_sensor',
        )

        assert 'use_sim_time:=false' in command
        assert 'use_PID_correction_factors:=true' in command

    def test_command_with_special_characters_in_frame_names(self):
        """Command should handle special characters in frame names."""
        command = build_sensor_process_command(
            executable_path='/path/to/sensor',
            use_sim_time=True,
            topic='/gaden/sensor',
            fixed_frame='odom_combined',
            sensor_frame='robot_base_link',
            sensor_model=30,
            rate=5.0,
            use_pid_correction_factors=False,
            sensor_node_name='sensor_node_1',
        )

        assert 'fixed_frame:=odom_combined' in command
        assert 'sensor_frame:=robot_base_link' in command

    def test_command_with_float_rate(self):
        """Command should format float rate values correctly."""
        command = build_sensor_process_command(
            executable_path='/path/to/sensor',
            use_sim_time=True,
            topic='/topic',
            fixed_frame='map',
            sensor_frame='base',
            sensor_model=1,
            rate=10.5,
            use_pid_correction_factors=False,
            sensor_node_name='sensor',
        )

        assert 'rate:=10.5' in command


class TestGadenSensorGateNodeInit:
    """Tests for GadenSensorGateNode initialization."""

    def test_node_initializes_with_default_parameters(self):
        """Node should initialize with default parameter values."""
        rclpy.init()
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node is not None
            assert node.exit_code == 0
            node.shutdown()
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_custom_frame_parameters(self):
        """Node should accept custom fixed_frame and sensor_frame parameters."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "fixed_frame:=custom_map",
            "-p", "sensor_frame:=custom_base",
        ])
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node._fixed_frame == "custom_map"
            assert node._sensor_frame == "custom_base"
            node.shutdown()
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_timeout_parameters(self):
        """Node should accept timeout and poll period parameters."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "timeout_sec:=60.0",
            "-p", "poll_period_sec:=1.0",
        ])
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node._poll_period_sec == 1.0
            node.shutdown()
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_sensor_parameters(self):
        """Node should accept sensor configuration parameters."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "sensor_model:=20",
            "-p", "rate:=10.0",
            "-p", "topic:=/custom/sensor",
        ])
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node is not None
            node.shutdown()
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestGadenSensorGateNodeShutdown:
    """Tests for GadenSensorGateNode shutdown behavior."""

    def test_shutdown_sets_shutting_down_flag(self):
        """shutdown() should set the _shutting_down flag."""
        rclpy.init()
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node._shutting_down is False
            node.shutdown()
            assert node._shutting_down is True
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_shutdown_handles_none_process(self):
        """shutdown() should handle case where process is None."""
        rclpy.init()
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node._process is None
            node.shutdown()  # Should not raise
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_exit_code_defaults_to_zero(self):
        """exit_code property should default to 0."""
        rclpy.init()
        try:
            from h2track_tracking.gaden_sensor_gate_node import GadenSensorGateNode
            node = GadenSensorGateNode()
            assert node.exit_code == 0
            node.shutdown()
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()
