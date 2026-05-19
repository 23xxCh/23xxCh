"""Blackboard system for h2track Behavior Tree integration.

Provides named accessors / mutators so nodes read and write shared state without
tight coupling.  The keys are organised by namespace:
  sensor.*   - latest sensor data
  nav2.*     - Nav2 state and targets
  tracker.*  - tracking algorithm outputs
  mission.*  - mission state machine outputs
"""

from __future__ import annotations

from typing import Any


class BlackboardNamespace:
    """Thin typed accessor over a flat dict, one per namespace."""

    def __init__(self, store: dict[str, Any], namespace: str) -> None:
        self._store = store
        self._ns = namespace
        self._init_keys()

    def _init_keys(self) -> None:
        for key in _BB_DEFS.get(self._ns, []):
            self._store.setdefault(f"{self._ns}.{key}", None)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        return self._store.get(f"{self._ns}.{key}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self._store[f"{self._ns}.{key}"] = value

    def __repr__(self) -> str:
        return f"BlackboardNamespace({self._ns!r})"


_BB_DEFS: dict[str, list[str]] = {
    "sensor": [
        "concentration",
        "robot_pose",
        "robot_yaw",
        "wind",
        "pf_estimate",
        "pf_confidence",
    ],
    "nav2": [
        "target_pose",
        "target_yaw",
        "status",
        "result",
        "task_complete",
        "goal_reached",
        "path_deviation",
        "recovery_needed",
        "nav_ready",
        "waiting_for_server",
    ],
    "tracker": [
        "target",
        "state",
        "heading",
        "step_size",
        "is_navigating_around_obstacle",
        "target_locked",
        "pf_estimate",
        "pf_confidence",
        "wind_estimate",
    ],
    "mission": [
        "mode",
        "mode_changed",
        "new_mode",
        "source_estimate",
        "patrol_target",
        "patrol_index",
    ],
    "safety": [
        "obstacle_detected",
        "suggested_action",
        "alternative_target",
        "stuck_duration",
    ],
}


class H2TrackBlackboard:
    """Convenience factory / facade for the shared blackboard store."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self.sensor = BlackboardNamespace(self._store, "sensor")
        self.nav2 = BlackboardNamespace(self._store, "nav2")
        self.tracker = BlackboardNamespace(self._store, "tracker")
        self.mission = BlackboardNamespace(self._store, "mission")
        self.safety = BlackboardNamespace(self._store, "safety")

    @property
    def store(self) -> dict[str, Any]:
        return self._store

    def reset(self) -> None:
        """Clear all blackboard entries (e.g. on mission reset)."""
        self._store.clear()
