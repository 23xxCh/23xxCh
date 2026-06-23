"""ROS 2 node that samples GADEN ground truth for evaluation.

Subscribes to /estimated_source (PF), /estimated_source_pose (Surge-Cast),
/amcl_pose, /gas_concentration. Periodically calls GADEN's /odor_value
(GasPosition) and /wind_value (WindPosition) services to sample ground-truth
concentration at the robot's position.

Collected samples can be dumped to JSON for offline analysis via the
dump_to_json() method or the /api/eval/ground-truth endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geometry_msgs.msg import PoseWithCovarianceStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32

try:
    from gaden_msgs.srv import GasPosition, WindPosition
except ImportError:  # GADEN not available in unit tests
    GasPosition = None  # type: ignore[misc,assignment]
    WindPosition = None  # type: ignore[misc,assignment]

from .ground_truth_report import (
    GroundTruthSample,
    compute_ground_truth_metrics,
    format_report_json,
)


class GroundTruthSampler(Node):
    """Samples GADEN ground truth and estimates for offline evaluation."""

    def __init__(self) -> None:
        super().__init__("ground_truth_sampler")

        self.declare_parameter("sample_rate_hz", 1.0)
        self.declare_parameter("source_x", 0.0)
        self.declare_parameter("source_y", 0.0)
        self.declare_parameter("service_timeout_sec", 2.0)

        self._source_truth = (
            float(self.get_parameter("source_x").value),
            float(self.get_parameter("source_y").value),
        )
        self._timeout = float(self.get_parameter("service_timeout_sec").value)
        self._samples: list[GroundTruthSample] = []
        self._robot_pose: tuple[float, float] = (0.0, 0.0)
        self._pf_estimate: tuple[float, float] | None = None
        self._concentration: float = 0.0
        self._odor_client = None
        self._wind_client = None
        self._timer = None

    def on_start(self) -> None:
        """Create subscriptions and start sampling (called externally)."""
        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        state_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, state_qos
        )
        self.create_subscription(
            PoseWithCovarianceStamped, "/estimated_source", self._on_pf, state_qos
        )
        self.create_subscription(
            Float32, "/gas_concentration", self._on_gas, sensor_qos
        )

        if GasPosition is not None:
            self._odor_client = self.create_client(GasPosition, "/odor_value")
        if WindPosition is not None:
            self._wind_client = self.create_client(WindPosition, "/wind_value")

        rate_hz = max(0.1, float(self.get_parameter("sample_rate_hz").value))
        self._timer = self.create_timer(1.0 / rate_hz, self._sample)

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        p = msg.pose.pose.position
        self._robot_pose = (float(p.x), float(p.y))

    def _on_pf(self, msg: PoseWithCovarianceStamped) -> None:
        p = msg.pose.pose.position
        self._pf_estimate = (float(p.x), float(p.y))

    def _on_gas(self, msg: Float32) -> None:
        self._concentration = float(msg.data)

    def _sample(self) -> None:
        """Sample ground-truth concentration at robot position via GADEN service."""
        if self._odor_client is None or not self._odor_client.service_is_ready():
            return

        rx, ry = self._robot_pose
        req = GasPosition.Request()
        req.x = [rx]
        req.y = [ry]
        req.z = [0.0]

        future = self._odor_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=self._timeout)

        truth_conc = 0.0
        if future.result() is not None and future.result().positions:
            gas_in_cell = future.result().positions[0]
            if gas_in_cell.concentration:
                truth_conc = float(gas_in_cell.concentration[0])

        stamp = self.get_clock().now().nanoseconds * 1e-9
        self._samples.append(
            GroundTruthSample(
                timestamp=stamp,
                robot_pose=self._robot_pose,
                estimate=self._pf_estimate,
                truth_concentration=truth_conc,
                estimated_concentration=self._concentration,
            )
        )

    def dump_to_json(self, path: str | Path) -> None:
        """Dump collected samples and computed metrics to a JSON file."""
        metrics = compute_ground_truth_metrics(self._samples, self._source_truth)
        report = format_report_json(metrics)
        report["samples"] = [
            {
                "timestamp": s.timestamp,
                "robot_pose": list(s.robot_pose),
                "estimate": list(s.estimate) if s.estimate else None,
                "truth_concentration": s.truth_concentration,
                "estimated_concentration": s.estimated_concentration,
            }
            for s in self._samples
        ]
        report["source_truth"] = list(self._source_truth)

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def get_metrics(self) -> dict[str, Any]:
        """Return current metrics as a dict (for web API)."""
        metrics = compute_ground_truth_metrics(self._samples, self._source_truth)
        return format_report_json(metrics)

    @property
    def samples(self) -> list[GroundTruthSample]:
        """Read-only access to collected samples."""
        return list(self._samples)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GroundTruthSampler()
    node.on_start()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
