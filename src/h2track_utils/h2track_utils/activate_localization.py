#!/usr/bin/env python3
"""Script to activate AMCL and map_server lifecycle nodes."""

import logging

import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition

logger = logging.getLogger(__name__)


def activate_node(node, node_name):
    """Activate a lifecycle node."""
    client = node.create_client(ChangeState, f'/{node_name}/change_state')

    if not client.wait_for_service(timeout_sec=5.0):
        logger.warning("Service /%s/change_state not available", node_name)
        return False

    # Configure
    request = ChangeState.Request()
    request.transition = Transition(id=Transition.TRANSITION_CONFIGURE)
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    if not future.done() or not future.result().success:
        logger.warning("Failed to configure %s", node_name)
        return False
    logger.info("%s configured", node_name)

    # Activate
    request.transition = Transition(id=Transition.TRANSITION_ACTIVATE)
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    if not future.done() or not future.result().success:
        logger.warning("Failed to activate %s", node_name)
        return False
    logger.info("%s activated", node_name)
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    rclpy.init()
    node = Node('localization_activator')

    logger.info("Activating localization nodes")

    # Activate map_server first
    activate_node(node, 'map_server')

    # Then activate AMCL
    activate_node(node, 'amcl')

    logger.info("Done")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
