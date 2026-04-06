#!/usr/bin/env python3
"""Monitor robot state for debugging - extended version."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
import time


class MonitorNode(Node):
    def __init__(self):
        super().__init__('monitor_node')
        self.gas_concentration = None
        self.robot_mode = None
        self.robot_position_amcl = None
        self.gas_count = 0
        self.mode_count = 0
        self.mode_changes = []

        self.create_subscription(Float32, '/gas_concentration', self.gas_cb, 10)
        self.create_subscription(String, '/robot_mode', self.mode_cb, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.amcl_cb, 10)

    def gas_cb(self, msg):
        self.gas_concentration = msg.data
        self.gas_count += 1

    def mode_cb(self, msg):
        self.robot_mode = msg.data
        self.mode_count += 1
        self.mode_changes.append((time.time(), msg.data))

    def amcl_cb(self, msg):
        self.robot_position_amcl = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y
        )


def main():
    rclpy.init()
    node = MonitorNode()
    start_time = time.time()
    duration = 120  # 2 minutes

    print("=== 监控开始 (120秒) ===")
    print(f"{'时间':>8} | {'浓度':>8} | {'模式':>15} | {'位置(amcl)':>15} | 气体 | 模式")
    print("-" * 80)

    try:
        while time.time() - start_time < duration:
            rclpy.spin_once(node, timeout_sec=0.1)
            elapsed = time.time() - start_time
            gas = f"{node.gas_concentration:.4f}" if node.gas_concentration is not None else "N/A"
            mode = node.robot_mode or "N/A"
            pos_amcl = f"({node.robot_position_amcl[0]:.2f}, {node.robot_position_amcl[1]:.2f})" if node.robot_position_amcl else "N/A"
            print(f"{elapsed:>8.1f}s | {gas:>8} | {mode:>15} | {pos_amcl:>15} | {node.gas_count:>4} | {node.mode_count:>4}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\n=== 监控结束 ===")
    if node.mode_changes:
        print("\n模式变化历史:")
        for ts, m in node.mode_changes:
            print(f"  {ts - start_time:.1f}s: {m}")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
