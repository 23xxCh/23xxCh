"""FastAPI application factory for the web console.

This module provides the create_app() factory function and main() entry point
for running the H2Track web console server.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .config import DEFAULT_LAUNCH_PROFILE
from .metrics_store import MetricsStore
from .routes import FASTAPI_AVAILABLE, WEBSOCKET_AVAILABLE, register_routes
from .simulation_controller import SimulationController
from .templates import HTML_PAGE
from .topic_collector import TopicMetricsCollector


STATIC_CONSOLE_DIRNAME = "static_console"
UI_MODE_STATIC = "static_bundle"
UI_MODE_LEGACY = "legacy_inline"


def _resolve_static_console_dir() -> Path | None:
    """Resolve the static console bundle directory.

    Checks both module directory and ROS package share directory.

    Returns:
        Path to static_console directory, or None if not found.
    """
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / STATIC_CONSOLE_DIRNAME]
    try:
        from ament_index_python.packages import get_package_share_directory

        candidates.append(
            Path(get_package_share_directory("h2track_tracking")) / STATIC_CONSOLE_DIRNAME
        )
    except Exception:
        pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _resolve_static_index_html() -> Path | None:
    """Resolve the static index.html file.

    Returns:
        Path to index.html, or None if not found.
    """
    static_dir = _resolve_static_console_dir()
    if static_dir is None:
        return None
    index_path = static_dir / "index.html"
    if index_path.exists() and index_path.is_file():
        return index_path
    return None


def _resolve_ui_meta() -> dict[str, Any]:
    """Resolve UI mode metadata.

    Returns:
        Dict with mode, bundle_ready, and bundle_path keys.
    """
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


def create_app(
    controller: SimulationController | None = None,
    llm_controller: Any | None = None,
    *,
    start_topic_collector: bool = False,
) -> Any:
    """Create a FastAPI application instance.

    This is the main factory function for creating the web console app.
    It sets up routes, static file serving, and lifecycle hooks.

    Args:
        controller: Optional SimulationController instance. If not provided,
            a new one will be created.
        llm_controller: Optional LlmController instance. If not provided,
            a new one will be created using the controller.
        start_topic_collector: If True, start the topic collector on startup.

    Returns:
        FastAPI application instance.

    Raises:
        RuntimeError: If FastAPI is not available.
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is not available. Install fastapi and uvicorn first.")

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from ..llm_agent import LlmController
    from .websocket import ConnectionManager

    app = FastAPI(title="H2Track Web Console")
    sim = controller or SimulationController()
    llm = llm_controller or LlmController(sim=sim)
    ui_meta = _resolve_ui_meta()
    collector = TopicMetricsCollector(sim._metrics) if start_topic_collector else None

    # Create WebSocket connection manager
    ws_manager = ConnectionManager() if WEBSOCKET_AVAILABLE else None

    # Start collector eagerly so live metrics remain available even if startup hooks are skipped.
    if collector is not None:
        collector.start()

    # Mount static assets if bundle is available
    if bool(ui_meta.get("bundle_ready")):
        static_dir = _resolve_static_console_dir()
        assert static_dir is not None
        assets_dir = static_dir / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Register all routes
    register_routes(
        app,
        sim=sim,
        llm=llm,
        ui_meta=ui_meta,
        resolve_static_index_html=_resolve_static_index_html,
        html_page=HTML_PAGE,
        ws_manager=ws_manager,
    )

    @app.on_event("startup")
    async def _on_startup() -> None:
        """Start topic collector on app startup."""
        if collector is not None:
            collector.start()

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """Stop topic collector on app shutdown."""
        if collector is not None:
            collector.stop()

    return app


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the web console server.

    Args:
        argv: Optional command-line arguments. Defaults to sys.argv.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
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
