# 代码质量优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `demo_web_server.py` (2231行) 和 `llm_agent.py` (906行) 拆分为多个小模块，提高代码可维护性。

**Architecture:** 按职责拆分，每个模块单一职责。`demo_web_server.py` 拆分为 web/ 子包，`llm_agent.py` 拆分为 llm/ 子包。保留原文件作为兼容入口。

**Tech Stack:** Python 3.10, ROS 2 Humble, FastAPI, pytest

---

## 阶段 1：拆分 demo_web_server.py

### Task 1: 创建 web/ 目录结构

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/__init__.py`

- [ ] **Step 1: 创建 web 目录和 __init__.py**

```python
# src/h2track_tracking/h2track_tracking/web/__init__.py
"""Web console modules for H2Track simulation control."""

from .app import create_app

__all__ = ["create_app"]
```

- [ ] **Step 2: 验证目录结构**

Run: `ls -la src/h2track_tracking/h2track_tracking/web/`
Expected: `__init__.py` 文件存在

- [ ] **Step 3: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/__init__.py
git commit -m "refactor(web): create web package structure"
```

---

### Task 2: 提取 config.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/config.py`
- Test: `src/h2track_tracking/test/test_web_config.py`

- [ ] **Step 1: 编写 config.py 测试**

```python
# src/h2track_tracking/test/test_web_config.py
"""Tests for web config module."""

import pytest
from h2track_tracking.web.config import (
    DEMO_PREP_COMMAND,
    DEFAULT_LAUNCH_PROFILE,
    normalize_launch_profile,
    build_demo_launch_command,
    _coerce_bool_token,
)


def test_demo_prep_command():
    assert DEMO_PREP_COMMAND[0] == "ros2"
    assert "demo_prep" in DEMO_PREP_COMMAND


def test_default_launch_profile():
    assert DEFAULT_LAUNCH_PROFILE["scene"] == "warehouse"
    assert DEFAULT_LAUNCH_PROFILE["use_gaden"] == "true"


def test_coerce_bool_token_true():
    assert _coerce_bool_token(True, default="false") == "true"
    assert _coerce_bool_token("yes", default="false") == "true"
    assert _coerce_bool_token("1", default="false") == "true"


def test_coerce_bool_token_false():
    assert _coerce_bool_token(False, default="true") == "false"
    assert _coerce_bool_token("no", default="true") == "false"
    assert _coerce_bool_token("0", default="true") == "false"


def test_normalize_launch_profile_defaults():
    result = normalize_launch_profile(None)
    assert result["scene"] == "warehouse"
    assert result["use_gaden"] == "true"


def test_normalize_launch_profile_override():
    result = normalize_launch_profile({"scene": "baseline", "use_gaden": "false"})
    assert result["scene"] == "baseline"
    assert result["use_gaden"] == "false"


def test_normalize_launch_profile_invalid_scene():
    result = normalize_launch_profile({"scene": "invalid"})
    assert result["scene"] == "warehouse"


def test_build_demo_launch_command():
    cmd = build_demo_launch_command()
    assert "ros2" in cmd
    assert "launch" in cmd
    assert "demo.launch.py" in cmd
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_web_config.py -v 2>&1 || true`
Expected: FAIL with "ModuleNotFoundError: No module named 'h2track_tracking.web.config'"

- [ ] **Step 3: 创建 config.py**

```python
# src/h2track_tracking/h2track_tracking/web/config.py
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

STATIC_CONSOLE_DIRNAME = "static_console"
UI_MODE_STATIC = "static_bundle"
UI_MODE_LEGACY = "legacy_inline"


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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_web_config.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/config.py
git add src/h2track_tracking/test/test_web_config.py
git commit -m "refactor(web): extract config module from demo_web_server"
```

---

### Task 3: 提取 metrics_store.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/metrics_store.py`
- Test: `src/h2track_tracking/test/test_metrics_store.py`

- [ ] **Step 1: 编写 metrics_store.py 测试**

```python
# src/h2track_tracking/test/test_metrics_store.py
"""Tests for MetricsStore class."""

import pytest
from h2track_tracking.web.metrics_store import MetricsStore, _now_iso


def test_now_iso_returns_string():
    result = _now_iso()
    assert isinstance(result, str)
    assert "T" in result  # ISO format


def test_metrics_store_initial_state():
    store = MetricsStore()
    snapshot = store.snapshot()
    assert snapshot["phase"]["current"] == "INIT"
    assert snapshot["mode"]["current"] is None
    assert snapshot["gas"]["current"] is None


def test_metrics_store_set_mode():
    store = MetricsStore()
    store.set_mode("PATROL")
    snapshot = store.snapshot()
    assert snapshot["mode"]["current"] == "PATROL"


def test_metrics_store_set_gas():
    store = MetricsStore()
    store.set_gas(1.5)
    snapshot = store.snapshot()
    assert snapshot["gas"]["current"] == 1.5


def test_metrics_store_set_source_found():
    store = MetricsStore()
    store.set_source_found(True)
    snapshot = store.snapshot()
    assert snapshot["source_found"]["current"] is True


def test_metrics_store_set_phase():
    store = MetricsStore()
    store.set_phase("NAV_READY", reason="test")
    snapshot = store.snapshot()
    assert snapshot["phase"]["current"] == "NAV_READY"


def test_metrics_store_observe_log_line_mode_transition():
    store = MetricsStore()
    store.observe_log_line("Mode transition: PATROL -> SEEK_TRACK")
    snapshot = store.snapshot()
    assert snapshot["mode"]["current"] == "SEEK_TRACK"


def test_metrics_store_observe_log_line_concentration():
    store = MetricsStore()
    store.observe_log_line("conc: 2.5")
    snapshot = store.snapshot()
    assert snapshot["gas"]["current"] == 2.5


def test_metrics_store_topic_health():
    store = MetricsStore()
    store.set_gas(1.0)
    snapshot = store.snapshot()
    assert "/gas_concentration" in snapshot["topic_health"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_metrics_store.py -v 2>&1 || true`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 创建 metrics_store.py**

```python
# src/h2track_tracking/h2track_tracking/web/metrics_store.py
"""Metrics storage and tracking for web console dashboard."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import threading
import time
from typing import Any, Deque


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


def _fmt_bool_cn(value: Any) -> str:
    """Format boolean value as Chinese text."""
    if isinstance(value, bool):
        return "是" if value else "否"
    return "未知"


MODE_TRANSITION_RE = re.compile(r"Mode transition:\s+\w+\s+->\s+([A-Z_]+)")
CONCENTRATION_RE = re.compile(r"(?:concentration|conc)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
NAV_BEGIN_RE = re.compile(r"Begin navigating from current location")


def summarize_gas_signal(*, raw_history: list[dict[str, Any]], raw_topic_health: dict[str, Any]) -> dict[str, str]:
    """Summarize gas signal status from raw history."""
    raw_values = [float(row.get("value", 0.0)) for row in raw_history if row.get("value") is not None]
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
    """Thread-safe store for simulation metrics and health data."""

    def __init__(self, max_points: int = 600) -> None:
        self._lock = threading.Lock()
        self._max_points = max_points
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
        self._mode_current: str | None = None
        self._mode_history: Deque[dict[str, Any]] = deque(maxlen=max_points)
        self._gas_current: float | None = None
        self._gas_history: Deque[dict[str, Any]] = deque(maxlen=max_points)
        self._gas_raw_current: float | None = None
        self._gas_raw_history: Deque[dict[str, Any]] = deque(maxlen=max_points)
        self._source_found: bool | None = None
        self._nav_goal_succeeded = 0
        self._nav_failed_to_make_progress = 0
        self._nav_goal_canceled = 0
        self._nav_goal_started_at_mono: float | None = None
        self._nav_goal_durations_sec: Deque[float] = deque(maxlen=max_points)
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
        self._node_health: dict[str, dict[str, Any]] = {}
        self._node_health_updated_at = _now_iso()
        self._updated_at = _now_iso()

    def _touch(self) -> None:
        self._updated_at = _now_iso()

    def _mark_topic_tick(self, topic: str, value: Any = None) -> None:
        stats = self._topic_stats.get(topic)
        if stats is None:
            return
        stats["timestamps"].append(time.monotonic())
        if value is not None:
            stats["last_value"] = value

    def set_phase(self, phase: str, reason: str = "") -> None:
        phase_name = str(phase).strip().upper()
        if not phase_name:
            return
        with self._lock:
            if self._phase_current == phase_name:
                return
            now_iso = _now_iso()
            now_mono = time.monotonic()
            if self._phase_timeline and self._phase_timeline[-1].get("end_ts") is None:
                prev = self._phase_timeline[-1]
                prev["end_ts"] = now_iso
                prev["duration_ms"] = int(max(0.0, now_mono - float(prev.get("_start_mono", now_mono))) * 1000.0)
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
        with self._lock:
            self._mode_current = mode
            self._mode_history.append({"timestamp": _now_iso(), "value": mode})
            self._mark_topic_tick("/robot_mode", mode)
            self._touch()

    def set_gas(self, value: float) -> None:
        with self._lock:
            self._gas_current = float(value)
            self._gas_history.append({"timestamp": _now_iso(), "value": float(value)})
            self._mark_topic_tick("/gas_concentration", float(value))
            self._touch()

    def set_gas_raw(self, value: float) -> None:
        with self._lock:
            self._gas_raw_current = float(value)
            self._gas_raw_history.append({"timestamp": _now_iso(), "value": float(value)})
            self._mark_topic_tick("/gaden/sensor_reading", float(value))
            self._touch()

    def set_source_found(self, value: bool) -> None:
        with self._lock:
            self._source_found = bool(value)
            self._mark_topic_tick("/source_found", bool(value))
            self._touch()

    def observe_odom_tick(self, *, x: float, y: float) -> None:
        with self._lock:
            self._mark_topic_tick("/odom", {"x": float(x), "y": float(y)})
            self._touch()

    def update_node_health(self, node_up_map: dict[str, bool], *, last_error: str = "") -> None:
        with self._lock:
            now_iso = _now_iso()
            self._node_health_updated_at = now_iso
            for node_name, is_up in node_up_map.items():
                prev = self._node_health.get(node_name, {})
                restart_count = int(prev.get("restart_count", 0))
                if bool(is_up) and not bool(prev.get("up", False)) and prev.get("last_seen"):
                    restart_count += 1
                self._node_health[node_name] = {
                    "name": node_name,
                    "up": bool(is_up),
                    "status": "up" if bool(is_up) else "down",
                    "restart_count": restart_count,
                    "last_seen": now_iso if bool(is_up) else prev.get("last_seen"),
                    "last_error": "" if bool(is_up) else (last_error or prev.get("last_error", "not discovered")),
                }
            self._touch()

    def _start_nav_goal(self) -> None:
        self._nav_goal_started_at_mono = time.monotonic()

    def _finalize_nav_goal(self) -> None:
        if self._nav_goal_started_at_mono is None:
            return
        duration = time.monotonic() - self._nav_goal_started_at_mono
        if duration >= 0.0:
            self._nav_goal_durations_sec.append(duration)
        self._nav_goal_started_at_mono = None

    def _topic_health_snapshot(self) -> dict[str, Any]:
        now_mono = time.monotonic()
        payload: dict[str, Any] = {}
        for topic, stats in self._topic_stats.items():
            timestamps: Deque[float] = stats["timestamps"]
            last_seen = timestamps[-1] if timestamps else None
            hz = 0.0
            if len(timestamps) >= 2:
                dt = timestamps[-1] - timestamps[0]
                if dt > 0:
                    hz = (len(timestamps) - 1) / dt
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
        text = line.strip()
        if not text:
            return
        mode_match = MODE_TRANSITION_RE.search(text)
        if mode_match:
            self.set_mode(mode_match.group(1))
            self.set_phase(mode_match.group(1), reason="mode_transition")
        conc_match = CONCENTRATION_RE.search(text)
        if conc_match:
            try:
                self.set_gas(float(conc_match.group(1)))
            except ValueError:
                pass
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

        if NAV_BEGIN_RE.search(text) or "navigating to goal:" in lowered:
            with self._lock:
                self._start_nav_goal()
                self._touch()
        if "source_found" in lowered and "true" in lowered:
            self.set_source_found(True)
        if "-> source_found" in lowered:
            self.set_source_found(True)
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
        with self._lock:
            gas_history = list(self._gas_history)[-limit:]
            gas_raw_history = list(self._gas_raw_history)[-limit:]
            mode_history = list(self._mode_history)[-limit:]
            phase_timeline = []
            for row in list(self._phase_timeline)[-limit:]:
                clean = {k: v for k, v in row.items() if k != "_start_mono"}
                phase_timeline.append(clean)
            mean_goal_time = None
            if self._nav_goal_durations_sec:
                mean_goal_time = sum(self._nav_goal_durations_sec) / len(self._nav_goal_durations_sec)
            current_goal_age = None
            if self._nav_goal_started_at_mono is not None:
                current_goal_age = max(0.0, time.monotonic() - self._nav_goal_started_at_mono)
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
                        raw_topic_health=self._topic_health_snapshot().get("/gaden/sensor_reading", {}),
                    ),
                },
                "source_found": {
                    "current": self._source_found,
                },
                "nav": {
                    "goal_succeeded": self._nav_goal_succeeded,
                    "failed_to_make_progress": self._nav_failed_to_make_progress,
                    "goal_canceled": self._nav_goal_canceled,
                    "mean_goal_time_sec": None if mean_goal_time is None else round(mean_goal_time, 3),
                    "current_goal_age_sec": None if current_goal_age is None else round(current_goal_age, 3),
                    "goal_durations_sec": [round(v, 3) for v in list(self._nav_goal_durations_sec)[-limit:]],
                },
                "topic_health": self._topic_health_snapshot(),
                "node_health": {
                    "updated_at": self._node_health_updated_at,
                    "nodes": list(self._node_health.values()),
                },
                "updated_at": self._updated_at,
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_metrics_store.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/metrics_store.py
git add src/h2track_tracking/test/test_metrics_store.py
git commit -m "refactor(web): extract MetricsStore to separate module"
```

---

### Task 4: 提取 simulation_controller.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/simulation_controller.py`
- Test: `src/h2track_tracking/test/test_simulation_controller.py`

- [ ] **Step 1: 编写 simulation_controller.py 测试**

```python
# src/h2track_tracking/test/test_simulation_controller.py
"""Tests for SimulationController class."""

import pytest
from h2track_tracking.web.simulation_controller import (
    SimulationController,
    CommandResult,
)
from h2track_tracking.web.metrics_store import MetricsStore


def test_simulation_controller_initial_state():
    controller = SimulationController()
    status = controller.status()
    assert status["state"] == "idle"
    assert status["pid"] is None
    assert status["last_error"] == ""


def test_simulation_controller_status_returns_dict():
    controller = SimulationController()
    status = controller.status()
    assert isinstance(status, dict)
    assert "state" in status
    assert "pid" in status
    assert "last_error" in status


def test_simulation_controller_recent_logs_empty():
    controller = SimulationController()
    logs = controller.recent_logs(limit=10)
    assert isinstance(logs, list)


def test_simulation_controller_metrics_snapshot():
    controller = SimulationController()
    snapshot = controller.metrics_snapshot(limit=10)
    assert isinstance(snapshot, dict)
    assert "phase" in snapshot
    assert "mode" in snapshot
    assert "gas" in snapshot


def test_simulation_controller_stop_when_idle():
    controller = SimulationController()
    ok, msg = controller.stop()
    assert ok is False
    assert "not running" in msg.lower()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_simulation_controller.py -v 2>&1 || true`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 创建 simulation_controller.py**

```python
# src/h2track_tracking/h2track_tracking/web/simulation_controller.py
"""Simulation lifecycle controller for web console."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import threading
import time
from typing import Any, Callable, Deque
import zipfile
import yaml

from .config import DEMO_PREP_COMMAND, DEFAULT_LAUNCH_PROFILE, normalize_launch_profile, build_demo_launch_command
from .metrics_store import MetricsStore, _now_iso


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _discover_setup_scripts() -> list[str]:
    scripts = [
        "/opt/ros/humble/setup.bash",
        "/home/user/gaden_ws/install/setup.bash",
        str((Path.cwd() / "install" / "setup.bash").resolve()),
    ]
    result: list[str] = []
    for script in scripts:
        path = Path(script)
        if path.exists() and path.is_file():
            result.append(str(path))
    return result


def _wrap_with_setup_sourcing(cmd: list[str]) -> list[str]:
    setup_parts = [f"source {shlex.quote(path)}" for path in _discover_setup_scripts()]
    run_part = " ".join(shlex.quote(part) for part in cmd)
    chain = " && ".join([*setup_parts, run_part]) if setup_parts else run_part
    return ["bash", "-lc", chain]


def _default_run_command(cmd: list[str]) -> CommandResult:
    wrapped_cmd = _wrap_with_setup_sourcing(cmd)
    result = subprocess.run(
        wrapped_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def _default_launch_process(cmd: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
    wrapped_cmd = _wrap_with_setup_sourcing(cmd)
    return subprocess.Popen(
        wrapped_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        preexec_fn=os.setsid,
    )


def _default_probe_topic(topic: str, timeout_sec: float = 0.8) -> str | None:
    try:
        timeout_arg = f"{max(timeout_sec, 0.1):.1f}"
        result = subprocess.run(
            ["timeout", timeout_arg, "ros2", "topic", "echo", topic, "--once"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for raw_line in (result.stdout or "").splitlines():
        line = raw_line.strip()
        if line.startswith("data:"):
            return line.split(":", 1)[1].strip()
    return None


def _candidate_scene_yaml_paths(scene: str) -> list[Path]:
    scene_name = str(scene or "warehouse").strip().lower() or "warehouse"
    cwd = Path.cwd()
    return [
        cwd / "src" / "h2track_sim" / "scenes" / scene_name / "scene.yaml",
        cwd / "install" / "h2track_sim" / "share" / "h2track_sim" / "scenes" / scene_name / "scene.yaml",
    ]


def load_scene_thresholds(scene: str) -> dict[str, float] | None:
    for path in _candidate_scene_yaml_paths(scene):
        if not path.exists():
            continue
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            mission = content.get("mission_manager", {}) if isinstance(content, dict) else {}
            enter = mission.get("enter_threshold")
            exit_ = mission.get("exit_threshold")
            source = mission.get("source_threshold")
            if enter is None and exit_ is None and source is None:
                return None
            out: dict[str, float] = {}
            if enter is not None:
                out["enter_threshold"] = float(enter)
            if exit_ is not None:
                out["exit_threshold"] = float(exit_)
            if source is not None:
                out["source_threshold"] = float(source)
            return out
        except Exception:
            continue
    return None


class SimulationController:
    """Manages simulation lifecycle: start, stop, logs, metrics."""

    def __init__(
        self,
        *,
        run_command: Callable[[list[str]], CommandResult] | None = None,
        launch_process: Callable[[list[str], dict[str, str]], Any] | None = None,
        topic_probe: Callable[[str, float], str | None] | None = None,
        topic_probe_interval_sec: float = 2.0,
        max_log_lines: int = 2000,
        metrics_store: MetricsStore | None = None,
    ) -> None:
        self._run_command = run_command or _default_run_command
        self._launch_process = launch_process or _default_launch_process
        self._topic_probe = topic_probe or _default_probe_topic
        self._topic_probe_interval_sec = max(0.0, float(topic_probe_interval_sec))
        self._metrics = metrics_store or MetricsStore()
        self._lock = threading.Lock()
        self._state = "idle"
        self._process: Any | None = None
        self._reader_thread: threading.Thread | None = None
        self._last_error = ""
        self._log_seq = 0
        self._logs: Deque[dict[str, Any]] = deque(maxlen=max_log_lines)
        self._last_topic_probe_at = 0.0
        self._last_node_health_probe_at = 0.0
        self._topic_probe_lock = threading.Lock()
        self._node_health_probe_lock = threading.Lock()
        self._launch_profile = dict(DEFAULT_LAUNCH_PROFILE)
        self._scene_threshold_cache: dict[str, dict[str, float] | None] = {}
        self._append_log("controller initialized")

    def _append_log(self, line: str, *, source: str = "system") -> None:
        self._metrics.observe_log_line(line)
        with self._lock:
            self._log_seq += 1
            self._logs.append(
                {
                    "id": self._log_seq,
                    "timestamp": _now_iso(),
                    "source": source,
                    "line": line.rstrip("\n"),
                }
            )

    def start(self) -> tuple[bool, str]:
        return self.start_with_profile(None)

    def start_with_profile(self, profile: dict[str, Any] | None) -> tuple[bool, str]:
        with self._lock:
            if self._state in {"starting", "running", "stopping"}:
                return False, f"simulation already {self._state}"
            self._state = "starting"
            self._last_error = ""

        self._append_log("running demo_prep...", source="control")
        try:
            prep_result = self._run_command(list(DEMO_PREP_COMMAND))
        except Exception as exc:
            with self._lock:
                self._state = "error"
                self._last_error = f"demo_prep execution failed: {exc}"
            self._append_log(self._last_error, source="control")
            return False, "demo_prep execution failed"
        for line in prep_result.stdout.splitlines():
            self._append_log(line, source="demo_prep")
        for line in prep_result.stderr.splitlines():
            self._append_log(line, source="demo_prep")
        if prep_result.returncode != 0:
            with self._lock:
                self._state = "error"
                self._last_error = "demo_prep failed"
            return False, "demo_prep failed"

        normalized_profile = normalize_launch_profile(profile)
        launch_cmd = build_demo_launch_command(normalized_profile)
        self._append_log(f"launching: {' '.join(launch_cmd)}", source="control")
        env = os.environ.copy()
        try:
            process = self._launch_process(launch_cmd, env)
        except Exception as exc:
            with self._lock:
                self._state = "error"
                self._last_error = f"launch failed: {exc}"
            self._append_log(self._last_error, source="control")
            return False, "launch failed"
        with self._lock:
            self._process = process
            self._state = "running"
            self._launch_profile = normalized_profile

        self._reader_thread = threading.Thread(target=self._read_process_output, daemon=True)
        self._reader_thread.start()
        return True, "simulation started"

    def _read_process_output(self) -> None:
        process = self._process
        if process is None:
            return
        stdout = getattr(process, "stdout", None)
        if stdout is not None:
            for line in stdout:
                self._append_log(line, source="sim")
        return_code = process.poll()
        if return_code is None:
            if not hasattr(process, "wait"):
                return
            return_code = process.wait()
        with self._lock:
            was_stopping = self._state == "stopping"
            self._process = None
            if was_stopping:
                self._state = "idle"
            elif return_code == 0:
                self._state = "idle"
            else:
                self._state = "error"
                self._last_error = f"simulation exited with code {return_code}"
        self._append_log(f"simulation exited with code {return_code}", source="control")

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            process = self._process
            state = self._state
            if process is None or state not in {"running", "starting"}:
                return False, "simulation is not running"
            self._state = "stopping"

        self._append_log("stopping simulation...", source="control")
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGINT)
            return True, "stop signal sent"
        except Exception as exc:
            with self._lock:
                self._state = "error"
                self._last_error = f"failed to stop simulation: {exc}"
            self._append_log(self._last_error, source="control")
            return False, str(exc)

    def status(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            recent_id = self._log_seq
            return {
                "state": self._state,
                "pid": None if process is None else process.pid,
                "last_error": self._last_error,
                "latest_log_id": recent_id,
                "launch_profile": dict(self._launch_profile),
            }

    def recent_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if limit <= 0:
                return []
            return list(self._logs)[-limit:]

    def logs_after(self, after_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [entry for entry in self._logs if int(entry["id"]) > after_id]

    def metrics_snapshot(self, limit: int = 120) -> dict[str, Any]:
        payload = self._metrics.snapshot(limit=limit)
        with self._lock:
            profile = dict(self._launch_profile)
        scene = str(profile.get("scene", "warehouse"))
        cached = self._scene_threshold_cache.get(scene)
        if cached is None and scene not in self._scene_threshold_cache:
            cached = load_scene_thresholds(scene)
            self._scene_threshold_cache[scene] = cached
        if str(profile.get("use_gaden", "true")).lower() != "true":
            payload["gas"]["signal_status"] = "simplified_field"
            payload["gas"]["signal_reason"] = "当前使用简化气体场，不依赖 GADEN 原始传感器"
        payload["launch_profile"] = profile
        payload["mission_thresholds"] = cached
        return payload

    def refresh_metrics_from_topics_if_needed(self) -> None:
        now = time.monotonic()
        with self._topic_probe_lock:
            if now - self._last_topic_probe_at < self._topic_probe_interval_sec:
                return
            self._last_topic_probe_at = now
        gas_text = self._topic_probe("/gas_concentration", 2.6)
        if gas_text:
            try:
                self._metrics.set_gas(float(gas_text))
            except ValueError:
                pass

    def refresh_runtime_health_if_needed(self) -> None:
        now = time.monotonic()
        with self._node_health_probe_lock:
            if now - self._last_node_health_probe_at < 3.0:
                return
            self._last_node_health_probe_at = now
        expected_nodes = [
            "/mission_manager_node",
            "/controller_server",
            "/planner_server",
            "/bt_navigator",
            "/slam_toolbox",
        ]
        with self._lock:
            profile = dict(self._launch_profile)
        if profile.get("use_gaden", "true") == "true":
            expected_nodes.extend(
                [
                    "/gaden_adapter_node",
                    "/gaden_sensor_gate_node",
                    "/gaden_player",
                    "/gaden_environment",
                ]
            )
        try:
            result = subprocess.run(
                ["timeout", "3.0", "ros2", "node", "list"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self._metrics.update_node_health(
                    {name: False for name in expected_nodes},
                    last_error=(result.stderr or "failed to read node list").strip(),
                )
                return
            lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
            observed = set(lines)
            node_up_map = {name: name in observed for name in expected_nodes}
            self._metrics.update_node_health(node_up_map)
        except Exception as exc:
            self._metrics.update_node_health(
                {name: False for name in expected_nodes},
                last_error=f"node probe error: {exc}",
            )

    def export_diagnostics(self, scene: str = "warehouse") -> str:
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = Path.cwd() / "artifacts" / "diag"
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"h2track_diag_{scene}_{timestamp}.zip"
        status_payload = self.status()
        metrics_payload = self.metrics_snapshot(limit=600)
        logs_payload = self.recent_logs(limit=2000)
        summary = {
            "scene": scene,
            "exported_at": _now_iso(),
            "status": status_payload,
            "metrics": metrics_payload,
            "fixed_launch_profile": {
                "scene": "warehouse",
                "use_gaden": True,
                "use_slam": True,
                "use_rviz": True,
                "headless": False,
            },
        }
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
            logs_jsonl = "\n".join(json.dumps(row, ensure_ascii=False) for row in logs_payload)
            zf.writestr("logs.jsonl", logs_jsonl)
        return str(zip_path)

    def export_run_report(self, scene: str = "warehouse") -> dict[str, str]:
        from .templates import _build_run_report_markdown

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = Path.cwd() / "artifacts" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"h2track_run_report_{scene}_{timestamp}.json"
        markdown_path = out_dir / f"h2track_run_report_{scene}_{timestamp}.md"
        status_payload = self.status()
        metrics_payload = self.metrics_snapshot(limit=600)
        logs_payload = self.recent_logs(limit=2000)
        report_payload = {
            "scene": scene,
            "exported_at": _now_iso(),
            "status": status_payload,
            "metrics": metrics_payload,
            "mission_thresholds": metrics_payload.get("mission_thresholds"),
            "launch_profile": status_payload.get("launch_profile"),
            "logs": logs_payload,
        }
        json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(_build_run_report_markdown(report_payload), encoding="utf-8")
        return {"json_path": str(json_path), "markdown_path": str(markdown_path)}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_simulation_controller.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/simulation_controller.py
git add src/h2track_tracking/test/test_simulation_controller.py
git commit -m "refactor(web): extract SimulationController to separate module"
```

---

### Task 5: 提取 templates.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/templates.py`

- [ ] **Step 1: 创建 templates.py (HTML 模板)**

从 `demo_web_server.py` 提取 `HTML_PAGE` 常量和 `_build_run_report_markdown` 函数。文件较大，包含完整的 HTML 模板。

- [ ] **Step 2: 验证导入**

Run: `cd /home/user/h2track-xian && python -c "from h2track_tracking.web.templates import HTML_PAGE, _build_run_report_markdown; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/templates.py
git commit -m "refactor(web): extract HTML templates to separate module"
```

---

### Task 6: 提取 topic_collector.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/topic_collector.py`

- [ ] **Step 1: 创建 topic_collector.py**

```python
# src/h2track_tracking/h2track_tracking/web/topic_collector.py
"""ROS topic collector for live dashboard metrics."""

from __future__ import annotations

import threading
from typing import Any

from .metrics_store import MetricsStore


class TopicMetricsCollector:
    """Optional ROS topic collector for live dashboard metrics."""

    def __init__(self, metrics_store: MetricsStore) -> None:
        self._metrics = metrics_store
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _worker(self) -> None:
        try:
            from nav_msgs.msg import Odometry
            try:
                from olfaction_msgs.msg import GasSensor
            except Exception:
                GasSensor = None
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import Bool, Float32, String
        except Exception:
            return

        class _Probe(Node):
            def __init__(self, metrics: MetricsStore) -> None:
                super().__init__("demo_web_metrics_collector")
                self._metrics = metrics
                self.create_subscription(String, "/robot_mode", self._on_mode, 10)
                self.create_subscription(Float32, "/gas_concentration", self._on_gas, 10)
                self.create_subscription(Bool, "/source_found", self._on_source_found, 10)
                self.create_subscription(Odometry, "/odom", self._on_odom, 10)
                if GasSensor is not None:
                    self.create_subscription(GasSensor, "/gaden/sensor_reading", self._on_gas_raw, 10)

            def _on_mode(self, msg: Any) -> None:
                self._metrics.set_mode(str(msg.data))

            def _on_gas(self, msg: Any) -> None:
                self._metrics.set_gas(float(msg.data))

            def _on_source_found(self, msg: Any) -> None:
                self._metrics.set_source_found(bool(msg.data))

            def _on_odom(self, msg: Any) -> None:
                pos = msg.pose.pose.position
                self._metrics.observe_odom_tick(x=float(pos.x), y=float(pos.y))

            def _on_gas_raw(self, msg: Any) -> None:
                self._metrics.set_gas_raw(float(msg.raw))

        started_here = not rclpy.ok()
        if started_here:
            rclpy.init(args=None)
        node: Any | None = None
        try:
            node = _Probe(self._metrics)
            while not self._stop_event.is_set():
                rclpy.spin_once(node, timeout_sec=0.2)
        finally:
            if node is not None:
                node.destroy_node()
            if started_here and rclpy.ok():
                rclpy.shutdown()
```

- [ ] **Step 2: 验证导入**

Run: `cd /home/user/h2track-xian && python -c "from h2track_tracking.web.topic_collector import TopicMetricsCollector; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/topic_collector.py
git commit -m "refactor(web): extract TopicMetricsCollector to separate module"
```

---

### Task 7: 创建 routes.py 和 app.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/web/routes.py`
- Create: `src/h2track_tracking/h2track_tracking/web/app.py`

- [ ] **Step 1: 创建 routes.py**

提取所有 FastAPI 路由定义。

- [ ] **Step 2: 创建 app.py**

```python
# src/h2track_tracking/h2track_tracking/web/app.py
"""FastAPI application factory for web console."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from .config import DEFAULT_LAUNCH_PROFILE
from .metrics_store import MetricsStore
from .simulation_controller import SimulationController
from .topic_collector import TopicMetricsCollector
from .templates import HTML_PAGE

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


def _resolve_static_console_dir():
    from pathlib import Path
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "static_console"]
    try:
        from ament_index_python.packages import get_package_share_directory
        candidates.append(Path(get_package_share_directory("h2track_tracking")) / "static_console")
    except Exception:
        pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _resolve_static_index_html():
    from pathlib import Path
    static_dir = _resolve_static_console_dir()
    if static_dir is None:
        return None
    index_path = static_dir / "index.html"
    if index_path.exists() and index_path.is_file():
        return index_path
    return None


def _resolve_ui_meta() -> dict[str, Any]:
    from pathlib import Path
    static_dir = _resolve_static_console_dir()
    index_path = _resolve_static_index_html()
    if static_dir is None or index_path is None:
        return {
            "mode": "legacy_inline",
            "bundle_ready": False,
            "bundle_path": None,
        }
    return {
        "mode": "static_bundle",
        "bundle_ready": True,
        "bundle_path": str(static_dir),
    }


def create_app(
    controller: SimulationController | None = None,
    llm_controller: Any | None = None,
    *,
    start_topic_collector: bool = False,
) -> Any:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is not available. Install fastapi and uvicorn first.")

    from .routes import register_routes

    app = FastAPI(title="H2Track Web Console")
    sim = controller or SimulationController()

    # LLM controller import
    if llm_controller is None:
        from ..llm_agent import LlmController
        llm = LlmController(sim=sim)
    else:
        llm = llm_controller

    ui_meta = _resolve_ui_meta()
    collector = TopicMetricsCollector(sim._metrics) if start_topic_collector else None
    if collector is not None:
        collector.start()

    if bool(ui_meta.get("bundle_ready")):
        from pathlib import Path
        static_dir = _resolve_static_console_dir()
        assert static_dir is not None
        assets_dir = static_dir / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    register_routes(app, sim, llm, ui_meta, collector)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run H2Track warehouse web console.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args(argv)

    if not FASTAPI_AVAILABLE:
        print("FastAPI/Starlette not installed. Install with: pip install fastapi uvicorn")
        return 1
    try:
        import uvicorn
    except Exception:
        print("uvicorn not installed. Install with: pip install uvicorn")
        return 1

    app = create_app(start_topic_collector=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 运行现有测试验证**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_demo_web_server.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/web/routes.py
git add src/h2track_tracking/h2track_tracking/web/app.py
git commit -m "refactor(web): extract routes and app factory"
```

---

### Task 8: 更新 demo_web_server.py 为入口文件

**Files:**
- Modify: `src/h2track_tracking/h2track_tracking/demo_web_server.py`

- [ ] **Step 1: 简化 demo_web_server.py**

```python
# src/h2track_tracking/h2track_tracking/demo_web_server.py
"""Web control console entry point.

This module provides backward compatibility by re-exporting from the web package.
"""

from .web.app import create_app, main
from .web.config import (
    DEMO_PREP_COMMAND,
    DEFAULT_LAUNCH_PROFILE,
    normalize_launch_profile,
    build_demo_launch_command,
)
from .web.metrics_store import MetricsStore
from .web.simulation_controller import SimulationController, CommandResult
from .web.topic_collector import TopicMetricsCollector

__all__ = [
    "create_app",
    "main",
    "DEMO_PREP_COMMAND",
    "DEFAULT_LAUNCH_PROFILE",
    "normalize_launch_profile",
    "build_demo_launch_command",
    "MetricsStore",
    "SimulationController",
    "CommandResult",
    "TopicMetricsCollector",
]


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行所有相关测试**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/test_demo_web_server.py src/h2track_tracking/test/test_web_config.py src/h2track_tracking/test/test_metrics_store.py src/h2track_tracking/test/test_simulation_controller.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/demo_web_server.py
git commit -m "refactor(web): simplify demo_web_server to entry point"
```

---

## 阶段 2：拆分 llm_agent.py

### Task 9: 创建 llm/ 目录结构

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/llm/__init__.py`

- [ ] **Step 1: 创建 llm 目录和 __init__.py**

```python
# src/h2track_tracking/h2track_tracking/llm/__init__.py
"""LLM assistant modules for H2Track web console."""

from .controller import LlmController
from .profile_store import LlmProfileStore
from .client import OpenAICompatClient

__all__ = ["LlmController", "LlmProfileStore", "OpenAICompatClient"]
```

- [ ] **Step 2: Commit**

```bash
git add src/h2track_tracking/h2track_tracking/llm/__init__.py
git commit -m "refactor(llm): create llm package structure"
```

---

### Task 10: 提取 profile_store.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/llm/profile_store.py`
- Test: `src/h2track_tracking/test/test_llm_profile_store.py`

- [ ] **Step 1: 编写测试**

- [ ] **Step 2: 创建模块**

- [ ] **Step 3: 运行测试**

- [ ] **Step 4: Commit**

---

### Task 11: 提取 client.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/llm/client.py`

- [ ] **Step 1: 创建模块**

- [ ] **Step 2: 验证导入**

- [ ] **Step 3: Commit**

---

### Task 12: 提取 controller.py

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/llm/controller.py`

- [ ] **Step 1: 创建模块**

- [ ] **Step 2: 验证导入**

- [ ] **Step 3: Commit**

---

### Task 13: 更新 llm_agent.py 为入口文件

**Files:**
- Modify: `src/h2track_tracking/h2track_tracking/llm_agent.py`

- [ ] **Step 1: 简化为入口**

- [ ] **Step 2: 运行测试**

- [ ] **Step 3: Commit**

---

## 阶段 3：补充测试覆盖

### Task 14: 补充核心模块测试

- [ ] **Step 1: 分析测试覆盖率**

- [ ] **Step 2: 补充缺失测试**

- [ ] **Step 3: Commit**

---

## 阶段 4：统一代码风格

### Task 15: 统一类型注解和文档

- [ ] **Step 1: 添加缺失的类型注解**

- [ ] **Step 2: 统一文档字符串风格**

- [ ] **Step 3: Commit**

---

## 最终验证

- [ ] **运行所有测试**

Run: `cd /home/user/h2track-xian && python -m pytest src/h2track_tracking/test/ -v`
Expected: All tests PASS

- [ ] **验证 Web 控制台启动**

Run: `cd /home/user/h2track-xian && python -c "from h2track_tracking.demo_web_server import create_app; print('OK')"`
Expected: OK

- [ ] **最终 Commit**

```bash
git add -A
git commit -m "refactor: complete code quality optimization

- Split demo_web_server.py (2231 lines) into web/ package
- Split llm_agent.py (906 lines) into llm/ package
- Add tests for new modules
- Unify code style and type annotations"
```
