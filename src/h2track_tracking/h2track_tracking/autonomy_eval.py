from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String


@dataclass
class BenchmarkState:
    start_time_sec: float = 0.0
    latest_mode: str | None = None
    mode_transition_count: int = 0
    first_mode_time_by_name: dict[str, float] = field(default_factory=dict)
    max_concentration: float | None = None
    concentration_sample_count: int = 0
    first_gas_detected_time_sec: float | None = None
    map_frozen_time_sec: float | None = None
    tracking_handoff_complete_time_sec: float | None = None
    tracking_handoff_failed_time_sec: float | None = None
    source_found_time_sec: float | None = None


def record_mode_sample(state: BenchmarkState, mode: str, now_sec: float) -> None:
    if mode not in state.first_mode_time_by_name:
        state.first_mode_time_by_name[mode] = now_sec
    if state.latest_mode is not None and state.latest_mode != mode:
        state.mode_transition_count += 1
    state.latest_mode = mode


def record_concentration_sample(
    state: BenchmarkState,
    concentration: float,
    now_sec: float,
    *,
    gas_threshold: float,
) -> None:
    state.concentration_sample_count += 1
    if state.max_concentration is None or concentration > state.max_concentration:
        state.max_concentration = concentration
    if state.first_gas_detected_time_sec is None and concentration >= gas_threshold:
        state.first_gas_detected_time_sec = now_sec


def record_signal(state: BenchmarkState, field_name: str, now_sec: float) -> None:
    if getattr(state, field_name) is None:
        setattr(state, field_name, now_sec)


def finalize_report(state: BenchmarkState, *, end_time_sec: float) -> dict[str, Any]:
    duration_sec = max(0.0, end_time_sec - state.start_time_sec)
    source_found = state.source_found_time_sec is not None
    tracking_handoff_failed = state.tracking_handoff_failed_time_sec is not None
    report = {
        "start_time_sec": state.start_time_sec,
        "end_time_sec": end_time_sec,
        "duration_sec": duration_sec,
        "mode_transition_count": state.mode_transition_count,
        "latest_mode": state.latest_mode,
        "first_mode_time_by_name": state.first_mode_time_by_name,
        "concentration_sample_count": state.concentration_sample_count,
        "max_concentration": state.max_concentration,
        "first_gas_detected_time_sec": state.first_gas_detected_time_sec,
        "map_frozen_time_sec": state.map_frozen_time_sec,
        "tracking_handoff_complete_time_sec": state.tracking_handoff_complete_time_sec,
        "tracking_handoff_failed_time_sec": state.tracking_handoff_failed_time_sec,
        "source_found_time_sec": state.source_found_time_sec,
        "source_found": source_found,
        "tracking_handoff_failed": tracking_handoff_failed,
        "source_found_latency_sec": None,
    }
    if source_found:
        report["source_found_latency_sec"] = state.source_found_time_sec - state.start_time_sec
    return report


class AutonomyEvalNode(Node):
    def __init__(
        self,
        *,
        gas_threshold: float,
    ) -> None:
        super().__init__("autonomy_eval_node")
        self._gas_threshold = gas_threshold
        self.state = BenchmarkState(start_time_sec=self._now_sec())

        self.create_subscription(String, "/robot_mode", self._mode_cb, 10)
        self.create_subscription(Float32, "/gas_concentration", self._gas_cb, 10)
        self.create_subscription(Bool, "/map_frozen", self._map_frozen_cb, 10)
        self.create_subscription(Bool, "/tracking_handoff_complete", self._handoff_complete_cb, 10)
        self.create_subscription(Bool, "/tracking_handoff_failed", self._handoff_failed_cb, 10)
        self.create_subscription(Bool, "/source_found", self._source_found_cb, 10)

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _mode_cb(self, msg: String) -> None:
        record_mode_sample(self.state, msg.data, self._now_sec())

    def _gas_cb(self, msg: Float32) -> None:
        record_concentration_sample(
            self.state,
            float(msg.data),
            self._now_sec(),
            gas_threshold=self._gas_threshold,
        )

    def _map_frozen_cb(self, msg: Bool) -> None:
        if msg.data:
            record_signal(self.state, "map_frozen_time_sec", self._now_sec())

    def _handoff_complete_cb(self, msg: Bool) -> None:
        if msg.data:
            record_signal(self.state, "tracking_handoff_complete_time_sec", self._now_sec())

    def _handoff_failed_cb(self, msg: Bool) -> None:
        if msg.data:
            record_signal(self.state, "tracking_handoff_failed_time_sec", self._now_sec())

    def _source_found_cb(self, msg: Bool) -> None:
        if msg.data:
            record_signal(self.state, "source_found_time_sec", self._now_sec())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect autonomy benchmark metrics from ROS topics.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Collection timeout in seconds.")
    parser.add_argument("--gas-threshold", type=float, default=0.5, help="Detection threshold for first gas hit.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/h2track_autonomy_metrics.json"),
        help="Path to write JSON report.",
    )
    parser.add_argument(
        "--stop-on-source-found",
        action="store_true",
        help="Stop collection early once /source_found=true is observed.",
    )
    parser.add_argument(
        "--require-source-found",
        action="store_true",
        help="Return non-zero if source_found was not observed within timeout.",
    )
    parser.add_argument(
        "--fail-on-handoff-failed",
        action="store_true",
        help="Return non-zero if tracking_handoff_failed was observed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    rclpy.init(args=argv)
    node = AutonomyEvalNode(gas_threshold=args.gas_threshold)

    deadline_sec = node.state.start_time_sec + max(1.0, args.timeout)
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)
            now_sec = node.get_clock().now().nanoseconds / 1e9
            if args.stop_on_source_found and node.state.source_found_time_sec is not None:
                break
            if now_sec >= deadline_sec:
                break
    finally:
        end_time_sec = node.get_clock().now().nanoseconds / 1e9
        report = finalize_report(node.state, end_time_sec=end_time_sec)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"autonomy_eval report: {args.output}")
        print(f"duration_sec={report['duration_sec']:.2f}")
        print(f"latest_mode={report['latest_mode']}")
        print(f"mode_transition_count={report['mode_transition_count']}")
        print(f"max_concentration={report['max_concentration']}")
        print(f"source_found={report['source_found']}")
        print(f"tracking_handoff_failed={report['tracking_handoff_failed']}")

        rc = 0
        if args.require_source_found and not report["source_found"]:
            rc = 2
        if args.fail_on_handoff_failed and report["tracking_handoff_failed"]:
            rc = 3 if rc == 0 else rc
        node.destroy_node()
        rclpy.shutdown()
        return rc


if __name__ == "__main__":
    raise SystemExit(main())

