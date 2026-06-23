#!/bin/env bash
# Clean up all stale ROS/Gazebo processes that interfere with launches.
# Use this when spawn_entity hangs, TF trees are disconnected, or
# "nodes in the graph share an exact name" warnings appear.
#
# Symptoms that call for running this:
#   - spawn_entity.py stuck on "Waiting for entity xml on robot_description"
#   - gzserver starts but produces no output after the version banner
#   - "Unable to start server[bind: Address already in use]" from Gazebo
#   - Duplicate node names in `ros2 node list` output
#   - TF errors: "not part of the same tree" despite robot_state_publisher running
#
# Root cause: prior launch attempts leave orphan processes (gzserver,
# robot_state_publisher, spawn_entity, nav2 nodes, pytest) that hold
# DDS graph entries and Gazebo's port 11345.

set -u

PATTERNS=(
    "pytest"
    "gzserver" "gzclient" "gazebo"
    "robot_state_publisher"
    "spawn_entity"
    "static_transform_publisher"
    "gaden_environment" "gaden_player" "gaden_sensor_gate" "gaden_adapter"
    "simulated_anemometer" "simulated_gas_sensor"
    "anemometer_adapter"
    "particle_filter_node"
    "bt_node_runner"
    "controller_server" "planner_server" "bt_navigator"
    "behavior_server" "smoother_server"
    "lifecycle_manager"
    "map_server" "amcl"
    "rviz2"
    "ros2 topic echo"
    "ros2 launch"
)

echo "Killing stale ROS/Gazebo processes..."
for pat in "${PATTERNS[@]}"; do
    pids=$(pgrep -f "$pat" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "  $pat: $(echo $pids | tr '\n' ' ')"
        kill -9 $pids 2>/dev/null || true
    fi
done

# Also kill anything listening on Gazebo's default port
gz_port_pids=$(lsof -ti :11345 2>/dev/null || true)
if [ -n "$gz_port_pids" ]; then
    echo "  port 11345 holders: $gz_port_pids"
    kill -9 $gz_port_pids 2>/dev/null || true
fi

sleep 3

# Restart ROS 2 daemon to flush stale DDS discovery cache
if command -v ros2 >/dev/null 2>&1; then
    echo "Restarting ros2 daemon..."
    ros2 daemon stop >/dev/null 2>&1 || true
    sleep 2
    ros2 daemon start >/dev/null 2>&1 || true
    sleep 2
fi

# Verify
remaining=$(pgrep -f "gzserver|robot_state_publisher|spawn_entity|particle_filter|bt_node_runner|anemometer_adapter|gaden_" 2>/dev/null || true)
if [ -n "$remaining" ]; then
    echo "WARNING: still running: $remaining"
else
    echo "All clean."
fi
