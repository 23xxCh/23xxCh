# H2Track — 氢气泄漏源自主追踪仿真 | Hydrogen Gas Source Tracking Simulation

[English](#english) | [中文](#中文)

---

# English

## Overview

H2Track is a ROS 2 Humble simulation workspace for autonomous hydrogen (H2) gas source localization. A robot patrols a Gazebo environment, detects gas concentration changes, and uses gradient-based tracking algorithms to locate the hydrogen leak source.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Behavior Tree (py_trees)              │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ Tracker  │  │ Costmap  │  │      Nav2Client       │  │
│  │(SurgeCast│  │  Guard   │  │  (NavigateToPose)     │  │
│  │ +Fusion) │  │          │  │                       │  │
│  └──────────┘  └──────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              Mission State Machine                       │
│  PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND     │
├─────────────────────────────────────────────────────────┤
│  Gas Model  │  Nav2 Stack  │  AMCL/SLAM  │  Costmap    │
│  (GADEN or  │  Lifecycle   │  Localization│  Inflation  │
│   Simulated)│  Nodes       │             │             │
├─────────────────────────────────────────────────────────┤
│              Gazebo Classic + URDF Robot                 │
└─────────────────────────────────────────────────────────┘
```

### Eight ROS 2 Packages

| Package | Build Type | Purpose |
|---------|------------|---------|
| `h2track_bringup` | ament_cmake | Launch files, scene configs, Gazebo worlds |
| `h2track_tracking` | ament_python | Tracking logic, gas model, mission state machine, BT pipeline |
| `h2track_interfaces` | ament_cmake | Custom message types (RobotState, SourceEstimate, RoleAssignment) |
| `h2track_description` | ament_cmake | URDF/xacro robot description |
| `h2track_gas_sim` | ament_python | Gas simulation (gas_field_node, GADEN adapter) |
| `h2track_web` | ament_python | FastAPI web console, REST/WebSocket API |
| `h2track_utils` | ament_python | Shared utilities (Nav2Lifecycle, Pose2D, demo tools) |
| `h2track_sim` | ament_cmake | Metapackage (depends on bringup + description) |

### Key Algorithms

- **Surge-Cast**: Wind-aware two-phase algorithm (SURGE upwind + CAST lateral search)
- **Particle Filter**: Probabilistic gas source localization with vectorized operations
- **Wind Estimator**: Infers wind direction from concentration gradients
- **Algorithm Fusion**: Combines Surge-Cast and Particle Filter estimates (weighted/switching/cascade modes)

## Quick Start

### Prerequisites

- ROS 2 Humble
- Gazebo Classic 11
- Nav2 stack
- (Optional) GADEN workspace — set `GADEN_WS` env var (defaults to `/home/user/gaden_ws`)

### Build

```bash
source /opt/ros/humble/setup.bash
source $GADEN_WS/install/setup.bash  # Required for GADEN mode
colcon build
```

### Run Simulation

```bash
source install/setup.bash

# With simplified gas model (no GADEN dependency)
ros2 launch h2track_bringup bringup.launch.py scene:=baseline use_gaden:=false use_bt:=true

# With GADEN realistic gas simulation
ros2 launch h2track_bringup bringup.launch.py scene:=warehouse use_gaden:=true use_bt:=true
```

### Run Tests

```bash
# Unit tests (no ROS required)
python3 -m pytest src/h2track_tracking/test/ src/h2track_bringup/test/ -v

# With coverage
python3 -m pytest src/h2track_tracking/test/ --cov=h2track_tracking --cov-report=term-missing
```

## Standard Demo Rehearsal Flow

1. **Prep**: Clear stale processes
   ```bash
   ros2 run h2track_utils demo_prep --scene warehouse
   ```

2. **Launch**: Start the simulation
   ```bash
   ros2 launch h2track_bringup demo.launch.py
   ```

3. **Self-check**: Verify the stack (separate terminal)
   ```bash
   ros2 run h2track_utils demo_selfcheck --timeout 5.0
   ```

If any step fails, do not start the formal demo.

## Mission State Machine

The robot transitions through four modes:

| Mode | Description | Trigger |
|------|-------------|---------|
| **PATROL** | Navigate waypoints via Nav2 | Initial state |
| **SEEK_CONFIRM** | Verify gas detection | Concentration >= `enter_threshold` |
| **SEEK_TRACK** | Gradient ascent toward source (Surge-Cast + Fusion) | Confirmed detection |
| **SOURCE_FOUND** | Publish estimated source position | Near source with high concentration |

## Scene Configuration

Scenes are defined in `src/h2track_bringup/scenes/<scene>/scene.yaml`:

```yaml
scene_name: baseline
use_gaden: true
use_slam: false
localizer_node: amcl
gas_source: {x: -4.0, y: 1.95}
gaden:
  project_path: install/test_env/share/test_env/scenarios/Exp_C/environment_configurations/config1
  sensor_frame: gas_sensor_link
gas_field:
  source_strength: 120.0
  decay_rate: 0.55
  wind_x: 0.4
  wind_y: 0.0
  gas_type: "H2"
mission_manager:
  enter_threshold: 5.0
  exit_threshold: 2.0
  source_threshold: 20.0
  source_radius: 1.0
  source_hold_steps: 2
fusion:
  use_fusion: true
  fusion_mode: weighted
  pf_weight: 0.3
  surge_weight: 0.7
```

> **Note**: GADEN `project_path` values are relative to `$GADEN_WS`. Set the `GADEN_WS` environment variable to override the default.

## Available Scenes

| Scene | Size | Gas Sim | Localization | Description |
|-------|------|---------|--------------|-------------|
| `baseline` | 10×10m | GADEN or simulated | AMCL | H2Track Lab with L-shaped corridors and obstacles |
| `warehouse` | ~8×6m | GADEN | SLAM | AWS RoboMaker Small Warehouse with shelves |
| `maze` | 10×6m | GADEN | AMCL | Maze corridors from GADEN 10x6_maze STL models |
| `snake` | 10×6m | GADEN | AMCL | Serpentine corridors from GADEN 10x6_snake STL models |
| `office` | ~10×10m | Simulated only | AMCL | Office with partitions, storage room, and cabinets |
| `benchmark` | ~8×6m | GADEN | AMCL | Standardized testing scene for algorithm comparison |

## Key ROS Topics

| Topic | Type | Purpose |
|-------|------|---------|
| `/gas_concentration` | `Float32` | Gas sensor reading (normalized) |
| `/robot_mode` | `String` | Current mission mode |
| `/source_found` | `Bool` | Source detection signal |
| `/estimated_source` | `PoseWithCovarianceStamped` | Source estimate with covariance |
| `/estimated_source_pose` | `PoseStamped` | Estimated source position |
| `/particle_cloud` | `PoseArray` | Particle positions for visualization |
| `/estimated_wind` | `String` | Wind vector: "wind_x,wind_y,confidence" |
| `/fusion_state` | `String` | Fusion state: "mode,pf_contrib,surge_contrib,target_x,target_y" |

## Supported Gases

| Gas | Formula | Behavior | Sensor Height | Alarm Threshold |
|-----|---------|----------|---------------|-----------------|
| Hydrogen | H2 | Rising (light) | 1.5m | 250 ppm |
| Methane | CH4 | Rising (light) | 1.2m | 5000 ppm |
| Carbon Monoxide | CO | Neutral | 0.5m | 50 ppm |
| Propane | C3H8 | Sinking (heavy) | 0.3m | 1000 ppm |

## Multi-Scene Regression Testing

```bash
# Single scene
ros2 run h2track_utils demo_regression --scene warehouse --rounds 10 --run-timeout-sec 110

# Multiple scenes in sequence
ros2 run h2track_utils demo_regression --scenes warehouse,maze,snake --rounds 3 --run-timeout-sec 120

# Per-scene configuration via YAML
ros2 run h2track_utils demo_regression \
  --scenes warehouse,maze \
  --scene-config scene_config.yaml

# Auto-detect use_gaden from scene.yaml
ros2 run h2track_utils demo_regression --scenes baseline,warehouse --rounds 5
```

Results are organized per-scene under `/tmp/h2track_regression_logs/` with an `overall_summary.json`.

## Web Console

```bash
ros2 run h2track_web demo_web_server --host 0.0.0.0 --port 18080
# Open http://<IP>:18080 in browser
```

## License

MIT License

---

# 中文

## 项目概述

H2Track 是一个基于 ROS 2 Humble 的氢气（H2）泄漏源自主定位仿真工作区。机器人在 Gazebo 环境中巡逻，检测气体浓度变化，并使用基于梯度的追踪算法定位氢气泄漏源。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   行为树 (py_trees)                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ 追踪器   │  │ 防撞检查 │  │     Nav2 导航客户端    │  │
│  │(SurgeCast│  │(Costmap  │  │  (NavigateToPose)     │  │
│  │ +融合)   │  │ Guard)   │  │                       │  │
│  └──────────┘  └──────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  任务状态机                               │
│  巡逻 → 确认检测 → 追踪源头 → 找到源头                    │
│  PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND      │
├─────────────────────────────────────────────────────────┤
│  气体模型  │  Nav2 导航栈  │  AMCL/SLAM  │  代价地图      │
│ (GADEN或  │  生命周期节点 │  定位       │  膨胀层       │
│  仿真模式) │             │             │             │
├─────────────────────────────────────────────────────────┤
│               Gazebo Classic + 机器人 URDF                │
└─────────────────────────────────────────────────────────┘
```

### 八个 ROS 2 功能包

| 功能包 | 构建类型 | 用途 |
|--------|----------|------|
| `h2track_bringup` | ament_cmake | 启动文件、场景配置、Gazebo 世界 |
| `h2track_tracking` | ament_python | 追踪逻辑、气体模型、任务状态机、行为树 |
| `h2track_interfaces` | ament_cmake | 自定义消息类型（RobotState、SourceEstimate、RoleAssignment） |
| `h2track_description` | ament_cmake | URDF/xacro 机器人描述 |
| `h2track_gas_sim` | ament_python | 气体仿真（gas_field_node、GADEN 适配器） |
| `h2track_web` | ament_python | FastAPI 网页控制台、REST/WebSocket API |
| `h2track_utils` | ament_python | 共享工具（Nav2Lifecycle、Pose2D、演示工具） |
| `h2track_sim` | ament_cmake | 元包（依赖 bringup + description） |

### 核心算法

- **Surge-Cast（冲刺-扫射）**：风感知的两阶段算法，SURGE 逆风追踪 + CAST 横向搜索
- **粒子滤波器**：基于概率的气体源定位，支持向量化加速
- **风向估计器**：从浓度梯度推断风向
- **算法融合**：结合 Surge-Cast 和粒子滤波器的估计结果（加权/切换/级联三种模式）

## 快速开始

### 环境要求

- ROS 2 Humble
- Gazebo Classic 11
- Nav2 导航栈
- （可选）GADEN 工作区 — 设置 `GADEN_WS` 环境变量（默认 `/home/user/gaden_ws`）

### 构建

```bash
source /opt/ros/humble/setup.bash
source $GADEN_WS/install/setup.bash  # GADEN 模式需要
colcon build
```

### 运行仿真

```bash
source install/setup.bash

# 使用简化气体模型（无需 GADEN）
ros2 launch h2track_bringup bringup.launch.py scene:=baseline use_gaden:=false use_bt:=true

# 使用 GADEN 真实气体仿真
ros2 launch h2track_bringup bringup.launch.py scene:=warehouse use_gaden:=true use_bt:=true
```

### 运行测试

```bash
# 单元测试（不需要 ROS 环境）
python3 -m pytest src/h2track_tracking/test/ src/h2track_bringup/test/ -v

# 带覆盖率
python3 -m pytest src/h2track_tracking/test/ --cov=h2track_tracking --cov-report=term-missing
```

## 任务状态机

机器人依次经历四个阶段：

| 阶段 | 说明 | 切换条件 |
|------|------|----------|
| **PATROL（巡逻）** | 按航点导航 | 初始状态 |
| **SEEK_CONFIRM（确认）** | 验证气体检测 | 浓度 >= `enter_threshold` |
| **SEEK_TRACK（追踪）** | 沿浓度梯度追踪（Surge-Cast + 融合） | 确认检测到气体 |
| **SOURCE_FOUND（找到源）** | 发布估计的源位置 | 靠近源且浓度高 |

## 场景配置

场景定义在 `src/h2track_bringup/scenes/<scene>/scene.yaml`：

```yaml
scene_name: baseline
use_gaden: true
use_slam: false
localizer_node: amcl
gas_source: {x: -4.0, y: 1.95}          # 气体源位置
gaden:
  project_path: install/test_env/share/test_env/scenarios/Exp_C/environment_configurations/config1
  sensor_frame: gas_sensor_link           # 传感器坐标系
gas_field:
  source_strength: 120.0                  # 源强度
  decay_rate: 0.55                        # 衰减率
  wind_x: 0.4                             # 风向 X 分量
  wind_y: 0.0                             # 风向 Y 分量
  gas_type: "H2"                          # 气体类型
mission_manager:
  enter_threshold: 5.0                    # 进入确认阈值
  exit_threshold: 2.0                     # 退出阈值
  source_threshold: 20.0                  # 源检测阈值
  source_radius: 1.0                      # 源判定半径（米）
  source_hold_steps: 2                    # 连续命中次数
fusion:
  use_fusion: true                        # 启用算法融合
  fusion_mode: weighted                   # 融合模式
  pf_weight: 0.3                          # 粒子滤波器权重
  surge_weight: 0.7                       # Surge-Cast 权重
```

> **注意**：GADEN `project_path` 为相对于 `$GADEN_WS` 的路径。设置 `GADEN_WS` 环境变量可覆盖默认值。

## 可用场景

| 场景 | 尺寸 | 气体仿真 | 定位方式 | 说明 |
|------|------|----------|----------|------|
| `baseline` | 10×10m | GADEN 或仿真 | AMCL | H2Track 实验室，L 形走廊和障碍物 |
| `warehouse` | ~8×6m | GADEN | SLAM | AWS RoboMaker 小型仓库，货架环境 |
| `maze` | 10×6m | GADEN | AMCL | 迷宫走廊，使用 GADEN 10x6_maze STL 模型 |
| `snake` | 10×6m | GADEN | AMCL | 蛇形走廊，使用 GADEN 10x6_snake STL 模型 |
| `office` | ~10×10m | 仅仿真 | AMCL | 办公室隔间、储物间、文件柜 |
| `benchmark` | ~8×6m | GADEN | AMCL | 标准化测试场景，用于算法对比 |

## 关键 ROS 话题

| 话题 | 类型 | 用途 |
|------|------|------|
| `/gas_concentration` | `Float32` | 气体传感器读数（归一化） |
| `/robot_mode` | `String` | 当前任务模式 |
| `/source_found` | `Bool` | 源检测信号 |
| `/estimated_source` | `PoseWithCovarianceStamped` | 带协方差的源估计 |
| `/estimated_source_pose` | `PoseStamped` | 估计的源位置 |
| `/particle_cloud` | `PoseArray` | 粒子位置可视化 |
| `/estimated_wind` | `String` | 风向量："wind_x,wind_y,confidence" |
| `/fusion_state` | `String` | 融合状态："mode,pf_contrib,surge_contrib,target_x,target_y" |

## 支持的气体类型

| 气体 | 分子式 | 行为 | 传感器高度 | 报警阈值 |
|------|--------|------|-----------|----------|
| 氢气 | H2 | 上升（轻） | 1.5m | 250 ppm |
| 甲烷 | CH4 | 上升（轻） | 1.2m | 5000 ppm |
| 一氧化碳 | CO | 中性 | 0.5m | 50 ppm |
| 丙烷 | C3H8 | 下沉（重） | 0.3m | 1000 ppm |

## 多场景回归测试

```bash
# 单场景测试
ros2 run h2track_utils demo_regression --scene warehouse --rounds 10 --run-timeout-sec 110

# 多场景连续测试
ros2 run h2track_utils demo_regression --scenes warehouse,maze,snake --rounds 3 --run-timeout-sec 120

# 通过 YAML 配置每个场景
ros2 run h2track_utils demo_regression \
  --scenes warehouse,maze \
  --scene-config scene_config.yaml

# 自动检测 use_gaden
ros2 run h2track_utils demo_regression --scenes baseline,warehouse --rounds 5
```

结果按场景组织在 `/tmp/h2track_regression_logs/` 下，包含 `overall_summary.json` 汇总。

## Web 控制台

```bash
ros2 run h2track_web demo_web_server --host 0.0.0.0 --port 18080
# 浏览器打开 http://<IP>:18080
```

## 许可证

MIT License
