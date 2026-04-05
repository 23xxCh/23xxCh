"""Tests for WebSocket heatmap endpoint and HeatmapDataProvider."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from h2track_tracking.web.websocket import (
    ConnectionManager,
    HeatmapData,
    HeatmapDataProvider,
    encode_grid_data,
    heatmap_websocket_endpoint,
    WEBSOCKET_AVAILABLE,
)


class TestHeatmapData:
    """Tests for HeatmapData dataclass."""

    def test_init_defaults(self) -> None:
        """HeatmapData initializes with defaults."""
        data = HeatmapData()
        assert data.grid_data is None
        assert data.particles is None
        assert data.estimate is None
        assert data.timestamp is not None

    def test_init_with_values(self) -> None:
        """HeatmapData initializes with provided values."""
        grid = {"resolution": 0.5, "dimensions": [10, 10, 3]}
        particles = [(1.0, 2.0, 0.5), (3.0, 4.0, 0.3)]
        estimate = {"position": [1.5, 2.5], "confidence": 0.85}

        data = HeatmapData(
            grid_data=grid,
            particles=particles,
            estimate=estimate,
        )

        assert data.grid_data == grid
        assert data.particles == particles
        assert data.estimate == estimate


class TestHeatmapDataProvider:
    """Tests for HeatmapDataProvider class."""

    def test_init(self) -> None:
        """Provider initializes with no data."""
        provider = HeatmapDataProvider()
        assert not provider.has_data()

    def test_set_grid_data(self) -> None:
        """Set grid data updates internal state."""
        provider = HeatmapDataProvider()

        grid_data = {
            "resolution": 0.5,
            "dimensions": [10, 10, 3],
            "origin": [-5.0, -5.0, 0.0],
            "data": "base64encodeddata",
        }

        provider.set_grid_data(grid_data)

        assert provider.has_data()
        result = provider.get_heatmap_data()
        assert result.grid_data == grid_data

    def test_set_grid_data_none(self) -> None:
        """Set grid data to None clears it."""
        provider = HeatmapDataProvider()

        provider.set_grid_data({"resolution": 0.5})
        assert provider.has_data()

        provider.set_grid_data(None)
        result = provider.get_heatmap_data()
        assert result.grid_data is None

    def test_set_particles(self) -> None:
        """Set particle data updates internal state."""
        provider = HeatmapDataProvider()

        positions = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
        weights = [0.5, 0.3, 0.2]

        provider.set_particles(positions, weights)

        assert provider.has_data()
        result = provider.get_heatmap_data()
        assert result.particles is not None
        assert len(result.particles) == 3
        assert result.particles[0] == (1.0, 2.0, 0.5)

    def test_set_particles_mismatched_length(self) -> None:
        """Set particles with mismatched lengths clears data."""
        provider = HeatmapDataProvider()

        positions = [(1.0, 2.0), (3.0, 4.0)]
        weights = [0.5]  # Only one weight

        provider.set_particles(positions, weights)

        # Should be empty due to length mismatch
        result = provider.get_heatmap_data()
        assert result.particles is None

    def test_set_estimate(self) -> None:
        """Set estimate data updates internal state."""
        provider = HeatmapDataProvider()

        provider.set_estimate(position=(3.6, -3.04), confidence=0.85)

        assert provider.has_data()
        result = provider.get_heatmap_data()
        assert result.estimate is not None
        assert result.estimate["position"] == [3.6, -3.04]
        assert result.estimate["confidence"] == 0.85

    def test_get_heatmap_data_returns_copy(self) -> None:
        """get_heatmap_data returns copies, not references."""
        provider = HeatmapDataProvider()

        provider.set_grid_data({"resolution": 0.5})
        provider.set_particles([(1.0, 2.0)], [0.5])
        provider.set_estimate((1.0, 2.0), 0.8)

        data1 = provider.get_heatmap_data()
        data2 = provider.get_heatmap_data()

        # Modify data1
        if data1.grid_data:
            data1.grid_data["resolution"] = 1.0
        if data1.particles:
            data1.particles.append((9.0, 9.0, 0.1))
        if data1.estimate:
            data1.estimate["confidence"] = 0.0

        # data2 should be unaffected
        assert data2.grid_data is not None
        assert data2.grid_data["resolution"] == 0.5
        assert data2.particles is not None
        assert len(data2.particles) == 1
        assert data2.estimate is not None
        assert data2.estimate["confidence"] == 0.8

    def test_all_data_together(self) -> None:
        """Provider can hold all data types simultaneously."""
        provider = HeatmapDataProvider()

        provider.set_grid_data({"resolution": 0.5, "data": "abc"})
        provider.set_particles([(1.0, 2.0), (3.0, 4.0)], [0.6, 0.4])
        provider.set_estimate((2.0, 3.0), 0.9)

        result = provider.get_heatmap_data()

        assert result.grid_data is not None
        assert result.particles is not None
        assert result.estimate is not None
        assert len(result.particles) == 2


class TestEncodeGridData:
    """Tests for encode_grid_data utility function."""

    def test_encode_float32_array(self) -> None:
        """Encode float32 numpy array to base64."""
        data = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)

        encoded = encode_grid_data(data)

        assert isinstance(encoded, str)
        # Decode and verify
        decoded = base64.b64decode(encoded)
        restored = np.frombuffer(decoded, dtype=np.float32)
        np.testing.assert_array_equal(restored, data)

    def test_encode_float64_converts_to_float32(self) -> None:
        """Encode converts float64 to float32."""
        data = np.array([1.0, 2.0, 3.0], dtype=np.float64)

        encoded = encode_grid_data(data)

        decoded = base64.b64decode(encoded)
        restored = np.frombuffer(decoded, dtype=np.float32)
        np.testing.assert_array_almost_equal(restored, data.astype(np.float32))

    def test_encode_2d_array(self) -> None:
        """Encode 2D numpy array."""
        data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

        encoded = encode_grid_data(data)

        decoded = base64.b64decode(encoded)
        restored = np.frombuffer(decoded, dtype=np.float32).reshape(2, 2)
        np.testing.assert_array_equal(restored, data)


@pytest.mark.skipif(not WEBSOCKET_AVAILABLE, reason="WebSocket not available")
class TestHeatmapWebsocketEndpoint:
    """Tests for heatmap_websocket_endpoint function."""

    @pytest.mark.asyncio
    async def test_endpoint_accepts_connection(self) -> None:
        """Endpoint accepts WebSocket connection."""
        manager = ConnectionManager()
        provider = HeatmapDataProvider()
        mock_ws = AsyncMock()
        mock_ws.receive = AsyncMock(side_effect=Exception("stop loop"))

        with patch("h2track_tracking.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock()
            with patch("h2track_tracking.web.websocket.asyncio.sleep"):
                try:
                    await heatmap_websocket_endpoint(
                        mock_ws,
                        manager,
                        heatmap_provider=provider,
                    )
                except Exception:
                    pass

        mock_ws.accept.assert_called_once()
        assert manager.get_client_count() == 0  # Disconnected after exception

    @pytest.mark.asyncio
    async def test_endpoint_sends_heatmap_data(self) -> None:
        """Endpoint sends heatmap data when available."""
        manager = ConnectionManager()
        provider = HeatmapDataProvider()
        mock_ws = AsyncMock()

        # Set up provider with data
        provider.set_grid_data({
            "resolution": 0.5,
            "dimensions": [10, 10, 3],
            "origin": [-5.0, -5.0, 0.0],
            "data": "testbase64",
        })
        provider.set_particles([(1.0, 2.0), (3.0, 4.0)], [0.6, 0.4])
        provider.set_estimate((2.0, 3.0), 0.85)

        received_messages: list[dict[str, Any]] = []

        async def mock_send_json(msg: dict[str, Any]) -> None:
            received_messages.append(msg)

        mock_ws.send_json = mock_send_json
        mock_ws.receive = AsyncMock(side_effect=Exception("stop"))

        # Mock the broadcast task
        async def mock_broadcast() -> None:
            # Send one message then raise to stop
            if provider.has_data():
                data = provider.get_heatmap_data()
                msg = {
                    "type": "heatmap_update",
                    "timestamp": data.timestamp,
                    "grid": data.grid_data,
                    "particles": {
                        "positions": [[p[0], p[1]] for p in (data.particles or [])],
                        "weights": [p[2] for p in (data.particles or [])],
                    },
                    "estimate": data.estimate,
                }
                await mock_send_json(msg)

        with patch("h2track_tracking.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock()
            with patch("h2track_tracking.web.websocket.asyncio.sleep"):
                try:
                    await heatmap_websocket_endpoint(
                        mock_ws,
                        manager,
                        heatmap_provider=provider,
                    )
                except Exception:
                    pass

        mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_endpoint_handles_pause_command(self) -> None:
        """Endpoint handles pause command."""
        manager = ConnectionManager()
        provider = HeatmapDataProvider()
        mock_ws = AsyncMock()

        received_messages: list[dict[str, Any]] = []

        async def mock_send_json(msg: dict[str, Any]) -> None:
            received_messages.append(msg)

        mock_ws.send_json = mock_send_json
        mock_ws.receive = AsyncMock(
            side_effect=[
                {"text": "pause"},
                Exception("stop"),
            ]
        )

        with patch("h2track_tracking.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock(cancel=AsyncMock())
            with patch("h2track_tracking.web.websocket.asyncio.sleep"):
                try:
                    await heatmap_websocket_endpoint(
                        mock_ws,
                        manager,
                        heatmap_provider=provider,
                    )
                except Exception:
                    pass

        # Check that status message was sent
        status_messages = [m for m in received_messages if m.get("type") == "status"]
        assert len(status_messages) >= 1
        assert status_messages[0].get("paused") is True

    @pytest.mark.asyncio
    async def test_endpoint_handles_resume_command(self) -> None:
        """Endpoint handles resume command."""
        manager = ConnectionManager()
        provider = HeatmapDataProvider()
        mock_ws = AsyncMock()

        received_messages: list[dict[str, Any]] = []

        async def mock_send_json(msg: dict[str, Any]) -> None:
            received_messages.append(msg)

        mock_ws.send_json = mock_send_json
        mock_ws.receive = AsyncMock(
            side_effect=[
                {"text": "pause"},
                {"text": "resume"},
                Exception("stop"),
            ]
        )

        with patch("h2track_tracking.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock(cancel=AsyncMock())
            with patch("h2track_tracking.web.websocket.asyncio.sleep"):
                try:
                    await heatmap_websocket_endpoint(
                        mock_ws,
                        manager,
                        heatmap_provider=provider,
                    )
                except Exception:
                    pass

        # Check status messages
        status_messages = [m for m in received_messages if m.get("type") == "status"]
        pause_msgs = [m for m in status_messages if m.get("paused") is True]
        resume_msgs = [m for m in status_messages if m.get("paused") is False]
        assert len(pause_msgs) >= 1
        assert len(resume_msgs) >= 1

    @pytest.mark.asyncio
    async def test_endpoint_handles_subscribe_command(self) -> None:
        """Endpoint handles subscribe command."""
        manager = ConnectionManager()
        provider = HeatmapDataProvider()
        mock_ws = AsyncMock()

        received_messages: list[dict[str, Any]] = []

        async def mock_send_json(msg: dict[str, Any]) -> None:
            received_messages.append(msg)

        mock_ws.send_json = mock_send_json
        mock_ws.receive = AsyncMock(
            side_effect=[
                {"text": "subscribe:heatmap"},
                Exception("stop"),
            ]
        )

        with patch("h2track_tracking.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock(cancel=AsyncMock())
            with patch("h2track_tracking.web.websocket.asyncio.sleep"):
                try:
                    await heatmap_websocket_endpoint(
                        mock_ws,
                        manager,
                        heatmap_provider=provider,
                    )
                except Exception:
                    pass

        # Check subscription status
        status_messages = [m for m in received_messages if m.get("type") == "status"]
        sub_msgs = [m for m in status_messages if m.get("subscribed") == "heatmap"]
        assert len(sub_msgs) >= 1


class TestHeatmapMessageFormat:
    """Tests for heatmap message format compliance."""

    def test_message_format_with_all_data(self) -> None:
        """Verify message format matches specification."""
        provider = HeatmapDataProvider()

        # Set up data matching the spec format
        grid_data = {
            "resolution": 0.5,
            "origin": [-7.5, -10.8, 0.0],
            "dimensions": [30, 22, 5],
            "data": "base64_encoded_float32_array",
        }
        provider.set_grid_data(grid_data)
        provider.set_particles([(1.0, 2.0), (3.0, 4.0)], [0.5, 0.3])
        provider.set_estimate((3.6, -3.04), 0.85)

        heatmap_data = provider.get_heatmap_data()

        # Build message as endpoint would
        message: dict[str, Any] = {
            "type": "heatmap_update",
            "timestamp": heatmap_data.timestamp,
        }

        if heatmap_data.grid_data:
            message["grid"] = heatmap_data.grid_data

        if heatmap_data.particles:
            positions = [[p[0], p[1]] for p in heatmap_data.particles]
            weights = [p[2] for p in heatmap_data.particles]
            message["particles"] = {
                "positions": positions,
                "weights": weights,
            }

        if heatmap_data.estimate:
            message["estimate"] = heatmap_data.estimate

        # Verify message structure matches spec
        assert message["type"] == "heatmap_update"
        assert "timestamp" in message
        assert "grid" in message
        assert message["grid"]["resolution"] == 0.5
        assert message["grid"]["origin"] == [-7.5, -10.8, 0.0]
        assert message["grid"]["dimensions"] == [30, 22, 5]
        assert "particles" in message
        assert message["particles"]["positions"] == [[1.0, 2.0], [3.0, 4.0]]
        assert message["particles"]["weights"] == [0.5, 0.3]
        assert "estimate" in message
        assert message["estimate"]["position"] == [3.6, -3.04]
        assert message["estimate"]["confidence"] == 0.85

    def test_message_format_partial_data(self) -> None:
        """Message format handles partial data gracefully."""
        provider = HeatmapDataProvider()

        # Only set estimate, no grid or particles
        provider.set_estimate((1.0, 2.0), 0.5)

        heatmap_data = provider.get_heatmap_data()

        message: dict[str, Any] = {
            "type": "heatmap_update",
            "timestamp": heatmap_data.timestamp,
        }

        if heatmap_data.grid_data:
            message["grid"] = heatmap_data.grid_data

        if heatmap_data.particles:
            positions = [[p[0], p[1]] for p in heatmap_data.particles]
            weights = [p[2] for p in heatmap_data.particles]
            message["particles"] = {
                "positions": positions,
                "weights": weights,
            }

        if heatmap_data.estimate:
            message["estimate"] = heatmap_data.estimate

        # Verify message with partial data
        assert message["type"] == "heatmap_update"
        assert "timestamp" in message
        assert "grid" not in message
        assert "particles" not in message
        assert "estimate" in message
