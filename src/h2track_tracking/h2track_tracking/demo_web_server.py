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
from .web.templates import HTML_PAGE, build_run_report_markdown


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
        markdown_path.write_text(build_run_report_markdown(report_payload), encoding="utf-8")
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
