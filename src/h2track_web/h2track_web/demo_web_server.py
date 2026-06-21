"""Web control console for one-click warehouse simulation startup and live logs.

This module serves as a backwards-compatible entry point that re-exports
all symbols from the web package. New code should import from h2track_tracking.web
directly.
"""

from __future__ import annotations

# Re-export all symbols from the web package for backwards compatibility
from .web import (
    # App exports
    STATIC_CONSOLE_DIRNAME,
    UI_MODE_LEGACY,
    UI_MODE_STATIC,
    create_app,
    main,
    _resolve_static_console_dir,
    _resolve_static_index_html,
    _resolve_ui_meta,
    # Config exports
    DEFAULT_LAUNCH_PROFILE,
    build_demo_launch_command,
    build_demo_prep_command,
    normalize_launch_profile,
    # MetricsStore exports
    CONCENTRATION_RE,
    MODE_TRANSITION_RE,
    NAV_BEGIN_RE,
    MetricsStore,
    summarize_gas_signal,
    # Routes exports
    FASTAPI_AVAILABLE,
    # SimulationController exports
    CommandResult,
    SimulationController,
    load_scene_thresholds,
    _candidate_scene_yaml_paths,
    # Templates exports
    HTML_PAGE,
    build_run_report_markdown,
    # TopicCollector exports
    TopicMetricsCollector,
)

__all__ = [
    # App
    "STATIC_CONSOLE_DIRNAME",
    "UI_MODE_LEGACY",
    "UI_MODE_STATIC",
    "create_app",
    "main",
    "_resolve_static_console_dir",
    "_resolve_static_index_html",
    "_resolve_ui_meta",
    # Config
    "DEFAULT_LAUNCH_PROFILE",
    "build_demo_launch_command",
    "build_demo_prep_command",
    "normalize_launch_profile",
    # MetricsStore
    "CONCENTRATION_RE",
    "MODE_TRANSITION_RE",
    "NAV_BEGIN_RE",
    "MetricsStore",
    "summarize_gas_signal",
    # Routes
    "FASTAPI_AVAILABLE",
    # SimulationController
    "CommandResult",
    "SimulationController",
    "load_scene_thresholds",
    "_candidate_scene_yaml_paths",
    # Templates
    "HTML_PAGE",
    "build_run_report_markdown",
    # TopicCollector
    "TopicMetricsCollector",
]


if __name__ == "__main__":
    raise SystemExit(main())
