"""LLM controller for chat-based interaction with simulation.

This module provides the LlmController class for:
- Managing LLM chat interactions
- Executing console, shell, and code evolution actions
- Integrating with SimulationController for simulation control
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import threading
from typing import Any
import uuid

from .client import OpenAICompatClient
from .profile_store import LlmProfileStore


def _now_iso() -> str:
    """Return current UTC datetime in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


FORBIDDEN_COMMAND_PATTERNS = [
    "rm -rf",
    "git reset --hard",
    "git checkout --",
    "mkfs",
    "shutdown",
    "reboot",
    ":(){",
]

ALLOWED_COMMAND_PREFIXES = [
    "ros2 ",
    "colcon ",
    "pytest ",
    "python3 -m pytest",
    "python3 ",
    "git ",
    "ls",
    "cat ",
    "rg ",
    "grep ",
    "sed ",
    "awk ",
    "head ",
    "tail ",
    "echo ",
    "timeout ",
    "cd ",
]

SYSTEM_PROMPT = """你是 H2Track 仓库仿真系统的 AI 运维与策略助手。
你必须输出 JSON，不要输出额外文本，格式如下：
{
  "analysis": "中文结论，简明扼要",
  "actions": [
    {
      "type": "console_action|shell_command|code_evolve",
      "title": "动作标题",
      "reason": "执行理由",
      "risk_level": "low|medium|high",
      "requires_confirm": true,
      "payload": {}
    }
  ]
}
启动/停止/刷新仿真优先使用 console_action（start_simulation/stop_simulation/refresh_status），不要生成 ./scripts/launch_sim.sh 这类旧脚本命令。
如果不建议执行动作，actions 返回空数组。"""


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from text.

    Handles:
    - Plain JSON objects
    - JSON fenced in ```json ... ```
    - JSON objects embedded in text

    Args:
        text: The text to parse.

    Returns:
        The extracted JSON object, or None if not found.
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("{") and raw.endswith("}"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw, re.IGNORECASE)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    brace = re.search(r"(\{[\s\S]*\})", raw)
    if brace:
        candidate = brace.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


class LlmController:
    """Controller for LLM-based chat and action execution.

    This class integrates:
    - LlmProfileStore for managing API configurations
    - OpenAICompatClient for making API calls
    - SimulationController for simulation management

    It provides:
    - Chat functionality with context awareness
    - Action execution (console_action, shell_command, code_evolve)
    - History and audit logging
    """

    def __init__(
        self,
        *,
        sim: Any,
        profile_store: LlmProfileStore | None = None,
        client: OpenAICompatClient | None = None,
    ) -> None:
        """Initialize the LLM controller.

        Args:
            sim: SimulationController instance for simulation management.
            profile_store: Optional LlmProfileStore for API configurations.
            client: Optional OpenAICompatClient for API calls.
        """
        self._sim = sim
        self._profiles = profile_store or LlmProfileStore()
        self._client = client or OpenAICompatClient()
        self._history: deque[dict[str, Any]] = deque(maxlen=200)
        self._audit: deque[dict[str, Any]] = deque(maxlen=400)
        self._lock = threading.Lock()

    def list_profiles(self) -> dict[str, Any]:
        """List all LLM profiles.

        Returns:
            Dictionary with active_profile_id, profiles list, and path.
        """
        return self._profiles.list_profiles()

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Save or update an LLM profile.

        Args:
            payload: Profile data to save.

        Returns:
            Dictionary with ok=True and the saved profile.
        """
        saved = self._profiles.save_profile(payload)
        return {"ok": True, "profile": saved}

    def activate_profile(self, profile_id: str) -> dict[str, Any]:
        """Activate an LLM profile.

        Args:
            profile_id: ID of the profile to activate.

        Returns:
            Dictionary with ok=True and active_profile_id.
        """
        self._profiles.activate_profile(profile_id)
        return {"ok": True, "active_profile_id": profile_id}

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        """Delete an LLM profile.

        Args:
            profile_id: ID of the profile to delete.

        Returns:
            Dictionary with ok=True.
        """
        self._profiles.delete_profile(profile_id)
        return {"ok": True}

    def check_profile(self, profile_id: str) -> dict[str, Any]:
        """Check if a profile is working by making a test API call.

        Args:
            profile_id: ID of the profile to check.

        Returns:
            Dictionary with ok=True, protocol_used, and preview.
        """
        profile = self._profiles.get_profile(profile_id)
        messages = [
            {"role": "system", "content": "Reply with a single word: OK"},
            {"role": "user", "content": "health check"},
        ]
        result = self._client.call(profile=profile, messages=messages)
        return {
            "ok": True,
            "protocol_used": result.get("protocol_used"),
            "preview": str(result.get("text", "")).strip()[:120],
        }

    def _build_context(self, *, log_limit: int, report_limit: int) -> dict[str, Any]:
        """Build context for LLM prompts.

        Args:
            log_limit: Maximum number of log entries to include.
            report_limit: Maximum number of reports to include.

        Returns:
            Dictionary with status, metrics, logs, and report summaries.
        """
        status = self._sim.status()
        metrics = self._sim.metrics_snapshot(limit=200)
        logs = self._sim.recent_logs(limit=max(1, min(int(log_limit), 3000)))
        reports_dir = Path.cwd() / "artifacts" / "reports"
        report_summaries: list[dict[str, Any]] = []
        if reports_dir.exists():
            json_files = sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in json_files[: max(1, min(int(report_limit), 10))]:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    report_summaries.append(
                        {
                            "path": str(p),
                            "scene": data.get("scene"),
                            "exported_at": data.get("exported_at"),
                            "state": (data.get("status") or {}).get("state"),
                            "phase": ((data.get("metrics") or {}).get("phase") or {}).get("current"),
                            "mode": ((data.get("metrics") or {}).get("mode") or {}).get("current"),
                            "gas": ((data.get("metrics") or {}).get("gas") or {}).get("current"),
                            "source_found": ((data.get("metrics") or {}).get("source_found") or {}).get("current"),
                        }
                    )
                except Exception:
                    continue
        return {
            "status": status,
            "metrics": metrics,
            "recent_logs": logs,
            "recent_report_summaries": report_summaries,
        }

    def _normalize_actions(self, actions: Any) -> list[dict[str, Any]]:
        """Normalize and validate action list.

        Args:
            actions: Raw actions from LLM response.

        Returns:
            List of validated action dictionaries.
        """
        if not isinstance(actions, list):
            return []
        out: list[dict[str, Any]] = []
        for row in actions:
            if not isinstance(row, dict):
                continue
            action_type = str(row.get("type") or "").strip().lower()
            if action_type not in {"console_action", "shell_command", "code_evolve"}:
                continue
            out.append(
                {
                    "type": action_type,
                    "title": str(row.get("title") or action_type),
                    "reason": str(row.get("reason") or ""),
                    "risk_level": str(row.get("risk_level") or "medium"),
                    "requires_confirm": bool(row.get("requires_confirm", True)),
                    "payload": row.get("payload") if isinstance(row.get("payload"), dict) else {},
                }
            )
        return out

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a chat message to the LLM.

        Args:
            payload: Chat payload containing:
                - profile_id: Optional profile ID to use.
                - message: The user message.
                - include_context: Whether to include simulation context.
                - log_limit: Max log entries in context.
                - report_limit: Max reports in context.

        Returns:
            Dictionary with ok=True, analysis, actions, and metadata.
        """
        profile_id = str(payload.get("profile_id") or "").strip() or None
        profile = self._profiles.get_profile(profile_id)
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")
        include_context = bool(payload.get("include_context", True))
        log_limit = int(payload.get("log_limit") or 1000)
        report_limit = int(payload.get("report_limit") or 3)
        context = self._build_context(log_limit=log_limit, report_limit=report_limit) if include_context else {}

        user_content = {
            "user_message": message,
            "context": context,
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ]
        model_result = self._client.call(profile=profile, messages=messages)
        text = str(model_result.get("text") or "")
        parsed = _extract_json_block(text) or {}
        analysis = str(parsed.get("analysis") or text or "").strip()
        actions = self._normalize_actions(parsed.get("actions"))
        out = {
            "ok": True,
            "analysis": analysis,
            "actions": actions,
            "protocol_used": model_result.get("protocol_used"),
            "profile_id": profile.get("id"),
            "model": profile.get("model"),
            "timestamp": _now_iso(),
        }
        with self._lock:
            self._history.append(
                {
                    "timestamp": out["timestamp"],
                    "profile_id": profile.get("id"),
                    "model": profile.get("model"),
                    "message": message,
                    "analysis": analysis,
                    "actions": actions,
                }
            )
        return out

    def _append_audit(self, entry: dict[str, Any]) -> None:
        """Append an entry to the audit log.

        Args:
            entry: The audit entry to append.
        """
        with self._lock:
            self._audit.append(entry)

    def _command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if a command is allowed by policy.

        Args:
            command: The command to check.

        Returns:
            Tuple of (allowed, reason).
        """
        text = str(command or "").strip()
        if not text:
            return False, "empty command"
        lowered = text.lower()
        for token in FORBIDDEN_COMMAND_PATTERNS:
            if token in lowered:
                return False, f"forbidden pattern: {token}"
        if not any(lowered.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES):
            return False, "command not allowed by policy"
        return True, ""

    def _execute_console_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a console action.

        Args:
            payload: Action payload with action type and parameters.

        Returns:
            Dictionary with ok and message or result.
        """
        action = str(payload.get("action") or "").strip().lower()
        if action == "start_simulation":
            ok, msg = self._sim.start_with_profile(payload.get("launch_profile"))
            return {"ok": ok, "message": msg}
        if action == "stop_simulation":
            ok, msg = self._sim.stop()
            return {"ok": ok, "message": msg}
        if action == "refresh_status":
            return {"ok": True, "status": self._sim.status()}
        if action == "export_diagnostics":
            scene = str(payload.get("scene") or self._sim.status().get("launch_profile", {}).get("scene", "warehouse"))
            path = self._sim.export_diagnostics(scene=scene)
            return {"ok": True, "path": path}
        if action == "export_run_report":
            scene = str(payload.get("scene") or self._sim.status().get("launch_profile", {}).get("scene", "warehouse"))
            artifact = self._sim.export_run_report(scene=scene)
            return {"ok": True, **artifact}
        return {"ok": False, "message": f"unsupported console action: {action}"}

    def _coerce_profile_token(self, value: Any, *, default: str) -> str:
        """Coerce a profile token value.

        Args:
            value: The value to coerce.
            default: Default value if not recognized.

        Returns:
            Coerced string value.
        """
        text = str(value or "").strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return "true"
        if text in {"false", "0", "no", "off"}:
            return "false"
        if text in {"warehouse", "baseline"}:
            return text
        return default

    def _translate_legacy_launch_script(self, command: str) -> dict[str, Any] | None:
        """Translate a legacy launch_sim.sh command to console action.

        Args:
            command: The shell command to translate.

        Returns:
            Translated action payload, or None if not a launch script command.
        """
        if "launch_sim.sh" not in command:
            return None
        try:
            tokens = shlex.split(command)
        except ValueError:
            return None
        launch_idx = -1
        for idx, token in enumerate(tokens):
            if token.endswith("launch_sim.sh"):
                launch_idx = idx
                break
        if launch_idx < 0:
            return None

        default_profile = {
            "scene": "warehouse",
            "use_gaden": "true",
            "use_slam": "true",
            "use_rviz": "true",
            "headless": "false",
        }
        try:
            status = self._sim.status()
            launch_profile = status.get("launch_profile") if isinstance(status, dict) else None
            if isinstance(launch_profile, dict):
                default_profile["scene"] = self._coerce_profile_token(launch_profile.get("scene"), default="warehouse")
                default_profile["use_gaden"] = self._coerce_profile_token(launch_profile.get("use_gaden"), default="true")
                default_profile["use_slam"] = self._coerce_profile_token(launch_profile.get("use_slam"), default="true")
                default_profile["use_rviz"] = self._coerce_profile_token(launch_profile.get("use_rviz"), default="true")
                default_profile["headless"] = self._coerce_profile_token(launch_profile.get("headless"), default="false")
        except Exception:
            pass

        args = tokens[launch_idx + 1 :]
        profile = dict(default_profile)
        i = 0
        while i < len(args):
            arg = args[i]
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if arg == "--scene" and nxt:
                profile["scene"] = self._coerce_profile_token(nxt, default=profile["scene"])
                i += 2
                continue
            if arg == "--gaden":
                profile["use_gaden"] = "true"
            elif arg == "--no-gaden":
                profile["use_gaden"] = "false"
            elif arg == "--slam":
                profile["use_slam"] = "true"
            elif arg == "--no-slam":
                profile["use_slam"] = "false"
            elif arg == "--rviz":
                profile["use_rviz"] = "true"
            elif arg == "--no-rviz":
                profile["use_rviz"] = "false"
            elif arg == "--headless":
                profile["headless"] = "true"
            elif arg == "--no-headless":
                profile["headless"] = "false"
            i += 1

        return {"action": "start_simulation", "launch_profile": profile}

    def _execute_shell_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a shell command.

        Args:
            payload: Command payload with command string.

        Returns:
            Dictionary with ok, returncode, stdout, stderr, and message.
        """
        command = str(payload.get("command") or "").strip()
        translated_payload = self._translate_legacy_launch_script(command)
        if translated_payload is not None:
            translated_result = dict(self._execute_console_action(translated_payload))
            translated_result["translated_from_shell_command"] = True
            translated_result["original_command"] = command
            if translated_result.get("ok"):
                translated_result["message"] = (
                    f"translated shell_command -> console_action start_simulation: "
                    f"{translated_result.get('message') or 'started'}"
                )
            return translated_result

        allowed, reason = self._command_allowed(command)
        if not allowed:
            return {"ok": False, "message": reason}
        timeout_sec = float(payload.get("timeout_sec") or 120.0)
        proc = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(Path.cwd()),
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_sec),
        )
        stderr_tail = (proc.stderr or "").strip().splitlines()
        stdout_tail = (proc.stdout or "").strip().splitlines()
        detail = ""
        if stderr_tail:
            detail = stderr_tail[-1]
        elif stdout_tail:
            detail = stdout_tail[-1]
        if not detail:
            detail = "no output"
        summary = (
            f"command succeeded (exit 0): {detail}"
            if proc.returncode == 0
            else f"command failed (exit {proc.returncode}): {detail}"
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-6000:],
            "stderr": (proc.stderr or "")[-6000:],
            "message": summary[:400],
        }

    def _run_shell(self, cmd: str, *, cwd: Path, timeout_sec: float) -> dict[str, Any]:
        """Run a shell command and return the result.

        Args:
            cmd: The command to run.
            cwd: Working directory.
            timeout_sec: Timeout in seconds.

        Returns:
            Dictionary with ok, returncode, stdout, stderr, and cmd.
        """
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_sec),
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-12000:],
            "stderr": (proc.stderr or "")[-12000:],
            "cmd": cmd,
        }

    def _execute_code_evolve(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a code evolution action.

        Creates a git worktree, applies patches or runs commands,
        verifies the changes, and optionally commits and pushes.

        Args:
            payload: Code evolution payload with:
                - topic: Topic name for the branch.
                - branch: Optional branch name.
                - patch: Optional git patch to apply.
                - commands: Optional list of commands to run.
                - verify_commands: Commands to verify changes.
                - commit_message: Commit message.
                - auto_push: Whether to push automatically.
                - timeout_sec: Timeout for operations.

        Returns:
            Dictionary with ok, branch, commit, worktree, and logs.
        """
        repo_root = Path.cwd()
        git_root_cmd = self._run_shell("git rev-parse --show-toplevel", cwd=repo_root, timeout_sec=20)
        if not git_root_cmd["ok"]:
            return {"ok": False, "message": "not a git repository", "detail": git_root_cmd}
        git_root = Path(str(git_root_cmd["stdout"]).strip())

        topic = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(payload.get("topic") or "auto-evolve")).strip("-").lower()
        if not topic:
            topic = "auto-evolve"
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch = str(payload.get("branch") or f"ai/{stamp}-{topic}")

        temp_root = Path("/tmp") / f"h2track_ai_evolve_{stamp}_{uuid.uuid4().hex[:8]}"
        worktree = temp_root
        timeout_sec = float(payload.get("timeout_sec") or 600.0)
        patch_text = str(payload.get("patch") or "")
        commands = payload.get("commands")
        if commands is None:
            commands = []
        if not isinstance(commands, list):
            return {"ok": False, "message": "commands must be a list"}
        commands = [str(c).strip() for c in commands if str(c).strip()]
        if not patch_text and not commands:
            return {"ok": False, "message": "code_evolve requires patch or commands"}

        for cmd in commands:
            allowed, reason = self._command_allowed(cmd)
            if not allowed:
                return {"ok": False, "message": f"code_evolve command denied: {reason}", "command": cmd}

        verify_commands = payload.get("verify_commands")
        if verify_commands is None:
            verify_commands = [
                "source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && "
                "PYTHONPATH=$PWD/src/h2track_tracking:$PYTHONPATH python3 -m pytest -q src/h2track_tracking/test src/h2track_sim/test",
                "source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && "
                "colcon build --packages-select h2track_tracking h2track_sim",
            ]
        if not isinstance(verify_commands, list):
            return {"ok": False, "message": "verify_commands must be a list"}
        verify_commands = [str(c).strip() for c in verify_commands if str(c).strip()]

        commit_message = str(payload.get("commit_message") or f"chore(ai): evolve {topic}")
        auto_push = bool(payload.get("auto_push", False))
        logs: list[dict[str, Any]] = []

        try:
            add_out = self._run_shell(
                f"git worktree add -b {shlex.quote(branch)} {shlex.quote(str(worktree))} HEAD",
                cwd=git_root,
                timeout_sec=60.0,
            )
            logs.append({"step": "worktree_add", **add_out})
            if not add_out["ok"]:
                return {"ok": False, "message": "failed to create worktree", "logs": logs}

            if patch_text:
                apply_proc = subprocess.run(
                    ["bash", "-lc", "git apply --whitespace=fix -"],
                    cwd=str(worktree),
                    check=False,
                    capture_output=True,
                    text=True,
                    input=patch_text,
                    timeout=max(1.0, timeout_sec),
                )
                patch_out = {
                    "ok": apply_proc.returncode == 0,
                    "returncode": apply_proc.returncode,
                    "stdout": (apply_proc.stdout or "")[-12000:],
                    "stderr": (apply_proc.stderr or "")[-12000:],
                    "cmd": "git apply --whitespace=fix -",
                }
                logs.append({"step": "apply_patch", **patch_out})
                if not patch_out["ok"]:
                    return {"ok": False, "message": "failed to apply patch", "logs": logs}

            for cmd in commands:
                out = self._run_shell(cmd, cwd=worktree, timeout_sec=timeout_sec)
                logs.append({"step": "user_command", **out})
                if not out["ok"]:
                    return {"ok": False, "message": "code_evolve command failed", "logs": logs}

            for cmd in verify_commands:
                out = self._run_shell(cmd, cwd=worktree, timeout_sec=timeout_sec)
                logs.append({"step": "verify", **out})
                if not out["ok"]:
                    return {"ok": False, "message": "verification failed", "logs": logs}

            status_out = self._run_shell("git status --porcelain", cwd=worktree, timeout_sec=20.0)
            logs.append({"step": "git_status", **status_out})
            if not status_out["ok"]:
                return {"ok": False, "message": "git status failed", "logs": logs}
            if not str(status_out["stdout"]).strip():
                return {"ok": False, "message": "no code changes to commit", "logs": logs}

            add_all = self._run_shell("git add -A", cwd=worktree, timeout_sec=30.0)
            logs.append({"step": "git_add", **add_all})
            if not add_all["ok"]:
                return {"ok": False, "message": "git add failed", "logs": logs}

            commit_out = self._run_shell(f"git commit -m {shlex.quote(commit_message)}", cwd=worktree, timeout_sec=60.0)
            logs.append({"step": "git_commit", **commit_out})
            if not commit_out["ok"]:
                return {"ok": False, "message": "git commit failed", "logs": logs}

            rev_out = self._run_shell("git rev-parse --short HEAD", cwd=worktree, timeout_sec=20.0)
            logs.append({"step": "git_rev_parse", **rev_out})
            commit = str(rev_out["stdout"]).strip() if rev_out["ok"] else ""

            if auto_push:
                push_out = self._run_shell(f"git push -u origin {shlex.quote(branch)}", cwd=worktree, timeout_sec=120.0)
                logs.append({"step": "git_push", **push_out})
                if not push_out["ok"]:
                    return {"ok": False, "message": "git push failed", "logs": logs, "branch": branch, "commit": commit}

            return {
                "ok": True,
                "branch": branch,
                "commit": commit,
                "worktree": str(worktree),
                "logs": logs,
            }
        finally:
            try:
                self._run_shell(f"git -C {shlex.quote(str(git_root))} worktree remove --force {shlex.quote(str(worktree))}", cwd=git_root, timeout_sec=30.0)
            except Exception:
                pass
            if worktree.exists():
                try:
                    shutil.rmtree(worktree, ignore_errors=True)
                except Exception:
                    pass

    def execute_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute an action from the LLM response.

        Args:
            action: Action dictionary with type, payload, title, risk_level.

        Returns:
            Result dictionary with ok and message or result data.
        """
        action_type = str(action.get("type") or "").strip().lower()
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        title = str(action.get("title") or action_type)
        risk_level = str(action.get("risk_level") or "medium")
        started_at = _now_iso()
        if action_type == "console_action":
            result = self._execute_console_action(payload)
        elif action_type == "shell_command":
            result = self._execute_shell_command(payload)
        elif action_type == "code_evolve":
            result = self._execute_code_evolve(payload)
        else:
            result = {"ok": False, "message": f"unsupported action type: {action_type}"}
        self._append_audit(
            {
                "timestamp": started_at,
                "title": title,
                "type": action_type,
                "risk_level": risk_level,
                "payload": payload,
                "result": result,
            }
        )
        return result

    def run_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a single LLM interaction and optionally execute actions.

        Args:
            payload: Run payload with:
                - objective: The objective for the LLM.
                - auto_execute: Whether to execute actions automatically.
                - allow_code_evolve: Whether to allow code_evolve actions.
                - profile_id: Optional profile ID.
                - include_context: Whether to include context.
                - log_limit: Max log entries.
                - report_limit: Max reports.

        Returns:
            Dictionary with ok, chat result, and executed actions.
        """
        objective = str(payload.get("objective") or "分析当前系统并给出可执行优化动作").strip()
        auto_execute = bool(payload.get("auto_execute", True))
        allow_code_evolve = bool(payload.get("allow_code_evolve", False))
        chat_result = self.chat(
            {
                "profile_id": payload.get("profile_id"),
                "message": objective,
                "include_context": bool(payload.get("include_context", True)),
                "log_limit": int(payload.get("log_limit") or 1000),
                "report_limit": int(payload.get("report_limit") or 3),
            }
        )
        executed: list[dict[str, Any]] = []
        if auto_execute:
            for act in chat_result.get("actions", []):
                if act.get("type") == "code_evolve" and not allow_code_evolve:
                    executed.append(
                        {
                            "action": act,
                            "result": {
                                "ok": False,
                                "message": "code_evolve skipped: allow_code_evolve=false",
                            },
                        }
                    )
                    continue
                executed.append({"action": act, "result": self.execute_action(act)})
        return {"ok": True, "chat": chat_result, "executed": executed}

    def history(self, limit: int = 50) -> dict[str, Any]:
        """Get chat history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            Dictionary with rows list.
        """
        with self._lock:
            rows = list(self._history)[-max(1, min(limit, 500)) :]
        return {"rows": rows}

    def audit(self, limit: int = 100) -> dict[str, Any]:
        """Get audit log.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            Dictionary with rows list.
        """
        with self._lock:
            rows = list(self._audit)[-max(1, min(limit, 1000)) :]
        return {"rows": rows}
