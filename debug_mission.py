#!/usr/bin/env python3
"""Debug script to check mission_manager_node state."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time


class DebugNode(Node):
    def __init__(self):
        super().__init__('debug_node')
        self.mode = None
        self.mode_count = 0
        self.create_subscription(String, '/robot_mode', self.mode_cb, 10)

        # Timer to print status
        self.create_timer(2.0, self.print_status)

    def mode_cb(self, msg):
        self.mode = msg.data
        self.mode_count += 1
        self.get_logger().info(f"Received robot_mode: {msg.data}")

    def print_status(self):
        if self.mode is None:
            self.get_logger().warn("No robot_mode received yet!")
        else:
            self.get_logger().info(f"Current mode: {self.mode}, count: {self.mode_count}")


def main():
    rclpy.init()
    node = DebugNode()

    print("Monitoring /robot_mode for 30 seconds...")
    print("If no messages received, mission_manager_node control loop may be stuck.")

    start_time = time.time()
    try:
        while time.time() - start_time < 30:
            rclpy.spin_once(node, timeout_sec=0.5)
    except KeyboardInterrupt:
        pass

    print(f"\nFinal count: {node.mode_count} messages received")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
