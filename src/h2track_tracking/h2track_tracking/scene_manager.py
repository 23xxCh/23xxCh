"""Scene management for dynamic scene loading and validation.

This module provides:
- SceneConfig: Immutable configuration for a scene
- SceneManager: Dynamic scene loading, validation, and creation

Scenes are stored in h2track_sim/scenes/<scene_name>/scene.yaml
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import get_h2track_sim_share_path, get_workspace_root


@dataclass(frozen=True)
class MissionThresholds:
    """Mission threshold configuration for gas detection state machine."""

    enter_threshold: float
    exit_threshold: float
    source_threshold: float
    confirm_samples: int
    source_radius: float
    source_hold_steps: int
    track_exit_samples: int | None = None
    track_step: float = 0.4
    sweep_angle_deg: float = 30.0


@dataclass(frozen=True)
class GadenConfig:
    """GADEN simulation configuration."""

    project_path: str
    playback_id: str
    player_freq: float = 1.0
    sensor_topic: str = "/gaden/sensor_reading"
    sensor_frame: str = "base_link"
    fixed_frame: str = "gaden_map"
    map_offset_x: float = 0.0
    map_offset_y: float = 0.0
    map_offset_z: float = 0.0
    map_roll: float = 0.0
    map_pitch: float = 0.0
    map_yaw: float = 0.0


@dataclass(frozen=True)
class GasFieldConfig:
    """Simplified gas field simulation configuration."""

    source_strength: float = 100.0
    decay_rate: float = 0.5
    plume_stddev: float = 1.0
    wind_x: float = 0.0
    wind_y: float = 0.0
    noise_stddev: float = 0.05
    publish_rate_hz: float = 5.0


@dataclass(frozen=True)
class InitialPose:
    """Initial robot pose configuration."""

    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class SceneConfig:
    """Immutable scene configuration.

    Attributes:
        name: Scene identifier (directory name)
        world_path: Path to Gazebo world file
        map_path: Path to map YAML file
        nav2_params_path: Path to Nav2 parameters file (optional)
        gas_source: Gas source position (x, y)
        patrol_points: List of patrol waypoints
        thresholds: Mission threshold configuration
        initial_pose: Initial robot pose
        use_gaden: Whether to use GADEN for gas simulation
        use_slam: Whether to use SLAM for mapping
        nav2_autostart: Whether Nav2 should autostart
        localizer_node: Localizer node type (amcl, none)
        model_path: Path to Gazebo models (optional)
        gaden_config: GADEN configuration (optional)
        gas_field_config: Gas field configuration for simplified simulation
        patrol_goal_timeout_sec: Timeout for patrol goals (optional)
    """

    name: str
    world_path: Path
    map_path: Path
    nav2_params_path: Path | None
    gas_source: tuple[float, float]
    patrol_points: list[tuple[float, float]]
    thresholds: MissionThresholds
    initial_pose: InitialPose
    use_gaden: bool = True
    use_slam: bool = False
    nav2_autostart: bool = True
    localizer_node: str = "amcl"
    model_path: Path | None = None
    gaden_config: GadenConfig | None = None
    gas_field_config: GasFieldConfig = field(default_factory=GasFieldConfig)
    patrol_goal_timeout_sec: float | None = None

    @classmethod
    def from_yaml(cls, scene_dir: Path) -> SceneConfig:
        """Load scene configuration from YAML file.

        Args:
            scene_dir: Path to scene directory containing scene.yaml

        Returns:
            SceneConfig instance

        Raises:
            FileNotFoundError: If scene.yaml not found
            KeyError: If required fields are missing
            ValueError: If configuration is invalid
        """
        yaml_path = scene_dir / "scene.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Scene config not found: {yaml_path}")

        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data, scene_dir)

    @classmethod
    def from_dict(cls, data: dict[str, Any], scene_dir: Path) -> SceneConfig:
        """Create SceneConfig from dictionary.

        Args:
            data: Parsed YAML data
            scene_dir: Path to scene directory for resolving relative paths

        Returns:
            SceneConfig instance
        """
        # Parse mission thresholds
        mm = data.get("mission_manager", {})
        thresholds = MissionThresholds(
            enter_threshold=mm.get("enter_threshold", 1.0),
            exit_threshold=mm.get("exit_threshold", 0.5),
            source_threshold=mm.get("source_threshold", 3.0),
            confirm_samples=mm.get("confirm_samples", 2),
            source_radius=mm.get("source_radius", 1.0),
            source_hold_steps=mm.get("source_hold_steps", 2),
            track_exit_samples=mm.get("track_exit_samples"),
            track_step=mm.get("track_step", 0.4),
            sweep_angle_deg=mm.get("sweep_angle_deg", 30.0),
        )

        # Parse initial pose
        initial_pose_data = mm.get("initial_pose", {})
        initial_pose = InitialPose(
            x=initial_pose_data.get("x", 0.0),
            y=initial_pose_data.get("y", 0.0),
            yaw=initial_pose_data.get("yaw", 0.0),
        )

        # Parse patrol points
        patrol_points = [
            (float(p[0]), float(p[1])) for p in mm.get("patrol_points", [])
        ]

        # Parse gas source
        gas_source_data = data.get("gas_source", {})
        gas_source = (gas_source_data.get("x", 0.0), gas_source_data.get("y", 0.0))

        # Resolve paths relative to scene directory
        world_path = scene_dir / data["world"] if "world" in data else scene_dir / "world.world"
        map_path = scene_dir / data["map"] if "map" in data else scene_dir / "map.yaml"

        # Nav2 params is optional
        nav2_params_path = None
        if data.get("nav2_params"):
            nav2_params_path = scene_dir / data["nav2_params"]

        # Model path is optional
        model_path = None
        if data.get("model_path"):
            model_path = scene_dir / data["model_path"]

        # Parse GADEN config
        gaden_config = None
        gaden_data = data.get("gaden", {})
        if gaden_data.get("enabled", False):
            gaden_config = GadenConfig(
                project_path=gaden_data.get("project_path", ""),
                playback_id=gaden_data.get("playback_id", "scene1"),
                player_freq=gaden_data.get("player_freq", 1.0),
                sensor_topic=gaden_data.get("sensor_topic", "/gaden/sensor_reading"),
                sensor_frame=gaden_data.get("sensor_frame", "base_link"),
                fixed_frame=gaden_data.get("fixed_frame", "gaden_map"),
                map_offset_x=gaden_data.get("map_offset_x", 0.0),
                map_offset_y=gaden_data.get("map_offset_y", 0.0),
                map_offset_z=gaden_data.get("map_offset_z", 0.0),
                map_roll=gaden_data.get("map_roll", 0.0),
                map_pitch=gaden_data.get("map_pitch", 0.0),
                map_yaw=gaden_data.get("map_yaw", 0.0),
            )

        # Parse gas field config
        gas_field_data = data.get("gas_field", {})
        gas_field_config = GasFieldConfig(
            source_strength=gas_field_data.get("source_strength", 100.0),
            decay_rate=gas_field_data.get("decay_rate", 0.5),
            plume_stddev=gas_field_data.get("plume_stddev", 1.0),
            wind_x=gas_field_data.get("wind_x", 0.0),
            wind_y=gas_field_data.get("wind_y", 0.0),
            noise_stddev=gas_field_data.get("noise_stddev", 0.05),
            publish_rate_hz=gas_field_data.get("publish_rate_hz", 5.0),
        )

        return cls(
            name=data.get("scene_name", scene_dir.name),
            world_path=world_path,
            map_path=map_path,
            nav2_params_path=nav2_params_path,
            gas_source=gas_source,
            patrol_points=patrol_points,
            thresholds=thresholds,
            initial_pose=initial_pose,
            use_gaden=data.get("use_gaden", True),
            use_slam=data.get("use_slam", False),
            nav2_autostart=data.get("nav2_autostart", True),
            localizer_node=data.get("localizer_node", "amcl"),
            model_path=model_path,
            gaden_config=gaden_config,
            gas_field_config=gas_field_config,
            patrol_goal_timeout_sec=mm.get("patrol_goal_timeout_sec"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert SceneConfig to dictionary for YAML serialization.

        Returns:
            Dictionary suitable for YAML serialization
        """
        result: dict[str, Any] = {
            "scene_name": self.name,
            "world": str(self.world_path.name),
            "map": str(self.map_path.name),
            "use_gaden": self.use_gaden,
            "use_slam": self.use_slam,
            "nav2_autostart": self.nav2_autostart,
            "localizer_node": self.localizer_node,
        }

        if self.nav2_params_path:
            result["nav2_params"] = str(self.nav2_params_path.name)

        if self.model_path:
            result["model_path"] = str(self.model_path.name)

        # Mission manager config
        mission_manager: dict[str, Any] = {
            "initial_pose": {
                "x": self.initial_pose.x,
                "y": self.initial_pose.y,
                "yaw": self.initial_pose.yaw,
            },
            "patrol_points": [[p[0], p[1]] for p in self.patrol_points],
            "enter_threshold": self.thresholds.enter_threshold,
            "exit_threshold": self.thresholds.exit_threshold,
            "source_threshold": self.thresholds.source_threshold,
            "confirm_samples": self.thresholds.confirm_samples,
            "source_radius": self.thresholds.source_radius,
            "source_hold_steps": self.thresholds.source_hold_steps,
            "track_step": self.thresholds.track_step,
            "sweep_angle_deg": self.thresholds.sweep_angle_deg,
        }
        if self.thresholds.track_exit_samples is not None:
            mission_manager["track_exit_samples"] = self.thresholds.track_exit_samples
        if self.patrol_goal_timeout_sec is not None:
            mission_manager["patrol_goal_timeout_sec"] = self.patrol_goal_timeout_sec
        result["mission_manager"] = mission_manager

        # Gas source
        result["gas_source"] = {"x": self.gas_source[0], "y": self.gas_source[1]}

        # GADEN config
        if self.gaden_config:
            result["gaden"] = {
                "enabled": True,
                "project_path": self.gaden_config.project_path,
                "playback_id": self.gaden_config.playback_id,
                "player_freq": self.gaden_config.player_freq,
                "sensor_topic": self.gaden_config.sensor_topic,
                "sensor_frame": self.gaden_config.sensor_frame,
                "fixed_frame": self.gaden_config.fixed_frame,
                "map_offset_x": self.gaden_config.map_offset_x,
                "map_offset_y": self.gaden_config.map_offset_y,
                "map_offset_z": self.gaden_config.map_offset_z,
                "map_roll": self.gaden_config.map_roll,
                "map_pitch": self.gaden_config.map_pitch,
                "map_yaw": self.gaden_config.map_yaw,
            }

        # Gas field config
        result["gas_field"] = {
            "source_strength": self.gas_field_config.source_strength,
            "decay_rate": self.gas_field_config.decay_rate,
            "plume_stddev": self.gas_field_config.plume_stddev,
            "wind_x": self.gas_field_config.wind_x,
            "wind_y": self.gas_field_config.wind_y,
            "noise_stddev": self.gas_field_config.noise_stddev,
            "publish_rate_hz": self.gas_field_config.publish_rate_hz,
        }

        return result


class SceneManager:
    """Manager for dynamic scene loading, validation, and creation.

    The SceneManager provides:
    - Scene listing and discovery
    - Scene loading and validation
    - Scene creation from templates
    """

    def __init__(self, scenes_dir: Path | None = None) -> None:
        """Initialize SceneManager.

        Args:
            scenes_dir: Directory containing scene subdirectories.
                       If None, uses h2track_sim share directory.
        """
        self._scenes_dir = scenes_dir
        self._cache: dict[str, SceneConfig] = {}

    @property
    def scenes_dir(self) -> Path:
        """Get scenes directory path."""
        if self._scenes_dir is not None:
            return self._scenes_dir

        # Try h2track_sim share path
        share_path = get_h2track_sim_share_path()
        if share_path:
            return share_path / "scenes"

        # Fallback to source directory
        workspace = get_workspace_root()
        return workspace / "src" / "h2track_sim" / "scenes"

    def list_scenes(self) -> list[str]:
        """List all available scene names.

        Returns:
            List of scene names (directory names)
        """
        scenes: list[str] = []
        if not self.scenes_dir.exists():
            return scenes

        for item in self.scenes_dir.iterdir():
            if item.is_dir() and (item / "scene.yaml").exists():
                scenes.append(item.name)

        return sorted(scenes)

    def scene_exists(self, name: str) -> bool:
        """Check if a scene exists.

        Args:
            name: Scene name (directory name)

        Returns:
            True if scene directory and scene.yaml exist
        """
        scene_dir = self.scenes_dir / name
        return scene_dir.is_dir() and (scene_dir / "scene.yaml").exists()

    def get_scene(self, name: str) -> SceneConfig | None:
        """Get scene configuration by name.

        Args:
            name: Scene name

        Returns:
            SceneConfig if scene exists, None otherwise
        """
        if name in self._cache:
            return self._cache[name]

        if not self.scene_exists(name):
            return None

        scene_dir = self.scenes_dir / name
        try:
            config = SceneConfig.from_yaml(scene_dir)
            self._cache[name] = config
            return config
        except (FileNotFoundError, KeyError, ValueError):
            return None

    def validate_scene(self, name: str) -> list[str]:
        """Validate scene configuration and files.

        Args:
            name: Scene name to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Check scene directory exists
        scene_dir = self.scenes_dir / name
        if not scene_dir.exists():
            errors.append(f"Scene directory not found: {scene_dir}")
            return errors

        # Check scene.yaml exists
        yaml_path = scene_dir / "scene.yaml"
        if not yaml_path.exists():
            errors.append(f"Scene config not found: {yaml_path}")
            return errors

        # Try to load config
        try:
            config = SceneConfig.from_yaml(scene_dir)
        except FileNotFoundError as e:
            errors.append(str(e))
            return errors
        except KeyError as e:
            errors.append(f"Missing required field: {e}")
            return errors
        except ValueError as e:
            errors.append(f"Invalid configuration: {e}")
            return errors

        # Validate world file exists
        if not config.world_path.exists():
            errors.append(f"World file not found: {config.world_path}")

        # Validate map file exists
        if not config.map_path.exists():
            errors.append(f"Map file not found: {config.map_path}")

        # Validate nav2 params if specified
        if config.nav2_params_path and not config.nav2_params_path.exists():
            errors.append(f"Nav2 params file not found: {config.nav2_params_path}")

        # Validate model path if specified
        if config.model_path and not config.model_path.exists():
            errors.append(f"Model path not found: {config.model_path}")

        # Validate mission thresholds
        if config.thresholds.enter_threshold <= config.thresholds.exit_threshold:
            errors.append(
                f"enter_threshold ({config.thresholds.enter_threshold}) must be "
                f"greater than exit_threshold ({config.thresholds.exit_threshold})"
            )

        if config.thresholds.source_threshold <= config.thresholds.enter_threshold:
            errors.append(
                f"source_threshold ({config.thresholds.source_threshold}) must be "
                f"greater than enter_threshold ({config.thresholds.enter_threshold})"
            )

        if config.thresholds.confirm_samples < 1:
            errors.append("confirm_samples must be at least 1")

        if config.thresholds.source_radius <= 0:
            errors.append("source_radius must be positive")

        # Validate patrol points
        if not config.patrol_points:
            errors.append("At least one patrol point is required")

        # Validate GADEN config if enabled
        if config.use_gaden and config.gaden_config:
            if not config.gaden_config.project_path:
                errors.append("GADEN project_path is required when GADEN is enabled")

        return errors

    def create_scene(self, template: str, name: str) -> Path:
        """Create a new scene from a template.

        Args:
            template: Name of template scene to copy
            name: Name for the new scene

        Returns:
            Path to the new scene directory

        Raises:
            ValueError: If template doesn't exist or scene already exists
        """
        # Validate template exists
        if not self.scene_exists(template):
            raise ValueError(f"Template scene not found: {template}")

        # Check new scene doesn't exist
        new_scene_dir = self.scenes_dir / name
        if new_scene_dir.exists():
            raise ValueError(f"Scene already exists: {name}")

        # Copy template directory
        template_dir = self.scenes_dir / template
        shutil.copytree(template_dir, new_scene_dir)

        # Update scene.yaml with new name
        yaml_path = new_scene_dir / "scene.yaml"
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        data["scene_name"] = name

        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        # Clear cache for this name if present
        self._cache.pop(name, None)

        return new_scene_dir

    def reload_scene(self, name: str) -> SceneConfig | None:
        """Reload scene configuration from disk.

        Args:
            name: Scene name to reload

        Returns:
            Reloaded SceneConfig, or None if scene doesn't exist
        """
        self._cache.pop(name, None)
        return self.get_scene(name)

    def get_scene_dir(self, name: str) -> Path | None:
        """Get scene directory path.

        Args:
            name: Scene name

        Returns:
            Path to scene directory, or None if not found
        """
        if not self.scene_exists(name):
            return None
        return self.scenes_dir / name
