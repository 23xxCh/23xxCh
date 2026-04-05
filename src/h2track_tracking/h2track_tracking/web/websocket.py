"""WebSocket connection manager for real-time metrics streaming.

This module provides:
- ConnectionManager: Manages WebSocket connections and broadcasting
- WebSocket endpoint handler with client command support

Client Commands:
    - pause: Pause metrics stream
    - resume: Resume metrics stream
    - subscribe:topic: Subscribe to specific data topics
    - unsubscribe:topic: Unsubscribe from topics
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

try:
    from fastapi import WebSocket, WebSocketDisconnect

    WEBSOCKET_AVAILABLE = True
except Exception:
    WEBSOCKET_AVAILABLE = False
    WebSocket = None  # type: ignore[misc,assignment]
    WebSocketDisconnect = None  # type: ignore[misc,assignment]


def _now_iso() -> str:
    """Return current time as ISO format string with timezone."""
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class ClientState:
    """State for a single WebSocket client connection.

    Attributes:
        websocket: The WebSocket connection
        paused: Whether the client's metrics stream is paused
        subscriptions: Set of topic names the client is subscribed to
        connected_at: ISO timestamp when the client connected
    """

    websocket: Any
    paused: bool = False
    subscriptions: set[str] = field(default_factory=set)
    connected_at: str = field(default_factory=_now_iso)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting.

    This class provides:
    - Thread-safe connection management
    - Client-specific state (pause/resume, subscriptions)
    - Broadcasting to all or filtered clients

    Thread Safety:
        All public methods are thread-safe.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._lock = threading.Lock()
        self._clients: dict[int, ClientState] = {}
        self._client_counter = 0

    def connect(self, websocket: Any) -> int:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register.

        Returns:
            Unique client ID for the connection.
        """
        with self._lock:
            self._client_counter += 1
            client_id = self._client_counter
            self._clients[client_id] = ClientState(websocket=websocket)
            return client_id

    def disconnect(self, client_id: int) -> None:
        """Remove a WebSocket connection.

        Args:
            client_id: The client ID returned from connect().
        """
        with self._lock:
            self._clients.pop(client_id, None)

    def set_paused(self, client_id: int, paused: bool) -> bool:
        """Set the paused state for a client.

        Args:
            client_id: The client ID.
            paused: Whether to pause the stream.

        Returns:
            True if the client exists and state was updated, False otherwise.
        """
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return False
            client.paused = paused
            return True

    def is_paused(self, client_id: int) -> bool:
        """Check if a client's stream is paused.

        Args:
            client_id: The client ID.

        Returns:
            True if paused, False otherwise.
        """
        with self._lock:
            client = self._clients.get(client_id)
            return client.paused if client else False

    def subscribe(self, client_id: int, topic: str) -> bool:
        """Subscribe a client to a specific topic.

        Args:
            client_id: The client ID.
            topic: The topic name to subscribe to.

        Returns:
            True if subscription was added, False if client not found.
        """
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return False
            client.subscriptions.add(topic)
            return True

    def unsubscribe(self, client_id: int, topic: str) -> bool:
        """Unsubscribe a client from a specific topic.

        Args:
            client_id: The client ID.
            topic: The topic name to unsubscribe from.

        Returns:
            True if subscription was removed, False if client not found.
        """
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return False
            client.subscriptions.discard(topic)
            return True

    def get_subscriptions(self, client_id: int) -> set[str]:
        """Get the set of topics a client is subscribed to.

        Args:
            client_id: The client ID.

        Returns:
            Copy of the subscriptions set, or empty set if client not found.
        """
        with self._lock:
            client = self._clients.get(client_id)
            return set(client.subscriptions) if client else set()

    def get_client_count(self) -> int:
        """Get the number of connected clients.

        Returns:
            Number of active WebSocket connections.
        """
        with self._lock:
            return len(self._clients)

    def get_client_state(self, client_id: int) -> dict[str, Any] | None:
        """Get the state for a specific client.

        Args:
            client_id: The client ID.

        Returns:
            Dict with paused, subscriptions, connected_at, or None if not found.
        """
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return None
            return {
                "paused": client.paused,
                "subscriptions": list(client.subscriptions),
                "connected_at": client.connected_at,
            }

    async def broadcast(
        self,
        message: dict[str, Any],
        *,
        topic: str | None = None,
        skip_paused: bool = True,
    ) -> int:
        """Broadcast a message to all connected clients.

        Args:
            message: The message to broadcast.
            topic: Optional topic filter. Only clients subscribed to this
                topic will receive the message (if they have any subscriptions).
            skip_paused: If True, skip clients with paused streams.

        Returns:
            Number of clients the message was sent to.
        """
        to_send: list[Any] = []
        with self._lock:
            for client_id, client in self._clients.items():
                # Skip paused clients if requested
                if skip_paused and client.paused:
                    continue

                # If topic is specified, check subscriptions
                if topic is not None:
                    # If client has subscriptions, only send if subscribed
                    if client.subscriptions and topic not in client.subscriptions:
                        continue

                to_send.append(client.websocket)

        sent_count = 0
        for websocket in to_send:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception:
                # Connection may have been closed; ignore errors
                pass

        return sent_count

    async def send_to(self, client_id: int, message: dict[str, Any]) -> bool:
        """Send a message to a specific client.

        Args:
            client_id: The client ID to send to.
            message: The message to send.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        websocket = None
        with self._lock:
            client = self._clients.get(client_id)
            if client is not None:
                websocket = client.websocket

        if websocket is None:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False


def parse_client_command(data: str | dict[str, Any]) -> dict[str, Any] | None:
    """Parse a client command message.

    Args:
        data: Raw string or dict from WebSocket.

    Returns:
        Parsed command dict with 'action' and optional 'topic' keys,
        or None if not a valid command.

    Supported commands:
        - pause -> {"action": "pause"}
        - resume -> {"action": "resume"}
        - subscribe:topic -> {"action": "subscribe", "topic": "topic"}
        - unsubscribe:topic -> {"action": "unsubscribe", "topic": "topic"}
    """
    if isinstance(data, str):
        text = data.strip().lower()
        if text == "pause":
            return {"action": "pause"}
        if text == "resume":
            return {"action": "resume"}
        if text.startswith("subscribe:"):
            topic = data.split(":", 1)[1].strip()
            if topic:
                return {"action": "subscribe", "topic": topic}
            return None
        if text.startswith("unsubscribe:"):
            topic = data.split(":", 1)[1].strip()
            if topic:
                return {"action": "unsubscribe", "topic": topic}
            return None
        # Try parsing as JSON
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None

    if isinstance(data, dict):
        action = str(data.get("action", "")).lower()
        if action in {"pause", "resume"}:
            return {"action": action}
        if action in {"subscribe", "unsubscribe"}:
            topic = data.get("topic")
            if topic:
                return {"action": action, "topic": str(topic)}
    return None


async def websocket_endpoint(
    websocket: Any,
    manager: ConnectionManager,
    *,
    get_metrics: Callable[[], dict[str, Any]],
    broadcast_interval_sec: float = 1.0,
) -> None:
    """Handle a WebSocket connection with metrics streaming.

    This function:
    1. Accepts the WebSocket connection
    2. Registers with the connection manager
    3. Starts a background task for metrics broadcasting
    4. Handles incoming client commands
    5. Cleans up on disconnect

    Args:
        websocket: The WebSocket connection.
        manager: The ConnectionManager instance.
        get_metrics: Callable that returns current metrics dict.
        broadcast_interval_sec: Interval between metrics broadcasts.
    """
    if not WEBSOCKET_AVAILABLE:
        raise RuntimeError("WebSocket support not available. Install fastapi.")

    await websocket.accept()
    client_id = manager.connect(websocket)

    async def broadcast_metrics() -> None:
        """Background task to broadcast metrics to this client."""
        while True:
            try:
                if not manager.is_paused(client_id):
                    metrics = get_metrics()
                    await manager.send_to(
                        client_id,
                        {"type": "metrics", "data": metrics, "timestamp": _now_iso()},
                    )
                await asyncio.sleep(broadcast_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    # Start broadcast task
    broadcast_task = asyncio.create_task(broadcast_metrics())

    try:
        while True:
            # Receive and handle commands
            try:
                raw = await websocket.receive()
            except Exception:
                break

            # Handle different message types
            if "text" in raw:
                command = parse_client_command(raw["text"])
            elif "bytes" in raw:
                try:
                    text = raw["bytes"].decode("utf-8")
                    command = parse_client_command(text)
                except UnicodeDecodeError:
                    command = None
            elif "json" in raw:
                command = parse_client_command(raw["json"])
            else:
                command = None

            if command is not None:
                action = command["action"]

                if action == "pause":
                    manager.set_paused(client_id, True)
                    await manager.send_to(
                        client_id,
                        {"type": "status", "paused": True, "timestamp": _now_iso()},
                    )

                elif action == "resume":
                    manager.set_paused(client_id, False)
                    await manager.send_to(
                        client_id,
                        {"type": "status", "paused": False, "timestamp": _now_iso()},
                    )

                elif action == "subscribe":
                    topic = command.get("topic", "")
                    if topic:
                        manager.subscribe(client_id, topic)
                        await manager.send_to(
                            client_id,
                            {
                                "type": "status",
                                "subscribed": topic,
                                "subscriptions": list(manager.get_subscriptions(client_id)),
                                "timestamp": _now_iso(),
                            },
                        )

                elif action == "unsubscribe":
                    topic = command.get("topic", "")
                    if topic:
                        manager.unsubscribe(client_id, topic)
                        await manager.send_to(
                            client_id,
                            {
                                "type": "status",
                                "unsubscribed": topic,
                                "subscriptions": list(manager.get_subscriptions(client_id)),
                                "timestamp": _now_iso(),
                            },
                        )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(client_id)
