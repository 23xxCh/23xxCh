"""Configuration constants and utilities for web console."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
def _get_scene_registry() -> Any:
    """Get scene registry with error handling.

    Returns:
        SceneRegistry instance or None if unavailable.
    """
    try:
        from .scene_registry import get_scene_registry
        return get_scene_registry()
    except ImportError as e:
        logger.warning(f"Scene registry module not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize scene registry: {e}")
        return None


DEFAULT_LAUNCH_PROFILE = {
    "scene": "warehouse",
    "use_gaden": "true",
    "use_slam": "true",
    "use_rviz": "true",
    "headless": "false",
}


def _coerce_bool_token(value: Any, *, default: str) -> str:
    """Convert various truthy/falsy values to 'true' or 'false' string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return "true"
    if text in {"false", "0", "no", "off"}:
        return "false"
    return default


def _sanitize_scene_id(scene: str) -> str:
    """Sanitize scene ID to prevent path traversal and injection.

    Only allows alphanumeric characters, hyphens, and underscores.
    """
    if not scene:
        return "warehouse"
    # Remove any path separators and dangerous characters
    sanitized = "".join(c for c in scene if c.isalnum() or c in "-_")
    # Limit length
    return sanitized[:64] or "warehouse"


def normalize_launch_profile(profile: dict[str, Any] | None) -> dict[str, str]:
    """Normalize and validate a launch profile configuration.

    Scene validation is performed against the scene registry to support
    dynamic scene discovery.
    """
    source = dict(DEFAULT_LAUNCH_PROFILE)
    if profile:
        source.update({k: v for k, v in profile.items() if v is not None})

    # Sanitize scene ID
    scene = _sanitize_scene_id(str(source.get("scene", "warehouse")).strip().lower())

    # Validate against available scenes (fallback to default if invalid)
    registry = _get_scene_registry()
    if registry is not None:
        try:
            if not registry.is_valid_scene(scene):
                default_scene = registry.get_default_scene()
                scene = default_scene
        except Exception as e:
            logger.debug(f"Scene validation failed: {e}")
    # If registry is None, accept the sanitized scene ID
    # (validation will happen at launch time)

    return {
        "scene": scene,
        "use_gaden": _coerce_bool_token(source.get("use_gaden"), default=DEFAULT_LAUNCH_PROFILE["use_gaden"]),
        "use_slam": _coerce_bool_token(source.get("use_slam"), default=DEFAULT_LAUNCH_PROFILE["use_slam"]),
        "use_rviz": _coerce_bool_token(source.get("use_rviz"), default=DEFAULT_LAUNCH_PROFILE["use_rviz"]),
        "headless": _coerce_bool_token(source.get("headless"), default=DEFAULT_LAUNCH_PROFILE["headless"]),
    }


def build_demo_prep_command(profile: dict[str, Any] | None = None) -> list[str]:
    """Build the demo_prep command based on profile.

    Args:
        profile: Launch profile configuration. If None, uses defaults.

    Returns:
        List of command arguments for demo_prep.
    """
    p = normalize_launch_profile(profile)
    return [
        "ros2",
        "run",
        "h2track_utils",
        "demo_prep",
        "--scene",
        p["scene"],
        "--use-gaden",
        p["use_gaden"],
    ]


def build_demo_launch_command(profile: dict[str, Any] | None = None) -> list[str]:
    """Build the ros2 launch command for demo."""
    p = normalize_launch_profile(profile)
    return [
        "ros2",
        "launch",
        "h2track_bringup",
        "demo.launch.py",
        f"scene:={p['scene']}",
        f"use_gaden:={p['use_gaden']}",
        f"use_slam:={p['use_slam']}",
        f"use_rviz:={p['use_rviz']}",
        f"headless:={p['headless']}",
    ]
