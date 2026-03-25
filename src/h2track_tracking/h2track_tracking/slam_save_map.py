"""Save SLAM map via nav2_map_server SaveMap service."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import rclpy
from rclpy.node import Node
from nav2_msgs.srv import SaveMap


def build_save_map_request(
    *,
    output_path: str,
    map_topic: str,
    image_format: str,
    map_mode: str,
    free_thresh: float,
    occupied_thresh: float,
) -> SaveMap.Request:
    request = SaveMap.Request()
    request.map_url = output_path
    request.map_topic = map_topic
    request.image_format = image_format
    request.map_mode = map_mode
    request.free_thresh = float(free_thresh)
    request.occupied_thresh = float(occupied_thresh)
    return request


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save map from SLAM/map topic.")
    parser.add_argument("--output", required=True, help="Output path prefix, e.g. /tmp/warehouse_map")
    parser.add_argument("--service", default="/map_saver/save_map", help="SaveMap service name")
    parser.add_argument("--map-topic", default="/map", help="Map topic name")
    parser.add_argument("--image-format", default="pgm", choices=["pgm", "png", "bmp"])
    parser.add_argument("--map-mode", default="trinary", choices=["trinary", "scale", "raw"])
    parser.add_argument("--free-thresh", type=float, default=0.25)
    parser.add_argument("--occupied-thresh", type=float, default=0.65)
    parser.add_argument("--timeout", type=float, default=15.0, help="Service wait timeout (seconds)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    rclpy.init(args=None)
    node = Node("slam_save_map_client")
    try:
        client = node.create_client(SaveMap, args.service)
        if not client.wait_for_service(timeout_sec=float(args.timeout)):
            node.get_logger().error(f"SaveMap service unavailable: {args.service}")
            return 1

        request = build_save_map_request(
            output_path=args.output,
            map_topic=args.map_topic,
            image_format=args.image_format,
            map_mode=args.map_mode,
            free_thresh=args.free_thresh,
            occupied_thresh=args.occupied_thresh,
        )
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=float(args.timeout))
        if not future.done():
            node.get_logger().error("SaveMap service call timed out")
            return 1
        response = future.result()
        if response is None or not response.result:
            node.get_logger().error("SaveMap service returned failure")
            return 1
        node.get_logger().info(f"Map saved: {args.output}.yaml / {args.output}.{args.image_format}")
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
