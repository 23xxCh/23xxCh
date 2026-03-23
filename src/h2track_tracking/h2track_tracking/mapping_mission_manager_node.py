from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String

from .mission_logic import ExplorationMissionConfig, ExplorationMissionStateMachine, MissionMode


class MappingMissionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("mapping_mission_manager_node")
        self.declare_parameter("enter_threshold", 1.5)
        self.declare_parameter("exit_threshold", 0.6)
        self.declare_parameter("confirm_samples", 2)
        self.declare_parameter("min_explore_samples", 0)

        config = ExplorationMissionConfig(
            enter_threshold=float(self.get_parameter("enter_threshold").value),
            exit_threshold=float(self.get_parameter("exit_threshold").value),
            confirm_samples=int(self.get_parameter("confirm_samples").value),
            min_explore_samples=int(self.get_parameter("min_explore_samples").value),
        )
        self._machine = ExplorationMissionStateMachine(config)
        self._freeze_requested = False

        self._mode_pub = self.create_publisher(String, "/robot_mode", 10)
        self._exploration_enabled_pub = self.create_publisher(Bool, "/exploration_enabled", 10)
        self._freeze_request_pub = self.create_publisher(Bool, "/freeze_map_requested", 10)
        self.create_subscription(Float32, "/gas_concentration", self._concentration_callback, 10)

        self._publish_mode_and_controls(self._machine.mode)

    def _publish_mode_and_controls(self, mode: MissionMode) -> None:
        self._mode_pub.publish(String(data=mode.name))
        exploration_enabled = mode is MissionMode.EXPLORE_MAPPING
        self._exploration_enabled_pub.publish(Bool(data=exploration_enabled))

        if mode is MissionMode.FREEZE_AND_RELOCALIZE and not self._freeze_requested:
            self._freeze_request_pub.publish(Bool(data=True))
            self._freeze_requested = True

    def _concentration_callback(self, msg: Float32) -> None:
        previous_mode = self._machine.mode
        mode = self._machine.update(float(msg.data))
        if mode is not previous_mode:
            self._publish_mode_and_controls(mode)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MappingMissionManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
