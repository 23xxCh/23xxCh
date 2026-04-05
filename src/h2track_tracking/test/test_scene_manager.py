"""Tests for scene_manager module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from h2track_tracking.scene_manager import (
    GadenConfig,
    GasFieldConfig,
    InitialPose,
    MissionThresholds,
    SceneConfig,
    SceneManager,
)


# Fixtures


@pytest.fixture
def temp_scenes_dir() -> Path:
    """Create a temporary scenes directory with test scenes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scenes_dir = Path(tmpdir) / "scenes"
        scenes_dir.mkdir()

        # Create baseline scene
        baseline_dir = scenes_dir / "baseline"
        baseline_dir.mkdir()
        baseline_yaml = baseline_dir / "scene.yaml"
        baseline_world = baseline_dir / "baseline.world"
        baseline_map = baseline_dir / "maps" / "baseline_map.yaml"
        baseline_map.parent.mkdir(parents=True)

        baseline_world.touch()
        baseline_map.touch()

        baseline_data = {
            "scene_name": "baseline",
            "world": "baseline.world",
            "map": "maps/baseline_map.yaml",
            "use_gaden": True,
            "use_slam": False,
            "nav2_params": None,
            "mission_manager": {
                "initial_pose": {"x": 1.0, "y": 2.0, "yaw": 0.5},
                "patrol_points": [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
                "enter_threshold": 1.5,
                "exit_threshold": 0.6,
                "source_threshold": 4.5,
                "confirm_samples": 2,
                "source_radius": 1.0,
                "source_hold_steps": 2,
            },
            "gas_source": {"x": 5.0, "y": 5.0},
            "gaden": {
                "enabled": True,
                "project_path": "/path/to/gaden",
                "playback_id": "scene1",
            },
            "gas_field": {
                "source_strength": 100.0,
                "decay_rate": 0.5,
            },
        }
        with baseline_yaml.open("w") as f:
            yaml.dump(baseline_data, f)

        # Create warehouse scene with different config
        warehouse_dir = scenes_dir / "warehouse"
        warehouse_dir.mkdir()
        warehouse_yaml = warehouse_dir / "scene.yaml"
        warehouse_world = warehouse_dir / "warehouse.world"
        warehouse_map = warehouse_dir / "maps" / "warehouse_map.yaml"
        warehouse_nav2 = warehouse_dir / "nav2_params.yaml"
        warehouse_map.parent.mkdir(parents=True)

        warehouse_world.touch()
        warehouse_map.touch()
        warehouse_nav2.touch()

        warehouse_data = {
            "scene_name": "warehouse",
            "world": "warehouse.world",
            "map": "maps/warehouse_map.yaml",
            "nav2_params": "nav2_params.yaml",
            "use_gaden": False,
            "use_slam": True,
            "mission_manager": {
                "initial_pose": {"x": 0.5, "y": 1.0, "yaw": 0.0},
                "patrol_points": [[1.5, 1.8], [2.4, 1.1]],
                "enter_threshold": 0.65,
                "exit_threshold": 0.4,
                "source_threshold": 3.4,
                "confirm_samples": 1,
                "source_radius": 1.0,
                "source_hold_steps": 1,
                "track_exit_samples": 3,
            },
            "gas_source": {"x": 3.6, "y": -3.0},
            "gaden": {"enabled": False},
        }
        with warehouse_yaml.open("w") as f:
            yaml.dump(warehouse_data, f)

        yield scenes_dir


@pytest.fixture
def scene_manager(temp_scenes_dir: Path) -> SceneManager:
    """Create a SceneManager with temporary scenes directory."""
    return SceneManager(scenes_dir=temp_scenes_dir)


# MissionThresholds Tests


class TestMissionThresholds:
    """Tests for MissionThresholds dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating MissionThresholds with default values."""
        thresholds = MissionThresholds(
            enter_threshold=1.0,
            exit_threshold=0.5,
            source_threshold=3.0,
            confirm_samples=2,
            source_radius=1.0,
            source_hold_steps=2,
        )

        assert thresholds.enter_threshold == 1.0
        assert thresholds.exit_threshold == 0.5
        assert thresholds.source_threshold == 3.0
        assert thresholds.confirm_samples == 2
        assert thresholds.source_radius == 1.0
        assert thresholds.source_hold_steps == 2
        assert thresholds.track_exit_samples is None
        assert thresholds.track_step == 0.4
        assert thresholds.sweep_angle_deg == 30.0

    def test_create_with_all_values(self) -> None:
        """Test creating MissionThresholds with all values specified."""
        thresholds = MissionThresholds(
            enter_threshold=1.5,
            exit_threshold=0.6,
            source_threshold=4.5,
            confirm_samples=3,
            source_radius=1.5,
            source_hold_steps=4,
            track_exit_samples=5,
            track_step=0.5,
            sweep_angle_deg=45.0,
        )

        assert thresholds.track_exit_samples == 5
        assert thresholds.track_step == 0.5
        assert thresholds.sweep_angle_deg == 45.0

    def test_frozen(self) -> None:
        """Test that MissionThresholds is immutable."""
        thresholds = MissionThresholds(
            enter_threshold=1.0,
            exit_threshold=0.5,
            source_threshold=3.0,
            confirm_samples=2,
            source_radius=1.0,
            source_hold_steps=2,
        )

        with pytest.raises(AttributeError):
            thresholds.enter_threshold = 2.0  # type: ignore


# GadenConfig Tests


class TestGadenConfig:
    """Tests for GadenConfig dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating GadenConfig with default values."""
        config = GadenConfig(
            project_path="/path/to/gaden",
            playback_id="scene1",
        )

        assert config.project_path == "/path/to/gaden"
        assert config.playback_id == "scene1"
        assert config.player_freq == 1.0
        assert config.sensor_topic == "/gaden/sensor_reading"
        assert config.sensor_frame == "base_link"
        assert config.fixed_frame == "gaden_map"

    def test_create_with_all_values(self) -> None:
        """Test creating GadenConfig with all values specified."""
        config = GadenConfig(
            project_path="/custom/path",
            playback_id="custom",
            player_freq=2.0,
            sensor_topic="/custom/sensor",
            sensor_frame="custom_frame",
            fixed_frame="custom_fixed",
            map_offset_x=1.0,
            map_offset_y=2.0,
            map_offset_z=3.0,
            map_roll=0.1,
            map_pitch=0.2,
            map_yaw=0.3,
        )

        assert config.project_path == "/custom/path"
        assert config.player_freq == 2.0
        assert config.sensor_topic == "/custom/sensor"
        assert config.map_offset_x == 1.0


# GasFieldConfig Tests


class TestGasFieldConfig:
    """Tests for GasFieldConfig dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating GasFieldConfig with default values."""
        config = GasFieldConfig()

        assert config.source_strength == 100.0
        assert config.decay_rate == 0.5
        assert config.plume_stddev == 1.0
        assert config.wind_x == 0.0
        assert config.wind_y == 0.0
        assert config.noise_stddev == 0.05
        assert config.publish_rate_hz == 5.0

    def test_create_with_all_values(self) -> None:
        """Test creating GasFieldConfig with all values specified."""
        config = GasFieldConfig(
            source_strength=150.0,
            decay_rate=0.32,
            plume_stddev=1.85,
            wind_x=0.18,
            wind_y=-0.06,
            noise_stddev=0.03,
            publish_rate_hz=10.0,
        )

        assert config.source_strength == 150.0
        assert config.decay_rate == 0.32
        assert config.wind_x == 0.18


# InitialPose Tests


class TestInitialPose:
    """Tests for InitialPose dataclass."""

    def test_create(self) -> None:
        """Test creating InitialPose."""
        pose = InitialPose(x=1.5, y=2.5, yaw=1.57)

        assert pose.x == 1.5
        assert pose.y == 2.5
        assert pose.yaw == 1.57

    def test_frozen(self) -> None:
        """Test that InitialPose is immutable."""
        pose = InitialPose(x=1.0, y=2.0, yaw=0.0)

        with pytest.raises(AttributeError):
            pose.x = 3.0  # type: ignore


# SceneConfig Tests


class TestSceneConfig:
    """Tests for SceneConfig dataclass."""

    def test_from_yaml(self, temp_scenes_dir: Path) -> None:
        """Test loading SceneConfig from YAML file."""
        scene_dir = temp_scenes_dir / "baseline"
        config = SceneConfig.from_yaml(scene_dir)

        assert config.name == "baseline"
        assert config.world_path.name == "baseline.world"
        assert config.map_path.name == "baseline_map.yaml"
        assert config.gas_source == (5.0, 5.0)
        assert len(config.patrol_points) == 3
        assert config.use_gaden is True
        assert config.use_slam is False

    def test_from_yaml_missing_file(self, temp_scenes_dir: Path) -> None:
        """Test error when YAML file is missing."""
        scene_dir = temp_scenes_dir / "nonexistent"
        scene_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            SceneConfig.from_yaml(scene_dir)

    def test_from_dict(self, temp_scenes_dir: Path) -> None:
        """Test creating SceneConfig from dictionary."""
        scene_dir = temp_scenes_dir / "baseline"
        yaml_path = scene_dir / "scene.yaml"
        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        config = SceneConfig.from_dict(data, scene_dir)

        assert config.name == "baseline"
        assert config.thresholds.enter_threshold == 1.5
        assert config.initial_pose.x == 1.0
        assert config.gas_source == (5.0, 5.0)

    def test_to_dict(self, temp_scenes_dir: Path) -> None:
        """Test converting SceneConfig to dictionary."""
        scene_dir = temp_scenes_dir / "baseline"
        config = SceneConfig.from_yaml(scene_dir)

        data = config.to_dict()

        assert data["scene_name"] == "baseline"
        assert data["use_gaden"] is True
        assert data["mission_manager"]["enter_threshold"] == 1.5
        assert data["gas_source"]["x"] == 5.0

    def test_to_dict_roundtrip(self, temp_scenes_dir: Path) -> None:
        """Test that to_dict -> from_dict preserves data."""
        scene_dir = temp_scenes_dir / "baseline"
        original = SceneConfig.from_yaml(scene_dir)

        data = original.to_dict()
        restored = SceneConfig.from_dict(data, scene_dir)

        assert restored.name == original.name
        assert restored.gas_source == original.gas_source
        assert restored.patrol_points == original.patrol_points
        assert restored.thresholds.enter_threshold == original.thresholds.enter_threshold
        assert restored.initial_pose.x == original.initial_pose.x

    def test_frozen(self, temp_scenes_dir: Path) -> None:
        """Test that SceneConfig is immutable."""
        scene_dir = temp_scenes_dir / "baseline"
        config = SceneConfig.from_yaml(scene_dir)

        with pytest.raises(AttributeError):
            config.name = "new_name"  # type: ignore

    def test_warehouse_scene(self, temp_scenes_dir: Path) -> None:
        """Test loading warehouse scene with different config."""
        scene_dir = temp_scenes_dir / "warehouse"
        config = SceneConfig.from_yaml(scene_dir)

        assert config.name == "warehouse"
        assert config.use_gaden is False
        assert config.use_slam is True
        assert config.nav2_params_path is not None
        assert config.nav2_params_path.name == "nav2_params.yaml"
        assert config.thresholds.track_exit_samples == 3


# SceneManager Tests


class TestSceneManager:
    """Tests for SceneManager class."""

    def test_list_scenes(self, scene_manager: SceneManager) -> None:
        """Test listing available scenes."""
        scenes = scene_manager.list_scenes()

        assert len(scenes) == 2
        assert "baseline" in scenes
        assert "warehouse" in scenes

    def test_list_scenes_empty_directory(self, tmp_path: Path) -> None:
        """Test listing scenes from empty directory."""
        manager = SceneManager(scenes_dir=tmp_path)
        scenes = manager.list_scenes()

        assert scenes == []

    def test_list_scenes_ignores_non_scene_dirs(self, tmp_path: Path) -> None:
        """Test that non-scene directories are ignored."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()

        # Create directory without scene.yaml
        (scenes_dir / "not_a_scene").mkdir()

        # Create valid scene
        valid_dir = scenes_dir / "valid"
        valid_dir.mkdir()
        (valid_dir / "scene.yaml").touch()

        manager = SceneManager(scenes_dir=scenes_dir)
        scenes = manager.list_scenes()

        assert scenes == ["valid"]

    def test_scene_exists(self, scene_manager: SceneManager) -> None:
        """Test checking scene existence."""
        assert scene_manager.scene_exists("baseline") is True
        assert scene_manager.scene_exists("warehouse") is True
        assert scene_manager.scene_exists("nonexistent") is False

    def test_get_scene(self, scene_manager: SceneManager) -> None:
        """Test getting scene configuration."""
        config = scene_manager.get_scene("baseline")

        assert config is not None
        assert config.name == "baseline"
        assert config.gas_source == (5.0, 5.0)

    def test_get_scene_nonexistent(self, scene_manager: SceneManager) -> None:
        """Test getting nonexistent scene."""
        config = scene_manager.get_scene("nonexistent")

        assert config is None

    def test_get_scene_caching(self, scene_manager: SceneManager) -> None:
        """Test that scene configs are cached."""
        config1 = scene_manager.get_scene("baseline")
        config2 = scene_manager.get_scene("baseline")

        assert config1 is config2

    def test_validate_scene_valid(self, scene_manager: SceneManager) -> None:
        """Test validating a valid scene."""
        errors = scene_manager.validate_scene("baseline")

        assert errors == []

    def test_validate_scene_nonexistent(self, scene_manager: SceneManager) -> None:
        """Test validating a nonexistent scene."""
        errors = scene_manager.validate_scene("nonexistent")

        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_validate_scene_missing_world(
        self, scene_manager: SceneManager, temp_scenes_dir: Path
    ) -> None:
        """Test validation catches missing world file."""
        # Delete world file
        world_path = temp_scenes_dir / "baseline" / "baseline.world"
        world_path.unlink()

        errors = scene_manager.validate_scene("baseline")

        assert len(errors) == 1
        assert "World file not found" in errors[0]

    def test_validate_scene_missing_map(
        self, scene_manager: SceneManager, temp_scenes_dir: Path
    ) -> None:
        """Test validation catches missing map file."""
        # Delete map file
        map_path = temp_scenes_dir / "baseline" / "maps" / "baseline_map.yaml"
        map_path.unlink()

        errors = scene_manager.validate_scene("baseline")

        assert any("Map file not found" in e for e in errors)

    def test_validate_scene_invalid_thresholds(
        self, scene_manager: SceneManager, temp_scenes_dir: Path
    ) -> None:
        """Test validation catches invalid threshold values."""
        # Modify scene.yaml with invalid thresholds
        yaml_path = temp_scenes_dir / "baseline" / "scene.yaml"
        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        # enter_threshold <= exit_threshold is invalid
        data["mission_manager"]["enter_threshold"] = 0.3
        data["mission_manager"]["exit_threshold"] = 0.5

        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        # Clear cache to force reload
        scene_manager._cache.pop("baseline", None)

        errors = scene_manager.validate_scene("baseline")

        assert any("enter_threshold" in e for e in errors)

    def test_validate_scene_empty_patrol_points(
        self, scene_manager: SceneManager, temp_scenes_dir: Path
    ) -> None:
        """Test validation catches empty patrol points."""
        yaml_path = temp_scenes_dir / "baseline" / "scene.yaml"
        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        data["mission_manager"]["patrol_points"] = []

        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        scene_manager._cache.pop("baseline", None)

        errors = scene_manager.validate_scene("baseline")

        assert any("patrol point" in e for e in errors)

    def test_validate_scene_missing_gaden_path(
        self, scene_manager: SceneManager, temp_scenes_dir: Path
    ) -> None:
        """Test validation catches missing GADEN project path."""
        yaml_path = temp_scenes_dir / "baseline" / "scene.yaml"
        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        data["gaden"]["project_path"] = ""

        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        scene_manager._cache.pop("baseline", None)

        errors = scene_manager.validate_scene("baseline")

        assert any("GADEN" in e for e in errors)

    def test_create_scene(self, scene_manager: SceneManager) -> None:
        """Test creating a new scene from template."""
        new_path = scene_manager.create_scene("baseline", "new_scene")

        assert new_path.exists()
        assert new_path.name == "new_scene"
        assert (new_path / "scene.yaml").exists()

        # Verify new scene is listed
        scenes = scene_manager.list_scenes()
        assert "new_scene" in scenes

        # Verify config has correct name
        config = scene_manager.get_scene("new_scene")
        assert config is not None
        assert config.name == "new_scene"

    def test_create_scene_nonexistent_template(self, scene_manager: SceneManager) -> None:
        """Test error when template doesn't exist."""
        with pytest.raises(ValueError, match="Template scene not found"):
            scene_manager.create_scene("nonexistent", "new_scene")

    def test_create_scene_already_exists(self, scene_manager: SceneManager) -> None:
        """Test error when scene already exists."""
        with pytest.raises(ValueError, match="Scene already exists"):
            scene_manager.create_scene("baseline", "baseline")

    def test_reload_scene(self, scene_manager: SceneManager) -> None:
        """Test reloading scene configuration."""
        # Get initial config
        config1 = scene_manager.get_scene("baseline")
        assert config1 is not None

        # Modify YAML
        yaml_path = scene_manager.scenes_dir / "baseline" / "scene.yaml"
        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)
        data["gas_source"]["x"] = 10.0
        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        # Reload and verify new value
        config2 = scene_manager.reload_scene("baseline")
        assert config2 is not None
        assert config2.gas_source == (10.0, 5.0)

        # Verify cache was cleared (different object)
        assert config1 is not config2

    def test_get_scene_dir(self, scene_manager: SceneManager) -> None:
        """Test getting scene directory path."""
        scene_dir = scene_manager.get_scene_dir("baseline")

        assert scene_dir is not None
        assert scene_dir.name == "baseline"

    def test_get_scene_dir_nonexistent(self, scene_manager: SceneManager) -> None:
        """Test getting directory for nonexistent scene."""
        scene_dir = scene_manager.get_scene_dir("nonexistent")

        assert scene_dir is None


# Integration Tests


class TestSceneManagerIntegration:
    """Integration tests with real scene files."""

    def test_load_real_baseline_scene(self) -> None:
        """Test loading the actual baseline scene from the repository."""
        workspace_root = Path("/home/user/h2track-xian")
        scenes_dir = workspace_root / "src" / "h2track_sim" / "scenes"

        if not scenes_dir.exists():
            pytest.skip("Real scenes directory not found")

        manager = SceneManager(scenes_dir=scenes_dir)

        # Check baseline exists
        assert manager.scene_exists("baseline")

        # Load and validate
        config = manager.get_scene("baseline")
        assert config is not None
        assert config.name == "baseline"
        assert config.use_gaden is True

    def test_load_real_warehouse_scene(self) -> None:
        """Test loading the actual warehouse scene from the repository."""
        workspace_root = Path("/home/user/h2track-xian")
        scenes_dir = workspace_root / "src" / "h2track_sim" / "scenes"

        if not scenes_dir.exists():
            pytest.skip("Real scenes directory not found")

        manager = SceneManager(scenes_dir=scenes_dir)

        assert manager.scene_exists("warehouse")

        config = manager.get_scene("warehouse")
        assert config is not None
        assert config.name == "warehouse"
        assert config.use_slam is True

    def test_validate_real_scenes(self) -> None:
        """Test validating real scenes from the repository."""
        workspace_root = Path("/home/user/h2track-xian")
        scenes_dir = workspace_root / "src" / "h2track_sim" / "scenes"

        if not scenes_dir.exists():
            pytest.skip("Real scenes directory not found")

        manager = SceneManager(scenes_dir=scenes_dir)

        for scene_name in manager.list_scenes():
            errors = manager.validate_scene(scene_name)
            # Note: Some files may not exist until after build
            # So we just check it doesn't crash
            assert isinstance(errors, list)


# Edge Cases


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_yaml_missing_required_fields(self, tmp_path: Path) -> None:
        """Test handling YAML with missing required fields."""
        scenes_dir = tmp_path / "scenes"
        scene_dir = scenes_dir / "incomplete"
        scene_dir.mkdir(parents=True)

        # Create YAML without patrol_points
        yaml_path = scene_dir / "scene.yaml"
        data = {
            "scene_name": "incomplete",
            # Missing mission_manager
        }
        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        manager = SceneManager(scenes_dir=scenes_dir)
        config = manager.get_scene("incomplete")

        # Should load with default/empty values
        assert config is not None
        assert config.name == "incomplete"
        assert config.patrol_points == []

    def test_scene_with_no_gaden_config(self, tmp_path: Path) -> None:
        """Test scene without GADEN configuration."""
        scenes_dir = tmp_path / "scenes"
        scene_dir = scenes_dir / "no_gaden"
        scene_dir.mkdir(parents=True)

        yaml_path = scene_dir / "scene.yaml"
        world_path = scene_dir / "world.world"
        map_path = scene_dir / "map.yaml"
        world_path.touch()
        map_path.touch()

        data = {
            "scene_name": "no_gaden",
            "world": "world.world",
            "map": "map.yaml",
            "use_gaden": False,
            "mission_manager": {
                "initial_pose": {"x": 0, "y": 0, "yaw": 0},
                "patrol_points": [[1, 1]],
                "enter_threshold": 1.0,
                "exit_threshold": 0.5,
                "source_threshold": 3.0,
                "confirm_samples": 1,
                "source_radius": 1.0,
                "source_hold_steps": 1,
            },
            "gas_source": {"x": 0, "y": 0},
        }
        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        manager = SceneManager(scenes_dir=scenes_dir)
        config = manager.get_scene("no_gaden")

        assert config is not None
        assert config.use_gaden is False
        assert config.gaden_config is None

    def test_patrol_goal_timeout(self, tmp_path: Path) -> None:
        """Test scene with patrol goal timeout."""
        scenes_dir = tmp_path / "scenes"
        scene_dir = scenes_dir / "timeout_scene"
        scene_dir.mkdir(parents=True)

        yaml_path = scene_dir / "scene.yaml"
        world_path = scene_dir / "world.world"
        map_path = scene_dir / "map.yaml"
        world_path.touch()
        map_path.touch()

        data = {
            "scene_name": "timeout_scene",
            "world": "world.world",
            "map": "map.yaml",
            "mission_manager": {
                "initial_pose": {"x": 0, "y": 0, "yaw": 0},
                "patrol_points": [[1, 1]],
                "enter_threshold": 1.0,
                "exit_threshold": 0.5,
                "source_threshold": 3.0,
                "confirm_samples": 1,
                "source_radius": 1.0,
                "source_hold_steps": 1,
                "patrol_goal_timeout_sec": 70.0,
            },
            "gas_source": {"x": 0, "y": 0},
        }
        with yaml_path.open("w") as f:
            yaml.dump(data, f)

        manager = SceneManager(scenes_dir=scenes_dir)
        config = manager.get_scene("timeout_scene")

        assert config is not None
        assert config.patrol_goal_timeout_sec == 70.0


# Default Scenes Tests


class TestDefaultScenes:
    """Tests for default scene configurations."""

    def test_baseline_thresholds_are_valid(self) -> None:
        """Test that baseline scene thresholds are properly ordered."""
        workspace_root = Path("/home/user/h2track-xian")
        scenes_dir = workspace_root / "src" / "h2track_sim" / "scenes"

        if not scenes_dir.exists():
            pytest.skip("Real scenes directory not found")

        manager = SceneManager(scenes_dir=scenes_dir)
        config = manager.get_scene("baseline")

        if config is None:
            pytest.skip("Baseline scene not found")

        # Thresholds should be ordered: exit < enter < source
        t = config.thresholds
        assert t.exit_threshold < t.enter_threshold
        assert t.enter_threshold < t.source_threshold

    def test_warehouse_thresholds_are_valid(self) -> None:
        """Test that warehouse scene thresholds are properly ordered."""
        workspace_root = Path("/home/user/h2track-xian")
        scenes_dir = workspace_root / "src" / "h2track_sim" / "scenes"

        if not scenes_dir.exists():
            pytest.skip("Real scenes directory not found")

        manager = SceneManager(scenes_dir=scenes_dir)
        config = manager.get_scene("warehouse")

        if config is None:
            pytest.skip("Warehouse scene not found")

        t = config.thresholds
        assert t.exit_threshold < t.enter_threshold
        assert t.enter_threshold < t.source_threshold
