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
│  └──────────┘  └──────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              Mission State Machine                       │
│  PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND     │
├─────────────────────────────────────────────────────────┤
│  Gas Model  │  Nav2 Stack  │  AMCL/SLAM  │  Costmap    │
├─────────────────────────────────────────────────────────┤
│              Gazebo Classic + URDF Robot                 │
└─────────────────────────────────────────────────────────┘
```

### Three ROS 2 Packages

| Package | Build Type | Purpose |
|---------|------------|---------|
| `h2track_sim` | ament_cmake | Launch files, scene configs, Gazebo worlds, URDF |
| `h2track_tracking` | ament_python | Tracking logic, gas model, mission state machine, BT |
| `h2track_interfaces` | ament_cmake | Custom message types |

### Key Algorithms

- **Surge-Cast**: Wind-aware two-phase algorithm (SURGE upwind + CAST lateral search)
- **Particle Filter**: Probabilistic gas source localization with vectorized operations
- **Wind Estimator**: Infers wind direction from concentration gradients
- **Algorithm Fusion**: Combines Surge-Cast and Particle Filter estimates

## Quick Start

### Prerequisites

- ROS 2 Humble
- Gazebo Classic 11
- Nav2 stack
- (Optional) GADEN workspace at `/home/user/gaden_ws`

### Build

```bash
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash  # Required for GADEN mode
colcon build
```

### Run Simulation

```bash
source install/setup.bash

# With simplified gas model (no GADEN dependency)
ros2 launch h2track_sim bringup.launch.py scene:=baseline use_gaden:=false use_bt:=true

# With GADEN realistic gas simulation
ros2 launch h2track_sim bringup.launch.py scene:=warehouse use_gaden:=true use_bt:=true
```

### Run Tests

```bash
python3 -m pytest src/h2track_tracking/test/ -v
```

## Mission State Machine

The robot transitions through four modes:

| Mode | Description | Trigger |
|------|-------------|---------|
| **PATROL** | Navigate waypoints via Nav2 | Initial state |
| **SEEK_CONFIRM** | Verify gas detection | Concentration >= `enter_threshold` |
| **SEEK_TRACK** | Gradient ascent toward source (Surge-Cast) | Confirmed detection |
| **SOURCE_FOUND** | Publish estimated source position | Near source with high concentration |

## Scene Configuration

Scenes are defined in `src/h2track_sim/scenes/<scene>/scene.yaml`:

```yaml
scene_name: baseline
gas_source: {x: -4.0, y: 1.95}
gas_field:
  source_strength: 120.0
  decay_rate: 0.55
  wind_x: 0.4
  wind_y: 0.0
mission_manager:
  enter_threshold: 5.0
  exit_threshold: 2.0
  source_threshold: 20.0
  source_radius: 1.0
  source_hold_steps: 2
```

## Available Scenes

| Scene | Description |
|-------|-------------|
| `baseline` | H2Track Lab environment |
| `warehouse` | AWS RoboMaker Small Warehouse |

## Key ROS Topics

| Topic | Type | Purpose |
|-------|------|---------|
| `/gas_concentration` | `Float32` | Gas sensor reading (normalized) |
| `/robot_mode` | `String` | Current mission mode |
| `/source_found` | `Bool` | Source detection signal |
| `/estimated_source` | `PoseWithCovarianceStamped` | Source estimate with covariance |
| `/estimated_wind` | `String` | Wind vector: "wind_x,wind_y,confidence" |
| `/fusion_state` | `String` | Fusion state: "mode,pf_contrib,surge_contrib" |

## Supported Gases

| Gas | Formula | Sensor Height | Alarm Threshold |
|-----|---------|---------------|-----------------|
| Hydrogen | H2 | 1.5m | 250 ppm |
| Methane | CH4 | 1.2m | 5000 ppm |
| Carbon Monoxide | CO | 0.5m | 50 ppm |
| Propane | C3H8 | 0.3m | 1000 ppm |

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
│  └──────────┘  │ Guard)   │  └───────────────────────┘  │
│                └──────────┘                              │
├─────────────────────────────────────────────────────────┤
│                  任务状态机                               │
│  巡逻 → 确认检测 → 追踪源头 → 找到源头                    │
│  PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND      │
├─────────────────────────────────────────────────────────┤
│  气体模型  │  Nav2 导航栈  │  AMCL/SLAM  │  代价地图      │
├─────────────────────────────────────────────────────────┤
│               Gazebo Classic + 机器人 URDF                │
└─────────────────────────────────────────────────────────┘
```

### 三个 ROS 2 功能包

| 功能包 | 构建类型 | 用途 |
|--------|----------|------|
| `h2track_sim` | ament_cmake | 启动文件、场景配置、Gazebo 世界、URDF |
| `h2track_tracking` | ament_python | 追踪逻辑、气体模型、任务状态机、行为树 |
| `h2track_interfaces` | ament_cmake | 自定义消息类型 |

### 核心算法

- **Surge-Cast（冲刺-扫射）**：风感知的两阶段算法，SURGE 逆风追踪 + CAST 横向搜索
- **粒子滤波器**：基于概率的气体源定位，支持向量化加速
- **风向估计器**：从浓度梯度推断风向
- **算法融合**：结合 Surge-Cast 和粒子滤波器的估计结果

## 快速开始

### 环境要求

- ROS 2 Humble
- Gazebo Classic 11
- Nav2 导航栈
- （可选）GADEN 工作区 `/home/user/gaden_ws`

### 构建

```bash
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash  # GADEN 模式需要
colcon build
```

### 运行仿真

```bash
source install/setup.bash

# 使用简化气体模型（无需 GADEN）
ros2 launch h2track_sim bringup.launch.py scene:=baseline use_gaden:=false use_bt:=true

# 使用 GADEN 真实气体仿真
ros2 launch h2track_sim bringup.launch.py scene:=warehouse use_gaden:=true use_bt:=true
```

### 运行测试

```bash
python3 -m pytest src/h2track_tracking/test/ -v
```

## 任务状态机

机器人依次经历四个阶段：

| 阶段 | 说明 | 切换条件 |
|------|------|----------|
| **PATROL（巡逻）** | 按航点导航 | 初始状态 |
| **SEEK_CONFIRM（确认）** | 验证气体检测 | 浓度 >= `enter_threshold` |
| **SEEK_TRACK（追踪）** | 沿浓度梯度追踪（Surge-Cast） | 确认检测到气体 |
| **SOURCE_FOUND（找到源）** | 发布估计的源位置 | 靠近源且浓度高 |

## 场景配置

场景定义在 `src/h2track_sim/scenes/<scene>/scene.yaml`：

```yaml
scene_name: baseline
gas_source: {x: -4.0, y: 1.95}          # 气体源位置
gas_field:
  source_strength: 120.0                  # 源强度
  decay_rate: 0.55                        # 衰减率
  wind_x: 0.4                             # 风向 X 分量
  wind_y: 0.0                             # 风向 Y 分量
mission_manager:
  enter_threshold: 5.0                    # 进入确认阈值
  exit_threshold: 2.0                     # 退出阈值
  source_threshold: 20.0                  # 源检测阈值
  source_radius: 1.0                      # 源判定半径（米）
  source_hold_steps: 2                    # 连续命中次数
```

## 可用场景

| 场景 | 说明 |
|------|------|
| `baseline` | H2Track 实验室环境 |
| `warehouse` | AWS RoboMaker 小型仓库 |

## 关键 ROS 话题

| 话题 | 类型 | 用途 |
|------|------|------|
| `/gas_concentration` | `Float32` | 气体传感器读数（归一化） |
| `/robot_mode` | `String` | 当前任务模式 |
| `/source_found` | `Bool` | 源检测信号 |
| `/estimated_source` | `PoseWithCovarianceStamped` | 带协方差的源估计 |
| `/estimated_wind` | `String` | 风向量："wind_x,wind_y,confidence" |
| `/fusion_state` | `String` | 融合状态："mode,pf_contrib,surge_contrib" |

## 支持的气体类型

| 气体 | 分子式 | 传感器高度 | 报警阈值 |
|------|--------|-----------|----------|
| 氢气 | H2 | 1.5m | 250 ppm |
| 甲烷 | CH4 | 1.2m | 5000 ppm |
| 一氧化碳 | CO | 0.5m | 50 ppm |
| 丙烷 | C3H8 | 0.3m | 1000 ppm |

## 运行回归测试

```bash
# 十轮回归测试
ros2 run h2track_tracking demo_regression --scene baseline --rounds 10 --run-timeout-sec 110
```

## Web 控制台

```bash
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080
# 浏览器打开 http://<IP>:18080
```

## 许可证

MIT License
