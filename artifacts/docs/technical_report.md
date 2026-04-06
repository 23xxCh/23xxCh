# H2Track 氢气源追踪仿真系统 - 技术报告与开发报告

**版本**: 0.1.0
**日期**: 2026-04-05
**ROS 版本**: ROS 2 Humble

---

## 一、项目概述

### 1.1 项目背景

H2Track 是一个基于 ROS 2 Humble 的氢气(H2)源追踪仿真系统。该系统模拟机器人在 Gazebo 仿真环境中执行巡逻任务，通过气体传感器检测氢气浓度变化，利用梯度上升算法定位氢气源。项目支持两种气体仿真模式：简化模式和 GADEN 真实丝状扩散模式。

### 1.2 系统目标

- 在仿真环境中验证气体源定位算法的有效性
- 提供可重复的演示环境用于算法调优
- 支持多场景配置，便于不同环境下的测试
- 提供 Web 控制台实现一键启动和实时监控

### 1.3 技术栈

| 组件 | 技术选型 |
|------|----------|
| 机器人操作系统 | ROS 2 Humble |
| 仿真环境 | Gazebo Classic |
| 导航框架 | Nav2 |
| 定位方案 | AMCL / SLAM Toolbox |
| 气体仿真 | GADEN (可选) / 简化模型 |
| 后端语言 | Python 3.10 |
| Web 框架 | FastAPI + Uvicorn |
| 前端 | React (静态构建) |

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         H2Track 系统架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ Web Console │───▶│ FastAPI     │───▶│ SimulationController    │ │
│  │ (React)     │    │ REST API    │    │ (demo_web_server.py)    │ │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘ │
│                                                   │                 │
│                                                   ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ROS 2 节点层                              │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │   │
│  │  │ mission_manager  │  │ gaden_adapter    │                 │   │
│  │  │ _node            │  │ _node            │                 │   │
│  │  └────────┬─────────┘  └────────┬─────────┘                 │   │
│  │           │                     │                           │   │
│  │           ▼                     ▼                           │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │   │
│  │  │ Nav2 Stack       │  │ GADEN Player     │                 │   │
│  │  │ (导航+定位)      │  │ (气体仿真)       │                 │   │
│  │  └────────┬─────────┘  └────────┬─────────┘                 │   │
│  │           │                     │                           │   │
│  └───────────┼─────────────────────┼───────────────────────────┘   │
│              │                     │                               │
│              ▼                     ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Gazebo 仿真层                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ 机器人模型   │  │ 传感器插件   │  │ 世界环境     │       │   │
│  │  │ (TurtleBot3) │  │ (LiDAR等)    │  │ (Warehouse)  │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 包结构

```
h2track-xian/
├── src/
│   ├── h2track_sim/           # ament_cmake 包
│   │   ├── launch/            # 启动文件
│   │   ├── scenes/            # 场景配置
│   │   │   ├── baseline/      # 实验室场景
│   │   │   └── warehouse/     # 仓库场景
│   │   ├── worlds/            # Gazebo 世界文件
│   │   └── config/            # 全局配置
│   │
│   └── h2track_tracking/      # ament_python 包
│       ├── h2track_tracking/  # 源代码
│       │   ├── mission_logic.py      # 状态机核心
│       │   ├── mission_manager_node.py
│       │   ├── gas_model.py          # 气体场模型
│       │   ├── gas_field_node.py
│       │   ├── gaden_adapter.py      # GADEN 适配器
│       │   ├── gaden_adapter_node.py
│       │   ├── demo_prep.py          # 演示准备工具
│       │   ├── demo_selfcheck.py     # 自检工具
│       │   ├── demo_regression.py    # 回归测试
│       │   ├── demo_web_server.py    # Web 控制台
│       │   └── llm_agent.py          # AI 辅助模块
│       └── test/              # 单元测试
│
├── install/                   # 编译安装目录
├── build/                     # 编译中间文件
└── log/                       # 编译日志
```

---

## 三、核心模块设计

### 3.1 任务状态机 (Mission State Machine)

状态机是系统的核心控制逻辑，定义在 `mission_logic.py` 中。

#### 状态转换图

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
              ┌─────────┐   浓度 >= enter_threshold    ┌──────┴───┐
              │ PATROL  │ ──────────────────────────▶ │ SEEK_    │
              │         │                              │ CONFIRM  │
              └────┬────┘                              └────┬─────┘
                   ▲                                        │
                   │                                        │
                   │ 浓度 < exit_threshold                  │ 浓度 >= enter_threshold
                   │                                        ▼
                   │                                  ┌──────────┐
                   │                                  │ SEEK_    │
                   └───────────────────────────────── │ TRACK    │
                                                      └────┬─────┘
                                                           │
                                                           │ 浓度 >= source_threshold
                                                           │ 且位置稳定
                                                           ▼
                                                      ┌──────────┐
                                                      │ SOURCE_  │
                                                      │ FOUND    │
                                                      └──────────┘
```

#### 核心数据结构

```python
class MissionMode(Enum):
    PATROL = auto()         # 巡逻模式
    SEEK_CONFIRM = auto()   # 确认检测
    SEEK_TRACK = auto()     # 追踪气源
    SOURCE_FOUND = auto()   # 找到气源

@dataclass(frozen=True)
class MissionConfig:
    patrol_points: list[tuple[float, float]]  # 巡逻路径点
    enter_threshold: float      # 进入追踪阈值
    exit_threshold: float       # 退出追踪阈值
    source_threshold: float     # 气源确认阈值
    confirm_samples: int        # 确认采样数
    source_radius: float        # 气源判定半径
    source_hold_steps: int      # 稳定保持步数
```

### 3.2 气体场模型 (Gas Field Model)

气体场模型提供两种实现方式：

#### 简化模型 (gas_model.py)

```python
@dataclass(frozen=True)
class GasFieldParams:
    source_x: float           # 气源 X 坐标
    source_y: float           # 气源 Y 坐标
    source_strength: float    # 气源强度
    decay_rate: float         # 衰减率
    plume_stddev: float       # 羽流标准差
    wind_x: float             # 风速 X 分量
    wind_y: float             # 风速 Y 分量
    noise_stddev: float       # 噪声标准差
```

浓度计算公式：
```
concentration = source_strength * exp(-decay_rate * distance) * plume_bias + noise
```

其中 `plume_bias` 考虑了风向对气体扩散的影响。

#### GADEN 集成

GADEN (Gas Dispersion Simulator) 提供真实的丝状气体扩散仿真：

| 组件 | 功能 |
|------|------|
| `gaden_environment` | 加载环境配置 |
| `gaden_player` | 播放预计算的气体场 |
| `simulated_gas_sensor` | 模拟气体传感器 |
| `gaden_adapter_node` | 转换传感器读数为浓度值 |

### 3.3 GADEN 适配器 (gaden_adapter.py)

支持多种氢气传感器模型的浓度转换：

```python
class HydrogenSensorModel(IntEnum):
    TGS2620 = 0
    TGS2600 = 1
    TGS2611 = 2
    TGS2610 = 3
    TGS2612 = 4
```

转换流程：
1. 读取原始传感器数据 (OHM/VOLT/PPM)
2. 根据传感器型号应用校准系数
3. 输出标准化浓度值 (PPM)

### 3.4 导航管理 (mission_manager_node.py)

#### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `patrol_goal_timeout_sec` | 45.0 | 巡逻目标超时时间 |
| `goal_reject_retry_sec` | 2.0 | 目标拒绝后重试间隔 |
| `track_step` | 0.7 | 追踪步长 |
| `sweep_angle_deg` | 30.0 | 扫描角度 |

#### TF 依赖

```
map ──▶ odom ──▶ base_link
 │
 └──▶ gaden_map (GADEN 模式)
```

---

## 四、场景配置系统

### 4.1 场景结构

```yaml
# scenes/warehouse/scene.yaml
scene_name: warehouse
world: scenes/warehouse/warehouse.world
map: scenes/warehouse/maps/warehouse_map.yaml
nav2_params: scenes/warehouse/nav2_params.yaml
use_gaden: true
use_slam: true

mission_manager:
  initial_pose: {x, y, yaw}
  patrol_points: [[x1, y1], [x2, y2], ...]
  enter_threshold: 0.65
  exit_threshold: 0.4
  source_threshold: 3.4
  confirm_samples: 1
  source_radius: 1.0
  source_hold_steps: 1

gas_source: {x, y}

gaden:
  project_path: /path/to/gaden/scenario
  playback_id: scene1
  player_freq: 0.5
  sensor_topic: /gaden/sensor_reading
```

### 4.2 可用场景

| 场景 | 说明 | 特点 |
|------|------|------|
| `baseline` | 实验室环境 | 小型测试环境，适合快速验证 |
| `warehouse` | 仓库环境 | AWS RoboMaker 小仓库，适合正式演示 |

---

## 五、启动系统

### 5.1 启动文件层次

```
demo.launch.py
    │
    ├── scene_loader.py (加载场景配置)
    │
    └── bringup.launch.py
            │
            ├── sim.launch.py (Gazebo + 机器人)
            │
            ├── nav2.launch.py (Nav2 导航栈)
            │
            ├── gas_field_node / GADEN 组件
            │
            └── mission_manager_node
```

### 5.2 启动参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `scene` | warehouse | 场景名称 |
| `use_gaden` | true | 是否使用 GADEN |
| `use_slam` | true | 是否使用 SLAM |
| `use_rviz` | true | 是否启动 RViz |
| `headless` | false | 无头模式 |

---

## 六、Web 控制台

### 6.1 功能概览

Web 控制台 (`demo_web_server.py`) 提供以下功能：

| 功能 | API 端点 | 说明 |
|------|----------|------|
| 启动仿真 | `POST /api/sim/start` | 一键启动演示 |
| 停止仿真 | `POST /api/sim/stop` | 停止当前运行 |
| 实时日志 | `GET /api/logs/stream` | SSE 日志流 |
| 指标快照 | `GET /api/metrics/recent` | 运行指标数据 |
| 导出诊断 | `POST /api/diag/export` | 导出诊断包 |
| 导出报告 | `POST /api/report/export` | 导出运行报告 |
| AI 对话 | `POST /api/llm/chat` | AI 分析与建议 |

### 6.2 监控指标

- **机器人模式**: 当前任务状态
- **气体浓度**: 实时浓度值及趋势图
- **导航统计**: 成功/失败/取消次数
- **话题健康度**: 各话题频率和超时状态
- **节点健康度**: 核心节点在线状态

### 6.3 AI 辅助功能

支持配置 OpenAI 兼容的模型端点，实现：
- 自然语言状态分析
- 结构化动作建议
- 自动执行优化操作

---

## 七、测试与验证

### 7.1 单元测试

```bash
# 运行所有测试
pytest src/h2track_tracking/test/ -v

# 运行单个测试文件
pytest src/h2track_tracking/test/test_mission_logic.py -v
pytest src/h2track_tracking/test/test_gas_model.py -v
```

### 7.2 演示准备流程

```bash
# 1. 清理残留进程
ros2 run h2track_tracking demo_prep --scene warehouse

# 2. 启动演示
ros2 launch h2track_sim demo.launch.py use_rviz:=true

# 3. 自检验证
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
```

### 7.3 回归测试

```bash
# 多轮稳定性测试
ros2 run h2track_tracking demo_regression \
    --scene warehouse \
    --use-gaden true \
    --rounds 3 \
    --run-timeout-sec 110
```

输出指标：
- 成功率
- 进入追踪模式次数
- 找到气源次数
- 平均找到时间
- 导航失败热点位置

---

## 八、关键 ROS 话题

| 话题 | 消息类型 | 发布者 | 订阅者 |
|------|----------|--------|--------|
| `/gas_concentration` | Float32 | gas_field_node / gaden_adapter_node | mission_manager_node |
| `/robot_mode` | String | mission_manager_node | 监控系统 |
| `/source_found` | Bool | mission_manager_node | 监控系统 |
| `/estimated_source_pose` | PoseStamped | mission_manager_node | RViz |
| `/amcl_pose` | PoseWithCovarianceStamped | amcl | mission_manager_node |
| `/odom` | Odometry | Gazebo | 多个节点 |

---

## 九、外部依赖

### 9.1 GADEN 工作空间

路径: `/home/user/gaden_ws`

必须预先准备：
- 环境配置文件
- 预计算的气体场数据
- `olfaction_msgs` 消息包

### 9.2 系统依赖

```bash
# ROS 2 Humble
source /opt/ros/humble/setup.bash

# GADEN 工作空间
source /home/user/gaden_ws/install/setup.bash

# 项目工作空间
source install/setup.bash
```

---

## 十、开发报告

### 10.1 设计决策

#### 10.1.1 纯逻辑与 ROS 解耦

核心模块 (`mission_logic.py`, `gas_model.py`, `gaden_adapter.py`) 设计为纯 Python 类，不依赖 ROS。这样做的好处：
- 可独立进行单元测试
- 便于在其他项目中复用
- 降低测试复杂度

#### 10.1.2 场景配置驱动

所有场景相关参数集中在 YAML 配置文件中，支持：
- 快速切换测试环境
- 参数调优无需修改代码
- 配置版本化管理

#### 10.1.3 启动门控机制

`gaden_sensor_gate_node` 和 `nav2_startup_gate_node` 实现了启动同步：
- 等待 TF 树就绪后再启动传感器
- 等待 Nav2 生命周期节点激活后再开始任务

### 10.2 已知问题与解决方案

| 问题 | 解决方案 |
|------|----------|
| 巡逻目标超时 | 自动跳过当前路径点，继续下一个 |
| 导航目标被拒绝 | 延迟重试机制 |
| GADEN 传感器启动过早 | TF 就绪门控 |
| FastDDS 锁文件残留 | demo_prep 自动清理 |

### 10.3 性能优化建议

1. **降低 GADEN 播放频率**: `player_freq: 0.5` 可减少 CPU 占用
2. **调整 Nav2 参数**: 根据场景调整 `nav2_params.yaml`
3. **使用无头模式**: `headless:=true` 可节省 GUI 资源

### 10.4 扩展方向

1. **多机器人协作**: 扩展状态机支持多机协同搜索
2. **动态障碍物**: 集成动态环境仿真
3. **真实传感器**: 适配真实氢气传感器硬件
4. **机器学习优化**: 使用 RL 优化搜索策略

---

## 十一、附录

### A. 常用命令速查

```bash
# 编译
colcon build

# 启动演示
ros2 launch h2track_sim demo.launch.py use_rviz:=true

# 启动 Web 控制台
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080

# 查看话题
ros2 topic echo /gas_concentration
ros2 topic echo /robot_mode

# 查看节点
ros2 node list

# 回归测试
ros2 run h2track_tracking demo_regression --scene warehouse --rounds 5
```

### B. 文件索引

| 文件 | 说明 |
|------|------|
| `mission_logic.py` | 任务状态机核心逻辑 |
| `mission_manager_node.py` | 任务管理 ROS 节点 |
| `gas_model.py` | 气体场数学模型 |
| `gaden_adapter.py` | GADEN 传感器适配器 |
| `demo_prep.py` | 演示环境准备工具 |
| `demo_selfcheck.py` | 运行时自检工具 |
| `demo_regression.py` | 回归测试工具 |
| `demo_web_server.py` | Web 控制台服务 |
| `llm_agent.py` | AI 辅助分析模块 |

---

**报告结束**
