"""Tests for Nav2 startup gate logic and ROS node."""

from unittest.mock import MagicMock, patch

import rclpy

from h2track_tracking.nav2_startup_gate import (
    GateAction,
    Nav2StartupGateConfig,
    Nav2StartupGateState,
)


def test_gate_waits_until_both_tf_and_service_are_ready():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT


def test_gate_requires_stable_ready_samples_before_startup():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=2))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.STARTUP


def test_gate_resets_stability_counter_when_dependency_drops():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=2))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
    assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.WAIT
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=2.0) is GateAction.STARTUP


def test_gate_tracks_startup_request_until_success():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.MONITOR
    assert state.step(tf_ready=True, service_ready=True, startup_result=True, elapsed_sec=1.5) is GateAction.COMPLETE


def test_gate_fails_when_startup_service_returns_failure():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

    assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
    assert state.step(tf_ready=True, service_ready=True, startup_result=False, elapsed_sec=1.0) is GateAction.FAIL


def test_gate_fails_when_timeout_is_reached_before_ready():
    state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=1.0, stable_ready_count=1))

    assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.FAIL


class TestNav2StartupGateStateEdgeCases:
    """Additional edge case tests for Nav2StartupGateState."""

    def test_gate_returns_complete_after_success(self):
        """Gate should continue returning COMPLETE after successful startup."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

        state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5)
        state.step(tf_ready=True, service_ready=True, startup_result=True, elapsed_sec=1.0)
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.COMPLETE
        assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=2.0) is GateAction.COMPLETE

    def test_gate_returns_fail_after_failure(self):
        """Gate should continue returning FAIL after failure."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

        state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5)
        state.step(tf_ready=True, service_ready=True, startup_result=False, elapsed_sec=1.0)
        assert state.step(tf_ready=True, service_ready=True, startup_result=True, elapsed_sec=1.5) is GateAction.FAIL

    def test_gate_waits_when_only_tf_ready(self):
        """Gate should wait when only TF is ready but not service."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

        assert state.step(tf_ready=True, service_ready=False, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT

    def test_gate_waits_when_only_service_ready(self):
        """Gate should wait when only service is ready but not TF."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=5.0, stable_ready_count=1))

        assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
        assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT

    def test_gate_timeout_at_exact_boundary(self):
        """Gate should fail exactly at timeout boundary."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=10.0, stable_ready_count=1))

        assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=9.9) is GateAction.WAIT
        assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=10.0) is GateAction.FAIL

    def test_gate_with_high_stable_ready_count(self):
        """Gate should require exact number of consecutive ready samples."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=30.0, stable_ready_count=5))

        for i in range(4):
            assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=i * 0.5) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=2.0) is GateAction.STARTUP

    def test_gate_resets_counter_when_tf_drops(self):
        """Ready counter should reset when TF becomes unavailable."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=10.0, stable_ready_count=2))

        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
        assert state.step(tf_ready=False, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=2.0) is GateAction.STARTUP

    def test_gate_resets_counter_when_service_drops(self):
        """Ready counter should reset when service becomes unavailable."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=10.0, stable_ready_count=2))

        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=False, startup_result=None, elapsed_sec=1.0) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.5) is GateAction.WAIT
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=2.0) is GateAction.STARTUP

    def test_gate_stays_in_monitor_while_startup_pending(self):
        """Gate should return MONITOR while startup request is pending."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=10.0, stable_ready_count=1))

        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP
        # Multiple steps with no result should stay in MONITOR
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=1.0) is GateAction.MONITOR
        assert state.step(tf_ready=False, service_ready=False, startup_result=None, elapsed_sec=1.5) is GateAction.MONITOR

    def test_gate_with_zero_stable_ready_count(self):
        """Gate with stable_ready_count=0 should startup immediately."""
        state = Nav2StartupGateState(Nav2StartupGateConfig(timeout_sec=30.0, stable_ready_count=0))

        # With zero count, should still require at least one ready
        assert state.step(tf_ready=True, service_ready=True, startup_result=None, elapsed_sec=0.5) is GateAction.STARTUP


class TestNav2StartupGateConfig:
    """Tests for Nav2StartupGateConfig."""

    def test_config_default_values(self):
        """Config should have sensible default values."""
        config = Nav2StartupGateConfig()
        assert config.timeout_sec == 30.0
        assert config.stable_ready_count == 1

    def test_config_custom_values(self):
        """Config should accept custom values."""
        config = Nav2StartupGateConfig(timeout_sec=60.0, stable_ready_count=5)
        assert config.timeout_sec == 60.0
        assert config.stable_ready_count == 5


class TestNav2StartupGateNodeInit:
    """Tests for Nav2StartupGateNode initialization."""

    def test_node_initializes_with_default_parameters(self):
        """Node should initialize with default parameter values."""
        rclpy.init()
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node is not None
            assert node.exit_code == 0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_custom_frame_parameters(self):
        """Node should accept custom target_frame and source_frame parameters."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "target_frame:=custom_odom",
            "-p", "source_frame:=custom_base",
        ])
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node._target_frame == "custom_odom"
            assert node._source_frame == "custom_base"
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_lifecycle_manager_service_parameter(self):
        """Node should accept lifecycle_manager_service parameter."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "lifecycle_manager_service:=/custom/manage_nodes",
        ])
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node._lifecycle_manager_service == "/custom/manage_nodes"
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_timeout_parameters(self):
        """Node should accept timeout and poll period parameters."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "timeout_sec:=45.0",
            "-p", "poll_period_sec:=1.0",
        ])
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node._poll_period_sec == 1.0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_accepts_stable_ready_count_parameter(self):
        """Node should accept stable_ready_count parameter."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "stable_ready_count:=3",
        ])
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node is not None
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestNav2StartupGateNodeExitCode:
    """Tests for Nav2StartupGateNode exit_code behavior."""

    def test_exit_code_defaults_to_zero(self):
        """exit_code property should default to 0."""
        rclpy.init()
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node.exit_code == 0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_has_use_sim_time_parameter(self):
        """Node should have use_sim_time parameter declared."""
        rclpy.init()
        try:
            from h2track_tracking.nav2_startup_gate_node import Nav2StartupGateNode
            node = Nav2StartupGateNode()
            assert node.has_parameter("use_sim_time")
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()
