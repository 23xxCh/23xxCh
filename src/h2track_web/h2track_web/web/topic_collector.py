"""ROS topic collector for live dashboard metrics and heatmap data.

This module provides the TopicMetricsCollector class which subscribes to
ROS topics and updates a MetricsStore with live data for the web console.
When a HeatmapDataProvider is supplied, it also bridges particle filter
and source estimate data to the WebSocket heatmap endpoint.

Topics monitored:
- /robot_mode (std_msgs/String) — TRANSIENT_LOCAL QoS
- /gas_concentration (std_msgs/Float32) — BEST_EFFORT QoS
- /source_found (std_msgs/Bool) — TRANSIENT_LOCAL QoS
- /odom (nav_msgs/Odometry)
- /gaden/sensor_reading (olfaction_msgs/GasSensor)
- /particle_cloud (geometry_msgs/PoseArray) — BEST_EFFORT QoS
- /estimated_source (PoseWithCovarianceStamped) — TRANSIENT_LOCAL QoS
- /amcl_pose (PoseWithCovarianceStamped) — TRANSIENT_LOCAL QoS
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, TYPE_CHECKING

from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from .metrics_store import MetricsStore

if TYPE_CHECKING:
    from .websocket import HeatmapDataProvider


class TopicMetricsCollector:
    """Optional ROS topic collector for live dashboard metrics.

    This class runs a ROS node in a background thread that subscribes to
    various topics and updates a MetricsStore with the received data.
    When a HeatmapDataProvider is supplied, it also bridges particle filter
    and source estimate data to the WebSocket heatmap endpoint, and builds
    a local ConcentrationGrid from accumulated gas readings.

    Usage:
        collector = TopicMetricsCollector(metrics_store, heatmap_provider)
        collector.start()  # Starts background thread
        # ... later ...
        collector.stop()   # Stops background thread
    """

    # Configurable heatmap grid parameters
    grid_resolution: float = 0.25   # meters per cell
    grid_size: int = 80             # cells per side
    grid_decay: float = 0.95        # decay factor per interval

    def __init__(
        self,
        metrics_store: MetricsStore,
        heatmap_provider: "HeatmapDataProvider | None" = None,
    ) -> None:
        """Initialize the topic collector.

        Args:
            metrics_store: The MetricsStore instance to update with topic data.
            heatmap_provider: Optional HeatmapDataProvider for WebSocket heatmap.
        """
        self._metrics = metrics_store
        self._heatmap_provider = heatmap_provider
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
        """Background thread worker that spins a ROS node for topic collection."""
        try:
            from geometry_msgs.msg import PoseArray
            from nav_msgs.msg import Odometry
            from geometry_msgs.msg import PoseWithCovarianceStamped

            try:
                from olfaction_msgs.msg import GasSensor
            except Exception:
                GasSensor = None  # type: ignore[misc,assignment]

            import numpy as np
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import Bool, Float32, String

            from ..heatmap.grid import ConcentrationGrid, HeatmapConfig
        except Exception:
            return

        class _Probe(Node):
            """Internal ROS node for collecting topic data."""

            def __init__(
                self,
                metrics: MetricsStore,
                heatmap_provider: "HeatmapDataProvider | None",
                collector: "TopicMetricsCollector",
            ) -> None:
                super().__init__("demo_web_metrics_collector")
                self._metrics = metrics
                self._heatmap = heatmap_provider
                self._collector = collector

                # gas_concentration is published with BEST_EFFORT QoS
                sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
                # bt_node_runner publishes mode/source_found/estimated_source with TRANSIENT_LOCAL
                state_qos = QoSProfile(
                    depth=10,
                    reliability=ReliabilityPolicy.RELIABLE,
                    durability=DurabilityPolicy.TRANSIENT_LOCAL,
                )

                # Subscribe to core topics
                self.create_subscription(String, "/robot_mode", self._on_mode, state_qos)
                self.create_subscription(Float32, "/gas_concentration", self._on_gas, sensor_qos)
                self.create_subscription(Bool, "/source_found", self._on_source_found, state_qos)
                self.create_subscription(Odometry, "/odom", self._on_odom, 10)

                # Subscribe to GADEN raw sensor if available
                if GasSensor is not None:
                    self.create_subscription(
                        GasSensor, "/gaden/sensor_reading", self._on_gas_raw, 10
                    )

                # Heatmap bridge subscriptions (only if provider supplied)
                if self._heatmap is not None:
                    # /particle_cloud published by ParticleFilterNode (BEST_EFFORT)
                    self.create_subscription(
                        PoseArray, "/particle_cloud", self._on_particle_cloud, sensor_qos
                    )
                    # /estimated_source published by ParticleFilterNode (TRANSIENT_LOCAL)
                    self.create_subscription(
                        PoseWithCovarianceStamped, "/estimated_source",
                        self._on_estimated_source, state_qos,
                    )
                    # /amcl_pose for ConcentrationGrid position mapping
                    self.create_subscription(
                        PoseWithCovarianceStamped, "/amcl_pose",
                        self._on_amcl_pose, state_qos,
                    )

                    # ConcentrationGrid for local heatmap construction
                    gs = self._collector.grid_size
                    gr = self._collector.grid_resolution
                    half = gs * gr / 2.0
                    self._grid = ConcentrationGrid(
                        config=HeatmapConfig(resolution=gr, decay_rate=self._collector.grid_decay),
                        dimensions=(gs, gs, 1),
                        origin=(-half, -half, 0.0),
                    )
                    self._robot_pos: tuple[float, float] | None = None
                    self._grid_push_interval = 0.5  # seconds
                    self._last_grid_push = 0.0
                    self._decay_interval = 1.0  # seconds
                    self._last_decay = 0.0

            def _on_mode(self, msg: Any) -> None:
                """Handle /robot_mode messages."""
                self._metrics.set_mode(str(msg.data))

            def _on_gas(self, msg: Any) -> None:
                """Handle /gas_concentration messages."""
                concentration = float(msg.data)
                self._metrics.set_gas(concentration)
                # Accumulate into ConcentrationGrid if heatmap provider exists
                if self._heatmap is not None and self._robot_pos is not None:
                    now = time.monotonic()
                    rx, ry = self._robot_pos
                    self._grid.update(
                        position=(rx, ry, 0.0),
                        concentration=concentration,
                        timestamp=now,
                    )
                    # Periodic decay
                    if now - self._last_decay >= self._decay_interval:
                        self._grid.decay()
                        self._last_decay = now
                    # Periodic push to WebSocket
                    if now - self._last_grid_push >= self._grid_push_interval:
                        self._heatmap.set_grid_data(self._grid.to_dict())
                        self._last_grid_push = now

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

            def _on_particle_cloud(self, msg: Any) -> None:
                """Handle /particle_cloud messages — bridge to heatmap."""
                if self._heatmap is None:
                    return
                positions = [(float(p.position.x), float(p.position.y)) for p in msg.poses]
                # ParticleFilterNode does not publish weights in PoseArray,
                # so we assign uniform weights for visualization.
                weights = [1.0 / max(len(positions), 1)] * len(positions)
                self._heatmap.set_particles(positions, weights)

            def _on_estimated_source(self, msg: Any) -> None:
                """Handle /estimated_source messages — bridge to heatmap."""
                if self._heatmap is None:
                    return
                p = msg.pose.pose.position
                cov = msg.pose.covariance
                confidence = 0.0
                if cov[0] > 0 and cov[7] > 0:
                    confidence = min(1.0, 1.0 / (math.sqrt(cov[0] * cov[7]) + 0.1))
                self._heatmap.set_estimate((float(p.x), float(p.y)), float(confidence))

            def _on_amcl_pose(self, msg: Any) -> None:
                """Handle /amcl_pose messages — track robot position for grid."""
                p = msg.pose.pose.position
                self._robot_pos = (float(p.x), float(p.y))

        started_here = not rclpy.ok()
        if started_here:
            rclpy.init(args=None)

        node: Any | None = None
        try:
            node = _Probe(self._metrics, self._heatmap_provider, self)
            while not self._stop_event.is_set():
                rclpy.spin_once(node, timeout_sec=0.2)
        finally:
            if node is not None:
                node.destroy_node()
            if started_here and rclpy.ok():
                rclpy.shutdown()
