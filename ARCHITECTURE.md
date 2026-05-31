# H2Track 架构文档

> 本文档面向新手开发者，帮助你快速理解项目结构和各模块功能。

## 项目总览

**H2Track** 是一个基于 ROS 2 Humble 的氢气源追踪仿真系统。机器人在 Gazebo 仿真环境中巡逻，检测气体浓度变化，使用梯度追踪和粒子滤波算法定位氢气源。

```
一句话概括：机器人巡逻 → 闻到气体 → 追踪气味 → 找到源头
```

---

## 系统架构

### 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Gazebo 仿真环境                            │
│  ┌─────────┐                                                    │
│  │ 机器人   │ ←── TF 变换 ──→ ┌──────────────┐                  │
│  │(URDF)   │                  │ 地图/定位     │                  │
│  └────┬────┘                  │ (AMCL/SLAM)  │                  │
│       │                       └──────────────┘                  │
│       ▼                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ 气体传感器   │───→│ 任务管理器   │───→│ Nav2 导航   │          │
│  │(GADEN/简化) │    │ (状态机)    │    │ (路径规划)  │          │
│  └─────────────┘    └──────┬──────┘    └─────────────┘          │
│                            │                                    │
│       ┌────────────────────┼────────────────────┐               │
│       ▼                    ▼                    ▼               │
│  ┌─────────┐        ┌──────────┐        ┌──────────┐           │
│  │Surge-Cast│        │粒子滤波   │        │ 算法融合  │           │
│  │(逆风追踪)│        │(源定位)   │        │(决策融合) │           │
│  └─────────┘        └──────────┘        └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流

```
/gas_concentration ──→ Surge-Cast ──→ 目标位置 ──→ Nav2 ──→ 机器人移动
        │                     │
        └─────────────────────┴──→ 粒子滤波 ──→ 源估计 ──→ 融合决策
```

---

## 包结构

项目包含三个 ROS 2 包：

| 包名 | 语言 | 构建类型 | 功能 |
|------|------|----------|------|
| `h2track_sim` | Python/XML | ament_cmake | 仿真环境：启动文件、场景配置、Gazebo 世界、机器人 URDF |
| `h2track_tracking` | Python | ament_python | 核心逻辑：气体模型、追踪算法、任务状态机、Web 控制台 |
| `h2track_interfaces` | CMake | ament_cmake | 自定义消息类型 |

---

## 核心模块详解

### 1. 任务状态机 (`mission_logic.py`)

**功能**：控制机器人的行为模式转换

**状态转换**：
```
PATROL（巡逻）→ SEEK_CONFIRM（确认检测）→ SEEK_TRACK（追踪）→ SOURCE_FOUND（找到源）
     ↑                                                              │
     └──────────────── 浓度下降 ────────────────────────────────────┘
```

**关键类**：
- `MissionMode` - 枚举类，定义四种状态
- `MissionConfig` - 配置参数（阈值、样本数等）
- `MissionStateMachine` - 状态机核心逻辑

**配置参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enter_threshold` | 0.65 | 触发确认模式的浓度阈值 |
| `exit_threshold` | 0.4 | 退出追踪的浓度阈值 |
| `source_threshold` | 3.4 | 判断接近源头的浓度阈值 |
| `source_radius` | 1.0m | 判定找到源头的半径 |

---

### 2. Surge-Cast 追踪算法 (`tracking/surge_cast.py`)

**功能**：基于风向的气体源追踪算法

**算法原理**：
1. **SURGE（冲刺）**：检测到烟羽时，逆风移动
2. **CAST（搜索）**：丢失烟羽时，横向搜索

**关键类**：
- `SurgeCastTracker` - 主追踪器
- `TrackingHistory` - 记录位置和浓度历史
- `PlumeDetector` - 检测烟羽边界

**自适应步长**：
- 高浓度（接近源头）：小步长（0.2m）精确定位
- 低浓度（远离源头）：大步长（1.0m）快速探索

---

### 3. 粒子滤波 (`particle_filter/`)

**功能**：概率源定位，通过粒子权重估计源头位置

**目录结构**：
```
particle_filter/
├── types.py           # Particle, SourceEstimate 数据类
├── filter.py          # ParticleFilter 核心滤波器
├── motion_model.py    # 随机游走运动模型
└── observation_model.py  # 高斯烟羽观测模型
```

**核心流程**：
```
初始化粒子 → 预测（添加噪声）→ 更新（根据浓度调整权重）→ 重采样 → 估计源头
```

**性能优化**：
- 支持向量化操作（`method='vectorized'`）
- 对于 500+ 粒子，速度提升 10-50 倍

**关键话题**：
- `/estimated_source` - 源头估计位置（带协方差）
- `/particle_cloud` - 粒子云可视化

---

### 4. 算法融合 (`tracking/fusion.py`)

**功能**：融合 Surge-Cast 和粒子滤波的估计结果

**三种融合模式**：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `weighted` | 根据置信度加权平均 | 默认模式，综合两者优势 |
| `switching` | 根据条件切换算法 | 烟羽不稳定时 |
| `cascade` | 粒子滤波指引区域，Surge-Cast 导航 | 大范围搜索 |

**输出话题**：
- `/fusion_state` - 融合状态：`"mode,pf_contrib,surge_contrib,target_x,target_y"`

---

### 5. 气体模型 (`gas_model.py`)

**功能**：简化的 2D 烟羽模型（非 GADEN 模式使用）

**关键类**：
- `GasFieldParams` - 气体场参数（源位置、强度、衰减率、风向等）
- `GasFieldModel` - 计算给定位置的气体浓度

**浓度计算公式**：
```
浓度 = 源强度 × exp(-衰减率 × 距离) × 烟羽偏置 + 噪声
```

**烟羽偏置**：根据风向计算，下风向浓度更高

---

### 6. 多气体支持 (`gas_types.py`)

**功能**：定义不同气体的物理属性

**支持的气体**：

| 气体 | 分子式 | 行为 | 传感器高度 | 报警阈值 |
|------|--------|------|-----------|----------|
| 氢气 | H₂ | 上升（轻） | 1.5m | 250 ppm |
| 甲烷 | CH₄ | 上升（轻） | 1.2m | 5000 ppm |
| 一氧化碳 | CO | 中性 | 0.5m | 50 ppm |
| 丙烷 | C₃H₈ | 下沉（重） | 0.3m | 1000 ppm |

**使用示例**：
```python
from h2track_tracking.gas_types import GasType, get_gas_properties

props = get_gas_properties(GasType.HYDROGEN)
print(f"传感器高度: {props.sensor_height}m")
```

---

### 7. Web 控制台 (`web/`)

**功能**：FastAPI Web 界面，一键启动/监控仿真

**目录结构**：
```
web/
├── app.py                  # FastAPI 应用工厂
├── routes.py               # REST 和 WebSocket 路由
├── websocket.py            # WebSocket 连接管理
├── auth.py                 # API 密钥认证
├── simulation_controller.py # 仿真生命周期控制
├── metrics_store.py        # 指标存储
└── topic_collector.py      # ROS 话题数据收集
```

**启动方式**：
```bash
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080
```

**API 端点**：
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/sim/start` | POST | 启动仿真 |
| `/api/sim/stop` | POST | 停止仿真 |
| `/api/sim/status` | GET | 仿真状态 |
| `/ws` | WebSocket | 实时指标流 |
| `/ws/heatmap` | WebSocket | 热力图数据流 |

---

### 8. GADEN 集成

**功能**：与 GADEN 气体仿真系统集成

**相关节点**：
- `gaden_environment` - 环境节点
- `gaden_player` - 播放预计算的烟羽数据
- `gaden_adapter_node` - 转换传感器读数到 `/gas_concentration`
- `gaden_sensor_gate_node` - 等待 TF 就绪后启动传感器

**配置要求**：
- 需要预处理的 GADEN 场景数据
- 必须设置 `use_gaden:=true`

---

### 9. 热力图系统 (`heatmap/`)

**功能**：浓度分布可视化

**关键类**：
- `ConcentrationGrid` - 3D 浓度网格存储
- `TimeSeriesStore` - 历史快照，支持回放

---

### 10. 导航恢复 (`recovery/`)

**功能**：导航失败时的恢复策略

**目录结构**：
```
recovery/
├── policies.py  # 恢复策略定义
├── actions.py   # 恢复动作执行
└── monitor.py   # 失败检测
```

---

### 11. 多机器人协调 (`multi_robot/`)

**功能**：多机器人协作定位气源

**关键类**：
- `MultiRobotCoordinator` - 协调节点
- `Role` - 角色枚举（TRACKER, EXPLORER, VERIFIER, IDLE）

**角色分配策略**：
1. 浓度最高的机器人成为 TRACKER
2. 其他机器人成为 EXPLORER
3. 当有高置信度估计时，派遣 VERIFIER 验证

---

### 12. 自定义消息 (`h2track_interfaces/`)

**消息类型**：

| 消息 | 字段 | 用途 |
|------|------|------|
| `RobotState.msg` | robot_id, x, y, yaw, mode, concentration | 机器人状态 |
| `SourceEstimate.msg` | robot_id, x, y, confidence, covariance[4] | 源头估计 |
| `RoleAssignment.msg` | robot_id, role, target_x, target_y | 角色分配 |

---

## 启动流程

### bringup.launch.py 完整启动链

```
1. sim.launch.py          → 启动 Gazebo + 生成机器人
2. nav2.launch.py         → 启动 Nav2 导航栈（延迟 12s）
3. nav2_startup_gate      → 等待 Nav2 就绪
4. gas_field_node         → 简化气体仿真（非 GADEN）
   或 gaden_* 节点        → GADEN 气体仿真
5. particle_filter_node   → 粒子滤波
6. mission_manager_node   → 任务管理器（延迟 22s）
7. rviz2                  → 可视化
```

### 场景配置

场景配置文件位于 `src/h2track_sim/scenes/<scene>/scene.yaml`：

```yaml
scene_name: warehouse
world: scenes/warehouse/warehouse.world    # Gazebo 世界
map: scenes/warehouse/maps/warehouse_map.yaml  # 地图
nav2_params: scenes/warehouse/nav2_params.yaml  # Nav2 参数
use_gaden: true
use_slam: true

mission_manager:
  initial_pose: {x: 0.0, y: 0.0, yaw: 0.0}
  patrol_points: [[3.0, 3.0], [-3.0, 3.0], [-3.0, -3.0], [3.0, -3.0]]
  enter_threshold: 0.65
  exit_threshold: 0.4
  source_threshold: 3.4
  source_radius: 1.0

gas_source: {x: -3.2, y: -3.0}  # 真实源位置（用于评估）

gaden:
  project_path: /path/to/gaden/scenario
  playback_id: scene1
  sensor_frame: gas_sensor_link
  fixed_frame: gaden_map
```

---

## 关键 ROS 话题

| 话题 | 消息类型 | 方向 | 说明 |
|------|----------|------|------|
| `/gas_concentration` | Float32 | 发布 | 气体浓度（归一化） |
| `/robot_mode` | String | 发布 | 当前任务状态 |
| `/source_found` | Bool | 发布 | 找到源头信号 |
| `/estimated_source` | PoseWithCovarianceStamped | 发布 | 粒子滤波估计 |
| `/particle_cloud` | PoseArray | 发布 | 粒子云可视化 |
| `/estimated_wind` | String | 发布 | 估计风向 |
| `/fusion_state` | String | 发布 | 融合状态 |
| `/amcl_pose` | PoseWithCovarianceStamped | 发布 | 机器人位姿 |

---

## 构建和运行

### 构建命令

```bash
# 加载依赖
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash  # GADEN 集成需要

# 构建
colcon build

# 运行测试
pytest src/h2track_tracking/test/ -v

# 测试覆盖率
pytest src/h2track_tracking/test/ --cov=src/h2track_tracking/h2track_tracking
```

### 启动命令

```bash
# 加载环境
source install/setup.bash

# 启动演示（GADEN 模式）
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_gaden:=true

# 启动演示（简化模式，无需 GADEN）
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_gaden:=false

# 启动 Web 控制台
ros2 run h2track_tracking demo_web_server --port 18080
```

---

## 扩展指南

### 添加新的追踪算法

1. 在 `tracking/` 目录创建新模块
2. 继承或实现 `TrackingAction` 接口
3. 在 `fusion.py` 中集成新算法

### 添加新的气体类型

1. 编辑 `gas_types.py`
2. 在 `GasType` 枚举中添加新类型
3. 在 `GAS_PROPERTIES` 字典中定义属性

### 添加新的场景

1. 创建 `src/h2track_sim/scenes/<new_scene>/` 目录
2. 添加 `scene.yaml` 配置文件
3. 添加 Gazebo 世界文件和地图
4. 使用 `scene:=<new_scene>` 启动

---

## 代码风格

- **纯 Python 模块**：ROS 无关，可单独测试（如 `gas_model.py`, `mission_logic.py`）
- **节点封装**：ROS 节点是对纯逻辑的薄封装
- **不可变配置**：使用 `@dataclass(frozen=True)` 定义配置类
- **类型注解**：所有函数签名都有类型注解

---

## 常见问题

### Q: 气体浓度始终为零？

检查：
1. GADEN 模式：确保 `sensor_frame` 设置为 `gas_sensor_link`
2. 确保已加载 GADEN 工作空间
3. 检查 GADEN 预处理数据是否存在

### Q: TF 树断裂？

验证 TF 链：
```bash
ros2 run tf2_ros tf2_echo gaden_map gas_sensor_link
```

### Q: Nav2 不导航？

检查生命周期节点：
```bash
ros2 lifecycle list /controller_server
ros2 lifecycle list /planner_server
```

---

## 参考资源

- [ROS 2 Humble 文档](https://docs.ros.org/en/humble/)
- [Nav2 导航框架](https://navigation.ros.org/)
- [GADEN 气体仿真](https://github.com/MAPIRlab/GADEN)
- [项目 README](./README.md)
- [CLAUDE.md](./CLAUDE.md) - Claude Code 开发指南
