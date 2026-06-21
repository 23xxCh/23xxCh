"""Report generation utilities for the web console.

This module contains pure report generation functions with no dependencies on other web modules.
"""

from __future__ import annotations

from typing import Any


def _fmt_bool_cn(value: Any) -> str:
    """Format a boolean value as Chinese text."""
    if isinstance(value, bool):
        return "是" if value else "否"
    return "未知"


def build_run_report_markdown(payload: dict[str, Any]) -> str:
    """Generate a markdown report from run metrics.

    Args:
        payload: Dictionary containing status, metrics, launch_profile, logs, etc.

    Returns:
        Markdown formatted string with the run report.
    """
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
