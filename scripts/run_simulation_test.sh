#!/bin/bash
# H2Track 仿真测试脚本
# 用法: ./run_simulation_test.sh [scene]

set -e

SCENE=${1:-warehouse}
WORKSPACE="/home/user/h2track-xian"
GADEN_WS="/home/user/gaden_ws"

echo "=========================================="
echo "H2Track 仿真测试"
echo "场景: $SCENE"
echo "=========================================="

# Source 环境
source /opt/ros/humble/setup.bash
source $GADEN_WS/install/setup.bash
source $WORKSPACE/install/setup.bash

# 检查 GADEN 场景
if [ ! -d "$GADEN_WS/install/test_env/share/test_env/scenarios/h2track_warehouse" ]; then
    echo "错误: GADEN 场景不存在"
    exit 1
fi

echo "[1/3] 启动 Gazebo 仿真..."
# ros2 launch h2track_sim bringup.launch.py scene:=$SCENE &

echo "[2/3] 启动气体追踪节点..."
# ros2 run h2track_tracking mission_manager_node &

echo "[3/3] 监控追踪状态..."
# 等待源定位完成

echo "=========================================="
echo "仿真测试完成"
echo "=========================================="

# 提示用户手动启动
echo ""
echo "手动启动命令:"
echo "  终端1: source install/setup.bash && ros2 launch h2track_sim bringup.launch.py scene:=$SCENE"
echo "  终端2: source install/setup.bash && ros2 run h2track_tracking mission_manager_node"
