# H2Track 技术开发说明文档

> 生成时间: 2026-04-06
> 版本: 1.0

---

## 一、项目概述

### 1.1 项目目标

H2Track 是一个基于 ROS 2 Humble 的氢气源追踪仿真系统，实现：
- 移动机器人在仓库环境中巡逻
- 检测氢气浓度变化
- 使用梯度上升和粒子滤波算法定位氢气源

### 1.2 技术栈

| 组件 | 技术 |
|------|------|
| ROS 版本 | ROS 2 Humble |
| 构建系统 | colcon + ament |
| 语言 | Python 3.10 |
| 仿真环境 | Gazebo |
| 导航 | Nav2 |
| 气体仿真 | GADEN (Filament模型) |
| Web控制台 | FastAPI + React/Vite |
| AI助手 | OpenAI兼容API |

### 1.3 项目指标

| 指标 | 数值 |
|------|------|
| Python文件 | 116 |
| 测试文件 | 48 |
| Launch文件 | 5 |
| YAML配置 | 8 |
| 代码行数 | 27,250 |
| 测试通过率 | 99.3% (889/895) |

---

## 二、系统架构

### 2.1 包结构

```
h2track-xian/
├── src/
│   ├── h2track_sim/           # ROS 2 包 (ament_cmake)
│   │   ├── launch/            # 启动文件
│   │   ├── scenes/            # 场景配置
│   │   ├── config/            # 参数配置
│   │   └── test/              # 测试
│   │
│   └── h2track_tracking/      # ROS 2 包 (ament_python)
│       ├── h2track_tracking/  # Python模块
│       │   ├── particle_filter/  # 粒子滤波源定位
│       │   ├── heatmap/       # 浓度可视化
│       │   ├── llm/           # AI助手模块
│       │   ├── web/           # Web控制台
│       │   └── recovery/      # 恢复机制
│       └── test/              # 测试
│
├── docs/                      # 文档
└── artifacts/                 # 构建产物
```

### 2.2 核心模块依赖图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Console                              │
│  (FastAPI + React)                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ LLM Agent   │  │ Simulation  │  │ WebSocket   │            │
│  │ (AI建议)    │  │ Controller  │  │ (实时数据)  │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                    │
│         └────────────────┴────────────────┘                    │
│                          │                                      │
├──────────────────────────┼──────────────────────────────────────┤
│                    ROS 2 Layer                                 │
│                          │                                      │
│  ┌─────────────┐  ┌──────┴──────┐  ┌─────────────┐            │
│  │ Mission     │  │  Particle   │  │   Gas       │            │
│  │ Manager     │  │  Filter     │  │   Adapter   │            │
│  │ (状态机)    │  │  (源定位)   │  │  (GADEN)    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Nav2        │  │  Gazebo     │  │   GADEN     │            │
│  │ (导航)      │  │  (仿真)     │  │  (气体)     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 任务状态机

```
PATROL ──────▶ SEEK_CONFIRM ──────▶ SEEK_TRACK ──────▶ SOURCE_FOUND
   │                │                    │
   │                │                    │
   └────────────────┴────────────────────┘
              (浓度 < exit_threshold)
                    │
                    ▼
                 PATROL
```

---

## 三、关键模块详解

### 3.1 粒子滤波器 (particle_filter/)

**用途**: 概率性气体源定位

**组件**:
- `ParticleFilter`: 核心滤波器 (predict/update/resample)
- `GaussianPlumeObservationModel`: 基于高斯羽流的观测模型
- `RandomWalkMotionModel`: 粒子运动模型
- `ParticleFilterNode`: ROS 2 包装器

**关键参数**:
```python
num_particles = 1000
initial_sigma = 2.0  # 初始分布标准差
resample_threshold = 0.5  # 有效粒子数阈值
```

### 3.2 气体模型 (gas_model.py)

**用途**: 简化气体场仿真 (use_gaden=false)

**核心类**: `GasFieldModel`

**关键参数**:
```yaml
source_strength: 160.0   # 源强度
decay_rate: 0.32         # 衰减率
plume_stddev: 1.85       # 羽流标准差
wind_x: 0.18             # X方向风速
wind_y: -0.06            # Y方向风速
```

### 3.3 LLM 助手 (llm/)

**用途**: AI驱动的决策支持和半自动控制

**组件**:
- `OpenAICompatClient`: OpenAI兼容API客户端
- `LlmController`: 动作执行和审计
- `LlmProfileStore`: 多配置管理
- `context_builder.py`: ROS状态上下文构建

**安全机制**:
- 命令白名单: `ALLOWED_COMMAND_PREFIXES`
- 禁止模式: `FORBIDDEN_COMMAND_PATTERNS` (如 `rm -rf`, `git reset --hard`)
- 风险等级分类: low/medium/high/critical

### 3.4 Web 控制台 (web/)

**用途**: 可视化控制界面

**API端点**:
```
POST /api/sim/start       # 启动仿真
POST /api/sim/stop        # 停止仿真
GET  /api/sim/status      # 状态查询
GET  /api/metrics/recent  # 指标快照
POST /api/llm/chat        # AI对话
```

**WebSocket端点**:
```
/ws                       # 实时指标
/ws/heatmap               # 浓度热图
```

---

## 四、当前问题分析

### 4.1 测试失败汇总

| 测试文件 | 失败原因 | 严重性 |
|----------|----------|--------|
| test_gaden_dependency_contract.py | GADEN源码变化 | 中 |
| test_gas_model.py | 测试断言逻辑错误 | 低 |
| test_gas_model_plugin.py | 同上 | 低 |
| test_scene_config.py | 变量未定义 | 中 |
| test_warehouse_map_contract.py | 巡检路径设计 | 低 |

### 4.2 GADEN 集成问题

**问题**: Wind文件数量不足 (25个 vs 需要566个)

**影响**: GADEN player崩溃，无法使用真实气体仿真

**临时方案**: 使用简化气体场 (`use_gaden=false`)

**根本解决**: 需要运行完整的CFD仿真生成更多wind文件

### 4.3 ROS 节点测试问题

**问题**: `test_particle_filter_node.py` 和 `test_demo_web_server.py` 导致段错误

**原因**: ROS节点销毁时的线程竞争

**建议**: 使用 `launch_testing` 框架或隔离测试环境

---

## 五、代码质量分析

### 5.1 优点

1. **模块化设计**: 纯Python模块与ROS节点分离，易于测试
2. **不可变数据结构**: 使用 `frozen=True` 的 dataclass
3. **类型注解**: 大部分函数有类型提示
4. **契约测试**: GADEN集成有专门的契约测试

### 5.2 待改进

1. **异步测试支持**: WebSocket测试需要 `pytest-asyncio`
2. **错误处理**: 部分模块缺少异常处理
3. **日志规范**: 应统一使用 `logging` 而非 `print`
4. **文档覆盖**: 部分模块缺少docstring

---

## 六、下一步开发建议

### 6.1 短期 (1-2周)

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 修复测试失败 | 6个测试需要修复 |
| P0 | 解决ROS节点测试崩溃 | 使用launch_testing |
| P1 | 添加pytest-asyncio | 支持异步测试 |
| P1 | 完善API文档 | 添加docstring |

### 6.2 中期 (2-4周)

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 生成更多wind文件 | 支持GADEN完整仿真 |
| P1 | 添加E2E测试 | 使用Playwright |
| P2 | 性能优化 | 粒子滤波器性能 |
| P2 | 监控告警 | 添加Prometheus指标 |

### 6.3 长期 (1-3月)

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P2 | 多机器人支持 | 扩展架构 |
| P2 | 实机部署 | 迁移到真实机器人 |
| P3 | 算法优化 | 改进源定位算法 |

---

## 七、优化建议

### 7.1 性能优化

```python
# 粒子滤波器优化建议
# 1. 使用Numba JIT编译
from numba import jit

@jit(nopython=True)
def compute_weights(particles, observations):
    ...

# 2. 向量化计算
import numpy as np
weights = np.exp(-distances**2 / (2 * sigma**2))
```

### 7.2 架构优化

```
建议添加消息队列解耦:
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Sensor  │────▶│  Queue  │────▶│ Process │
│ Input   │     │ (Redis) │     │ Node    │
└─────────┘     └─────────┘     └─────────┘
```

### 7.3 测试优化

```python
# 添加测试标记
import pytest

@pytest.mark.unit
def test_gas_model():
    ...

@pytest.mark.integration
def test_gaden_integration():
    ...

@pytest.mark.e2e
def test_full_demo():
    ...

# 运行: pytest -m unit
```

---

## 八、开发工作流

### 8.1 构建和测试

```bash
# Source dependencies
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash

# Build
colcon build --packages-select h2track_tracking h2track_sim

# Test
PYTHONPATH=src/h2track_tracking:$PYTHONPATH \
python3 -m pytest src/h2track_tracking/test/ -v -m unit

# Run demo
ros2 launch h2track_sim demo.launch.py use_gaden:=false
```

### 8.2 代码审查清单

- [ ] 类型注解完整
- [ ] 单元测试覆盖
- [ ] 无硬编码值
- [ ] 错误处理完善
- [ ] 日志级别适当
- [ ] 文档更新

---

## 九、参考资料

- [ROS 2 Humble 文档](https://docs.ros.org/en/humble/)
- [Nav2 文档](https://navigation.ros.org/)
- [GADEN 论文](http://www.mdpi.com/1424-8220/17/7/1479)
- [粒子滤波算法](https://en.wikipedia.org/wiki/Particle_filter)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

---

## 十、变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-04-06 | 1.0 | 初始版本，完整分析报告 |
