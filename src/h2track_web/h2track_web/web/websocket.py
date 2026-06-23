"""WebSocket connection manager for real-time metrics streaming.

This module provides:
- ConnectionManager: Manages WebSocket connections and broadcasting
- WebSocket endpoint handler with client command support
- HeatmapDataProvider: Provides heatmap data for WebSocket streaming
- Heatmap WebSocket endpoint for real-time visualization

Client Commands:
    - pause: Pause metrics stream
    - resume: Resume metrics stream
    - subscribe:topic: Subscribe to specific data topics
    - unsubscribe:topic: Unsubscribe from topics
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional
import numpy as np

try:
    from fastapi import WebSocket, WebSocketDisconnect

    WEBSOCKET_AVAILABLE = True
except Exception:
    WEBSOCKET_AVAILABLE = False
    WebSocket = None  # type: ignore[misc,assignment]
    WebSocketDisconnect = None  # type: ignore[misc,assignment]

# Maximum WebSocket message size (1MB) to prevent DoS
MAX_WEBSOCKET_MESSAGE_SIZE = 1024 * 1024
# Maximum command string length
MAX_COMMAND_LENGTH = 4096


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
        to_send: list[tuple[int, Any]] = []
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

                to_send.append((client_id, client.websocket))

        sent_count = 0
        failed_clients: list[int] = []

        for client_id, websocket in to_send:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception:
                # Connection may have been closed; mark for cleanup
                failed_clients.append(client_id)

        # Clean up failed connections
        for client_id in failed_clients:
            self.disconnect(client_id)

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
    # Validate message size for string input
    if isinstance(data, str):
        if len(data) > MAX_COMMAND_LENGTH:
            return None
        text = data.strip().lower()
        if text == "pause":
            return {"action": "pause"}
        if text == "resume":
            return {"action": "resume"}
        if text.startswith("subscribe:"):
            topic = data.split(":", 1)[1].strip()
            if topic and len(topic) <= 256:  # Limit topic length
                return {"action": "subscribe", "topic": topic}
            return None
        if text.startswith("unsubscribe:"):
            topic = data.split(":", 1)[1].strip()
            if topic and len(topic) <= 256:
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
            if topic and len(str(topic)) <= 256:
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

            # Validate message size to prevent DoS
            if "text" in raw and len(raw["text"]) > MAX_WEBSOCKET_MESSAGE_SIZE:
                await manager.send_to(
                    client_id,
                    {"type": "error", "message": "Message too large", "timestamp": _now_iso()},
                )
                continue
            if "bytes" in raw and len(raw["bytes"]) > MAX_WEBSOCKET_MESSAGE_SIZE:
                await manager.send_to(
                    client_id,
                    {"type": "error", "message": "Message too large", "timestamp": _now_iso()},
                )
                continue

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
        except Exception:
            pass
        manager.disconnect(client_id)


@dataclass
class HeatmapData:
    """Container for heatmap data to be sent via WebSocket."""

    grid_data: Optional[dict[str, Any]] = None
    particles: Optional[list[tuple[float, float, float]]] = None  # [(x, y, weight), ...]
    estimate: Optional[dict[str, Any]] = None
    timestamp: str = field(default_factory=_now_iso)


class HeatmapDataProvider:
    """Provider for heatmap data that collects from ROS topics.

    This class provides a clean interface for WebSocket endpoints to access
    heatmap data without direct ROS dependencies. The ROS integration is done
    by setting the data from external callbacks.

    Thread Safety:
        All public methods are thread-safe.
    """

    def __init__(self) -> None:
        """Initialize the heatmap data provider."""
        self._lock = threading.Lock()
        self._grid_data: Optional[dict[str, Any]] = None
        self._particles: list[tuple[float, float, float]] = []
        self._estimate: Optional[dict[str, Any]] = None

    def set_grid_data(self, data: dict[str, Any]) -> None:
        """Set the concentration grid data.

        Args:
            data: Dictionary with 'resolution', 'dimensions', 'origin', 'data' keys.
                  The 'data' field should be base64-encoded float32 array.
        """
        with self._lock:
            self._grid_data = data.copy() if data else None

    def set_particles(
        self,
        positions: list[tuple[float, float]],
        weights: list[float],
    ) -> None:
        """Set particle filter particle data.

        Args:
            positions: List of (x, y) position tuples.
            weights: List of particle weights (same length as positions).
        """
        with self._lock:
            if len(positions) == len(weights):
                self._particles = [
                    (float(p[0]), float(p[1]), float(w))
                    for p, w in zip(positions, weights)
                ]
            else:
                self._particles = []

    def set_estimate(
        self,
        position: tuple[float, float],
        confidence: float,
    ) -> None:
        """Set the source estimate data.

        Args:
            position: Estimated (x, y) position.
            confidence: Confidence value [0, 1].
        """
        with self._lock:
            self._estimate = {
                "position": [float(position[0]), float(position[1])],
                "confidence": float(confidence),
            }

    def get_heatmap_data(self) -> HeatmapData:
        """Get all heatmap data.

        Returns:
            HeatmapData with current grid, particles, and estimate.
        """
        with self._lock:
            return HeatmapData(
                grid_data=self._grid_data.copy() if self._grid_data else None,
                particles=list(self._particles) if self._particles else None,
                estimate=self._estimate.copy() if self._estimate else None,
            )

    def has_data(self) -> bool:
        """Check if any heatmap data is available.

        Returns:
            True if grid, particles, or estimate data is available.
        """
        with self._lock:
            return (
                self._grid_data is not None
                or bool(self._particles)
                or self._estimate is not None
            )


async def heatmap_websocket_endpoint(
    websocket: Any,
    manager: ConnectionManager,
    *,
    heatmap_provider: HeatmapDataProvider,
    broadcast_interval_sec: float = 0.5,
) -> None:
    """Handle a WebSocket connection for heatmap data streaming.

    This endpoint streams:
    - ConcentrationGrid data for heatmap visualization
    - Particle filter particles for visualization
    - Source estimate with confidence

    Message Format:
        {
            "type": "heatmap_update",
            "timestamp": "2026-04-05T12:00:00.000Z",
            "grid": {
                "resolution": 0.5,
                "origin": [-7.5, -10.8, 0.0],
                "dimensions": [30, 22, 5],
                "data": "base64_encoded_float32_array"
            },
            "particles": {
                "positions": [[x1, y1], [x2, y2], ...],
                "weights": [w1, w2, ...]
            },
            "estimate": {
                "position": [3.6, -3.04],
                "confidence": 0.85
            }
        }

    Args:
        websocket: The WebSocket connection.
        manager: The ConnectionManager instance.
        heatmap_provider: Provider for heatmap data.
        broadcast_interval_sec: Interval between data broadcasts (default: 0.5s = 2 Hz).
    """
    if not WEBSOCKET_AVAILABLE:
        raise RuntimeError("WebSocket support not available. Install fastapi.")

    await websocket.accept()
    client_id = manager.connect(websocket)

    async def broadcast_heatmap() -> None:
        """Background task to broadcast heatmap data to this client."""
        while True:
            try:
                if not manager.is_paused(client_id) and heatmap_provider.has_data():
                    heatmap_data = heatmap_provider.get_heatmap_data()

                    message: dict[str, Any] = {
                        "type": "heatmap_update",
                        "timestamp": heatmap_data.timestamp,
                    }

                    # Add grid data if available
                    if heatmap_data.grid_data:
                        message["grid"] = heatmap_data.grid_data

                    # Add particles if available
                    if heatmap_data.particles:
                        positions = [[p[0], p[1]] for p in heatmap_data.particles]
                        weights = [p[2] for p in heatmap_data.particles]
                        message["particles"] = {
                            "positions": positions,
                            "weights": weights,
                        }

                    # Add estimate if available
                    if heatmap_data.estimate:
                        message["estimate"] = heatmap_data.estimate

                    await manager.send_to(client_id, message)

                await asyncio.sleep(broadcast_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    # Start broadcast task
    broadcast_task = asyncio.create_task(broadcast_heatmap())

    try:
        while True:
            # Receive and handle commands
            try:
                raw = await websocket.receive()
            except Exception:
                break

            # Validate message size to prevent DoS
            if "text" in raw and len(raw["text"]) > MAX_WEBSOCKET_MESSAGE_SIZE:
                await manager.send_to(
                    client_id,
                    {"type": "error", "message": "Message too large", "timestamp": _now_iso()},
                )
                continue
            if "bytes" in raw and len(raw["bytes"]) > MAX_WEBSOCKET_MESSAGE_SIZE:
                await manager.send_to(
                    client_id,
                    {"type": "error", "message": "Message too large", "timestamp": _now_iso()},
                )
                continue

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
        except Exception:
            pass
        manager.disconnect(client_id)


def encode_grid_data(data: np.ndarray) -> str:
    """Encode numpy grid data as base64 string.

    Args:
        data: Numpy array of concentration values.

    Returns:
        Base64-encoded string of float32 data.
    """
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    return base64.b64encode(data.tobytes()).decode("ascii")
