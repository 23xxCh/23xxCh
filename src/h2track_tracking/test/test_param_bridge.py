"""Tests for bt_node_runner.param_bridge — parameter declaration and config construction."""

from __future__ import annotations

import pytest
import rclpy
from rclpy.node import Node

from h2track_tracking.bt_node_runner.param_bridge import (
    declare_parameters,
    build_mission_config,
    build_surge_config,
    build_fusion_config,
)
from h2track_tracking.mission_logic import MissionConfig
from h2track_tracking.tracking.types import SurgeCastConfig
from h2track_tracking.tracking.fusion import FusionConfig


@pytest.fixture
def node():
    rclpy.init()
    n = Node("test_param_bridge")
    declare_parameters(n)
    yield n
    n.destroy_node()
    rclpy.shutdown()


class TestDeclareParameters:
    def test_declares_all_parameters(self, node):
        expected = [
            "initial_pose_x", "initial_pose_y", "initial_pose_yaw",
            "patrol_points", "enter_threshold", "exit_threshold",
            "source_threshold", "confirm_samples", "track_exit_samples",
            "source_radius", "source_hold_steps", "track_timeout_sec",
            "adaptive_source_ratio", "source_x", "source_y",
            "patrol_goal_timeout_sec", "goal_reject_retry_sec",
            "localizer_node", "use_slam", "publish_initial_pose",
            "use_particle_filter_estimate", "particle_filter_min_confidence",
            "use_surge_cast", "surge_step", "cast_step",
            "cast_distance_limit", "wind_x", "wind_y",
            "estimate_wind", "wind_estimation_min_samples",
            "use_fusion", "fusion_mode", "fusion_pf_weight",
            "fusion_surge_weight",
        ]
        for name in expected:
            assert node.has_parameter(name), f"Missing parameter: {name}"

    def test_default_values_match_dataclass_defaults(self, node):
        mc = MissionConfig(patrol_points=[])
        sc = SurgeCastConfig()
        assert float(node.get_parameter("enter_threshold").value) == mc.enter_threshold
        assert float(node.get_parameter("exit_threshold").value) == mc.exit_threshold
        assert float(node.get_parameter("source_threshold").value) == mc.source_threshold
        assert int(node.get_parameter("confirm_samples").value) == mc.confirm_samples
        assert float(node.get_parameter("surge_step").value) == sc.surge_step
        assert float(node.get_parameter("cast_step").value) == sc.cast_step
        assert float(node.get_parameter("wind_x").value) == sc.wind_x


class TestBuildMissionConfig:
    def test_builds_config_from_defaults(self, node):
        config = build_mission_config(node)
        assert isinstance(config, MissionConfig)
        assert config.enter_threshold > 0
        assert config.exit_threshold > 0
        assert config.source_threshold > config.enter_threshold
        assert config.source_radius > 0

    def test_patrol_points_parsed(self, node):
        config = build_mission_config(node)
        # Default patrol string should produce at least 2 points
        assert len(config.patrol_points) >= 2

    def test_source_position_from_params(self, node):
        config = build_mission_config(node)
        assert config.actual_source is not None
        sx, sy = config.actual_source
        assert isinstance(sx, float)
        assert isinstance(sy, float)


class TestBuildSurgeConfig:
    def test_builds_config_from_defaults(self, node):
        config = build_surge_config(node)
        assert isinstance(config, SurgeCastConfig)
        assert config.surge_step > 0
        assert config.cast_step > 0
        assert config.cast_distance_limit > 0

    def test_thresholds_match_mission_params(self, node):
        mc = build_mission_config(node)
        sc = build_surge_config(node)
        assert sc.plume_found_threshold == mc.enter_threshold
        assert sc.plume_lost_threshold == mc.exit_threshold
        assert sc.source_threshold == mc.source_threshold


class TestBuildFusionConfig:
    def test_builds_config_from_defaults(self, node):
        config = build_fusion_config(node)
        assert isinstance(config, FusionConfig)
        assert config.blending_mode == "weighted"
        assert 0 < config.pf_weight_base < 1
        assert 0 < config.surge_weight < 1

    def test_weights_sum_approximately_one(self, node):
        config = build_fusion_config(node)
        total = config.pf_weight_base + config.surge_weight
        assert abs(total - 1.0) < 0.05
