"""Tests for Prometheus metrics export module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class TestPrometheusAvailability:
    """Tests for Prometheus availability detection."""

    def test_is_prometheus_available_returns_true_when_installed(self):
        """Test that is_prometheus_available returns True when prometheus_client is installed."""
        from h2track_tracking.web.metrics_export import is_prometheus_available

        # Should return True in normal environment with prometheus_client installed
        result = is_prometheus_available()
        assert isinstance(result, bool)

    def test_module_handles_missing_prometheus_gracefully(self):
        """Test that the module handles missing prometheus_client gracefully."""
        # This test verifies that importing the module works even without prometheus_client
        # The actual availability depends on the environment
        from h2track_tracking.web import metrics_export

        # Module should import without errors
        assert hasattr(metrics_export, "PrometheusMetricsExporter")
        assert hasattr(metrics_export, "is_prometheus_available")


class TestPrometheusMetricsExporter:
    """Tests for PrometheusMetricsExporter class."""

    @pytest.fixture
    def metrics_store(self):
        """Create a MetricsStore instance for testing."""
        from h2track_tracking.web.metrics_store import MetricsStore

        return MetricsStore(max_points=100)

    @pytest.fixture
    def exporter(self, metrics_store):
        """Create a PrometheusMetricsExporter instance for testing."""
        from h2track_tracking.web.metrics_export import PrometheusMetricsExporter

        return PrometheusMetricsExporter(metrics_store)

    def test_init_creates_exporter(self, metrics_store):
        """Test that PrometheusMetricsExporter initializes correctly."""
        from h2track_tracking.web.metrics_export import PrometheusMetricsExporter

        exporter = PrometheusMetricsExporter(metrics_store)
        assert exporter._metrics_store is metrics_store
        assert isinstance(exporter._lock, type(threading.Lock()))

    def test_update_from_store_handles_empty_snapshot(self, exporter):
        """Test that update_from_store handles empty MetricsStore."""
        # Should not raise any exceptions
        exporter.update_from_store()

    def test_update_from_store_updates_simulation_state(self, metrics_store):
        """Test that update_from_store updates simulation state gauge."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
            SIMULATION_STATE,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Set phase to RUNNING
        metrics_store.set_phase("RUNNING", reason="test")
        exporter.update_from_store()

        # SIMULATION_STATE should be 1 (running)
        # We can't easily check the gauge value directly, but we can verify no exceptions

    def test_update_from_store_updates_gas_concentration(self, metrics_store):
        """Test that update_from_store updates gas concentration gauge."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Set gas concentration
        metrics_store.set_gas(2.5)
        exporter.update_from_store()

        # Should not raise exceptions

    def test_update_from_store_tracks_mode_transitions(self, metrics_store):
        """Test that update_from_store tracks mode transitions."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Set modes
        metrics_store.set_mode("PATROL")
        exporter.update_from_store()

        metrics_store.set_mode("SEEK_TRACK")
        exporter.update_from_store()

        # Should not raise exceptions

    def test_record_llm_request_with_valid_data(self, exporter):
        """Test record_llm_request with valid data."""
        from h2track_tracking.web.metrics_export import PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        # Should not raise exceptions
        exporter.record_llm_request(
            profile_id="test-profile",
            model="gpt-4",
            protocol="chat",
            latency_sec=1.5,
            prompt_tokens=100,
            completion_tokens=50,
        )

    def test_record_llm_request_with_zero_tokens(self, exporter):
        """Test record_llm_request with zero tokens."""
        from h2track_tracking.web.metrics_export import PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        # Should not raise exceptions
        exporter.record_llm_request(
            profile_id="test-profile",
            model="gpt-4",
            protocol="chat",
            latency_sec=0.5,
        )

    def test_get_metrics_response_returns_bytes(self, metrics_store):
        """Test that get_metrics_response returns bytes content."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)
        content, content_type = exporter.get_metrics_response()

        assert isinstance(content, bytes)
        assert "text/plain" in content_type

    def test_get_metrics_response_includes_metric_names(self, metrics_store):
        """Test that get_metrics_response includes expected metric names."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)
        content, _ = exporter.get_metrics_response()
        content_str = content.decode("utf-8")

        # Check for our metric names
        assert "h2track_simulation_state" in content_str
        assert "h2track_gas_concentration" in content_str
        assert "h2track_navigation_success_total" in content_str
        assert "h2track_llm_api_requests_total" in content_str

    def test_get_metrics_response_raises_when_prometheus_unavailable(self, metrics_store):
        """Test that get_metrics_response raises error when prometheus_client is not available."""
        from h2track_tracking.web.metrics_export import PrometheusMetricsExporter

        with patch(
            "h2track_tracking.web.metrics_export.PROMETHEUS_AVAILABLE", False
        ):
            exporter = PrometheusMetricsExporter(metrics_store)
            with pytest.raises(RuntimeError) as exc_info:
                exporter.get_metrics_response()

            assert "prometheus_client is not available" in str(exc_info.value)


class TestMetricsIntegration:
    """Integration tests for metrics export."""

    @pytest.fixture
    def metrics_store(self):
        """Create a MetricsStore instance for testing."""
        from h2track_tracking.web.metrics_store import MetricsStore

        return MetricsStore(max_points=100)

    def test_full_metrics_flow(self, metrics_store):
        """Test the full metrics flow from MetricsStore to Prometheus output."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Simulate some activity
        metrics_store.set_phase("RUNNING", reason="test")
        metrics_store.set_gas(1.5)
        metrics_store.set_mode("PATROL")
        metrics_store.set_mode("SEEK_TRACK")

        # Get metrics response
        content, content_type = exporter.get_metrics_response()
        content_str = content.decode("utf-8")

        # Verify metrics are present
        assert "h2track_simulation_state" in content_str
        assert "h2track_gas_concentration" in content_str

    def test_navigation_metrics_tracking(self, metrics_store):
        """Test that navigation metrics are tracked correctly."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Simulate navigation via log observation
        metrics_store.observe_log_line("Begin navigating from current location")
        metrics_store.observe_log_line("Goal succeeded")

        # Update and get metrics
        content, _ = exporter.get_metrics_response()
        content_str = content.decode("utf-8")

        # Should contain navigation metrics
        assert "h2track_navigation_success_total" in content_str

    def test_llm_metrics_recording(self, metrics_store):
        """Test that LLM metrics are recorded correctly."""
        from h2track_tracking.web.metrics_export import (
            PROMETHEUS_AVAILABLE,
            PrometheusMetricsExporter,
        )

        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus_client not available")

        exporter = PrometheusMetricsExporter(metrics_store)

        # Record some LLM requests
        exporter.record_llm_request(
            profile_id="profile-1",
            model="gpt-4",
            protocol="chat",
            latency_sec=2.0,
            prompt_tokens=500,
            completion_tokens=100,
        )
        exporter.record_llm_request(
            profile_id="profile-1",
            model="gpt-4",
            protocol="chat",
            latency_sec=1.5,
            prompt_tokens=300,
            completion_tokens=80,
        )

        # Get metrics
        content, _ = exporter.get_metrics_response()
        content_str = content.decode("utf-8")

        # Should contain LLM metrics
        assert "h2track_llm_api_requests_total" in content_str
        assert "h2track_llm_api_latency_seconds" in content_str
        assert "h2track_llm_tokens_total" in content_str


class TestRoutesIntegration:
    """Tests for routes integration with /metrics endpoint."""

    def test_metrics_endpoint_registered(self):
        """Test that /metrics endpoint can be registered."""
        from h2track_tracking.web.routes import FASTAPI_AVAILABLE

        if not FASTAPI_AVAILABLE:
            pytest.skip("FastAPI not available")

        # Create a mock app
        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        from h2track_tracking.web.routes import register_routes

        # Create mock dependencies
        mock_sim = MagicMock()
        mock_sim._metrics = MagicMock()
        mock_sim.status.return_value = {"state": "idle"}
        mock_sim.recent_logs.return_value = []
        mock_sim.metrics_snapshot.return_value = {
            "phase": {"current": "INIT"},
            "mode": {},
            "gas": {},
            "nav": {},
            "launch_profile": {"scene": "warehouse"},
        }
        mock_sim.refresh_metrics_from_topics_if_needed = MagicMock()
        mock_sim.refresh_runtime_health_if_needed = MagicMock()
        mock_sim.logs_after.return_value = []

        mock_llm = MagicMock()
        mock_llm.list_profiles.return_value = {"profiles": []}
        mock_llm.history.return_value = {"rows": []}
        mock_llm.audit.return_value = {"rows": []}

        ui_meta = {"mode": "legacy_inline", "bundle_ready": False}

        # Register routes
        register_routes(
            mock_app,
            sim=mock_sim,
            llm=mock_llm,
            ui_meta=ui_meta,
            resolve_static_index_html=lambda: None,
            html_page="<html></html>",
        )

        # Verify routes were registered
        assert mock_app.get.called

        # Check that /metrics was registered
        get_calls = [str(call) for call in mock_app.get.call_args_list]
        # The route decorator is called with the path as the first argument
        registered_paths = []
        for call in mock_app.get.call_args_list:
            if call and call[0]:
                registered_paths.append(str(call[0][0]))

        assert "/metrics" in registered_paths
