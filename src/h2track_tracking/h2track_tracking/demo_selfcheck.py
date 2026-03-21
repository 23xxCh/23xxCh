"""Demo-oriented runtime self-check helpers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Iterable
import time

from lifecycle_msgs.srv import GetState
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener


REQUIRED_NAV2_NODES = (
    "map_server",
    "amcl",
    "controller_server",
    "planner_server",
    "bt_navigator",
)
REQUIRED_DEMO_NODES = (
    "mission_manager_node",
    "gaden_adapter_node",
    "gaden_sensor_gate_node",
)
REQUIRED_TOPICS = (
    "/odom",
    "/scan",
    "/gas_concentration",
)
REQUIRED_TF_EDGES = (
    ("map", "odom"),
    ("odom", "base_link"),
    ("gaden_map", "base_link"),
)
REQUIRED_ACTIVE_LIFECYCLE_NODES = (
    "amcl",
    "controller_server",
    "planner_server",
    "bt_navigator",
)


@dataclass(frozen=True)
class DemoHealthReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeSnapshot:
    nodes: set[str] = field(default_factory=set)
    topics: set[str] = field(default_factory=set)
    tf_edges: set[tuple[str, str]] = field(default_factory=set)
    active_lifecycle_nodes: set[str] = field(default_factory=set)


def _normalize_names(names: Iterable[str]) -> set[str]:
    return {name.lstrip("/") for name in names}


def merge_runtime_samples(samples: Iterable[RuntimeSnapshot]) -> RuntimeSnapshot:
    merged = RuntimeSnapshot()
    for sample in samples:
        merged = RuntimeSnapshot(
            nodes=merged.nodes | _normalize_names(sample.nodes),
            topics=merged.topics | set(sample.topics),
            tf_edges=merged.tf_edges | set(sample.tf_edges),
            active_lifecycle_nodes=merged.active_lifecycle_nodes | _normalize_names(sample.active_lifecycle_nodes),
        )
    return merged


def evaluate_demo_health(
    nodes: Iterable[str],
    topics: Iterable[str],
    tf_edges: Iterable[tuple[str, str]],
    active_lifecycle_nodes: Iterable[str],
) -> DemoHealthReport:
    node_set = _normalize_names(nodes)
    topic_set = set(topics)
    tf_edge_set = set(tf_edges)
    active_set = _normalize_names(active_lifecycle_nodes)
    errors: list[str] = []

    missing_nav2 = sorted(set(REQUIRED_NAV2_NODES) - node_set)
    if missing_nav2:
        errors.append(f"Missing Nav2 nodes: {', '.join(missing_nav2)}")

    missing_demo_nodes = sorted(set(REQUIRED_DEMO_NODES) - node_set)
    if missing_demo_nodes:
        errors.append(f"Missing demo nodes: {', '.join(missing_demo_nodes)}")

    missing_topics = sorted(set(REQUIRED_TOPICS) - topic_set)
    if missing_topics:
        errors.append(f"Missing topics: {', '.join(missing_topics)}")

    missing_tf = sorted(set(REQUIRED_TF_EDGES) - tf_edge_set)
    if missing_tf:
        pretty_edges = ", ".join(f"{parent} -> {child}" for parent, child in missing_tf)
        errors.append(f"Missing TF edges: {pretty_edges}")

    inactive_nodes = sorted(set(REQUIRED_ACTIVE_LIFECYCLE_NODES) - active_set)
    if inactive_nodes:
        errors.append(f"Nav2 lifecycle nodes not active: {', '.join(inactive_nodes)}")

    return DemoHealthReport(ok=not errors, errors=errors, warnings=[])


class DemoSelfcheckNode(Node):
    def __init__(self) -> None:
        super().__init__("demo_selfcheck")
        self._tf_buffer = Buffer(cache_time=Duration(seconds=5.0))
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._lifecycle_clients: dict[str, object] = {}

    def collect_report(self, timeout_sec: float) -> DemoHealthReport:
        deadline = time.monotonic() + timeout_sec
        samples: list[RuntimeSnapshot] = []

        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            samples.append(self._capture_snapshot())

        if not samples:
            samples.append(self._capture_snapshot())

        merged = merge_runtime_samples(samples)
        return evaluate_demo_health(
            nodes=merged.nodes,
            topics=merged.topics,
            tf_edges=merged.tf_edges,
            active_lifecycle_nodes=merged.active_lifecycle_nodes,
        )

    def _capture_snapshot(self) -> RuntimeSnapshot:
        topic_names = {name for name, _types in self.get_topic_names_and_types()}
        tf_edges = {edge for edge in REQUIRED_TF_EDGES if self._can_transform(*edge)}
        active_nodes = {name for name in REQUIRED_ACTIVE_LIFECYCLE_NODES if self._node_is_active(name)}
        return RuntimeSnapshot(
            nodes=_normalize_names(self.get_node_names()),
            topics=topic_names,
            tf_edges=tf_edges,
            active_lifecycle_nodes=active_nodes,
        )

    def _can_transform(self, target_frame: str, source_frame: str) -> bool:
        return self._tf_buffer.can_transform(
            target_frame,
            source_frame,
            Time(),
            timeout=Duration(seconds=0.05),
        )

    def _node_is_active(self, node_name: str) -> bool:
        client = self._lifecycle_clients.get(node_name)
        if client is None:
            client = self.create_client(GetState, f"/{node_name}/get_state")
            self._lifecycle_clients[node_name] = client
        if not client.wait_for_service(timeout_sec=0.1):
            return False

        future = client.call_async(GetState.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=0.3)
        if not future.done() or future.result() is None:
            return False
        return future.result().current_state.label == "active"


def _format_report(report: DemoHealthReport) -> str:
    if report.ok:
        return "DEMO SELFCHECK OK"
    lines = ["DEMO SELFCHECK FAILED"]
    lines.extend(f"- {error}" for error in report.errors)
    lines.extend(f"- warning: {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether the stable demo stack is ready.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for graph and TF discovery.")
    args = parser.parse_args(argv)

    rclpy.init(args=None)
    node = DemoSelfcheckNode()
    try:
        report = node.collect_report(timeout_sec=args.timeout)
        print(_format_report(report))
        return 0 if report.ok else 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
