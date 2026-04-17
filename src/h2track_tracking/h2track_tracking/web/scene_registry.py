"""Scene registry for discovering and managing available scenes.

This module provides scene discovery and metadata management for multi-map support.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SceneInfo:
    """Information about an available scene.

    Attributes:
        id: Scene identifier (directory name)
        name: Human-readable scene name
        description: Scene description
        world_file: Path to Gazebo world file
        map_file: Path to Nav2 map file
        nav2_params: Path to Nav2 parameters file
        use_gaden: Whether scene uses GADEN simulation
        use_slam: Whether scene uses SLAM
        has_gaden_config: Whether GADEN configuration exists
        thumbnail: Optional path to thumbnail image
        metadata: Additional scene metadata
    """

    id: str
    name: str
    description: str
    world_file: str
    map_file: str
    nav2_params: str
    use_gaden: bool
    use_slam: bool
    has_gaden_config: bool
    thumbnail: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "world_file": self.world_file,
            "map_file": self.map_file,
            "nav2_params": self.nav2_params,
            "use_gaden": self.use_gaden,
            "use_slam": self.use_slam,
            "has_gaden_config": self.has_gaden_config,
            "thumbnail": self.thumbnail,
            "metadata": self.metadata or {},
        }


class SceneRegistry:
    """Registry for discovering and caching available scenes.

    Scans the scenes directory for valid scene configurations.
    """

    def __init__(self, scenes_dir: str | Path | None = None) -> None:
        """Initialize the scene registry.

        Args:
            scenes_dir: Path to scenes directory. If None, attempts to find
                it in the h2track_sim package.
        """
        if scenes_dir is None:
            scenes_dir = self._find_default_scenes_dir()
        self._scenes_dir = Path(scenes_dir)
        self._cache: dict[str, SceneInfo] | None = None

    @staticmethod
    def _find_default_scenes_dir() -> Path:
        """Find the default scenes directory.

        Tries multiple locations in order:
        1. Source directory (development)
        2. Install directory (deployed)
        """
        cwd = Path.cwd()
        candidates = [
            cwd / "src" / "h2track_sim" / "scenes",
            cwd / "install" / "h2track_sim" / "share" / "h2track_sim" / "scenes",
        ]
        for path in candidates:
            if path.exists():
                return path
        # Return first candidate as fallback
        return candidates[0]

    def _load_scene_config(self, scene_dir: Path) -> dict[str, Any] | None:
        """Load scene.yaml configuration from a scene directory.

        Args:
            scene_dir: Path to scene directory

        Returns:
            Parsed YAML content or None if invalid
        """
        config_path = scene_dir / "scene.yaml"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as exc:
            logger.warning(f"Failed to load scene config from {config_path}: {exc}")
            return None

    def _validate_scene(self, scene_id: str, config: dict[str, Any]) -> SceneInfo | None:
        """Validate scene configuration and create SceneInfo.

        Args:
            scene_id: Scene identifier (directory name)
            config: Parsed scene configuration

        Returns:
            SceneInfo if valid, None otherwise
        """
        if not isinstance(config, dict):
            return None

        # Required fields
        world_file = config.get("world")
        map_file = config.get("map")

        if not world_file or not map_file:
            logger.debug(f"Scene {scene_id} missing required fields (world/map)")
            return None

        # Extract metadata
        scene_name = config.get("scene_name", scene_id)
        description = config.get("description", f"Scene: {scene_name}")
        nav2_params = config.get("nav2_params", "config/nav2_params.yaml")
        use_gaden = config.get("use_gaden", True)
        use_slam = config.get("use_slam", False)

        # Check for GADEN configuration
        gaden_config = config.get("gaden", {})
        has_gaden_config = isinstance(gaden_config, dict) and gaden_config.get(
            "project_path"
        )

        # Check for thumbnail
        scene_dir = self._scenes_dir / scene_id
        thumbnail_candidates = ["thumbnail.png", "thumbnail.jpg", "preview.png", "preview.jpg"]
        thumbnail = None
        for candidate in thumbnail_candidates:
            thumb_path = scene_dir / candidate
            if thumb_path.exists():
                thumbnail = str(thumb_path)
                break

        # Build metadata
        metadata: dict[str, Any] = {}
        if "mission_manager" in config:
            mission = config["mission_manager"]
            metadata["patrol_points_count"] = len(mission.get("patrol_points", []))
            metadata["initial_pose"] = mission.get("initial_pose", {})
        if "gas_source" in config:
            metadata["gas_source"] = config["gas_source"]

        return SceneInfo(
            id=scene_id,
            name=scene_name,
            description=description,
            world_file=world_file,
            map_file=map_file,
            nav2_params=nav2_params,
            use_gaden=use_gaden,
            use_slam=use_slam,
            has_gaden_config=bool(has_gaden_config),
            thumbnail=thumbnail,
            metadata=metadata,
        )

    def discover_scenes(self, force_refresh: bool = False) -> dict[str, SceneInfo]:
        """Discover all available scenes.

        Args:
            force_refresh: Force re-discovery even if cache exists

        Returns:
            Dictionary mapping scene IDs to SceneInfo
        """
        if self._cache is not None and not force_refresh:
            return dict(self._cache)

        scenes: dict[str, SceneInfo] = {}

        if not self._scenes_dir.exists():
            logger.warning(f"Scenes directory not found: {self._scenes_dir}")
            self._cache = scenes
            return scenes

        for scene_dir in self._scenes_dir.iterdir():
            if not scene_dir.is_dir():
                continue

            scene_id = scene_dir.name
            config = self._load_scene_config(scene_dir)
            if config is None:
                continue

            scene_info = self._validate_scene(scene_id, config)
            if scene_info is not None:
                scenes[scene_id] = scene_info
                logger.debug(f"Discovered scene: {scene_id}")

        self._cache = scenes
        logger.info(f"Discovered {len(scenes)} scenes: {list(scenes.keys())}")
        return dict(scenes)

    def get_scene(self, scene_id: str) -> SceneInfo | None:
        """Get information about a specific scene.

        Args:
            scene_id: Scene identifier

        Returns:
            SceneInfo if found, None otherwise
        """
        scenes = self.discover_scenes()
        return scenes.get(scene_id)

    def list_scenes(self) -> list[SceneInfo]:
        """List all available scenes.

        Returns:
            List of SceneInfo objects
        """
        scenes = self.discover_scenes()
        return list(scenes.values())

    def is_valid_scene(self, scene_id: str) -> bool:
        """Check if a scene ID is valid.

        Args:
            scene_id: Scene identifier to check

        Returns:
            True if scene exists and is valid
        """
        return self.get_scene(scene_id) is not None

    def get_default_scene(self) -> str:
        """Get the default scene ID.

        Returns:
            Default scene ID (first available or 'warehouse')
        """
        scenes = self.discover_scenes()
        if not scenes:
            return "warehouse"
        # Prefer warehouse if available
        if "warehouse" in scenes:
            return "warehouse"
        # Otherwise return first available
        return next(iter(scenes.keys()))


# Global registry instance with thread-safe access
_global_registry: SceneRegistry | None = None
_registry_lock = threading.Lock()


def get_scene_registry() -> SceneRegistry:
    """Get the global scene registry instance.

    Thread-safe singleton access using double-checked locking.

    Returns:
        SceneRegistry singleton instance
    """
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = SceneRegistry()
    return _global_registry


def reset_scene_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _global_registry
    with _registry_lock:
        _global_registry = None
