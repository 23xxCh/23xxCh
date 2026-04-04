"""Thread-safe store for simulation metrics and health data.

This module provides the MetricsStore class for tracking:
- Phase transitions (INIT, PREP, LAUNCH, NAV_READY, RUNNING, STOPPING, EXITED)
- Robot mode (PATROL, SEEK_CONFIRM, SEEK_TRACK, SOURCE_FOUND)
- Gas concentration history
- Navigation statistics
- Topic health status
- Node health status
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque


# Regex patterns for log parsing
MODE_TRANSITION_RE = re.compile(r"Mode transition:\s+\w+\s+->\s+([A-Z_]+)")
CONCENTRATION_RE = re.compile(r"(?:concentration|conc)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
NAV_BEGIN_RE = re.compile(r"Begin navigating from current location")


def _now_iso() -> str:
    """Return current time as ISO format string with timezone."""
    return datetime.now(tz=timezone.utc).isoformat()


def summarize_gas_signal(
    *, raw_history: list[dict[str, Any]], raw_topic_health: dict[str, Any]
) -> dict[str, str]:
    """Summarize gas signal status from raw history and topic health.

    Args:
        raw_history: List of gas reading history entries
        raw_topic_health: Topic health status for /gaden/sensor_reading

    Returns:
        Dictionary with signal_status and signal_reason keys
    """
    raw_values = [
        float(row.get("value", 0.0))
        for row in raw_history
        if row.get("value") is not None
    ]
    raw_status = str(raw_topic_health.get("status", "stale"))

    if not raw_values:
        return {
            "signal_status": "no_samples",
            "signal_reason": "未收到原始 GADEN 读数",
        }

    if raw_status != "ok":
        return {
            "signal_status": "stale",
            "signal_reason": "原始 GADEN 话题已过期",
        }

    if max(abs(value) for value in raw_values) <= 1e-9:
        return {
            "signal_status": "flatline_zero",
            "signal_reason": "原始气体读数连续为全零",
        }

    return {
        "signal_status": "active",
        "signal_reason": "原始 GADEN 气体读数正常供数",
    }


class MetricsStore:
    """Thread-safe store for simulation metrics and health data.

    This class tracks various metrics during simulation runtime:
    - Phase transitions with timestamps and durations
    - Robot mode changes
    - Gas concentration history
    - Navigation goal statistics
    - Topic health (staleness detection)
    - Node health (up/down status and restart counts)

    All methods are thread-safe via an internal lock.
    """

    def __init__(self, max_points: int = 600) -> None:
        """Initialize the metrics store.

        Args:
            max_points: Maximum number of data points to retain in history buffers
        """
        self._lock = threading.Lock()
        self._max_points = max_points

        # Phase tracking
        self._phase_current = "INIT"
        self._phase_timeline: Deque[dict[str, Any]] = deque(maxlen=max_points)
        init_ts = _now_iso()
        self._phase_timeline.append(
            {
                "phase": "INIT",
                "start_ts": init_ts,
                "end_ts": None,
                "duration_ms": None,
                "reason": "init",
                "_start_mono": time.monotonic(),
            }
        )
        self._phase_started_iso = init_ts

        # Mode tracking
        self._mode_current: str | None = None
        self._mode_history: Deque[dict[str, Any]] = deque(maxlen=max_points)

        # Gas concentration tracking
        self._gas_current: float | None = None
        self._gas_history: Deque[dict[str, Any]] = deque(maxlen=max_points)
        self._gas_raw_current: float | None = None
        self._gas_raw_history: Deque[dict[str, Any]] = deque(maxlen=max_points)

        # Source found status
        self._source_found: bool | None = None

        # Navigation statistics
        self._nav_goal_succeeded = 0
        self._nav_failed_to_make_progress = 0
        self._nav_goal_canceled = 0
        self._nav_goal_started_at_mono: float | None = None
        self._nav_goal_durations_sec: Deque[float] = deque(maxlen=max_points)

        # Topic health tracking
        self._topic_stats: dict[str, dict[str, Any]] = {
            "/gas_concentration": {
                "timestamps": deque(maxlen=max_points),
                "last_value": None,
                "stale_threshold_sec": 2.5,
            },
            "/gaden/sensor_reading": {
                "timestamps": deque(maxlen=max_points),
                "last_value": None,
                "stale_threshold_sec": 2.5,
            },
            "/robot_mode": {
                "timestamps": deque(maxlen=max_points),
                "last_value": None,
                "stale_threshold_sec": 20.0,
            },
            "/source_found": {
                "timestamps": deque(maxlen=max_points),
                "last_value": None,
                "stale_threshold_sec": 20.0,
            },
            "/odom": {
                "timestamps": deque(maxlen=max_points),
                "last_value": None,
                "stale_threshold_sec": 1.5,
            },
        }

        # Node health tracking
        self._node_health: dict[str, dict[str, Any]] = {}
        self._node_health_updated_at = _now_iso()

        # Last update timestamp
        self._updated_at = _now_iso()

    def _touch(self) -> None:
        """Update the last modification timestamp."""
        self._updated_at = _now_iso()

    def _mark_topic_tick(self, topic: str, value: Any = None) -> None:
        """Record a topic update with timestamp.

        Args:
            topic: Topic name to update
            value: Optional value to store
        """
        stats = self._topic_stats.get(topic)
        if stats is None:
            return
        stats["timestamps"].append(time.monotonic())
        if value is not None:
            stats["last_value"] = value

    def set_phase(self, phase: str, reason: str = "") -> None:
        """Update the current phase.

        Args:
            phase: New phase name (will be normalized to uppercase)
            reason: Reason for the phase transition
        """
        phase_name = str(phase).strip().upper()
        if not phase_name:
            return

        with self._lock:
            if self._phase_current == phase_name:
                return

            now_iso = _now_iso()
            now_mono = time.monotonic()

            # Close previous phase
            if self._phase_timeline and self._phase_timeline[-1].get("end_ts") is None:
                prev = self._phase_timeline[-1]
                prev["end_ts"] = now_iso
                prev["duration_ms"] = int(
                    max(0.0, now_mono - float(prev.get("_start_mono", now_mono))) * 1000.0
                )

            # Add new phase
            self._phase_timeline.append(
                {
                    "phase": phase_name,
                    "start_ts": now_iso,
                    "end_ts": None,
                    "duration_ms": None,
                    "reason": reason,
                    "_start_mono": now_mono,
                }
            )

            self._phase_current = phase_name
            self._phase_started_iso = now_iso
            self._touch()

    def set_mode(self, mode: str) -> None:
        """Update the current robot mode.

        Args:
            mode: New mode value
        """
        with self._lock:
            self._mode_current = mode
            self._mode_history.append({"timestamp": _now_iso(), "value": mode})
            self._mark_topic_tick("/robot_mode", mode)
            self._touch()

    def set_gas(self, value: float) -> None:
        """Update gas concentration.

        Args:
            value: Gas concentration reading
        """
        with self._lock:
            self._gas_current = float(value)
            self._gas_history.append({"timestamp": _now_iso(), "value": float(value)})
            self._mark_topic_tick("/gas_concentration", float(value))
            self._touch()

    def set_gas_raw(self, value: float) -> None:
        """Update raw GADEN gas sensor reading.

        Args:
            value: Raw gas sensor reading from GADEN
        """
        with self._lock:
            self._gas_raw_current = float(value)
            self._gas_raw_history.append(
                {"timestamp": _now_iso(), "value": float(value)}
            )
            self._mark_topic_tick("/gaden/sensor_reading", float(value))
            self._touch()

    def set_source_found(self, value: bool) -> None:
        """Update source found status.

        Args:
            value: Whether the source has been found
        """
        with self._lock:
            self._source_found = bool(value)
            self._mark_topic_tick("/source_found", bool(value))
            self._touch()

    def observe_odom_tick(self, *, x: float, y: float) -> None:
        """Record an odometry update.

        Args:
            x: X position
            y: Y position
        """
        with self._lock:
            self._mark_topic_tick("/odom", {"x": float(x), "y": float(y)})
            self._touch()

    def update_node_health(
        self, node_up_map: dict[str, bool], *, last_error: str = ""
    ) -> None:
        """Update node health status.

        Args:
            node_up_map: Dictionary mapping node names to their up/down status
            last_error: Optional error message for down nodes
        """
        with self._lock:
            now_iso = _now_iso()
            self._node_health_updated_at = now_iso

            for node_name, is_up in node_up_map.items():
                prev = self._node_health.get(node_name, {})
                restart_count = int(prev.get("restart_count", 0))

                # Increment restart count if node was down and is now up
                if bool(is_up) and not bool(prev.get("up", False)) and prev.get("last_seen"):
                    restart_count += 1

                self._node_health[node_name] = {
                    "name": node_name,
                    "up": bool(is_up),
                    "status": "up" if bool(is_up) else "down",
                    "restart_count": restart_count,
                    "last_seen": now_iso if bool(is_up) else prev.get("last_seen"),
                    "last_error": (
                        ""
                        if bool(is_up)
                        else (last_error or prev.get("last_error", "not discovered"))
                    ),
                }
            self._touch()

    def _start_nav_goal(self) -> None:
        """Mark the start of a navigation goal."""
        self._nav_goal_started_at_mono = time.monotonic()

    def _finalize_nav_goal(self) -> None:
        """Finalize and record the duration of the current navigation goal."""
        if self._nav_goal_started_at_mono is None:
            return
        duration = time.monotonic() - self._nav_goal_started_at_mono
        if duration >= 0.0:
            self._nav_goal_durations_sec.append(duration)
        self._nav_goal_started_at_mono = None

    def _topic_health_snapshot(self) -> dict[str, Any]:
        """Generate a snapshot of topic health status.

        Returns:
            Dictionary mapping topic names to their health status
        """
        now_mono = time.monotonic()
        payload: dict[str, Any] = {}

        for topic, stats in self._topic_stats.items():
            timestamps: Deque[float] = stats["timestamps"]
            last_seen = timestamps[-1] if timestamps else None

            # Calculate frequency
            hz = 0.0
            if len(timestamps) >= 2:
                dt = timestamps[-1] - timestamps[0]
                if dt > 0:
                    hz = (len(timestamps) - 1) / dt

            # Calculate staleness
            stale_sec = None if last_seen is None else max(0.0, now_mono - last_seen)
            threshold = float(stats.get("stale_threshold_sec", 2.0))
            status = "ok" if stale_sec is not None and stale_sec <= threshold else "stale"

            payload[topic] = {
                "status": status,
                "hz": round(hz, 3),
                "stale_sec": None if stale_sec is None else round(stale_sec, 3),
                "last_value": stats.get("last_value"),
                "threshold_sec": threshold,
            }

        return payload

    def observe_log_line(self, line: str) -> None:
        """Parse a log line and update metrics accordingly.

        This method extracts:
        - Mode transitions
        - Gas concentration values
        - Phase changes
        - Navigation events
        - Source found status

        Args:
            line: Log line to parse
        """
        text = line.strip()
        if not text:
            return

        # Mode transition detection
        mode_match = MODE_TRANSITION_RE.search(text)
        if mode_match:
            self.set_mode(mode_match.group(1))
            self.set_phase(mode_match.group(1), reason="mode_transition")

        # Concentration detection
        conc_match = CONCENTRATION_RE.search(text)
        if conc_match:
            try:
                self.set_gas(float(conc_match.group(1)))
            except ValueError:
                pass

        # Phase detection from log patterns
        lowered = text.lower()
        if "running demo_prep" in lowered:
            self.set_phase("PREP", reason="demo_prep")
        elif "launching:" in lowered:
            self.set_phase("LAUNCH", reason="launch")
        elif "nav2 is ready for use" in lowered:
            self.set_phase("NAV_READY", reason="nav_ready")
        elif "stopping simulation" in lowered:
            self.set_phase("STOPPING", reason="stop")
        elif "simulation exited with code" in lowered:
            self.set_phase("EXITED", reason="exit")

        # Navigation goal tracking
        if NAV_BEGIN_RE.search(text) or "navigating to goal:" in lowered:
            with self._lock:
                self._start_nav_goal()
                self._touch()

        # Source found detection
        if "source_found" in lowered and "true" in lowered:
            self.set_source_found(True)
        if "-> source_found" in lowered:
            self.set_source_found(True)

        # Navigation result tracking
        with self._lock:
            if "Goal succeeded" in text:
                self._finalize_nav_goal()
                self._nav_goal_succeeded += 1
            if "Canceling current task" in text:
                self._finalize_nav_goal()
                self._nav_goal_canceled += 1
            if "Failed to make progress" in text:
                self._finalize_nav_goal()
                self._nav_failed_to_make_progress += 1
            self._touch()

    def snapshot(self, limit: int = 120) -> dict[str, Any]:
        """Generate a snapshot of all metrics.

        Args:
            limit: Maximum number of history entries to include

        Returns:
            Dictionary containing all current metrics and histories
        """
        with self._lock:
            gas_history = list(self._gas_history)[-limit:]
            gas_raw_history = list(self._gas_raw_history)[-limit:]
            mode_history = list(self._mode_history)[-limit:]

            # Build phase timeline, stripping internal fields
            phase_timeline = []
            for row in list(self._phase_timeline)[-limit:]:
                clean = {k: v for k, v in row.items() if k != "_start_mono"}
                phase_timeline.append(clean)

            # Calculate navigation statistics
            mean_goal_time = None
            if self._nav_goal_durations_sec:
                mean_goal_time = sum(self._nav_goal_durations_sec) / len(
                    self._nav_goal_durations_sec
                )

            current_goal_age = None
            if self._nav_goal_started_at_mono is not None:
                current_goal_age = max(
                    0.0, time.monotonic() - self._nav_goal_started_at_mono
                )

            topic_health = self._topic_health_snapshot()

            return {
                "phase": {
                    "current": self._phase_current,
                    "started_at": self._phase_started_iso,
                    "timeline": phase_timeline,
                },
                "mode": {
                    "current": self._mode_current,
                    "history": mode_history,
                },
                "gas": {
                    "current": self._gas_current,
                    "history": gas_history,
                    "raw_current": self._gas_raw_current,
                    "raw_history": gas_raw_history,
                    **summarize_gas_signal(
                        raw_history=gas_raw_history,
                        raw_topic_health=topic_health.get("/gaden/sensor_reading", {}),
                    ),
                },
                "source_found": {
                    "current": self._source_found,
                },
                "nav": {
                    "goal_succeeded": self._nav_goal_succeeded,
                    "failed_to_make_progress": self._nav_failed_to_make_progress,
                    "goal_canceled": self._nav_goal_canceled,
                    "mean_goal_time_sec": (
                        None if mean_goal_time is None else round(mean_goal_time, 3)
                    ),
                    "current_goal_age_sec": (
                        None if current_goal_age is None else round(current_goal_age, 3)
                    ),
                    "goal_durations_sec": [
                        round(v, 3) for v in list(self._nav_goal_durations_sec)[-limit:]
                    ],
                },
                "topic_health": topic_health,
                "node_health": {
                    "updated_at": self._node_health_updated_at,
                    "nodes": list(self._node_health.values()),
                },
                "updated_at": self._updated_at,
            }
