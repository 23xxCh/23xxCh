"""Tests for WebSocket connection manager and endpoint."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from h2track_web.web.websocket import (
    ClientState,
    ConnectionManager,
    parse_client_command,
    websocket_endpoint,
    WEBSOCKET_AVAILABLE,
)


class TestParseClientCommand:
    """Tests for parse_client_command function."""

    def test_parse_pause_string(self) -> None:
        """Parse 'pause' command from string."""
        result = parse_client_command("pause")
        assert result == {"action": "pause"}

    def test_parse_resume_string(self) -> None:
        """Parse 'resume' command from string."""
        result = parse_client_command("resume")
        assert result == {"action": "resume"}

    def test_parse_subscribe_string(self) -> None:
        """Parse 'subscribe:topic' command from string."""
        result = parse_client_command("subscribe:metrics")
        assert result == {"action": "subscribe", "topic": "metrics"}

    def test_parse_unsubscribe_string(self) -> None:
        """Parse 'unsubscribe:topic' command from string."""
        result = parse_client_command("unsubscribe:logs")
        assert result == {"action": "unsubscribe", "topic": "logs"}

    def test_parse_subscribe_empty_topic(self) -> None:
        """Parse 'subscribe:' with empty topic returns None."""
        result = parse_client_command("subscribe:")
        assert result is None

    def test_parse_invalid_string(self) -> None:
        """Parse invalid string returns None."""
        result = parse_client_command("invalid_command")
        assert result is None

    def test_parse_json_pause(self) -> None:
        """Parse JSON pause command."""
        result = parse_client_command({"action": "pause"})
        assert result == {"action": "pause"}

    def test_parse_json_resume(self) -> None:
        """Parse JSON resume command."""
        result = parse_client_command({"action": "resume"})
        assert result == {"action": "resume"}

    def test_parse_json_subscribe(self) -> None:
        """Parse JSON subscribe command."""
        result = parse_client_command({"action": "subscribe", "topic": "metrics"})
        assert result == {"action": "subscribe", "topic": "metrics"}

    def test_parse_json_unsubscribe(self) -> None:
        """Parse JSON unsubscribe command."""
        result = parse_client_command({"action": "unsubscribe", "topic": "logs"})
        assert result == {"action": "unsubscribe", "topic": "logs"}

    def test_parse_json_missing_topic(self) -> None:
        """Parse JSON subscribe without topic returns None."""
        result = parse_client_command({"action": "subscribe"})
        assert result is None

    def test_parse_json_invalid_action(self) -> None:
        """Parse JSON with invalid action returns None."""
        result = parse_client_command({"action": "invalid"})
        assert result is None

    def test_parse_json_string(self) -> None:
        """Parse JSON string command."""
        result = parse_client_command('{"action": "pause"}')
        assert result == {"action": "pause"}


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_init(self) -> None:
        """ConnectionManager initializes with no clients."""
        manager = ConnectionManager()
        assert manager.get_client_count() == 0

    def test_connect_returns_client_id(self) -> None:
        """Connect returns unique client ID."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        client_id_1 = manager.connect(mock_ws)
        client_id_2 = manager.connect(mock_ws)

        assert client_id_1 == 1
        assert client_id_2 == 2
        assert manager.get_client_count() == 2

    def test_disconnect_removes_client(self) -> None:
        """Disconnect removes client from manager."""
        manager = ConnectionManager()
        mock_ws = MagicMock()

        client_id = manager.connect(mock_ws)
        assert manager.get_client_count() == 1

        manager.disconnect(client_id)
        assert manager.get_client_count() == 0

    def test_disconnect_nonexistent_client(self) -> None:
        """Disconnect with invalid ID does nothing."""
        manager = ConnectionManager()
        manager.disconnect(999)  # Should not raise
        assert manager.get_client_count() == 0

    def test_set_paused(self) -> None:
        """Set paused state for client."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        client_id = manager.connect(mock_ws)

        assert manager.is_paused(client_id) is False

        result = manager.set_paused(client_id, True)
        assert result is True
        assert manager.is_paused(client_id) is True

        manager.set_paused(client_id, False)
        assert manager.is_paused(client_id) is False

    def test_set_paused_invalid_client(self) -> None:
        """Set paused for invalid client returns False."""
        manager = ConnectionManager()
        result = manager.set_paused(999, True)
        assert result is False

    def test_is_paused_invalid_client(self) -> None:
        """is_paused for invalid client returns False."""
        manager = ConnectionManager()
        assert manager.is_paused(999) is False

    def test_subscribe(self) -> None:
        """Subscribe client to topics."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        client_id = manager.connect(mock_ws)

        result = manager.subscribe(client_id, "metrics")
        assert result is True
        assert "metrics" in manager.get_subscriptions(client_id)

        manager.subscribe(client_id, "logs")
        assert manager.get_subscriptions(client_id) == {"metrics", "logs"}

    def test_subscribe_invalid_client(self) -> None:
        """Subscribe for invalid client returns False."""
        manager = ConnectionManager()
        result = manager.subscribe(999, "metrics")
        assert result is False

    def test_unsubscribe(self) -> None:
        """Unsubscribe client from topics."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        client_id = manager.connect(mock_ws)

        manager.subscribe(client_id, "metrics")
        manager.subscribe(client_id, "logs")

        result = manager.unsubscribe(client_id, "metrics")
        assert result is True
        assert manager.get_subscriptions(client_id) == {"logs"}

    def test_unsubscribe_invalid_client(self) -> None:
        """Unsubscribe for invalid client returns False."""
        manager = ConnectionManager()
        result = manager.unsubscribe(999, "metrics")
        assert result is False

    def test_get_subscriptions_invalid_client(self) -> None:
        """get_subscriptions for invalid client returns empty set."""
        manager = ConnectionManager()
        assert manager.get_subscriptions(999) == set()

    def test_get_client_state(self) -> None:
        """Get client state returns correct info."""
        manager = ConnectionManager()
        mock_ws = MagicMock()
        client_id = manager.connect(mock_ws)

        manager.subscribe(client_id, "metrics")
        manager.set_paused(client_id, True)

        state = manager.get_client_state(client_id)
        assert state is not None
        assert state["paused"] is True
        assert "metrics" in state["subscriptions"]
        assert "connected_at" in state

    def test_get_client_state_invalid(self) -> None:
        """Get client state for invalid client returns None."""
        manager = ConnectionManager()
        assert manager.get_client_state(999) is None

    @pytest.mark.asyncio
    async def test_send_to(self) -> None:
        """Send message to specific client."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        client_id = manager.connect(mock_ws)

        result = await manager.send_to(client_id, {"type": "test", "data": "hello"})
        assert result is True
        mock_ws.send_json.assert_called_once_with({"type": "test", "data": "hello"})

    @pytest.mark.asyncio
    async def test_send_to_invalid_client(self) -> None:
        """Send to invalid client returns False."""
        manager = ConnectionManager()
        result = await manager.send_to(999, {"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast(self) -> None:
        """Broadcast message to all clients."""
        manager = ConnectionManager()
        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        manager.connect(mock_ws_1)
        manager.connect(mock_ws_2)

        sent_count = await manager.broadcast({"type": "test"})
        assert sent_count == 2
        mock_ws_1.send_json.assert_called_once()
        mock_ws_2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_skip_paused(self) -> None:
        """Broadcast skips paused clients."""
        manager = ConnectionManager()
        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        client_id_1 = manager.connect(mock_ws_1)
        manager.connect(mock_ws_2)
        manager.set_paused(client_id_1, True)

        sent_count = await manager.broadcast({"type": "test"}, skip_paused=True)
        assert sent_count == 1
        mock_ws_1.send_json.assert_not_called()
        mock_ws_2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_include_paused(self) -> None:
        """Broadcast includes paused clients when skip_paused=False."""
        manager = ConnectionManager()
        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        client_id_1 = manager.connect(mock_ws_1)
        manager.connect(mock_ws_2)
        manager.set_paused(client_id_1, True)

        sent_count = await manager.broadcast({"type": "test"}, skip_paused=False)
        assert sent_count == 2
        mock_ws_1.send_json.assert_called_once()
        mock_ws_2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_topic_filter(self) -> None:
        """Broadcast filters by topic subscription."""
        manager = ConnectionManager()
        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()

        client_id_1 = manager.connect(mock_ws_1)
        manager.connect(mock_ws_2)
        manager.subscribe(client_id_1, "metrics")

        # Broadcast with topic filter
        sent_count = await manager.broadcast(
            {"type": "test"}, topic="metrics"
        )
        assert sent_count == 2  # Both receive since client 2 has no subscriptions

        # Subscribe client 2 to different topic
        manager.unsubscribe(client_id_1, "metrics")
        manager.subscribe(client_id_1, "logs")

        sent_count = await manager.broadcast(
            {"type": "test"}, topic="metrics"
        )
        assert sent_count == 1  # Only client 2 receives (no subscriptions = receives all)


class TestClientState:
    """Tests for ClientState dataclass."""

    def test_init_defaults(self) -> None:
        """ClientState initializes with defaults."""
        mock_ws = MagicMock()
        state = ClientState(websocket=mock_ws)

        assert state.websocket is mock_ws
        assert state.paused is False
        assert state.subscriptions == set()
        assert state.connected_at is not None

    def test_init_with_values(self) -> None:
        """ClientState initializes with provided values."""
        mock_ws = MagicMock()
        state = ClientState(
            websocket=mock_ws,
            paused=True,
            subscriptions={"metrics", "logs"},
        )

        assert state.websocket is mock_ws
        assert state.paused is True
        assert state.subscriptions == {"metrics", "logs"}


@pytest.mark.skipif(not WEBSOCKET_AVAILABLE, reason="WebSocket not available")
class TestWebsocketEndpoint:
    """Tests for websocket_endpoint function."""

    @pytest.mark.asyncio
    async def test_endpoint_accepts_connection(self) -> None:
        """Endpoint accepts WebSocket connection."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.receive = AsyncMock(side_effect=Exception("stop loop"))

        with patch("h2track_web.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock()
            with patch("h2track_web.web.websocket.asyncio.sleep"):
                try:
                    await websocket_endpoint(
                        mock_ws,
                        manager,
                        get_metrics=lambda: {"test": "data"},
                    )
                except Exception:
                    pass

        mock_ws.accept.assert_called_once()
        assert manager.get_client_count() == 0  # Disconnected after exception

    @pytest.mark.asyncio
    async def test_endpoint_handles_pause_command(self) -> None:
        """Endpoint handles pause command."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        # Simulate receiving a pause command then disconnecting
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

        with patch("h2track_web.web.websocket.asyncio.create_task") as mock_task:
            mock_task.return_value = AsyncMock(cancel=AsyncMock())
            with patch("h2track_web.web.websocket.asyncio.sleep"):
                try:
                    await websocket_endpoint(
                        mock_ws,
                        manager,
                        get_metrics=lambda: {"test": "data"},
                    )
                except Exception:
                    pass

        # Check that status message was sent
        status_messages = [m for m in received_messages if m.get("type") == "status"]
        assert len(status_messages) >= 1
        assert status_messages[0].get("paused") is True
