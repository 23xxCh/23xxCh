from pathlib import Path

import pytest

from h2track_tracking import demo_web_server as web
from h2track_tracking.web import app as web_app
from h2track_tracking.web import simulation_controller as web_sim
from h2track_tracking.web.config import (
    build_demo_launch_command,
    DEFAULT_LAUNCH_PROFILE,
)


def test_build_fixed_demo_launch_command_uses_warehouse_defaults():
    cmd = build_demo_launch_command(DEFAULT_LAUNCH_PROFILE)
    assert cmd == [
        "ros2",
        "launch",
        "h2track_sim",
        "demo.launch.py",
        "scene:=warehouse",
        "use_gaden:=true",
        "use_slam:=true",
        "use_rviz:=true",
        "headless:=false",
    ]


def test_build_demo_launch_command_supports_runtime_profile():
    cmd = build_demo_launch_command(
        {
            "scene": "baseline",
            "use_gaden": "false",
            "use_slam": "false",
            "use_rviz": "false",
            "headless": "true",
        }
    )
    assert cmd == [
        "ros2",
        "launch",
        "h2track_sim",
        "demo.launch.py",
        "scene:=baseline",
        "use_gaden:=false",
        "use_slam:=false",
        "use_rviz:=false",
        "headless:=true",
    ]


def test_concentration_regex_accepts_short_conc_key():
    m = web.CONCENTRATION_RE.search("Mode transition: SEEK_CONFIRM -> SEEK_TRACK (conc=2.504)")
    assert m is not None
    assert float(m.group(1)) == pytest.approx(2.504, abs=1e-9)


def test_load_scene_thresholds_reads_mission_thresholds(tmp_path, monkeypatch):
    scene_yaml = tmp_path / "scene.yaml"
    scene_yaml.write_text(
        "mission_manager:\n"
        "  enter_threshold: 0.65\n"
        "  exit_threshold: 0.40\n"
        "  source_threshold: 3.4\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "_candidate_scene_yaml_paths", lambda _scene: [scene_yaml])

    thresholds = web.load_scene_thresholds("warehouse")

    assert thresholds == {
        "enter_threshold": pytest.approx(0.65, abs=1e-9),
        "exit_threshold": pytest.approx(0.40, abs=1e-9),
        "source_threshold": pytest.approx(3.4, abs=1e-9),
    }


def test_metrics_snapshot_includes_profile_thresholds_and_goal_durations(monkeypatch):
    monkeypatch.setattr(
        web_sim,
        "load_scene_thresholds",
        lambda scene: {"enter_threshold": 0.7, "exit_threshold": 0.4, "source_threshold": 3.3}
        if scene == "warehouse"
        else None,
    )

    store = web.MetricsStore(max_points=16)
    for _ in range(2):
        store.observe_log_line("Begin navigating from current location")
        store.observe_log_line("Goal succeeded")
    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
        metrics_store=store,
    )
    controller._launch_profile = {
        "scene": "warehouse",
        "use_gaden": "true",
        "use_slam": "true",
        "use_rviz": "true",
        "headless": "false",
    }

    payload = controller.metrics_snapshot(limit=8)

    assert payload["launch_profile"]["scene"] == "warehouse"
    assert payload["mission_thresholds"]["source_threshold"] == pytest.approx(3.3, abs=1e-9)
    assert isinstance(payload["nav"]["goal_durations_sec"], list)


def test_metrics_snapshot_flags_flatline_zero_gaden_signal():
    store = web.MetricsStore(max_points=16)
    for _ in range(6):
        store.set_gas_raw(0.0)
        store.set_gas(0.0)

    payload = store.snapshot(limit=16)

    assert payload["gas"]["raw_current"] == pytest.approx(0.0, abs=1e-9)
    assert payload["gas"]["signal_status"] == "flatline_zero"
    assert "全零" in payload["gas"]["signal_reason"]


def test_metrics_snapshot_flags_active_gaden_signal_when_raw_positive():
    store = web.MetricsStore(max_points=16)
    for value in (0.0, 0.0, 0.45, 1.1):
        store.set_gas_raw(value)
        store.set_gas(value)

    payload = store.snapshot(limit=16)

    assert payload["gas"]["raw_current"] == pytest.approx(1.1, abs=1e-9)
    assert payload["gas"]["signal_status"] == "active"
    assert "正常" in payload["gas"]["signal_reason"]


def test_controller_start_rejects_duplicate_start():
    started = {"count": 0}

    class _Proc:
        pid = 4321

        def poll(self):
            return None

    def _run_prep(cmd):
        assert cmd[:4] == ["ros2", "run", "h2track_tracking", "demo_prep"]
        return web.CommandResult(returncode=0, stdout="DEMO PREP OK\n", stderr="")

    def _launch(cmd, env):
        started["count"] += 1
        return _Proc()

    controller = web.SimulationController(run_command=_run_prep, launch_process=_launch)

    accepted, _ = controller.start()
    assert accepted is True
    accepted2, msg2 = controller.start()
    assert accepted2 is False
    assert "already" in msg2.lower()
    assert started["count"] == 1


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_create_app_exposes_required_routes():
    app = web.create_app()
    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/api/ui/meta" in paths
    assert "/api/sim/start" in paths
    assert "/api/sim/stop" in paths
    assert "/api/sim/status" in paths
    assert "/api/logs/recent" in paths
    assert "/api/logs/stream" in paths
    assert "/api/metrics/recent" in paths
    assert "/api/health/nodes" in paths
    assert "/api/diag/export" in paths
    assert "/api/report/export" in paths
    assert "/api/llm/profiles" in paths
    assert "/api/llm/chat" in paths
    assert "/api/llm/action/execute" in paths
    assert "/api/llm/loop/run-once" in paths
    assert "/api/llm/history" in paths
    assert "/api/llm/audit" in paths


def test_resolve_ui_meta_defaults_to_legacy_without_bundle(monkeypatch):
    monkeypatch.setattr(web_app, "_resolve_static_console_dir", lambda: None)
    monkeypatch.setattr(web_app, "_resolve_static_index_html", lambda: None)

    payload = web._resolve_ui_meta()
    assert payload["mode"] == web.UI_MODE_LEGACY
    assert payload["bundle_ready"] is False


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_ui_meta_endpoint_returns_mode():
    from fastapi.testclient import TestClient

    app = web.create_app()
    client = TestClient(app)
    resp = client.get("/api/ui/meta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] in {web.UI_MODE_LEGACY, web.UI_MODE_STATIC}
    assert isinstance(data["bundle_ready"], bool)


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_index_prefers_static_bundle_when_available(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    index_path = tmp_path / "index.html"
    index_path.write_text("<html><body>react bundle</body></html>", encoding="utf-8")
    static_dir = tmp_path / "static_console"
    static_dir.mkdir(exist_ok=True)
    assets = static_dir / "assets"
    assets.mkdir(exist_ok=True)

    monkeypatch.setattr(web_app, "_resolve_static_console_dir", lambda: static_dir)
    monkeypatch.setattr(web_app, "_resolve_static_index_html", lambda: index_path)

    app = web.create_app()
    client = TestClient(app)
    resp = client.get("/")

    assert resp.status_code == 200
    assert "react bundle" in resp.text


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_create_app_starts_topic_collector_eagerly(monkeypatch):
    started = {"count": 0}

    class _FakeCollector:
        def __init__(self, _metrics_store):
            pass

        def start(self):
            started["count"] += 1

        def stop(self):
            return None

    monkeypatch.setattr(web_app, "TopicMetricsCollector", _FakeCollector)
    _ = web.create_app(start_topic_collector=True)

    assert started["count"] == 1


def test_html_contains_dashboard_sections_and_controls():
    html = web.HTML_PAGE
    assert 'id="stateCard"' in html
    assert 'id="pidCard"' in html
    assert 'id="errorCard"' in html
    assert 'id="phaseBadge"' in html
    assert 'id="connBadge"' in html
    assert 'id="sourceFilter"' in html
    assert 'id="logSearch"' in html
    assert 'id="autoScrollToggle"' in html
    assert 'id="logs"' in html
    assert 'id="modeMetric"' in html
    assert 'id="gasMetric"' in html
    assert 'id="gasThresholds"' in html
    assert 'id="sourceMetric"' in html
    assert 'id="navMetric"' in html
    assert 'id="gasSpark"' in html
    assert 'id="navSpark"' in html
    assert 'id="phaseTimeline"' in html
    assert 'id="phaseFlow"' in html
    assert 'id="topicHealthBody"' in html
    assert 'id="nodeHealthBody"' in html
    assert 'id="exportDiagBtn"' in html
    assert 'id="diagExportResult"' in html
    assert 'id="exportReportBtn"' in html
    assert 'id="reportExportResult"' in html
    assert 'id="sceneSelect"' in html
    assert 'id="useGadenSelect"' in html
    assert 'id="useSlamSelect"' in html
    assert 'id="useRvizSelect"' in html
    assert 'id="headlessSelect"' in html
    assert 'id="activeProfileText"' in html
    assert 'id="llmProfileSelect"' in html
    assert 'id="llmProfileName"' in html
    assert 'id="llmBaseUrl"' in html
    assert 'id="llmApiKey"' in html
    assert 'id="llmModel"' in html
    assert 'id="llmProtocol"' in html
    assert 'id="llmSaveProfileBtn"' in html
    assert 'id="llmReloadProfilesBtn"' in html
    assert 'id="llmActivateProfileBtn"' in html
    assert 'id="llmCheckProfileBtn"' in html
    assert 'id="llmPromptInput"' in html
    assert 'id="llmAllowCodeEvolve"' in html
    assert 'id="llmSendBtn"' in html
    assert 'id="llmRunOnceBtn"' in html
    assert 'id="llmReplyText"' in html
    assert 'id="llmActionsList"' in html


def test_html_contains_interaction_logic_for_filters_and_button_locking():
    html = web.HTML_PAGE
    assert "startBtn.disabled" in html
    assert "stopBtn.disabled" in html
    assert "sourceFilter" in html
    assert "logSearch" in html
    assert "autoScrollToggle" in html
    assert "connected" in html or "disconnected" in html
    assert "fetch('/api/metrics/recent" in html
    assert "drawGasSparkline" in html
    assert "drawNavSparkline" in html
    assert "mission_thresholds" in html
    assert "goal_durations_sec" in html
    assert "fetch('/api/diag/export'" in html
    assert "fetch('/api/report/export'" in html
    assert "fetch('/api/llm/profiles'" in html
    assert "fetch('/api/llm/chat'" in html
    assert "fetch('/api/llm/action/execute'" in html
    assert "fetch('/api/llm/loop/run-once'" in html
    assert "allow_code_evolve" in html
    assert "collectLaunchProfile" in html
    assert "renderPhaseFlow" in html
    assert "Content-Type': 'application/json'" in html
    assert "body: JSON.stringify(profile)" in html
    assert "finally {" in html


def test_html_uses_chinese_copy_and_songti_font():
    html = web.HTML_PAGE
    assert "Songti SC" in html
    assert "SimSun" in html
    assert "H2Track 仓库控制台" in html
    assert "开始仿真" in html
    assert "停止仿真" in html
    assert "空闲" in html
    assert "初始化" in html
    assert "话题健康度" in html
    assert "连接状态：连接中" in html


def test_metrics_store_observes_mode_gas_source_and_nav_events():
    store = web.MetricsStore(max_points=16)
    store.observe_log_line("Mode transition: PATROL -> SEEK_TRACK")
    store.observe_log_line("concentration=1.875")
    store.observe_log_line("Goal succeeded")
    store.observe_log_line("Failed to make progress")
    store.observe_log_line("Mode transition: SEEK_TRACK -> SOURCE_FOUND")

    snap = store.snapshot(limit=8)
    assert snap["mode"]["current"] == "SOURCE_FOUND"
    assert snap["source_found"]["current"] is True
    assert snap["gas"]["current"] == pytest.approx(1.875, abs=1e-6)
    assert snap["nav"]["goal_succeeded"] == 1
    assert snap["nav"]["failed_to_make_progress"] == 1
    assert "phase" in snap
    assert "timeline" in snap["phase"]
    assert "goal_canceled" in snap["nav"]
    assert "mean_goal_time_sec" in snap["nav"]
    assert "topic_health" in snap
    assert "node_health" in snap


def test_controller_metrics_topic_probe_fallback_populates_missing_gas():
    probe_values = {
        "/gas_concentration": "0.375",
    }

    def _probe(topic: str, _timeout_sec: float):
        return probe_values.get(topic)

    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
        topic_probe=_probe,
    )

    controller.refresh_metrics_from_topics_if_needed()
    snap = controller.metrics_snapshot(limit=8)
    assert snap["gas"]["current"] == pytest.approx(0.375, abs=1e-6)


def test_controller_metrics_topic_probe_appends_multiple_gas_points():
    probe_values = iter(["0.10", "0.25"])

    def _probe(topic: str, _timeout_sec: float):
        if topic != "/gas_concentration":
            return None
        return next(probe_values, None)

    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
        topic_probe=_probe,
        topic_probe_interval_sec=0.0,
    )

    controller.refresh_metrics_from_topics_if_needed()
    controller.refresh_metrics_from_topics_if_needed()

    snap = controller.metrics_snapshot(limit=8)
    assert snap["gas"]["current"] == pytest.approx(0.25, abs=1e-6)
    assert len(snap["gas"]["history"]) >= 2


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_metrics_recent_endpoint_returns_snapshot():
    from fastapi.testclient import TestClient

    store = web.MetricsStore()
    store.set_mode("PATROL")
    store.set_gas(0.42)
    store.set_source_found(False)
    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
        metrics_store=store,
    )
    app = web.create_app(controller=controller)
    client = TestClient(app)

    response = client.get("/api/metrics/recent?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"]["current"] == "PATROL"
    assert payload["gas"]["current"] == pytest.approx(0.42, abs=1e-6)
    assert payload["source_found"]["current"] is False
    assert "phase" in payload
    assert "topic_health" in payload
    assert "node_health" in payload


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_api_start_duplicate_returns_409():
    from fastapi.testclient import TestClient

    class _Proc:
        pid = 7788
        stdout = None

        def poll(self):
            return None

    def _run_prep(_cmd):
        return web.CommandResult(returncode=0, stdout="DEMO PREP OK\n", stderr="")

    def _launch(_cmd, _env):
        return _Proc()

    app = web.create_app(
        controller=web.SimulationController(run_command=_run_prep, launch_process=_launch)
    )
    client = TestClient(app)

    first = client.post("/api/sim/start")
    second = client.post("/api/sim/start")

    assert first.status_code == 202
    assert second.status_code == 409


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_api_start_accepts_runtime_launch_profile():
    from fastapi.testclient import TestClient

    seen = {"cmd": None}

    class _Proc:
        pid = 9900
        stdout = None

        def poll(self):
            return None

    def _run_prep(_cmd):
        return web.CommandResult(returncode=0, stdout="DEMO PREP OK\n", stderr="")

    def _launch(cmd, _env):
        seen["cmd"] = cmd
        return _Proc()

    app = web.create_app(
        controller=web.SimulationController(run_command=_run_prep, launch_process=_launch)
    )
    client = TestClient(app)

    response = client.post(
        "/api/sim/start",
        json={
            "scene": "baseline",
            "use_gaden": False,
            "use_slam": False,
            "use_rviz": False,
            "headless": True,
        },
    )
    assert response.status_code == 202
    assert seen["cmd"] is not None
    assert "scene:=baseline" in seen["cmd"]
    assert "use_gaden:=false" in seen["cmd"]
    assert "use_slam:=false" in seen["cmd"]
    assert "use_rviz:=false" in seen["cmd"]
    assert "headless:=true" in seen["cmd"]


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_diag_export_endpoint_returns_artifact_path(tmp_path):
    from fastapi.testclient import TestClient

    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
    )
    app = web.create_app(controller=controller)
    client = TestClient(app)
    response = client.post("/api/diag/export")

    assert response.status_code == 202
    payload = response.json()
    assert payload["ok"] is True
    assert payload["path"].endswith(".zip")
    assert Path(payload["path"]).exists()


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_report_export_endpoint_returns_json_and_markdown_paths():
    from fastapi.testclient import TestClient

    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
    )
    app = web.create_app(controller=controller)
    client = TestClient(app)
    response = client.post("/api/report/export")

    assert response.status_code == 202
    payload = response.json()
    assert payload["ok"] is True
    assert payload["json_path"].endswith(".json")
    assert payload["markdown_path"].endswith(".md")
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()


@pytest.mark.skipif(not web.FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_llm_endpoints_use_controller_contract():
    from fastapi.testclient import TestClient

    class _FakeLLM:
        def list_profiles(self):
            return {"active_profile_id": "p1", "profiles": [{"id": "p1", "name": "default"}], "path": "/tmp/x.json"}

        def save_profile(self, payload):
            return {"ok": True, "profile": {"id": payload.get("id", "p2"), "name": payload.get("name", "new")}}

        def activate_profile(self, profile_id: str):
            return {"ok": True, "active_profile_id": profile_id}

        def check_profile(self, profile_id: str):
            return {"ok": True, "protocol_used": "chat", "preview": f"ok:{profile_id}"}

        def delete_profile(self, profile_id: str):
            return {"ok": True}

        def chat(self, payload):
            return {
                "ok": True,
                "analysis": "分析完成",
                "actions": [{"type": "console_action", "title": "刷新", "payload": {"action": "refresh_status"}}],
                "protocol_used": "chat",
            }

        def execute_action(self, action):
            return {"ok": True, "action": action}

        def run_once(self, payload):
            return {"ok": True, "chat": {"analysis": "run once"}, "executed": []}

        def history(self, limit: int = 50):
            return {"rows": [{"id": 1}]}

        def audit(self, limit: int = 100):
            return {"rows": [{"id": 1}]}

    controller = web.SimulationController(
        run_command=lambda _cmd: web.CommandResult(returncode=0, stdout="", stderr=""),
        launch_process=lambda _cmd, _env: object(),
    )
    app = web.create_app(controller=controller, llm_controller=_FakeLLM())
    client = TestClient(app)

    r_profiles = client.get("/api/llm/profiles")
    assert r_profiles.status_code == 200
    assert r_profiles.json()["active_profile_id"] == "p1"

    r_save = client.post("/api/llm/profiles", json={"name": "alpha"})
    assert r_save.status_code == 202
    assert r_save.json()["ok"] is True

    r_activate = client.post("/api/llm/profiles/p1/activate")
    assert r_activate.status_code == 202
    assert r_activate.json()["active_profile_id"] == "p1"

    r_check = client.post("/api/llm/profiles/p1/check")
    assert r_check.status_code == 200
    assert r_check.json()["ok"] is True

    r_chat = client.post("/api/llm/chat", json={"message": "分析当前状态"})
    assert r_chat.status_code == 200
    assert r_chat.json()["analysis"] == "分析完成"
    assert isinstance(r_chat.json()["actions"], list)

    r_exec = client.post(
        "/api/llm/action/execute",
        json={"action": {"type": "console_action", "payload": {"action": "refresh_status"}}},
    )
    assert r_exec.status_code == 202
    assert r_exec.json()["ok"] is True

    r_once = client.post("/api/llm/loop/run-once", json={"objective": "run"})
    assert r_once.status_code == 202
    assert r_once.json()["ok"] is True

    r_history = client.get("/api/llm/history")
    assert r_history.status_code == 200
    assert isinstance(r_history.json()["rows"], list)

    r_audit = client.get("/api/llm/audit")
    assert r_audit.status_code == 200
    assert isinstance(r_audit.json()["rows"], list)
