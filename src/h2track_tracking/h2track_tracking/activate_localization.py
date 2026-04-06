#!/usr/bin/env python3
"""Script to activate AMCL and map_server lifecycle nodes."""

import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition
import time


def activate_node(node, node_name):
    """Activate a lifecycle node."""
    client = node.create_client(ChangeState, f'/{node_name}/change_state')

    if not client.wait_for_service(timeout_sec=5.0):
        print(f"[WARN] Service /{node_name}/change_state not available")
        return False

    # Configure
    request = ChangeState.Request()
    request.transition = Transition(id=Transition.TRANSITION_CONFIGURE)
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    if not future.done() or not future.result().success:
        print(f"[WARN] Failed to configure {node_name}")
        return False
    print(f"[OK] {node_name} configured")

    # Activate
    request.transition = Transition(id=Transition.TRANSITION_ACTIVATE)
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    if not future.done() or not future.result().success:
        print(f"[WARN] Failed to activate {node_name}")
        return False
    print(f"[OK] {node_name} activated")
    return True


def main():
    rclpy.init()
    node = Node('localization_activator')

    print("=== Activating localization nodes ===")

    # Activate map_server first
    activate_node(node, 'map_server')

    # Then activate AMCL
    activate_node(node, 'amcl')

    print("\n=== Done ===")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
