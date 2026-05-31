from pathlib import Path

import pytest

from h2track_tracking import llm as llm_agent


def test_profile_store_round_trip(tmp_path):
    store = llm_agent.LlmProfileStore(path=tmp_path / "profiles.json")
    saved = store.save_profile(
        {
            "name": "local-vllm",
            "base_url": "http://127.0.0.1:8000",
            "api_key": "abc123456",
            "model": "gpt-4.1-mini",
            "protocol": "chat",
            "set_active": True,
        }
    )
    assert saved["name"] == "local-vllm"
    listed = store.list_profiles()
    assert listed["active_profile_id"] is not None
    assert len(listed["profiles"]) == 1
    assert listed["profiles"][0]["has_api_key"] is True
    assert listed["profiles"][0]["api_key_preview"].startswith("***")


def test_profile_store_requires_core_fields(tmp_path):
    store = llm_agent.LlmProfileStore(path=tmp_path / "profiles.json")
    with pytest.raises(ValueError):
        store.save_profile({"name": "x"})


def test_extract_json_block_fallback():
    raw = """analysis text
```json
{"analysis":"ok","actions":[]}
```"""
    obj = llm_agent._extract_json_block(raw)
    assert obj is not None
    assert obj["analysis"] == "ok"


def test_openai_compat_endpoint_building():
    client = llm_agent.OpenAICompatClient()
    assert client._endpoint_for("https://api.example.com", "chat") == "https://api.example.com/v1/chat/completions"
    assert client._endpoint_for("https://api.example.com/v1", "chat") == "https://api.example.com/v1/chat/completions"
    assert client._endpoint_for("https://api.example.com/v2", "chat") == "https://api.example.com/v2/chat/completions"
    assert client._endpoint_for("https://api.example.com/v2", "responses") == "https://api.example.com/v2/responses"


class _FakeSim:
    def __init__(self) -> None:
        self._started = False

    def status(self):
        return {"state": "idle", "launch_profile": {"scene": "warehouse"}}

    def metrics_snapshot(self, limit=120):
        return {"phase": {"current": "INIT"}, "mode": {"current": "PATROL"}, "gas": {"current": 0.1}}

    def recent_logs(self, limit=200):
        return [{"id": 1, "timestamp": "2026-01-01T00:00:00Z", "source": "sim", "line": "line"}]

    def start_with_profile(self, _profile):
        self._started = True
        return True, "started"

    def stop(self):
        self._started = False
        return True, "stopped"

    def export_diagnostics(self, scene="warehouse"):
        return f"/tmp/{scene}.zip"

    def export_run_report(self, scene="warehouse"):
        return {"json_path": f"/tmp/{scene}.json", "markdown_path": f"/tmp/{scene}.md"}


def test_llm_controller_command_policy_blocks_dangerous(tmp_path):
    controller = llm_agent.LlmController(
        sim=_FakeSim(),
        profile_store=llm_agent.LlmProfileStore(path=tmp_path / "profiles.json"),
    )
    ok, reason = controller._command_allowed("rm -rf /tmp/x")
    assert ok is False
    assert "forbidden" in reason


def test_llm_controller_exec_console_action_refresh(tmp_path):
    controller = llm_agent.LlmController(
        sim=_FakeSim(),
        profile_store=llm_agent.LlmProfileStore(path=tmp_path / "profiles.json"),
    )
    result = controller.execute_action(
        {"type": "console_action", "title": "刷新状态", "payload": {"action": "refresh_status"}}
    )
    assert result["ok"] is True
    assert "status" in result


def test_llm_controller_exec_shell_command_denied(tmp_path):
    controller = llm_agent.LlmController(
        sim=_FakeSim(),
        profile_store=llm_agent.LlmProfileStore(path=tmp_path / "profiles.json"),
    )
    result = controller.execute_action(
        {"type": "shell_command", "title": "危险命令", "payload": {"command": "git reset --hard"}}
    )
    assert result["ok"] is False


def test_llm_controller_exec_shell_command_failure_has_message(tmp_path):
    controller = llm_agent.LlmController(
        sim=_FakeSim(),
        profile_store=llm_agent.LlmProfileStore(path=tmp_path / "profiles.json"),
    )
    result = controller.execute_action(
        {
            "type": "shell_command",
            "title": "坏命令",
            "payload": {"command": "ls /__h2track_missing_path__"},
        }
    )
    assert result["ok"] is False
    assert result["returncode"] != 0
    assert isinstance(result.get("message"), str)
    assert result["message"].startswith("command failed")


def test_llm_controller_exec_shell_command_launch_script_maps_to_console_action(tmp_path):
    controller = llm_agent.LlmController(
        sim=_FakeSim(),
        profile_store=llm_agent.LlmProfileStore(path=tmp_path / "profiles.json"),
    )
    result = controller.execute_action(
        {
            "type": "shell_command",
            "title": "启动仿真",
            "payload": {
                "command": "cd /home/user/h2track-xian && ./scripts/launch_sim.sh --scene warehouse --gaden --slam --rviz"
            },
        }
    )
    assert result["ok"] is True
    assert result.get("translated_from_shell_command") is True
    assert "start_simulation" in str(result.get("message", ""))


def test_llm_controller_history_and_audit(tmp_path):
    store = llm_agent.LlmProfileStore(path=tmp_path / "profiles.json")
    store.save_profile(
        {
            "name": "local",
            "base_url": "http://127.0.0.1:8000",
            "api_key": "abc123",
            "model": "x",
            "protocol": "chat",
            "set_active": True,
        }
    )
    controller = llm_agent.LlmController(sim=_FakeSim(), profile_store=store)
    controller._append_audit({"id": 1})  # intentionally using internal append for minimal coverage
    rows = controller.audit(limit=10)["rows"]
    assert isinstance(rows, list)


def test_run_once_skips_code_evolve_when_not_allowed(tmp_path):
    class _FakeClient:
        def call(self, *, profile, messages):
            return {
                "text": '{"analysis":"ok","actions":[{"type":"code_evolve","title":"evolve","payload":{"commands":["echo hi"]}}]}',
                "raw": {},
                "protocol_used": "chat",
            }

    store = llm_agent.LlmProfileStore(path=tmp_path / "profiles.json")
    store.save_profile(
        {
            "name": "local",
            "base_url": "http://127.0.0.1:8000",
            "api_key": "abc123",
            "model": "x",
            "protocol": "chat",
            "set_active": True,
        }
    )
    controller = llm_agent.LlmController(sim=_FakeSim(), profile_store=store, client=_FakeClient())
    result = controller.run_once(
        {
            "objective": "do evolve",
            "auto_execute": True,
            "allow_code_evolve": False,
        }
    )
    assert result["ok"] is True
    assert result["chat"]["actions"][0]["type"] == "code_evolve"
    assert result["executed"][0]["result"]["ok"] is False
    assert "allow_code_evolve=false" in result["executed"][0]["result"]["message"]
