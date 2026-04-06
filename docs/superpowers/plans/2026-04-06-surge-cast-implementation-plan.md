---
name: surge-cast-implementation-plan
description: Implementation plan for Surge-Cast gas tracking system
type: plan
---

# Surge-Cast 气体源定位系统实现计划

## 概述

基于设计文档实现生产级 Surge-Cast 气体源定位系统。

**设计文档**: `docs/superpowers/specs/2026-04-06-surge-cast-tracking-design.md`

## Phase 1: 核心跟踪模块

### Task 1.1: 创建 tracking 模块结构

**文件**: `src/h2track_tracking/h2track_tracking/tracking/__init__.py`

创建新模块目录和初始化文件。

### Task 1.2: 实现跟踪状态和数据类型

**文件**: `src/h2track_tracking/h2track_tracking/tracking/types.py`

定义:
- `TrackingState` 枚举 (PATROL, SURGE, CAST, SOURCE_FOUND)
- `TrackingAction` 数据类
- `SurgeCastConfig` 配置类

### Task 1.3: 实现烟羽检测器

**文件**: `src/h2track_tracking/h2track_tracking/tracking/plume_detector.py`

实现 `PlumeDetector` 类:
- 浓度历史维护
- 烟羽状态判断
- 置信度计算

**测试**: `src/h2track_tracking/test/test_plume_detector.py`

### Task 1.4: 实现 Surge-Cast 核心算法

**文件**: `src/h2track_tracking/h2track_tracking/tracking/surge_cast.py`

实现 `SurgeCastTracker` 类:
- 状态机逻辑
- SURGE 逆风移动
- CAST 横向搜索
- 历史最佳位置追踪

**测试**: `src/h2track_tracking/test/test_surge_cast.py`

## Phase 2: 粒子滤波器集成

### Task 2.1: 实现粒子滤波器集成器

**文件**: `src/h2track_tracking/h2track_tracking/tracking/pf_integrator.py`

实现 `ParticleFilterIntegrator` 类:
- 订阅 `/estimated_source`
- 置信度过滤
- 导航提示生成

**测试**: `src/h2track_tracking/test/test_pf_integrator.py`

## Phase 3: 避障导航集成

### Task 3.1: 实现避障导航器

**文件**: `src/h2track_tracking/h2track_tracking/tracking/obstacle_avoider.py`

实现 `ObstacleAwareNavigator` 类:
- Nav2 集成
- 障碍物检测
- 绕行路径规划

## Phase 4: Mission Manager 集成

### Task 4.1: 更新 Mission Manager Node

**文件**: `src/h2track_tracking/h2track_tracking/mission_manager_node.py`

- 替换现有跟踪逻辑为 Surge-Cast
- 添加风向参数
- 集成粒子滤波器

### Task 4.2: 更新场景配置

**文件**:
- `src/h2track_sim/scenes/baseline/scene.yaml`
- `src/h2track_sim/scenes/warehouse/scene.yaml`

添加 Surge-Cast 配置参数。

## Phase 5: 测试和验证

### Task 5.1: 单元测试

所有新模块的单元测试，覆盖率 > 80%。

### Task 5.2: 集成测试

- baseline 场景测试
- warehouse 场景测试 (有障碍物)
- 不同风向条件测试

### Task 5.3: 回归测试

运行 `demo_regression` 验证稳定性。

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `tracking/__init__.py` | 创建 | 模块初始化 |
| `tracking/types.py` | 创建 | 数据类型定义 |
| `tracking/plume_detector.py` | 创建 | 烟羽检测器 |
| `tracking/surge_cast.py` | 创建 | 核心算法 |
| `tracking/pf_integrator.py` | 创建 | PF 集成器 |
| `tracking/obstacle_avoider.py` | 创建 | 避障导航 |
| `mission_manager_node.py` | 修改 | 集成新模块 |
| `test/test_plume_detector.py` | 创建 | 单元测试 |
| `test/test_surge_cast.py` | 创建 | 单元测试 |
| `test/test_pf_integrator.py` | 创建 | 单元测试 |
| `scenes/baseline/scene.yaml` | 修改 | 添加配置 |
| `scenes/warehouse/scene.yaml` | 修改 | 添加配置 |

## 风险和缓解

| 风险 | 缓解措施 |
|------|----------|
| 风向不准确 | 粒子滤波器提供备选方向 |
| 障碍物阻挡 | Nav2 自动绕行 |
| 烟羽断裂 | CAST 状态重新搜索 |
| 参数不适用 | 提供场景级配置覆盖 |

## 验收标准

1. 所有单元测试通过
2. 集成测试成功率 >= 80%
3. 无障碍场景定位精度 <= 1m
4. 代码覆盖率 >= 80%
