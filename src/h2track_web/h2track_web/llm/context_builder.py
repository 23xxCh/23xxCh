"""Context building for LLM prompts.

This module provides functions for building context from simulation state,
metrics, logs, and reports for LLM prompts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_context(
    *,
    sim: Any,
    log_limit: int,
    report_limit: int,
) -> dict[str, Any]:
    """Build context for LLM prompts.

    Args:
        sim: SimulationController instance.
        log_limit: Maximum number of log entries to include.
        report_limit: Maximum number of reports to include.

    Returns:
        Dictionary with status, metrics, logs, and report summaries.
    """
    status = sim.status()
    metrics = sim.metrics_snapshot(limit=200)
    logs = sim.recent_logs(limit=max(1, min(int(log_limit), 3000)))
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
