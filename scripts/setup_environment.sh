#!/bin/bash
# H2Track + Fishbot 环境设置脚本
# 用法: source setup_environment.sh

set -e

echo "=========================================="
echo "H2Track + Fishbot 环境设置"
echo "=========================================="

# ROS2 Humble
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo "✓ ROS2 Humble 已加载"
else
    echo "✗ ROS2 Humble 未找到"
    return 1
fi

# GADEN 工作空间
GADEN_WS="/home/user/gaden_ws"
if [ -f "$GADEN_WS/install/setup.bash" ]; then
    source $GADEN_WS/install/setup.bash
    echo "✓ GADEN 工作空间已加载"
else
    echo "⚠ GADEN 工作空间未找到"
fi

# Fishbot 工作空间
FISHBOT_WS="/home/user/fishbot/fishbot_ws"
if [ -f "$FISHBOT_WS/install/setup.bash" ]; then
    source $FISHBOT_WS/install/setup.bash
    echo "✓ Fishbot 工作空间已加载"
else
    echo "⚠ Fishbot 工作空间未找到"
fi

# H2Track 工作空间
H2TRACK_WS="/home/user/h2track-xian"
if [ -f "$H2TRACK_WS/install/setup.bash" ]; then
    source $H2TRACK_WS/install/setup.bash
    echo "✓ H2Track 工作空间已加载"
else
    echo "✗ H2Track 工作空间未找到"
    return 1
fi

# 设置环境变量
export ROS_DOMAIN_ID=0
export RCUTILS_COLORIZED_OUTPUT=1

echo ""
echo "=========================================="
echo "环境设置完成！"
echo "=========================================="
echo ""
echo "可用命令:"
echo "  ros2 launch h2track_tracking fishbot_integration.launch.py"
echo "  ros2 run h2track_tracking gas_sensor_node"
echo "  ros2 run h2track_tracking mission_manager_node"
echo ""
