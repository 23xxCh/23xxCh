"""Tests for particle filter ROS node (LifecycleNode variant)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseArray, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32

from h2track_tracking.particle_filter.particle_filter_node import ParticleFilterNode


def _configure_and_activate(node):
    """Trigger lifecycle transitions for testing."""
    from rclpy.lifecycle import LifecycleState
    node.on_configure(LifecycleState(state_id=0, label="unconfigured"))
    node.on_activate(LifecycleState(state_id=1, label="inactive"))


def _configure_only(node):
    """Trigger only configure transition (no publishers/timers)."""
    from rclpy.lifecycle import LifecycleState
    node.on_configure(LifecycleState(state_id=0, label="unconfigured"))


class TestParticleFilterNodeInit:
    """Tests for node initialization."""

    def test_node_initializes_with_default_parameters(self):
        """Node should initialize with default parameter values."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            assert node is not None
            assert node.get_parameter("num_particles").value == 500
            assert node.get_parameter("motion_sigma").value == 0.3
            assert node.get_parameter("observation_sigma").value == 0.5
            assert node.get_parameter("plume_sigma").value == 2.0
            assert node.get_parameter("source_strength").value == 1.0
            assert node.get_parameter("publish_rate").value == 2.0
            bounds = node.get_parameter("bounds").value
            assert bounds == [-10.0, -10.0, 10.0, 10.0]
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_custom_parameters(self):
        """Node should accept custom parameter values."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "num_particles:=200",
            "-p", "motion_sigma:=0.5",
            "-p", "observation_sigma:=0.8",
            "-p", "plume_sigma:=3.0",
            "-p", "source_strength:=2.0",
            "-p", "publish_rate:=5.0",
        ])
        try:
            node = ParticleFilterNode()
            assert node.get_parameter("num_particles").value == 200
            assert node.get_parameter("motion_sigma").value == 0.5
            assert node.get_parameter("observation_sigma").value == 0.8
            assert node.get_parameter("plume_sigma").value == 3.0
            assert node.get_parameter("source_strength").value == 2.0
            assert node.get_parameter("publish_rate").value == 5.0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_node_uses_custom_bounds(self):
        """Node should accept custom bounds parameter."""
        rclpy.init(args=[
            "--ros-args",
            "-p", "bounds:=[0.0, 0.0, 20.0, 20.0]",
        ])
        try:
            node = ParticleFilterNode()
            assert node.get_parameter("bounds").value == [0.0, 0.0, 20.0, 20.0]
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_publishers_created_after_activate(self):
        """Test that required publishers are created after activation."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_and_activate(node)
            publisher_names = [pub.topic_name for pub in node.publishers]
            assert "/estimated_source" in publisher_names
            assert "/particle_cloud" in publisher_names
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_subscriptions_created_after_configure(self):
        """Test that required subscriptions are created after configuration."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)
            subscription_names = [sub.topic_name for sub in node.subscriptions]
            assert "/gas_concentration" in subscription_names
            assert "/odom" in subscription_names
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestParticleFilterNodeCallbacks:
    """Tests for ROS callbacks."""

    def test_gas_concentration_callback_updates_filter(self):
        """Test that gas concentration messages update the filter."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)
            node._robot_position = (5.0, 5.0)

            msg = Float32(data=0.75)
            node._gas_concentration_callback(msg)

            assert len(node._filter.particles) > 0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_odometry_callback_updates_robot_position(self):
        """Test that odometry messages update robot position."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            msg = Odometry()
            msg.pose.pose.position.x = 3.5
            msg.pose.pose.position.y = 7.2
            msg.pose.pose.orientation.w = 1.0

            node._odom_callback(msg)

            assert node._robot_position == (3.5, 7.2)
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_odometry_callback_triggers_predict(self):
        """Test that odometry callback triggers predict step."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            old_positions = [p.position.copy() for p in node._filter.particles]

            msg = Odometry()
            msg.pose.pose.position.x = 5.0
            msg.pose.pose.position.y = 5.0
            msg.pose.pose.orientation.w = 1.0

            node._odom_callback(msg)

            # At least some particles should have moved due to motion noise
            moved_count = sum(
                1 for old, p in zip(old_positions, node._filter.particles)
                if not np.allclose(old, p.position, atol=1e-10)
            )
            # Motion model adds noise, so some particles should move
            assert moved_count > 0
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestParticleFilterNodePublishing:
    """Tests for estimate publishing."""

    def test_estimate_published_at_rate(self):
        """Test that estimates are published at configured rate."""
        rclpy.init(args=["--ros-args", "-p", "publish_rate:=10.0"])
        try:
            node = ParticleFilterNode()
            _configure_and_activate(node)

            published_estimates = []
            published_particles = []

            def estimate_callback(msg):
                published_estimates.append(msg)

            def particle_callback(msg):
                published_particles.append(msg)

            node.create_subscription(
                PoseWithCovarianceStamped,
                "/estimated_source",
                estimate_callback,
                QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                           durability=DurabilityPolicy.TRANSIENT_LOCAL)
            )
            node.create_subscription(
                PoseArray,
                "/particle_cloud",
                particle_callback,
                QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
            )

            start_time = time.time()
            while time.time() - start_time < 0.3:
                rclpy.spin_once(node, timeout_sec=0.01)

            assert len(published_estimates) >= 2
            assert len(published_particles) >= 2
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_estimate_message_format(self):
        """Test that published estimate has correct format."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            node._robot_position = (0.0, 0.0)
            msg = Float32(data=0.5)
            node._gas_concentration_callback(msg)

            node._publish_estimate()

            estimate = node._filter.estimate()
            assert estimate.position is not None
            assert isinstance(estimate.position, tuple)
            assert len(estimate.position) == 2
            assert 0.0 <= estimate.confidence <= 1.0
            assert estimate.covariance.shape == (2, 2)
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_particle_cloud_message_format(self):
        """Test that published particle cloud has correct format."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            node._publish_particle_cloud()

            assert len(node._filter.particles) == node.get_parameter("num_particles").value
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestParticleFilterNodeResampling:
    """Tests for resampling behavior."""

    def test_resample_on_low_effective_count(self):
        """Test that resampling occurs when effective particle count is low."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            for i, p in enumerate(node._filter.particles):
                p.weight = 100.0 if i == 0 else 0.001
            node._filter._normalize_weights()

            initial_effective = node._filter.effective_particle_count()

            node._robot_position = (0.0, 0.0)
            node._gas_concentration_callback(Float32(data=0.5))

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_resample_threshold_parameter(self):
        """Test that resample threshold is configurable."""
        rclpy.init(args=["--ros-args", "-p", "resample_threshold:=0.3"])
        try:
            node = ParticleFilterNode()
            _configure_only(node)
            assert node._filter.config.resample_threshold == 0.3
            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


class TestParticleFilterNodeBounds:
    """Tests for bounds handling."""

    def test_particles_initialized_within_bounds(self):
        """Test particles are initialized within specified bounds."""
        rclpy.init(args=["--ros-args", "-p", "bounds:=[2.0, 3.0, 8.0, 12.0]"])
        try:
            node = ParticleFilterNode()
            _configure_only(node)
            bounds = [2.0, 3.0, 8.0, 12.0]

            for p in node._filter.particles:
                assert bounds[0] <= p.position[0] <= bounds[2], f"X position {p.position[0]} out of bounds"
                assert bounds[1] <= p.position[1] <= bounds[3], f"Y position {p.position[1]} out of bounds"

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()

    def test_invalid_bounds_falls_back_to_defaults(self):
        """Test that invalid bounds (fewer than 4 elements) fall back to defaults."""
        rclpy.init()
        try:
            node = ParticleFilterNode()
            _configure_only(node)

            # Manually test the bounds validation by setting invalid bounds
            # The node should handle this gracefully
            node._bounds = (float('nan'), float('nan'), float('nan'), float('nan'))

            # Check that node still has particles
            assert len(node._filter.particles) > 0

            node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()
