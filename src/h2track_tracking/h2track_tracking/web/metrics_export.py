"""Prometheus metrics export for H2Track web console.

This module provides Prometheus-format metrics for external monitoring integration.
All metrics are exposed via the /metrics endpoint.

Metric categories:
- Simulation metrics: state, uptime, scene info
- Navigation metrics: success/failure counts, duration histogram
- Gas tracking: concentration gauge, mode transitions
- LLM metrics: API requests, latency, tokens
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

# Prometheus client is optional - graceful degradation if not installed
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore[misc,assignment]
    Gauge = None  # type: ignore[misc,assignment]
    Histogram = None  # type: ignore[misc,assignment]
    generate_latest = None  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from .metrics_store import MetricsStore


# Metric definitions (created only if prometheus_client is available)
if PROMETHEUS_AVAILABLE:
    # Simulation metrics
    SIMULATION_STATE = Gauge(
        "h2track_simulation_state",
        "Simulation running state (1=running, 0=stopped)",
    )
    SIMULATION_UPTIME_SECONDS = Counter(
        "h2track_simulation_uptime_seconds_total",
        "Total seconds the simulation has been running",
    )
    SCENE_INFO = Gauge(
        "h2track_scene_info",
        "Scene information label",
        ["scene"],
    )

    # Navigation metrics
    NAVIGATION_SUCCESS = Counter(
        "h2track_navigation_success_total",
        "Total successful navigation goals",
    )
    NAVIGATION_FAILURE = Counter(
        "h2track_navigation_failure_total",
        "Total failed navigation goals",
    )
    NAVIGATION_DURATION = Histogram(
        "h2track_navigation_duration_seconds",
        "Navigation goal duration in seconds",
        buckets=(1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
    )

    # Gas tracking metrics
    GAS_CONCENTRATION = Gauge(
        "h2track_gas_concentration",
        "Current gas concentration reading",
    )
    MODE_TRANSITIONS = Counter(
        "h2track_mode_transitions_total",
        "Total mode transitions",
        ["mode"],
    )

    # LLM metrics
    LLM_API_REQUESTS = Counter(
        "h2track_llm_api_requests_total",
        "Total LLM API requests",
        ["profile_id", "model", "protocol"],
    )
    LLM_API_LATENCY = Histogram(
        "h2track_llm_api_latency_seconds",
        "LLM API request latency in seconds",
        buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    )
    LLM_TOKENS = Counter(
        "h2track_llm_tokens_total",
        "Total LLM tokens processed",
        ["profile_id", "model", "type"],
    )

    # Internal state for uptime tracking
    _simulation_start_time: float | None = None
    _uptime_lock = threading.Lock()
else:
    # Define placeholder objects for type hints when Prometheus is not available
    SIMULATION_STATE = None  # type: ignore[misc,assignment]
    SIMULATION_UPTIME_SECONDS = None  # type: ignore[misc,assignment]
    SCENE_INFO = None  # type: ignore[misc,assignment]
    NAVIGATION_SUCCESS = None  # type: ignore[misc,assignment]
    NAVIGATION_FAILURE = None  # type: ignore[misc,assignment]
    NAVIGATION_DURATION = None  # type: ignore[misc,assignment]
    GAS_CONCENTRATION = None  # type: ignore[misc,assignment]
    MODE_TRANSITIONS = None  # type: ignore[misc,assignment]
    LLM_API_REQUESTS = None  # type: ignore[misc,assignment]
    LLM_API_LATENCY = None  # type: ignore[misc,assignment]
    LLM_TOKENS = None  # type: ignore[misc,assignment]
    _simulation_start_time = None
    _uptime_lock = threading.Lock()


class PrometheusMetricsExporter:
    """Exports H2Track metrics in Prometheus format.

    This class bridges MetricsStore data to Prometheus metrics and provides
    the /metrics endpoint response.

    Thread Safety:
        All methods are thread-safe.
    """

    def __init__(self, metrics_store: MetricsStore) -> None:
        """Initialize the Prometheus metrics exporter.

        Args:
            metrics_store: The MetricsStore instance to read metrics from.
        """
        self._metrics_store = metrics_store
        self._lock = threading.Lock()
        self._last_mode: str | None = None
        self._last_nav_succeeded: int = 0
        self._last_nav_failed: int = 0
        self._last_gas: float | None = None

    def update_from_store(self) -> None:
        """Update Prometheus metrics from MetricsStore snapshot.

        This method should be called periodically to sync the internal
        MetricsStore state with Prometheus gauges and counters.
        """
        if not PROMETHEUS_AVAILABLE:
            return

        snapshot = self._metrics_store.snapshot(limit=10)

        with self._lock:
            # Update simulation state
            phase = snapshot.get("phase", {}).get("current", "INIT")
            is_running = phase not in {"INIT", "STOPPING", "EXITED", "idle", "error"}
            SIMULATION_STATE.set(1.0 if is_running else 0.0)  # type: ignore[union-attr]

            # Track uptime
            global _simulation_start_time
            with _uptime_lock:
                if is_running and _simulation_start_time is None:
                    _simulation_start_time = time.monotonic()
                elif not is_running and _simulation_start_time is not None:
                    # Add accumulated uptime before resetting
                    elapsed = time.monotonic() - _simulation_start_time
                    SIMULATION_UPTIME_SECONDS.inc(elapsed)  # type: ignore[union-attr]
                    _simulation_start_time = None

            # Update scene info
            profile = snapshot.get("launch_profile", {})
            scene = str(profile.get("scene", "warehouse"))
            SCENE_INFO.labels(scene=scene).set(1.0)  # type: ignore[union-attr]

            # Update navigation metrics (incremental)
            nav = snapshot.get("nav", {})
            current_succeeded = int(nav.get("goal_succeeded", 0))
            current_failed = int(nav.get("failed_to_make_progress", 0)) + int(
                nav.get("goal_canceled", 0)
            )

            # Increment counters for new successes
            if current_succeeded > self._last_nav_succeeded:
                delta = current_succeeded - self._last_nav_succeeded
                NAVIGATION_SUCCESS.inc(delta)  # type: ignore[union-attr]
                self._last_nav_succeeded = current_succeeded

            # Increment counters for new failures
            if current_failed > self._last_nav_failed:
                delta = current_failed - self._last_nav_failed
                NAVIGATION_FAILURE.inc(delta)  # type: ignore[union-attr]
                self._last_nav_failed = current_failed

            # Record navigation durations
            durations = nav.get("goal_durations_sec", [])
            if durations:
                for duration in durations:
                    try:
                        NAVIGATION_DURATION.observe(float(duration))  # type: ignore[union-attr]
                    except (TypeError, ValueError):
                        pass

            # Update gas concentration
            gas = snapshot.get("gas", {})
            gas_current = gas.get("current")
            if gas_current is not None:
                try:
                    GAS_CONCENTRATION.set(float(gas_current))  # type: ignore[union-attr]
                except (TypeError, ValueError):
                    pass

            # Track mode transitions
            mode = snapshot.get("mode", {}).get("current")
            if mode and mode != self._last_mode:
                MODE_TRANSITIONS.labels(mode=mode).inc()  # type: ignore[union-attr]
                self._last_mode = mode

    def record_llm_request(
        self,
        *,
        profile_id: str,
        model: str,
        protocol: str,
        latency_sec: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record an LLM API request.

        Args:
            profile_id: The profile ID used.
            model: The model name.
            protocol: The protocol used (chat/responses).
            latency_sec: Request latency in seconds.
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
        """
        if not PROMETHEUS_AVAILABLE:
            return

        LLM_API_REQUESTS.labels(  # type: ignore[union-attr]
            profile_id=profile_id or "unknown",
            model=model or "unknown",
            protocol=protocol or "unknown",
        ).inc()
        LLM_API_LATENCY.observe(max(0.0, latency_sec))  # type: ignore[union-attr]

        if prompt_tokens > 0:
            LLM_TOKENS.labels(  # type: ignore[union-attr]
                profile_id=profile_id or "unknown",
                model=model or "unknown",
                type="prompt",
            ).inc(prompt_tokens)

        if completion_tokens > 0:
            LLM_TOKENS.labels(  # type: ignore[union-attr]
                profile_id=profile_id or "unknown",
                model=model or "unknown",
                type="completion",
            ).inc(completion_tokens)

    def get_metrics_response(self) -> tuple[bytes, str]:
        """Generate Prometheus metrics response.

        Returns:
            Tuple of (content_bytes, content_type).

        Raises:
            RuntimeError: If prometheus_client is not available.
        """
        if not PROMETHEUS_AVAILABLE:
            raise RuntimeError(
                "prometheus_client is not available. Install with: pip install prometheus_client"
            )

        # Update metrics from store before generating response
        self.update_from_store()

        content = generate_latest()  # type: ignore[misc]
        return content, "text/plain; version=0.0.4; charset=utf-8"


def is_prometheus_available() -> bool:
    """Check if prometheus_client is available.

    Returns:
        True if prometheus_client is installed and usable.
    """
    return PROMETHEUS_AVAILABLE
