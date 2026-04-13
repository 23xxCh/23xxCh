"""Simulation controller for managing simulation lifecycle.

This module provides the SimulationController class for:
- Starting and stopping simulations
- Log collection and streaming
- Metrics tracking via MetricsStore
- Process management
- Diagnostic and run report exports
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque
import zipfile

from .config import (
    DEFAULT_LAUNCH_PROFILE,
    normalize_launch_profile,
    build_demo_launch_command,
    build_demo_prep_command,
)
from .metrics_store import MetricsStore, _now_iso
from .reports import build_run_report_markdown


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution."""

    returncode: int
    stdout: str
    stderr: str


def _default_run_command(cmd: list[str]) -> CommandResult:
    """Execute a command and return the result."""
    result = subprocess.run(
        cmd,
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
    """Launch a subprocess with the given command and environment."""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        preexec_fn=os.setsid,
    )


def _default_probe_topic(topic: str, timeout_sec: float = 0.8) -> str | None:
    """Probe a ROS topic for a single message."""
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
    """Return candidate paths for scene YAML files."""
    scene_name = str(scene or "warehouse").strip().lower() or "warehouse"
    cwd = Path.cwd()
    return [
        cwd / "src" / "h2track_sim" / "scenes" / scene_name / "scene.yaml",
        cwd / "install" / "h2track_sim" / "share" / "h2track_sim" / "scenes" / scene_name / "scene.yaml",
    ]


def load_scene_thresholds(scene: str) -> dict[str, float] | None:
    """Load mission thresholds from scene YAML file."""
    import yaml

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
    """Manages simulation lifecycle, logs, and metrics.

    This class provides:
    - start/stop methods for simulation control
    - Log collection and streaming
    - Metrics tracking via MetricsStore
    - Diagnostic export functionality

    Thread Safety:
        All public methods are thread-safe.
    """

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
        """Initialize the simulation controller.

        Args:
            run_command: Function to run a command and return CommandResult.
            launch_process: Function to launch a subprocess.
            topic_probe: Function to probe a ROS topic.
            topic_probe_interval_sec: Minimum interval between topic probes.
            max_log_lines: Maximum number of log lines to retain.
            metrics_store: Optional MetricsStore instance.
        """
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
        """Append a log entry.

        Args:
            line: Log line content.
            source: Source identifier (system, sim, control, demo_prep).
        """
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
        """Start the simulation with default profile.

        Returns:
            Tuple of (success, message).
        """
        return self.start_with_profile(None)

    def start_with_profile(self, profile: dict[str, Any] | None) -> tuple[bool, str]:
        """Start the simulation with the given profile.

        Args:
            profile: Launch profile configuration. If None, uses defaults.

        Returns:
            Tuple of (success, message).
        """
        with self._lock:
            if self._state in {"starting", "running", "stopping"}:
                return False, f"simulation already {self._state}"
            self._state = "starting"
            self._last_error = ""

        self._append_log("running demo_prep...", source="control")
        try:
            prep_cmd = build_demo_prep_command(profile)
            prep_result = self._run_command(prep_cmd)
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
        """Read and process output from the simulation process."""
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
        """Stop the running simulation.

        Returns:
            Tuple of (success, message).
        """
        with self._lock:
            process = self._process
            if process is None or self._state not in {"running", "starting"}:
                return False, "simulation is not running"
            self._state = "stopping"
            # Hold process reference while still holding lock
            process_to_kill = process

        self._append_log("stopping simulation...", source="control")
        try:
            os.killpg(os.getpgid(process_to_kill.pid), signal.SIGINT)
            return True, "stop signal sent"
        except Exception as exc:
            with self._lock:
                if self._state == "stopping":
                    self._state = "error"
                self._last_error = f"failed to stop simulation: {exc}"
            self._append_log(self._last_error, source="control")
            return False, str(exc)

    def status(self) -> dict[str, Any]:
        """Get the current simulation status.

        Returns:
            Dictionary with state, pid, last_error, latest_log_id, launch_profile.
        """
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
        """Get recent log entries.

        Args:
            limit: Maximum number of logs to return.

        Returns:
            List of log entries, each with id, timestamp, source, line.
        """
        with self._lock:
            if limit <= 0:
                return []
            return list(self._logs)[-limit:]

    def logs_after(self, after_id: int) -> list[dict[str, Any]]:
        """Get logs with id greater than after_id.

        Args:
            after_id: Only return logs with id > after_id.

        Returns:
            List of newer log entries.
        """
        with self._lock:
            return [entry for entry in self._logs if int(entry["id"]) > after_id]

    def metrics_snapshot(self, limit: int = 120) -> dict[str, Any]:
        """Get a snapshot of current metrics.

        Args:
            limit: Maximum history entries to include.

        Returns:
            Metrics snapshot dictionary.
        """
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
        """Refresh gas concentration from ROS topics if interval has elapsed."""
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
        """Refresh node health status if interval has elapsed."""
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
        """Export diagnostics to a zip file.

        Args:
            scene: Scene name for the export.

        Returns:
            Path to the created zip file.
        """
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
        """Export a run report as JSON and Markdown.

        Args:
            scene: Scene name for the export.

        Returns:
            Dictionary with json_path and markdown_path.
        """
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
        markdown_path.write_text(build_run_report_markdown(report_payload), encoding="utf-8")
        return {"json_path": str(json_path), "markdown_path": str(markdown_path)}
