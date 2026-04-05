"""FastAPI route definitions for the web console.

This module contains all FastAPI route handlers extracted from demo_web_server.py.
Each route delegates to SimulationController, LlmController, or MetricsStore.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .auth import get_auth_dependency, settings as auth_settings

try:
    from fastapi import HTTPException, Query, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False
    HTTPException = None  # type: ignore[misc,assignment]
    Query = None  # type: ignore[misc,assignment]
    Request = None  # type: ignore[misc,assignment]
    FileResponse = None  # type: ignore[misc,assignment]
    HTMLResponse = None  # type: ignore[misc,assignment]
    JSONResponse = None  # type: ignore[misc,assignment]
    StreamingResponse = None  # type: ignore[misc,assignment]


# Type alias for Request that works when FastAPI is not available
RequestType = Request if FASTAPI_AVAILABLE else Any  # type: ignore[misc]


async def _read_json_dict(request: "RequestType") -> dict[str, Any]:
    """Read and validate JSON dict from request body.

    Args:
        request: FastAPI Request object.

    Returns:
        Parsed JSON dictionary, or empty dict if invalid.

    Raises:
        HTTPException: If JSON is invalid or not a dict.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return {}
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON payload: {exc}") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    return body


def register_routes(
    app: Any,
    *,
    sim: Any,
    llm: Any,
    ui_meta: dict[str, Any],
    resolve_static_index_html: Any,
    html_page: str,
) -> None:
    """Register all FastAPI routes on the given app.

    Args:
        app: FastAPI application instance.
        sim: SimulationController instance.
        llm: LlmController instance.
        ui_meta: UI metadata dict with mode, bundle_ready, bundle_path.
        resolve_static_index_html: Function to resolve static index.html path.
        html_page: HTML content for legacy inline mode.
    """
    # Get auth dependency - None if auth disabled or FastAPI unavailable
    auth_dep = get_auth_dependency()

    @app.get("/", response_class=HTMLResponse)
    def index() -> Any:
        """Root endpoint - serve static bundle or legacy HTML."""
        index_path = resolve_static_index_html()
        if index_path is not None:
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(content=html_page)

    @app.get("/api/ui/meta")
    def get_ui_meta() -> Any:
        """Get UI mode metadata (static bundle vs legacy inline)."""
        return JSONResponse(content=ui_meta)

    @app.post("/api/sim/start")
    async def start_sim(request: "RequestType", _auth: str = auth_dep) -> Any:  # type: ignore[valid-type]
        """Start simulation with optional launch profile."""
        payload = await _read_json_dict(request)
        ok, message = sim.start_with_profile(payload)
        if not ok:
            raise HTTPException(status_code=409, detail=message)
        return JSONResponse(status_code=202, content={"ok": True, "message": message})

    @app.post("/api/sim/stop")
    def stop_sim(_auth: str = auth_dep) -> Any:
        """Stop running simulation."""
        ok, message = sim.stop()
        if not ok:
            raise HTTPException(status_code=409, detail=message)
        return JSONResponse(status_code=202, content={"ok": True, "message": message})

    @app.get("/api/sim/status")
    def get_status() -> Any:
        """Get current simulation status."""
        return JSONResponse(content=sim.status())

    @app.get("/api/logs/recent")
    def get_recent(limit: int = Query(default=200, ge=1, le=2000)) -> Any:  # type: ignore[valid-type]
        """Get recent log entries."""
        logs = sim.recent_logs(limit=limit)
        return JSONResponse(content={"logs": logs, "latest_id": sim.status()["latest_log_id"]})

    @app.get("/api/metrics/recent")
    def get_metrics_recent(limit: int = Query(default=120, ge=1, le=2000)) -> Any:  # type: ignore[valid-type]
        """Get recent metrics snapshot."""
        sim.refresh_metrics_from_topics_if_needed()
        sim.refresh_runtime_health_if_needed()
        return JSONResponse(content=sim.metrics_snapshot(limit=limit))

    @app.get("/api/health/nodes")
    def get_nodes_health() -> Any:
        """Get node health status."""
        sim.refresh_runtime_health_if_needed()
        payload = sim.metrics_snapshot(limit=1).get("node_health", {})
        return JSONResponse(content=payload)

    @app.post("/api/diag/export")
    def export_diag() -> Any:
        """Export diagnostics to zip file."""
        try:
            path = sim.export_diagnostics(scene="warehouse")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"diagnostic export failed: {exc}") from exc
        return JSONResponse(status_code=202, content={"ok": True, "path": path})

    @app.post("/api/report/export")
    def export_report() -> Any:
        """Export run report as JSON and Markdown."""
        try:
            status_payload = sim.status()
            profile = status_payload.get("launch_profile", {}) if isinstance(status_payload, dict) else {}
            scene = str(profile.get("scene", "warehouse"))
            artifacts = sim.export_run_report(scene=scene)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"run report export failed: {exc}") from exc
        return JSONResponse(status_code=202, content={"ok": True, **artifacts})

    @app.get("/api/llm/profiles")
    def get_llm_profiles() -> Any:
        """List all LLM profiles."""
        try:
            payload = llm.list_profiles()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"list profiles failed: {exc}") from exc
        return JSONResponse(content=payload)

    @app.post("/api/llm/profiles")
    async def save_llm_profile(request: "RequestType") -> Any:  # type: ignore[valid-type]
        """Save or update an LLM profile."""
        payload = await _read_json_dict(request)
        try:
            result = llm.save_profile(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"save profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/profiles/{profile_id}/activate")
    def activate_llm_profile(profile_id: str) -> Any:
        """Activate an LLM profile by ID."""
        try:
            result = llm.activate_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"activate profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/profiles/{profile_id}/check")
    def check_llm_profile(profile_id: str) -> Any:
        """Check connectivity for an LLM profile."""
        try:
            result = llm.check_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"profile check failed: {exc}") from exc
        return JSONResponse(content=result)

    @app.delete("/api/llm/profiles/{profile_id}")
    def delete_llm_profile(profile_id: str) -> Any:
        """Delete an LLM profile by ID."""
        try:
            result = llm.delete_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"delete profile failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.post("/api/llm/chat")
    async def llm_chat(request: "RequestType", _auth: str = auth_dep) -> Any:  # type: ignore[valid-type]
        """Send a chat message to the LLM."""
        payload = await _read_json_dict(request)
        try:
            result = llm.chat(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"llm chat failed: {exc}") from exc
        return JSONResponse(content=result)

    @app.post("/api/llm/action/execute")
    async def execute_llm_action(request: "RequestType") -> Any:  # type: ignore[valid-type]
        """Execute an LLM-suggested action."""
        payload = await _read_json_dict(request)
        action = payload.get("action")
        if not isinstance(action, dict):
            raise HTTPException(status_code=400, detail="action object is required")
        try:
            result = llm.execute_action(action)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"execute action failed: {exc}") from exc
        status_code = 202 if result.get("ok") else 409
        return JSONResponse(status_code=status_code, content=result)

    @app.post("/api/llm/loop/run-once")
    async def llm_loop_run_once(request: "RequestType") -> Any:  # type: ignore[valid-type]
        """Run a single LLM autonomous loop iteration."""
        payload = await _read_json_dict(request)
        try:
            result = llm.run_once(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"run-once failed: {exc}") from exc
        return JSONResponse(status_code=202, content=result)

    @app.get("/api/llm/history")
    def llm_history(limit: int = Query(default=50, ge=1, le=500)) -> Any:  # type: ignore[valid-type]
        """Get LLM chat history."""
        return JSONResponse(content=llm.history(limit=limit))

    @app.get("/api/llm/audit")
    def llm_audit(limit: int = Query(default=100, ge=1, le=1000)) -> Any:  # type: ignore[valid-type]
        """Get LLM action audit log."""
        return JSONResponse(content=llm.audit(limit=limit))

    @app.get("/api/logs/stream")
    async def stream_logs(request: "RequestType", after_id: int = Query(default=0, ge=0)) -> Any:  # type: ignore[valid-type]
        """Stream logs via Server-Sent Events."""

        async def _events() -> Any:
            cursor = after_id
            while True:
                if await request.is_disconnected():
                    break
                new_entries = sim.logs_after(cursor)
                if new_entries:
                    for entry in new_entries:
                        cursor = int(entry["id"])
                        payload = json.dumps(entry, ensure_ascii=False)
                        yield f"id: {cursor}\nevent: log\ndata: {payload}\n\n"
                else:
                    yield "event: ping\ndata: {}\n\n"
                    await asyncio.sleep(1.0)

        return StreamingResponse(_events(), media_type="text/event-stream")
