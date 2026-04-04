"""Web control console for one-click warehouse simulation startup and live logs."""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import threading
import time
from typing import Any, Callable, Deque
import zipfile
import yaml

from .llm_agent import LlmController
from .web.config import (
    DEMO_PREP_COMMAND,
    DEFAULT_LAUNCH_PROFILE,
    normalize_launch_profile,
    build_demo_launch_command,
)
from .web.metrics_store import (
    MetricsStore,
    _now_iso,
    summarize_gas_signal,
    MODE_TRANSITION_RE,
    CONCENTRATION_RE,
    NAV_BEGIN_RE,
)


try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


STATIC_CONSOLE_DIRNAME = "static_console"
UI_MODE_STATIC = "static_bundle"
UI_MODE_LEGACY = "legacy_inline"


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


def _resolve_static_console_dir() -> Path | None:
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / STATIC_CONSOLE_DIRNAME]
    try:
        from ament_index_python.packages import get_package_share_directory

        candidates.append(Path(get_package_share_directory("h2track_tracking")) / STATIC_CONSOLE_DIRNAME)
    except Exception:
        pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _resolve_static_index_html() -> Path | None:
    static_dir = _resolve_static_console_dir()
    if static_dir is None:
        return None
    index_path = static_dir / "index.html"
    if index_path.exists() and index_path.is_file():
        return index_path
    return None


def _resolve_ui_meta() -> dict[str, Any]:
    static_dir = _resolve_static_console_dir()
    index_path = _resolve_static_index_html()
    if static_dir is None or index_path is None:
        return {
            "mode": UI_MODE_LEGACY,
            "bundle_ready": False,
            "bundle_path": None,
        }
    return {
        "mode": UI_MODE_STATIC,
        "bundle_ready": True,
        "bundle_path": str(static_dir),
    }


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _fmt_bool_cn(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    return "未知"


def _build_run_report_markdown(payload: dict[str, Any]) -> str:
    status = payload.get("status", {}) if isinstance(payload, dict) else {}
    metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
    launch_profile = payload.get("launch_profile", {}) if isinstance(payload, dict) else {}
    nav = metrics.get("nav", {}) if isinstance(metrics, dict) else {}
    phase = metrics.get("phase", {}) if isinstance(metrics, dict) else {}
    mode = metrics.get("mode", {}) if isinstance(metrics, dict) else {}
    gas = metrics.get("gas", {}) if isinstance(metrics, dict) else {}
    source_found = metrics.get("source_found", {}) if isinstance(metrics, dict) else {}
    thresholds = payload.get("mission_thresholds", {}) if isinstance(payload, dict) else {}
    logs = payload.get("logs", []) if isinstance(payload, dict) else []
    tail_logs = logs[-30:] if isinstance(logs, list) else []

    md_lines = [
        "# H2Track 运行报告",
        "",
        f"- 导出时间: {payload.get('exported_at', '-')}",
        f"- 场景: {payload.get('scene', '-')}",
        f"- 当前状态: {status.get('state', '-')}",
        f"- 当前阶段: {(phase or {}).get('current', '-')}",
        f"- 当前模式: {(mode or {}).get('current', '-')}",
        f"- 当前浓度: {(gas or {}).get('current', '-')}",
        f"- 是否找到源头: {_fmt_bool_cn((source_found or {}).get('current'))}",
        "",
        "## 启动配置",
        "",
        f"- scene: {launch_profile.get('scene', '-')}",
        f"- use_gaden: {launch_profile.get('use_gaden', '-')}",
        f"- use_slam: {launch_profile.get('use_slam', '-')}",
        f"- use_rviz: {launch_profile.get('use_rviz', '-')}",
        f"- headless: {launch_profile.get('headless', '-')}",
        "",
        "## 任务阈值",
        "",
        f"- enter_threshold: {(thresholds or {}).get('enter_threshold', '-')}",
        f"- exit_threshold: {(thresholds or {}).get('exit_threshold', '-')}",
        f"- source_threshold: {(thresholds or {}).get('source_threshold', '-')}",
        "",
        "## 导航统计",
        "",
        f"- goal_succeeded: {(nav or {}).get('goal_succeeded', 0)}",
        f"- failed_to_make_progress: {(nav or {}).get('failed_to_make_progress', 0)}",
        f"- goal_canceled: {(nav or {}).get('goal_canceled', 0)}",
        f"- mean_goal_time_sec: {(nav or {}).get('mean_goal_time_sec', '-')}",
        "",
        "## 最近日志（末 30 行）",
        "",
    ]
    if not tail_logs:
        md_lines.append("- 无日志")
    else:
        for row in tail_logs:
            ts = row.get("timestamp", "-")
            src = row.get("source", "system")
            line = str(row.get("line", "")).replace("\n", " ")
            md_lines.append(f"- [{ts}] [{src}] {line}")
    md_lines.append("")
    return "\n".join(md_lines)


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


class SimulationController:
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


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>H2Track 仓库控制台</title>
  <style>
    :root {
      --bg: #0b111a;
      --panel: #121c2b;
      --panel-2: #0f1724;
      --line: #223248;
      --text: #dbe8f7;
      --muted: #90a3bb;
      --ok: #22c55e;
      --warn: #f59e0b;
      --err: #ef4444;
      --run: #38bdf8;
      --idle: #64748b;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Songti SC", "SimSun", "Noto Serif CJK SC", serif; background: radial-gradient(circle at top left, #102033, var(--bg)); color: var(--text); }
    .wrap { max-width: 1280px; margin: 20px auto; padding: 0 16px 24px; }
    .title-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
    .title { margin: 0; font-size: 22px; letter-spacing: .4px; }
    .badge { border: 1px solid var(--line); background: var(--panel-2); padding: 6px 10px; font-size: 12px; border-radius: 999px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
    .card { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); padding: 10px 12px; min-height: 68px; }
    .card .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .8px; }
    .card .value { margin-top: 6px; font-size: 16px; font-weight: 700; word-break: break-all; }
    .status-idle { color: var(--idle); }
    .status-starting, .status-stopping { color: var(--warn); }
    .status-running { color: var(--run); }
    .status-error { color: var(--err); }
    .toolbar { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); padding: 10px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
    .toolbar button { background: #16253a; color: var(--text); border: 1px solid #315078; padding: 8px 14px; border-radius: 8px; cursor: pointer; }
    .toolbar button:hover { background: #1c2f47; }
    .toolbar button:disabled { opacity: .45; cursor: not-allowed; }
    .toolbar select, .toolbar input[type="text"] { background: var(--panel-2); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; }
    .toolbar input[type="text"] { min-width: 220px; }
    .toolbar .check { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; }
    .info { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); padding: 10px; color: var(--muted); font-size: 12px; margin-bottom: 12px; }
    .logbox { border: 1px solid var(--line); border-radius: 10px; background: #0a131f; height: 62vh; overflow: auto; padding: 10px; }
    .logline { white-space: pre-wrap; line-height: 1.38; padding: 2px 0; font-size: 12px; color: #cbd8e8; border-bottom: 1px dotted rgba(57, 78, 106, 0.22); }
    .logline.source-control { color: #93c5fd; }
    .logline.source-demo_prep { color: #fcd34d; }
    .logline.source-sim { color: #c4b5fd; }
    .logline.source-system { color: #94a3b8; }
    .logline.error { color: #fca5a5; font-weight: 600; }
    .muted { color: var(--muted); }
    .metrics-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
    .metric { min-height: 120px; }
    .metric .value { font-size: 20px; }
    .spark-wrap { margin-top: 8px; border: 1px solid var(--line); border-radius: 8px; background: #0b1421; padding: 4px; }
    #gasSpark { width: 100%; height: 52px; display: block; }
    .nav-kv { margin-top: 8px; font-size: 12px; color: var(--muted); line-height: 1.5; }
    .panel { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); padding: 10px 12px; margin-bottom: 12px; }
    .panel .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .8px; margin-bottom: 8px; }
    .phase-flow { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
    .phase-step { border: 1px solid var(--line); border-radius: 8px; background: #0b1421; padding: 8px; font-size: 12px; color: var(--muted); text-align: center; }
    .phase-step.active { color: #c8f8ff; border-color: #38bdf8; box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.25); }
    .table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .table th, .table td { border-bottom: 1px dotted rgba(57, 78, 106, 0.35); padding: 6px 4px; text-align: left; }
    .table th { color: var(--muted); font-weight: 600; }
    .chip-ok { color: var(--ok); }
    .chip-stale, .chip-down { color: var(--warn); }
    .export-note { margin-left: 6px; color: var(--muted); font-size: 12px; }
    @media (max-width: 980px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title-row">
      <h2 class="title">H2Track 仓库控制台</h2>
      <div id="connBadge" class="badge">连接状态：连接中</div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="label">状态</div>
        <div id="stateCard" class="value status-idle">空闲</div>
      </div>
      <div class="card">
        <div class="label">进程 PID</div>
        <div id="pidCard" class="value">-</div>
      </div>
      <div class="card">
        <div class="label">最新日志 ID</div>
        <div id="latestLogCard" class="value">0</div>
      </div>
      <div class="card">
        <div class="label">阶段</div>
        <div id="phaseBadge" class="value" data-phase="INIT">初始化</div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 12px;">
      <div class="label">最近错误</div>
      <div id="errorCard" class="value">-</div>
    </div>

    <div class="metrics-grid">
      <div class="card metric">
        <div class="label">机器人模式</div>
        <div id="modeMetric" class="value">暂无</div>
      </div>
      <div class="card metric">
        <div class="label">气体浓度</div>
        <div id="gasMetric" class="value">暂无</div>
        <div id="gasThresholds" class="nav-kv">阈值: 暂无</div>
        <div class="spark-wrap"><canvas id="gasSpark" width="260" height="52"></canvas></div>
      </div>
      <div class="card metric">
        <div class="label">是否找到源头</div>
        <div id="sourceMetric" class="value">暂无</div>
      </div>
      <div class="card metric">
        <div class="label">导航结果统计</div>
        <div id="navMetric" class="value">暂无</div>
        <div id="navDetail" class="nav-kv">成功: 0<br/>前进失败: 0</div>
        <div class="spark-wrap"><canvas id="navSpark" width="260" height="52"></canvas></div>
      </div>
    </div>

    <div class="panel">
      <div class="label">启动流程状态条</div>
      <div id="phaseFlow" class="phase-flow"></div>
    </div>

    <div class="panel">
      <div class="label">阶段时间轴</div>
      <div id="phaseTimeline" class="muted">暂无阶段事件</div>
    </div>

    <div class="panel">
      <div class="label">话题健康度</div>
      <table class="table">
        <thead>
          <tr><th>话题</th><th>状态</th><th>频率(Hz)</th><th>超时(秒)</th><th>最新值</th></tr>
        </thead>
        <tbody id="topicHealthBody"></tbody>
      </table>
    </div>

    <div class="panel">
      <div class="label">节点健康度</div>
      <table class="table">
        <thead>
          <tr><th>节点</th><th>状态</th><th>重启次数</th><th>最近在线</th></tr>
        </thead>
        <tbody id="nodeHealthBody"></tbody>
      </table>
    </div>

    <div class="toolbar">
      <button id="startBtn">开始仿真</button>
      <button id="stopBtn">停止仿真</button>
      <button id="refreshBtn">刷新状态</button>
      <button id="exportDiagBtn">导出诊断包</button><span id="diagExportResult" class="export-note"></span>
      <button id="exportReportBtn">导出运行报告</button><span id="reportExportResult" class="export-note"></span>
      <select id="sceneSelect">
        <option value="warehouse">场景: warehouse</option>
        <option value="baseline">场景: baseline</option>
      </select>
      <select id="useGadenSelect">
        <option value="true">GADEN: 开</option>
        <option value="false">GADEN: 关</option>
      </select>
      <select id="useSlamSelect">
        <option value="true">SLAM: 开</option>
        <option value="false">SLAM: 关</option>
      </select>
      <select id="useRvizSelect">
        <option value="true">RViz: 开</option>
        <option value="false">RViz: 关</option>
      </select>
      <select id="headlessSelect">
        <option value="false">GUI: 开</option>
        <option value="true">GUI: 关(无头)</option>
      </select>
      <select id="sourceFilter">
        <option value="all">来源：全部</option>
        <option value="control">控制</option>
        <option value="demo_prep">demo_prep</option>
        <option value="sim">sim</option>
        <option value="system">系统</option>
      </select>
      <input id="logSearch" type="text" placeholder="搜索日志..." />
      <label class="check"><input id="autoScrollToggle" type="checkbox" checked /> 自动滚动</label>
      <span id="resultCount" class="muted">0 行</span>
    </div>

    <div class="info">
      当前启动配置：
      <strong id="activeProfileText">scene=warehouse, use_gaden=true, use_slam=true, use_rviz=true, headless=false</strong>
    </div>

    <div class="panel">
      <div class="label">AI 模型配置（兼容 OpenAI 协议）</div>
      <div class="toolbar" style="margin-bottom: 8px;">
        <select id="llmProfileSelect"></select>
        <input id="llmProfileName" type="text" placeholder="配置名称" />
        <input id="llmBaseUrl" type="text" placeholder="Base URL, 例: http://127.0.0.1:8000" />
        <input id="llmApiKey" type="text" placeholder="API Key" />
        <input id="llmModel" type="text" placeholder="模型名, 例: gpt-4.1-mini" />
        <select id="llmProtocol">
          <option value="chat">协议: chat completions</option>
          <option value="responses">协议: responses</option>
          <option value="dual">协议: dual(先responses后chat)</option>
        </select>
        <button id="llmSaveProfileBtn">保存配置</button>
        <button id="llmReloadProfilesBtn">刷新配置</button>
        <button id="llmActivateProfileBtn">设为当前</button>
        <button id="llmCheckProfileBtn">连接测试</button>
      </div>
      <div id="llmProfileStatus" class="muted">尚未加载模型配置</div>
    </div>

    <div class="panel">
      <div class="label">AI 对话与动作建议</div>
      <div class="toolbar" style="margin-bottom: 8px;">
        <input id="llmPromptInput" type="text" placeholder="输入你的自然语言指令，例如：分析当前卡点并给出优化动作" style="min-width: 460px;" />
        <label class="check"><input id="llmAllowCodeEvolve" type="checkbox" /> 允许单轮流程执行代码进化</label>
        <button id="llmSendBtn">发送给 AI</button>
        <button id="llmRunOnceBtn">执行 AI 单轮自动流程</button>
      </div>
      <div id="llmReplyBox" class="card" style="min-height: 80px; margin-bottom: 8px;">
        <div class="label">AI 分析结论</div>
        <div id="llmReplyText" class="value" style="font-size: 14px; font-weight: 500;">暂无</div>
      </div>
      <div id="llmActionsBox" class="card" style="min-height: 80px;">
        <div class="label">AI 建议动作（确认后执行）</div>
        <div id="llmActionsList" class="muted">暂无动作</div>
      </div>
    </div>

    <div id="logs" class="logbox"></div>
  </div>

  <script>
    const logsEl = document.getElementById('logs');
    const stateCard = document.getElementById('stateCard');
    const pidCard = document.getElementById('pidCard');
    const latestLogCard = document.getElementById('latestLogCard');
    const errorCard = document.getElementById('errorCard');
    const phaseBadge = document.getElementById('phaseBadge');
    const connBadge = document.getElementById('connBadge');
    const sourceFilter = document.getElementById('sourceFilter');
    const logSearch = document.getElementById('logSearch');
    const autoScrollToggle = document.getElementById('autoScrollToggle');
    const resultCount = document.getElementById('resultCount');
    const modeMetric = document.getElementById('modeMetric');
    const gasMetric = document.getElementById('gasMetric');
    const gasThresholds = document.getElementById('gasThresholds');
    const sourceMetric = document.getElementById('sourceMetric');
    const navMetric = document.getElementById('navMetric');
    const navDetail = document.getElementById('navDetail');
    const gasSpark = document.getElementById('gasSpark');
    const navSpark = document.getElementById('navSpark');
    const phaseFlow = document.getElementById('phaseFlow');
    const phaseTimeline = document.getElementById('phaseTimeline');
    const topicHealthBody = document.getElementById('topicHealthBody');
    const nodeHealthBody = document.getElementById('nodeHealthBody');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const exportDiagBtn = document.getElementById('exportDiagBtn');
    const diagExportResult = document.getElementById('diagExportResult');
    const exportReportBtn = document.getElementById('exportReportBtn');
    const reportExportResult = document.getElementById('reportExportResult');
    const sceneSelect = document.getElementById('sceneSelect');
    const useGadenSelect = document.getElementById('useGadenSelect');
    const useSlamSelect = document.getElementById('useSlamSelect');
    const useRvizSelect = document.getElementById('useRvizSelect');
    const headlessSelect = document.getElementById('headlessSelect');
    const activeProfileText = document.getElementById('activeProfileText');
    const llmProfileSelect = document.getElementById('llmProfileSelect');
    const llmProfileName = document.getElementById('llmProfileName');
    const llmBaseUrl = document.getElementById('llmBaseUrl');
    const llmApiKey = document.getElementById('llmApiKey');
    const llmModel = document.getElementById('llmModel');
    const llmProtocol = document.getElementById('llmProtocol');
    const llmSaveProfileBtn = document.getElementById('llmSaveProfileBtn');
    const llmReloadProfilesBtn = document.getElementById('llmReloadProfilesBtn');
    const llmActivateProfileBtn = document.getElementById('llmActivateProfileBtn');
    const llmCheckProfileBtn = document.getElementById('llmCheckProfileBtn');
    const llmProfileStatus = document.getElementById('llmProfileStatus');
    const llmPromptInput = document.getElementById('llmPromptInput');
    const llmAllowCodeEvolve = document.getElementById('llmAllowCodeEvolve');
    const llmSendBtn = document.getElementById('llmSendBtn');
    const llmRunOnceBtn = document.getElementById('llmRunOnceBtn');
    const llmReplyText = document.getElementById('llmReplyText');
    const llmActionsList = document.getElementById('llmActionsList');
    const STATE_LABELS = {
      idle: '空闲',
      starting: '启动中',
      running: '运行中',
      stopping: '停止中',
      error: '错误',
      unknown: '未知',
    };
    const PHASE_LABELS = {
      INIT: '初始化',
      PREP: '预处理',
      LAUNCH: '启动中',
      NAV_READY: '导航就绪',
      RUNNING: '运行中',
      STOPPING: '停止中',
      EXITED: '已退出',
    };
    const PHASE_FLOW = ['PREP', 'LAUNCH', 'NAV_READY', 'PATROL', 'SEEK_TRACK', 'SOURCE_FOUND'];

    let allEntries = [];
    let lastId = 0;
    let es = null;
    let llmProfilesCache = [];

    function formatStateLabel(state) {
      const key = String(state || 'unknown').toLowerCase();
      return STATE_LABELS[key] || key;
    }

    function setPhaseBadge(rawPhase) {
      const raw = String(rawPhase || '').toUpperCase();
      phaseBadge.dataset.phase = raw;
      phaseBadge.textContent = PHASE_LABELS[raw] || raw || '-';
      renderPhaseFlow(raw);
    }

    function renderPhaseFlow(activePhase) {
      const active = String(activePhase || '').toUpperCase();
      phaseFlow.innerHTML = PHASE_FLOW.map((phase) => {
        const cls = phase === active ? 'phase-step active' : 'phase-step';
        return `<div class="${cls}">${PHASE_LABELS[phase] || phase}</div>`;
      }).join('');
    }

    function formatLaunchProfile(profile) {
      const p = profile || {};
      return `scene=${p.scene ?? '-'}, use_gaden=${p.use_gaden ?? '-'}, use_slam=${p.use_slam ?? '-'}, use_rviz=${p.use_rviz ?? '-'}, headless=${p.headless ?? '-'}`;
    }

    function syncLaunchControls(profile) {
      if (!profile) return;
      if (profile.scene) sceneSelect.value = String(profile.scene);
      if (profile.use_gaden) useGadenSelect.value = String(profile.use_gaden);
      if (profile.use_slam) useSlamSelect.value = String(profile.use_slam);
      if (profile.use_rviz) useRvizSelect.value = String(profile.use_rviz);
      if (profile.headless) headlessSelect.value = String(profile.headless);
      activeProfileText.textContent = formatLaunchProfile(profile);
    }

    function collectLaunchProfile() {
      return {
        scene: sceneSelect.value,
        use_gaden: useGadenSelect.value,
        use_slam: useSlamSelect.value,
        use_rviz: useRvizSelect.value,
        headless: headlessSelect.value,
      };
    }

    function selectedLlmProfileId() {
      return llmProfileSelect.value || '';
    }

    function fillLlmProfileFields(profile) {
      if (!profile) return;
      llmProfileName.value = profile.name || '';
      llmBaseUrl.value = profile.base_url || '';
      llmModel.value = profile.model || '';
      llmProtocol.value = profile.protocol || 'chat';
      llmApiKey.value = '';
      if (profile.api_key_preview) {
        llmApiKey.placeholder = `已保存: ${profile.api_key_preview}`;
      } else {
        llmApiKey.placeholder = 'API Key';
      }
    }

    function renderLlmProfiles(payload) {
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
      llmProfilesCache = profiles;
      const active = payload?.active_profile_id || (profiles[0]?.id || '');
      llmProfileSelect.innerHTML = profiles.map((p) => {
        const n = p.name || p.id || 'profile';
        return `<option value="${escapeHtml(String(p.id || ''))}">${escapeHtml(String(n))}</option>`;
      }).join('');
      if (active) llmProfileSelect.value = String(active);
      const current = profiles.find((p) => String(p.id) === String(llmProfileSelect.value)) || profiles[0];
      fillLlmProfileFields(current || null);
      llmProfileStatus.textContent = profiles.length
        ? `已加载 ${profiles.length} 个配置，存储路径: ${payload.path || '-'}`
        : '暂无模型配置，请先填写并保存';
    }

    function currentLlmProfilePayload() {
      const existing = llmProfilesCache.find((p) => String(p.id) === String(selectedLlmProfileId()));
      const payload = {
        id: existing?.id || undefined,
        name: llmProfileName.value.trim() || 'default',
        base_url: llmBaseUrl.value.trim(),
        model: llmModel.value.trim(),
        protocol: llmProtocol.value,
        set_active: true,
      };
      const keyText = llmApiKey.value.trim();
      if (keyText) payload.api_key = keyText;
      return payload;
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function lineIsError(entry) {
      const text = String(entry.line || '').toLowerCase();
      return text.includes('error') || text.includes('failed') || text.includes('exception') || text.includes('traceback');
    }

    function setConnectionState(state) {
      const cn = state === 'connected' ? '已连接' : (state === 'reconnecting' ? '重连中' : '已断开');
      connBadge.textContent = `连接状态：${cn}`;
      if (state === 'connected') connBadge.style.color = '#22c55e';
      else if (state === 'reconnecting') connBadge.style.color = '#f59e0b';
      else connBadge.style.color = '#ef4444';
    }

    function updateButtons(state) {
      startBtn.disabled = ['starting', 'running', 'stopping'].includes(state);
      stopBtn.disabled = !['starting', 'running', 'stopping'].includes(state);
    }

    function updatePhaseFromLine(entry) {
      const line = String(entry.line || '').toLowerCase();
      if (line.includes('running demo_prep')) setPhaseBadge('PREP');
      else if (line.includes('launching:')) setPhaseBadge('LAUNCH');
      else if (line.includes('stopping simulation')) setPhaseBadge('STOPPING');
      else if (line.includes('simulation exited')) setPhaseBadge('EXITED');
    }

    function drawGasSparkline(values, thresholds) {
      const ctx = gasSpark.getContext('2d');
      const w = gasSpark.width;
      const h = gasSpark.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#0b1421';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#1f3048';
      ctx.beginPath();
      ctx.moveTo(0, h - 0.5);
      ctx.lineTo(w, h - 0.5);
      ctx.stroke();
      if (!values.length) return;
      const minV = Math.min(...values);
      const maxV = Math.max(...values);
      const allMin = Math.min(
        minV,
        Number.isFinite(Number(thresholds?.exit_threshold)) ? Number(thresholds.exit_threshold) : minV,
        Number.isFinite(Number(thresholds?.enter_threshold)) ? Number(thresholds.enter_threshold) : minV,
        Number.isFinite(Number(thresholds?.source_threshold)) ? Number(thresholds.source_threshold) : minV,
      );
      const allMax = Math.max(
        maxV,
        Number.isFinite(Number(thresholds?.exit_threshold)) ? Number(thresholds.exit_threshold) : maxV,
        Number.isFinite(Number(thresholds?.enter_threshold)) ? Number(thresholds.enter_threshold) : maxV,
        Number.isFinite(Number(thresholds?.source_threshold)) ? Number(thresholds.source_threshold) : maxV,
      );
      const yFrom = (val) => h - ((val - allMin) / Math.max(0.001, allMax - allMin)) * (h - 4) - 2;

      const drawThreshold = (value, color) => {
        if (!Number.isFinite(Number(value))) return;
        const y = yFrom(Number(value));
        ctx.strokeStyle = color;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
        ctx.setLineDash([]);
      };

      drawThreshold(thresholds?.exit_threshold, '#f59e0b');
      drawThreshold(thresholds?.enter_threshold, '#38bdf8');
      drawThreshold(thresholds?.source_threshold, '#22c55e');

      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      values.forEach((val, idx) => {
        const x = values.length === 1 ? w : (idx / (values.length - 1)) * w;
        const y = yFrom(val);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    function drawNavSparkline(values) {
      const ctx = navSpark.getContext('2d');
      const w = navSpark.width;
      const h = navSpark.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#0b1421';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#1f3048';
      ctx.beginPath();
      ctx.moveTo(0, h - 0.5);
      ctx.lineTo(w, h - 0.5);
      ctx.stroke();
      if (!values.length) return;
      const minV = Math.min(...values);
      const maxV = Math.max(...values);
      const span = Math.max(0.001, maxV - minV);
      ctx.strokeStyle = '#a78bfa';
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      values.forEach((val, idx) => {
        const x = values.length === 1 ? w : (idx / (values.length - 1)) * w;
        const y = h - ((val - minV) / span) * (h - 4) - 2;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    function fmt(value, digits = 3) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
      return Number(value).toFixed(digits);
    }

    function renderPhaseTimeline(phasePayload) {
      const timeline = Array.isArray(phasePayload?.timeline) ? phasePayload.timeline : [];
      const current = String(phasePayload?.current || '').toUpperCase();
      if (current) setPhaseBadge(current);
      if (!timeline.length) {
        phaseTimeline.textContent = '暂无阶段事件';
        return;
      }
      const tail = timeline
        .slice(-6)
        .map((row) => `${PHASE_LABELS[String(row.phase || '').toUpperCase()] || row.phase}@${row.start_ts}`)
        .join('  →  ');
      phaseTimeline.textContent = tail;
    }

    function renderTopicHealth(topicHealth) {
      const entries = Object.entries(topicHealth || {});
      if (!entries.length) {
        topicHealthBody.innerHTML = '<tr><td colspan="5" class="muted">暂无话题采样</td></tr>';
        return;
      }
      topicHealthBody.innerHTML = entries.map(([topic, row]) => {
        const status = String(row?.status || 'unknown');
        const klass = status === 'ok' ? 'chip-ok' : 'chip-stale';
        const statusText = status === 'ok' ? '正常' : (status === 'stale' ? '超时' : status);
        return `<tr>
          <td>${escapeHtml(topic)}</td>
          <td class="${klass}">${escapeHtml(statusText)}</td>
          <td>${fmt(row?.hz, 2)}</td>
          <td>${fmt(row?.stale_sec, 2)}</td>
          <td>${escapeHtml(JSON.stringify(row?.last_value ?? '-'))}</td>
        </tr>`;
      }).join('');
    }

    function renderNodeHealth(nodeHealthPayload) {
      const nodes = Array.isArray(nodeHealthPayload?.nodes) ? nodeHealthPayload.nodes : [];
      if (!nodes.length) {
        nodeHealthBody.innerHTML = '<tr><td colspan="4" class="muted">暂无节点健康数据</td></tr>';
        return;
      }
      nodeHealthBody.innerHTML = nodes.map((row) => {
        const up = Boolean(row?.up);
        const klass = up ? 'chip-ok' : 'chip-down';
        return `<tr>
          <td>${escapeHtml(String(row?.name ?? '-'))}</td>
          <td class="${klass}">${up ? '在线' : '离线'}</td>
          <td>${escapeHtml(String(row?.restart_count ?? 0))}</td>
          <td>${escapeHtml(String(row?.last_seen ?? '-'))}</td>
        </tr>`;
      }).join('');
    }

    async function fetchMetrics() {
      const r = await fetch('/api/metrics/recent?limit=120');
      const data = await r.json();
      const mode = data.mode?.current ?? null;
      const gasCurrent = data.gas?.current ?? null;
      const thresholds = data.mission_thresholds || null;
      const sourceFound = data.source_found?.current;
      const navSuccess = data.nav?.goal_succeeded ?? 0;
      const navFailed = data.nav?.failed_to_make_progress ?? 0;
      const navCanceled = data.nav?.goal_canceled ?? 0;
      const meanGoalSec = data.nav?.mean_goal_time_sec;
      const currentGoalSec = data.nav?.current_goal_age_sec;
      const navDurations = Array.isArray(data.nav?.goal_durations_sec) ? data.nav.goal_durations_sec : [];
      modeMetric.textContent = mode ?? '暂无';
      if (typeof gasCurrent === 'number') gasMetric.textContent = `${gasCurrent.toFixed(3)} ppm`;
      else gasMetric.textContent = '暂无';
      if (thresholds) {
        gasThresholds.textContent = `阈值: 退出=${fmt(thresholds.exit_threshold, 2)} / 进入=${fmt(thresholds.enter_threshold, 2)} / 锁定=${fmt(thresholds.source_threshold, 2)} ppm`;
      } else {
        gasThresholds.textContent = '阈值: 暂无';
      }
      if (typeof sourceFound === 'boolean') {
        sourceMetric.textContent = sourceFound ? '是' : '否';
        sourceMetric.style.color = sourceFound ? '#22c55e' : '#f59e0b';
      } else {
        sourceMetric.textContent = '暂无';
        sourceMetric.style.color = '#94a3b8';
      }
      navMetric.textContent = `${navSuccess}/${navFailed}/${navCanceled}`;
      navDetail.innerHTML = `成功: ${navSuccess}<br/>前进失败: ${navFailed}<br/>取消: ${navCanceled}<br/>平均到点时长: ${meanGoalSec ?? '暂无'}<br/>当前目标耗时: ${currentGoalSec ?? '暂无'}`;
      const gasHistory = Array.isArray(data.gas?.history) ? data.gas.history : [];
      drawGasSparkline(gasHistory.map((row) => Number(row.value)).filter((x) => Number.isFinite(x)), thresholds);
      drawNavSparkline(navDurations.map((x) => Number(x)).filter((x) => Number.isFinite(x)));
      renderPhaseTimeline(data.phase);
      renderTopicHealth(data.topic_health);
      renderNodeHealth(data.node_health);
    }

    function renderLogs() {
      const sourceValue = sourceFilter.value;
      const query = logSearch.value.trim().toLowerCase();
      const visible = allEntries.filter((entry) => {
        if (sourceValue !== 'all' && String(entry.source) !== sourceValue) return false;
        if (query && !String(entry.line || '').toLowerCase().includes(query)) return false;
        return true;
      });
      resultCount.textContent = `${visible.length} 行`;
      logsEl.innerHTML = visible.map((entry) => {
        const src = String(entry.source || 'system');
        const errorClass = lineIsError(entry) ? ' error' : '';
        const txt = `[${entry.timestamp}] [${src}] ${entry.line}`;
        return `<div class="logline source-${src}${errorClass}">${escapeHtml(txt)}</div>`;
      }).join('');
      if (autoScrollToggle.checked) {
        logsEl.scrollTop = logsEl.scrollHeight;
      }
    }

    function appendEntry(entry) {
      allEntries.push(entry);
      if (allEntries.length > 2000) allEntries = allEntries.slice(allEntries.length - 2000);
      lastId = Math.max(lastId, Number(entry.id || 0));
      updatePhaseFromLine(entry);
      renderLogs();
    }

    async function refreshStatus() {
      const r = await fetch('/api/sim/status');
      const data = await r.json();
      const state = String(data.state || 'unknown');
      stateCard.textContent = formatStateLabel(state);
      stateCard.className = `value status-${state}`;
      pidCard.textContent = data.pid ?? '-';
      latestLogCard.textContent = String(data.latest_log_id ?? 0);
      errorCard.textContent = data.last_error || '-';
      const currentPhaseRaw = String(phaseBadge.dataset.phase || '').toUpperCase();
      if (state === 'running' && ['INIT', 'PREP', 'LAUNCH', 'EXITED'].includes(currentPhaseRaw)) {
        setPhaseBadge('RUNNING');
      }
      syncLaunchControls(data.launch_profile || null);
      updateButtons(state);
      return data;
    }

    async function loadRecent() {
      const r = await fetch('/api/logs/recent?limit=300');
      const data = await r.json();
      allEntries = [];
      for (const entry of data.logs) appendEntry(entry);
    }

    function connectStream() {
      if (es) es.close();
      setConnectionState('reconnecting');
      es = new EventSource(`/api/logs/stream?after_id=${lastId}`);
      es.addEventListener('open', () => setConnectionState('connected'));
      es.addEventListener('log', (ev) => {
        const entry = JSON.parse(ev.data);
        appendEntry(entry);
      });
      es.onerror = () => {
        setConnectionState('reconnecting');
      };
    }

    async function start() {
      startBtn.disabled = true;
      try {
        const profile = collectLaunchProfile();
        activeProfileText.textContent = formatLaunchProfile(profile);
        const r = await fetch('/api/sim/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(profile),
        });
        const data = await r.json();
        if (!r.ok) alert(data.detail || '启动失败');
        await loadRecent();
        await fetchMetrics();
      } catch (err) {
        alert(`启动请求失败: ${String(err)}`);
      } finally {
        await refreshStatus();
      }
    }

    async function stop() {
      stopBtn.disabled = true;
      try {
        const r = await fetch('/api/sim/stop', { method: 'POST' });
        const data = await r.json();
        if (!r.ok) alert(data.detail || '停止失败');
        await fetchMetrics();
      } catch (err) {
        alert(`停止请求失败: ${String(err)}`);
      } finally {
        await refreshStatus();
      }
    }

    async function exportDiagnostics() {
        exportDiagBtn.disabled = true;
        diagExportResult.textContent = '导出中...';
      try {
        const r = await fetch('/api/diag/export', { method: 'POST' });
        const data = await r.json();
        if (!r.ok) {
          diagExportResult.textContent = `失败：${data.detail || '未知错误'}`;
          return;
        }
        diagExportResult.textContent = `已保存：${data.path}`;
      } catch (err) {
        diagExportResult.textContent = `失败：${String(err)}`;
      } finally {
        exportDiagBtn.disabled = false;
      }
    }

    async function exportRunReport() {
      exportReportBtn.disabled = true;
      reportExportResult.textContent = '导出中...';
      try {
        const r = await fetch('/api/report/export', { method: 'POST' });
        const data = await r.json();
        if (!r.ok) {
          reportExportResult.textContent = `失败：${data.detail || '未知错误'}`;
          return;
        }
        reportExportResult.textContent = `JSON: ${data.json_path} | MD: ${data.markdown_path}`;
      } catch (err) {
        reportExportResult.textContent = `失败：${String(err)}`;
      } finally {
        exportReportBtn.disabled = false;
      }
    }

    async function loadLlmProfiles() {
      try {
        const r = await fetch('/api/llm/profiles');
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || '加载模型配置失败');
        renderLlmProfiles(data);
      } catch (err) {
        llmProfileStatus.textContent = `加载失败: ${String(err)}`;
      }
    }

    async function saveLlmProfile() {
      llmSaveProfileBtn.disabled = true;
      try {
        const payload = currentLlmProfilePayload();
        const r = await fetch('/api/llm/profiles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || '保存失败');
        llmProfileStatus.textContent = `已保存配置: ${data.profile?.name || '-'}`;
        await loadLlmProfiles();
      } catch (err) {
        llmProfileStatus.textContent = `保存失败: ${String(err)}`;
      } finally {
        llmSaveProfileBtn.disabled = false;
      }
    }

    async function activateLlmProfile() {
      const pid = selectedLlmProfileId();
      if (!pid) return;
      llmActivateProfileBtn.disabled = true;
      try {
        const r = await fetch(`/api/llm/profiles/${encodeURIComponent(pid)}/activate`, { method: 'POST' });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || '激活失败');
        llmProfileStatus.textContent = `当前配置已切换: ${pid}`;
        await loadLlmProfiles();
      } catch (err) {
        llmProfileStatus.textContent = `激活失败: ${String(err)}`;
      } finally {
        llmActivateProfileBtn.disabled = false;
      }
    }

    async function checkLlmProfile() {
      const pid = selectedLlmProfileId();
      if (!pid) return;
      llmCheckProfileBtn.disabled = true;
      try {
        const r = await fetch(`/api/llm/profiles/${encodeURIComponent(pid)}/check`, { method: 'POST' });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || '检查失败');
        llmProfileStatus.textContent = `连接测试成功: protocol=${data.protocol_used || '-'}, preview=${data.preview || ''}`;
      } catch (err) {
        llmProfileStatus.textContent = `连接测试失败: ${String(err)}`;
      } finally {
        llmCheckProfileBtn.disabled = false;
      }
    }

    function renderLlmActions(actions) {
      if (!Array.isArray(actions) || !actions.length) {
        llmActionsList.textContent = '暂无动作';
        return;
      }
      llmActionsList.innerHTML = actions.map((a, idx) => {
        const title = escapeHtml(String(a.title || `动作${idx + 1}`));
        const reason = escapeHtml(String(a.reason || ''));
        const risk = escapeHtml(String(a.risk_level || 'medium'));
        return `<div style="padding:8px; border-bottom:1px dotted rgba(57,78,106,.35);">
          <div><strong>${title}</strong> [${escapeHtml(String(a.type || '-'))}] 风险:${risk}</div>
          <div class="muted" style="margin:4px 0 8px 0;">${reason}</div>
          <button data-action-index="${idx}" class="llm-exec-btn">执行此动作</button>
        </div>`;
      }).join('');
      document.querySelectorAll('.llm-exec-btn').forEach((btn) => {
        btn.addEventListener('click', async (ev) => {
          const idx = Number(ev.target.getAttribute('data-action-index'));
          const action = actions[idx];
          if (!action) return;
          ev.target.disabled = true;
          try {
            const r = await fetch('/api/llm/action/execute', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ action }),
            });
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || data.message || data.stderr || `执行失败(${r.status})`);
            const suffix = data && data.message ? `，${String(data.message)}` : '';
            llmProfileStatus.textContent = `动作已执行: ${action.title || action.type}${suffix}`;
            await loadRecent();
            await fetchMetrics();
            await refreshStatus();
          } catch (err) {
            llmProfileStatus.textContent = `动作执行失败: ${String(err)}`;
          } finally {
            ev.target.disabled = false;
          }
        });
      });
    }

    async function sendLlmPrompt() {
      const message = llmPromptInput.value.trim();
      if (!message) return;
      llmSendBtn.disabled = true;
      llmReplyText.textContent = 'AI 分析中...';
      try {
        const r = await fetch('/api/llm/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            profile_id: selectedLlmProfileId(),
            message,
            include_context: true,
            log_limit: 1000,
            report_limit: 3,
          }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || 'AI 调用失败');
        llmReplyText.textContent = data.analysis || '无分析结论';
        renderLlmActions(data.actions || []);
        llmProfileStatus.textContent = `AI 响应完成: protocol=${data.protocol_used || '-'}, model=${data.model || '-'}`;
      } catch (err) {
        llmReplyText.textContent = `失败: ${String(err)}`;
        renderLlmActions([]);
      } finally {
        llmSendBtn.disabled = false;
      }
    }

    async function runLlmOnce() {
      llmRunOnceBtn.disabled = true;
      llmReplyText.textContent = 'AI 单轮流程执行中...';
      try {
        const objective = llmPromptInput.value.trim() || '分析当前运行状态，给出可执行优化动作并执行';
        const r = await fetch('/api/llm/loop/run-once', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            profile_id: selectedLlmProfileId(),
            objective,
            include_context: true,
            log_limit: 1000,
            report_limit: 3,
            auto_execute: true,
            allow_code_evolve: Boolean(llmAllowCodeEvolve.checked),
          }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || '单轮流程失败');
        const chat = data.chat || {};
        llmReplyText.textContent = chat.analysis || '无分析结论';
        renderLlmActions(chat.actions || []);
        llmProfileStatus.textContent = `单轮流程完成: 执行动作数 ${Array.isArray(data.executed) ? data.executed.length : 0}`;
        await loadRecent();
        await fetchMetrics();
        await refreshStatus();
      } catch (err) {
        llmReplyText.textContent = `失败: ${String(err)}`;
      } finally {
        llmRunOnceBtn.disabled = false;
      }
    }

    sourceFilter.addEventListener('change', renderLogs);
    logSearch.addEventListener('input', renderLogs);
    autoScrollToggle.addEventListener('change', renderLogs);
    llmProfileSelect.addEventListener('change', () => {
      const profile = llmProfilesCache.find((p) => String(p.id) === String(llmProfileSelect.value));
      fillLlmProfileFields(profile || null);
    });
    startBtn.onclick = start;
    stopBtn.onclick = stop;
    refreshBtn.onclick = refreshStatus;
    exportDiagBtn.onclick = exportDiagnostics;
    exportReportBtn.onclick = exportRunReport;
    llmReloadProfilesBtn.onclick = loadLlmProfiles;
    llmSaveProfileBtn.onclick = saveLlmProfile;
    llmActivateProfileBtn.onclick = activateLlmProfile;
    llmCheckProfileBtn.onclick = checkLlmProfile;
    llmSendBtn.onclick = sendLlmPrompt;
    llmRunOnceBtn.onclick = runLlmOnce;

    (async () => {
      setPhaseBadge('INIT');
      syncLaunchControls({
        scene: 'warehouse',
        use_gaden: 'true',
        use_slam: 'true',
        use_rviz: 'true',
        headless: 'false',
      });
      await loadRecent();
      await refreshStatus();
      await fetchMetrics();
      await loadLlmProfiles();
      connectStream();
      setInterval(refreshStatus, 3000);
      setInterval(fetchMetrics, 1000);
    })();
  </script>
</body>
</html>
"""


def create_app(
    controller: SimulationController | None = None,
    llm_controller: LlmController | None = None,
    *,
    start_topic_collector: bool = False,
) -> Any:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is not available. Install fastapi and uvicorn first.")

    app = FastAPI(title="H2Track Web Console")
    sim = controller or SimulationController()
    llm = llm_controller or LlmController(sim=sim)
    ui_meta = _resolve_ui_meta()
    collector = TopicMetricsCollector(sim._metrics) if start_topic_collector else None
    if collector is not None:
        # Start eagerly so live metrics remain available even if startup hooks are skipped.
        collector.start()
    if bool(ui_meta.get("bundle_ready")):
        static_dir = _resolve_static_console_dir()
        assert static_dir is not None
        assets_dir = static_dir / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    async def _read_json_dict(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return {}
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON payload: {exc}") from exc
        if body is None:
            return {}
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object")
        return body

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        index_path = _resolve_static_index_html()
        if index_path is not None:
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(content=HTML_PAGE)

    @app.get("/api/ui/meta")
    def get_ui_meta() -> JSONResponse:
        return JSONResponse(content=ui_meta)

    @app.post("/api/sim/start")
    async def start_sim(request: Request) -> JSONResponse:
        payload = await _read_json_dict(request)
        ok, message = sim.start_with_profile(payload)
        if not ok:
            raise HTTPException(status_code=409, detail=message)
        return JSONResponse(status_code=202, content={"ok": True, "message": message})

    @app.post("/api/sim/stop")
    def stop_sim() -> JSONResponse:
        ok, message = sim.stop()
        if not ok:
            raise HTTPException(status_code=409, detail=message)
        return JSONResponse(status_code=202, content={"ok": True, "message": message})

    @app.get("/api/sim/status")
    def get_status() -> JSONResponse:
        return JSONResponse(content=sim.status())

    @app.get("/api/logs/recent")
    def get_recent(limit: int = Query(default=200, ge=1, le=2000)) -> JSONResponse:
        logs = sim.recent_logs(limit=limit)
        return JSONResponse(content={"logs": logs, "latest_id": sim.status()["latest_log_id"]})

    @app.get("/api/metrics/recent")
    def get_metrics_recent(limit: int = Query(default=120, ge=1, le=2000)) -> JSONResponse:
        sim.refresh_metrics_from_topics_if_needed()
        sim.refresh_runtime_health_if_needed()
        return JSONResponse(content=sim.metrics_snapshot(limit=limit))

    @app.get("/api/health/nodes")
    def get_nodes_health() -> JSONResponse:
        sim.refresh_runtime_health_if_needed()
        payload = sim.metrics_snapshot(limit=1).get("node_health", {})
        return JSONResponse(content=payload)

    @app.post("/api/diag/export")
    def export_diag() -> JSONResponse:
        try:
            path = sim.export_diagnostics(scene="warehouse")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"diagnostic export failed: {exc}") from exc
        return JSONResponse(status_code=202, content={"ok": True, "path": path})

    @app.post("/api/report/export")
    def export_report() -> JSONResponse:
        try:
            status_payload = sim.status()
            profile = status_payload.get("launch_profile", {}) if isinstance(status_payload, dict) else {}
            scene = str(profile.get("scene", "warehouse"))
            artifacts = sim.export_run_report(scene=scene)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"run report export failed: {exc}") from exc
        return JSONResponse(status_code=202, content={"ok": True, **artifacts})

    @app.get("/api/llm/profiles")
    def get_llm_profiles() -> JSONResponse:
        try:
            payload = llm.list_profiles()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"list profiles failed: {exc}") from exc
        return JSONResponse(content=payload)

    @app.post("/api/llm/profiles")
    async def save_llm_profile(request: Request) -> JSONResponse:
        payload = await _read_json_dict(request)
        try:
            result = llm.save_profile(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"save profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/profiles/{profile_id}/activate")
    def activate_llm_profile(profile_id: str) -> JSONResponse:
        try:
            result = llm.activate_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"activate profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/profiles/{profile_id}/check")
    def check_llm_profile(profile_id: str) -> JSONResponse:
        try:
            result = llm.check_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"profile check failed: {exc}") from exc
        return JSONResponse(content=result)

    @app.delete("/api/llm/profiles/{profile_id}")
    def delete_llm_profile(profile_id: str) -> JSONResponse:
        try:
            result = llm.delete_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"delete profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/chat")
    async def llm_chat(request: Request) -> JSONResponse:
        payload = await _read_json_dict(request)
        try:
            result = llm.chat(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"llm chat failed: {exc}") from exc
        return JSONResponse(content=result)

    @app.post("/api/llm/action/execute")
    async def execute_llm_action(request: Request) -> JSONResponse:
        payload = await _read_json_dict(request)
        action = payload.get("action")
        if not isinstance(action, dict):
            raise HTTPException(status_code=400, detail="action object is required")
        try:
            result = llm.execute_action(action)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"execute action failed: {exc}") from exc
        status_code = 202 if result.get("ok") else 409
        return JSONResponse(status_code=status_code, content=result)

    @app.post("/api/llm/loop/run-once")
    async def llm_loop_run_once(request: Request) -> JSONResponse:
        payload = await _read_json_dict(request)
        try:
            result = llm.run_once(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"run-once failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.get("/api/llm/history")
    def llm_history(limit: int = Query(default=50, ge=1, le=500)) -> JSONResponse:
        return JSONResponse(content=llm.history(limit=limit))

    @app.get("/api/llm/audit")
    def llm_audit(limit: int = Query(default=100, ge=1, le=1000)) -> JSONResponse:
        return JSONResponse(content=llm.audit(limit=limit))

    @app.get("/api/logs/stream")
    async def stream_logs(request: Request, after_id: int = Query(default=0, ge=0)) -> StreamingResponse:
        async def _events() -> Any:
            cursor = after_id
            while True:
                if await request.is_disconnected():
                    break
                new_entries = sim.logs_after(cursor)
                if new_entries:
                    for entry in new_entries:
                        cursor = int(entry["id"])
                        payload = json.dumps(entry, ensure_ascii=False)
                        yield f"id: {cursor}\nevent: log\ndata: {payload}\n\n"
                else:
                    yield "event: ping\ndata: {}\n\n"
                    await asyncio.sleep(1.0)

        return StreamingResponse(_events(), media_type="text/event-stream")

    @app.on_event("startup")
    async def _on_startup() -> None:
        if collector is not None:
            collector.start()

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        if collector is not None:
            collector.stop()

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
