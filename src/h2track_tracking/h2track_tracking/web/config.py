"""Configuration constants and utilities for web console."""

from __future__ import annotations

from typing import Any


DEMO_PREP_COMMAND = [
    "ros2",
    "run",
    "h2track_tracking",
    "demo_prep",
    "--scene",
    "warehouse",
    "--use-gaden",
    "true",
]


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


def normalize_launch_profile(profile: dict[str, Any] | None) -> dict[str, str]:
    """Normalize and validate a launch profile configuration."""
    source = dict(DEFAULT_LAUNCH_PROFILE)
    if profile:
        source.update({k: v for k, v in profile.items() if v is not None})
    scene = str(source.get("scene", "warehouse")).strip().lower()
    if scene not in {"warehouse", "baseline"}:
        scene = "warehouse"
    return {
        "scene": scene,
        "use_gaden": _coerce_bool_token(source.get("use_gaden"), default=DEFAULT_LAUNCH_PROFILE["use_gaden"]),
        "use_slam": _coerce_bool_token(source.get("use_slam"), default=DEFAULT_LAUNCH_PROFILE["use_slam"]),
        "use_rviz": _coerce_bool_token(source.get("use_rviz"), default=DEFAULT_LAUNCH_PROFILE["use_rviz"]),
        "headless": _coerce_bool_token(source.get("headless"), default=DEFAULT_LAUNCH_PROFILE["headless"]),
    }


def build_demo_launch_command(profile: dict[str, Any] | None = None) -> list[str]:
    """Build the ros2 launch command for demo."""
    p = normalize_launch_profile(profile)
    return [
        "ros2",
        "launch",
        "h2track_sim",
        "demo.launch.py",
        f"scene:={p['scene']}",
        f"use_gaden:={p['use_gaden']}",
        f"use_slam:={p['use_slam']}",
        f"use_rviz:={p['use_rviz']}",
        f"headless:={p['headless']}",
    ]
