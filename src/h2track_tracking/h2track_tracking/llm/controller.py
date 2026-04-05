"""LLM controller for chat-based interaction with simulation.

This module provides the LlmController class for:
- Managing LLM chat interactions
- Executing console, shell, and code evolution actions
- Integrating with SimulationController for simulation control
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
from typing import Any

from .actions import (
    ALLOWED_COMMAND_PREFIXES,
    FORBIDDEN_COMMAND_PATTERNS,
    command_allowed,
    execute_code_evolve,
    execute_console_action,
    execute_shell_command,
)
from .chat import SYSTEM_PROMPT, extract_json_block, normalize_actions
from .client import OpenAICompatClient
from .context_builder import build_context
from .profile_store import LlmProfileStore


def _now_iso() -> str:
    """Return current UTC datetime in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


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
        import json

        profile_id = str(payload.get("profile_id") or "").strip() or None
        profile = self._profiles.get_profile(profile_id)
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")
        include_context = bool(payload.get("include_context", True))
        log_limit = int(payload.get("log_limit") or 1000)
        report_limit = int(payload.get("report_limit") or 3)
        context = (
            build_context(sim=self._sim, log_limit=log_limit, report_limit=report_limit)
            if include_context
            else {}
        )

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
        parsed = extract_json_block(text) or {}
        analysis = str(parsed.get("analysis") or text or "").strip()
        actions = normalize_actions(parsed.get("actions"))
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
        return command_allowed(command)

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
            result = execute_console_action(payload, sim=self._sim)
        elif action_type == "shell_command":
            result = execute_shell_command(payload, sim=self._sim)
        elif action_type == "code_evolve":
            result = execute_code_evolve(payload)
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
