"""ROS topic collector for live dashboard metrics.

This module provides the TopicMetricsCollector class which subscribes to
ROS topics and updates a MetricsStore with live data for the web console.

Topics monitored:
- /robot_mode (std_msgs/String)
- /gas_concentration (std_msgs/Float32)
- /source_found (std_msgs/Bool)
- /odom (nav_msgs/Odometry)
- /gaden/sensor_reading (olfaction_msgs/GasSensor)
"""

from __future__ import annotations

import threading
from typing import Any

from .metrics_store import MetricsStore


class TopicMetricsCollector:
    """Optional ROS topic collector for live dashboard metrics.

    This class runs a ROS node in a background thread that subscribes to
    various topics and updates a MetricsStore with the received data.

    Usage:
        collector = TopicMetricsCollector(metrics_store)
        collector.start()  # Starts background thread
        # ... later ...
        collector.stop()   # Stops background thread
    """

    def __init__(self, metrics_store: MetricsStore) -> None:
        """Initialize the topic collector.

        Args:
            metrics_store: The MetricsStore instance to update with topic data.
        """
        self._metrics = metrics_store
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background collection thread.

        If the thread is already running, this method does nothing.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background collection thread.

        Signals the worker to stop and waits up to 1 second for it to join.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _worker(self) -> None:
        """Background thread worker that spins a ROS node for topic collection.

        This method:
        1. Imports ROS dependencies (returns early if unavailable)
        2. Creates an internal _Probe node with subscriptions
        3. Spins the node until stop() is called
        4. Cleans up ROS resources on exit
        """
        try:
            from nav_msgs.msg import Odometry

            try:
                from olfaction_msgs.msg import GasSensor
            except Exception:
                GasSensor = None  # type: ignore[misc,assignment]

            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import Bool, Float32, String
        except Exception:
            return

        class _Probe(Node):
            """Internal ROS node for collecting topic data."""

            def __init__(self, metrics: MetricsStore) -> None:
                super().__init__("demo_web_metrics_collector")
                self._metrics = metrics

                # Subscribe to core topics
                self.create_subscription(String, "/robot_mode", self._on_mode, 10)
                self.create_subscription(Float32, "/gas_concentration", self._on_gas, 10)
                self.create_subscription(Bool, "/source_found", self._on_source_found, 10)
                self.create_subscription(Odometry, "/odom", self._on_odom, 10)

                # Subscribe to GADEN raw sensor if available
                if GasSensor is not None:
                    self.create_subscription(
                        GasSensor, "/gaden/sensor_reading", self._on_gas_raw, 10
                    )

            def _on_mode(self, msg: Any) -> None:
                """Handle /robot_mode messages."""
                self._metrics.set_mode(str(msg.data))

            def _on_gas(self, msg: Any) -> None:
                """Handle /gas_concentration messages."""
                self._metrics.set_gas(float(msg.data))

            def _on_source_found(self, msg: Any) -> None:
                """Handle /source_found messages."""
                self._metrics.set_source_found(bool(msg.data))

            def _on_odom(self, msg: Any) -> None:
                """Handle /odom messages."""
                pos = msg.pose.pose.position
                self._metrics.observe_odom_tick(x=float(pos.x), y=float(pos.y))

            def _on_gas_raw(self, msg: Any) -> None:
                """Handle /gaden/sensor_reading messages."""
                self._metrics.set_gas_raw(float(msg.raw))

        started_here = not rclpy.ok()
        if started_here:
            rclpy.init(args=None)

        node: Any | None = None
        try:
            node = _Probe(self._metrics)
            while not self._stop_event.is_set():
                rclpy.spin_once(node, timeout_sec=0.2)
        finally:
            if node is not None:
                node.destroy_node()
            if started_here and rclpy.ok():
                rclpy.shutdown()
