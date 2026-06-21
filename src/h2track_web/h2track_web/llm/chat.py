"""Chat utilities for LLM controller.

This module provides:
- JSON extraction from LLM responses
- Action normalization and validation
- System prompt for the H2Track AI assistant
"""

from __future__ import annotations

import json
import re
from typing import Any


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


def extract_json_block(text: str) -> dict[str, Any] | None:
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


def normalize_actions(actions: Any) -> list[dict[str, Any]]:
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
