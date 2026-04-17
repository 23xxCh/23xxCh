"""Test script for scene_registry module."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from h2track_tracking.web.scene_registry import SceneRegistry, SceneInfo


def test_scene_registry():
    """Test scene discovery and validation."""
    scenes_dir = Path(__file__).parent.parent.parent / "h2track_sim" / "scenes"
    registry = SceneRegistry(scenes_dir)

    # Test discovery
    scenes = registry.list_scenes()
    print(f"Found {len(scenes)} scenes")
    assert len(scenes) >= 3, f"Expected at least 3 scenes, got {len(scenes)}"

    # Test scene info
    for scene in scenes:
        print(f"  - {scene.id}: {scene.name}")
        assert scene.id, "Scene ID is required"
        assert scene.world_file, "World file is required"
        assert scene.map_file, "Map file is required"

    # Test default scene
    default = registry.get_default_scene()
    print(f"\nDefault scene: {default}")
    assert default in ["warehouse", "baseline", "office"]

    # Test validation
    assert registry.is_valid_scene("warehouse") is True
    assert registry.is_valid_scene("office") is True
    assert registry.is_valid_scene("nonexistent") is False

    # Test get_scene
    warehouse = registry.get_scene("warehouse")
    assert warehouse is not None
    assert warehouse.id == "warehouse"

    # Test to_dict
    data = warehouse.to_dict()
    assert "id" in data
    assert "name" in data
    assert "description" in data

    print("\nAll scene_registry tests passed!")


def test_config():
    """Test config module."""
    from h2track_tracking.web.config import normalize_launch_profile, _sanitize_scene_id

    # Test sanitization
    assert _sanitize_scene_id("warehouse") == "warehouse"
    assert _sanitize_scene_id("../../../etc/passwd") == "etcpasswd"
    assert _sanitize_scene_id("") == "warehouse"
    assert _sanitize_scene_id("scene-with-dashes") == "scene-with-dashes"
    assert _sanitize_scene_id("scene@#$%^&*()") == "scene"

    # Test normalize with valid scene
    result = normalize_launch_profile({"scene": "office"})
    assert result["scene"] == "office"

    # Test normalize with invalid scene (should fallback)
    result = normalize_launch_profile({"scene": "nonexistent"})
    assert result["scene"] == "warehouse"  # Falls back to default

    print("\nAll config tests passed!")


if __name__ == "__main__":
    test_scene_registry()
    test_config()
    print("\n=== All tests passed! ===")
