"""Web console modules for H2Track simulation control."""

from . import app
from .app import (
    STATIC_CONSOLE_DIRNAME,
    UI_MODE_LEGACY,
    UI_MODE_STATIC,
    create_app,
    main,
    _resolve_static_console_dir,
    _resolve_static_index_html,
    _resolve_ui_meta,
)
from .auth import (
    AuthSettings,
    get_auth_dependency,
    settings as auth_settings,
    verify_api_key,
)
from .config import (
    DEMO_PREP_COMMAND,
    DEFAULT_LAUNCH_PROFILE,
    build_demo_launch_command,
    normalize_launch_profile,
)
from .metrics_store import (
    CONCENTRATION_RE,
    MODE_TRANSITION_RE,
    NAV_BEGIN_RE,
    MetricsStore,
    summarize_gas_signal,
)
from .routes import FASTAPI_AVAILABLE, WEBSOCKET_AVAILABLE
from .simulation_controller import (
    CommandResult,
    SimulationController,
    load_scene_thresholds,
    _candidate_scene_yaml_paths,
)
from .templates import HTML_PAGE
from .reports import build_run_report_markdown
from .topic_collector import TopicMetricsCollector
from .websocket import (
    ConnectionManager,
    ClientState,
    parse_client_command,
    websocket_endpoint,
)

__all__ = [
    # app module
    "app",
    # app symbols
    "STATIC_CONSOLE_DIRNAME",
    "UI_MODE_LEGACY",
    "UI_MODE_STATIC",
    "create_app",
    "main",
    "_resolve_static_console_dir",
    "_resolve_static_index_html",
    "_resolve_ui_meta",
    # auth
    "AuthSettings",
    "auth_settings",
    "get_auth_dependency",
    "verify_api_key",
    # config
    "DEMO_PREP_COMMAND",
    "DEFAULT_LAUNCH_PROFILE",
    "build_demo_launch_command",
    "normalize_launch_profile",
    # metrics_store
    "CONCENTRATION_RE",
    "MODE_TRANSITION_RE",
    "NAV_BEGIN_RE",
    "MetricsStore",
    "summarize_gas_signal",
    # routes
    "FASTAPI_AVAILABLE",
    "WEBSOCKET_AVAILABLE",
    # simulation_controller
    "CommandResult",
    "SimulationController",
    "load_scene_thresholds",
    # templates
    "HTML_PAGE",
    "build_run_report_markdown",
    # topic_collector
    "TopicMetricsCollector",
    # websocket
    "ConnectionManager",
    "ClientState",
    "parse_client_command",
    "websocket_endpoint",
]
