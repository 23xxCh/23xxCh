---
name: surge-cast-gas-tracking
description: Surge-Cast algorithm with particle filter for production-grade gas source localization
type: project
---

# Surge-Cast 气体源定位系统设计

## 概述

实现生产级气体源定位系统，结合 Surge-Cast 算法和粒子滤波器，支持有障碍物环境下的精确导航。

## 架构设计

### 状态机设计

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
┌──────────┐   高浓度    ┌──────────┐   丢失烟羽    ┌──────────┐
│ PATROL   │ ─────────→ │ SURGE    │ ──────────→   │ CAST     │
│ (巡逻)   │            │ (逆风)   │               │ (横移)   │
└──────────┘            └──────────┘               └──────────┘
     ▲                       │                          │
     │                       │ 找到烟羽                  │
     │                       ▼                          │
     │                 ┌──────────┐                     │
     │    极低浓度     │ SOURCE_  │◄────────────────────┘
     └──────────────── │ FOUND    │   达到源阈值
                        └──────────┘
```

### 核心组件

1. **SurgeCastTracker** - 核心 Surge-Cast 算法实现
2. **PlumeDetector** - 烟羽检测与状态判断
3. **ParticleFilterIntegrator** - 粒子滤波器集成
4. **ObstacleAwareNavigator** - 避障导航

### 模块结构

```
h2track_tracking/
├── tracking/
│   ├── __init__.py
│   ├── surge_cast.py       # Surge-Cast 核心算法
│   ├── plume_detector.py   # 烟羽检测
│   ├── state_machine.py    # 跟踪状态机
│   └── obstacle_avoider.py # 避障集成
├── particle_filter/
│   └── ... (现有)
└── mission_manager_node.py # 集成入口
```

## 算法详细设计

### 1. Surge-Cast 核心算法

```python
class TrackingState(Enum):
    PATROL = auto()      # 巡逻状态
    SURGE = auto()       # 逆风移动
    CAST = auto()        # 横向搜索
    SOURCE_FOUND = auto() # 找到源头

class SurgeCastTracker:
    """Surge-Cast 气体源定位跟踪器"""

    def __init__(self, config: SurgeCastConfig):
        self.state = TrackingState.PATROL
        self.wind_direction = 0.0  # 风向（弧度）
        self.cast_direction = 1    # 横移方向 (+1 或 -1)
        self.best_position = None  # 历史最佳位置
        self.best_concentration = 0.0

    def update(self, concentration: float, robot_pose: Pose2D,
               wind: tuple[float, float]) -> TrackingAction:
        """更新跟踪状态并返回下一步动作"""

        # 更新历史最佳
        if concentration > self.best_concentration:
            self.best_concentration = concentration
            self.best_position = robot_pose

        # 状态转换
        if self.state == TrackingState.SURGE:
            if concentration < self.config.plume_lost_threshold:
                self.state = TrackingState.CAST
                self.cast_start_pose = robot_pose
            elif concentration >= self.config.source_threshold:
                self.state = TrackingState.SOURCE_FOUND

        elif self.state == TrackingState.CAST:
            if concentration >= self.config.plume_found_threshold:
                self.state = TrackingState.SURGE
            # 横移距离达到上限，切换方向
            if self._cast_distance() > self.config.cast_distance_limit:
                self.cast_direction *= -1

        return self._get_action()
```

### 2. 烟羽检测器

```python
class PlumeDetector:
    """检测机器人是否在烟羽内"""

    def __init__(self, config: PlumeDetectorConfig):
        self.history: deque[tuple[float, float]] = deque(maxlen=config.history_size)
        self.in_plume = False

    def update(self, concentration: float) -> bool:
        """更新并返回是否在烟羽内"""
        self.history.append(concentration)

        if len(self.history) < self.config.min_samples:
            return False

        avg_conc = sum(self.history) / len(self.history)
        self.in_plume = avg_conc >= self.config.plume_threshold
        return self.in_plume

    def get_confidence(self) -> float:
        """返回烟羽检测置信度"""
        if not self.history:
            return 0.0
        recent = list(self.history)[-5:]
        return sum(1 for c in recent if c > self.config.plume_threshold) / len(recent)
```

### 3. 粒子滤波器集成

```python
class ParticleFilterIntegrator:
    """将粒子滤波器估计集成到导航决策"""

    def __init__(self, min_confidence: float = 0.3):
        self.min_confidence = min_confidence
        self.estimate = None
        self.confidence = 0.0

    def update(self, estimate: SourceEstimate):
        """更新粒子滤波器估计"""
        self.estimate = estimate
        self.confidence = estimate.confidence

    def get_navigational_hint(self, robot_pose: Pose2D) -> Pose2D | None:
        """返回导航提示，如果置信度足够"""
        if self.confidence < self.min_confidence:
            return None
        return Pose2D(self.estimate.position[0], self.estimate.position[1])
```

### 4. 避障导航

```python
class ObstacleAwareNavigator:
    """避障导航器，集成 Nav2"""

    def __init__(self, navigator: BasicNavigator):
        self.navigator = navigator
        self.blocked_count = 0

    def navigate_to(self, target: Pose2D, upwind_direction: float) -> bool:
        """导航到目标，避开障碍物"""
        # 检查目标是否可达
        if not self._is_reachable(target):
            # 尝试绕行
            alternative = self._find_alternative(target, upwind_direction)
            if alternative:
                target = alternative
            else:
                return False

        return self.navigator.goToPose(self._make_goal(target))

    def _find_alternative(self, target: Pose2D, preferred_direction: float) -> Pose2D | None:
        """找到绕行路径"""
        # 尝试左右绕行
        for offset in [-30, 30, -60, 60]:
            angle = preferred_direction + math.radians(offset)
            alt_target = Pose2D(
                target.x + 0.5 * math.cos(angle),
                target.y + 0.5 * math.sin(angle)
            )
            if self._is_reachable(alt_target):
                return alt_target
        return None
```

## 配置参数

### SurgeCastConfig

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `plume_found_threshold` | 5.0 | 进入 SURGE 状态的浓度阈值 |
| `plume_lost_threshold` | 2.0 | 进入 CAST 状态的浓度阈值 |
| `source_threshold` | 20.0 | 确认找到源头的浓度阈值 |
| `surge_step` | 0.5 | 逆风移动步长 |
| `cast_step` | 0.3 | 横移步长 |
| `cast_distance_limit` | 3.0 | 单次横移最大距离 |
| `use_particle_filter` | true | 是否使用粒子滤波器 |
| `min_pf_confidence` | 0.3 | 粒子滤波器最小置信度 |

## 数据流

```
/gas_concentration ──→ PlumeDetector ──→ SurgeCastTracker
                                                    │
/odom ───────────────→ (robot_pose) ──────────────→│
                                                    │
/wind_estimate ──────→ (wind_direction) ──────────→│
                                                    │
/estimated_source ───→ ParticleFilterIntegrator ──→│
                                                    │
                                                    ▼
                                            TrackingAction
                                                    │
                                                    ▼
                                          mission_manager_node
                                                    │
                                                    ▼
                                           /cmd_vel (via Nav2)
```

## 测试策略

### 单元测试

1. `test_surge_cast.py` - 测试状态转换逻辑
2. `test_plume_detector.py` - 测试烟羽检测
3. `test_particle_integrator.py` - 测试粒子滤波器集成

### 集成测试

1. 在 baseline 场景测试完整流程
2. 在 warehouse 场景测试避障
3. 测试不同风向条件

### 成功标准

1. 在无障碍环境下，90% 以上试验在 3 分钟内找到源头
2. 在有障碍环境下，80% 以上试验成功
3. 定位精度在 1 米范围内

## 实现计划

1. **Phase 1**: 实现 Surge-Cast 核心算法
2. **Phase 2**: 集成粒子滤波器
3. **Phase 3**: 添加避障支持
4. **Phase 4**: 测试和调优

## Why

**为什么选择 Surge-Cast + 粒子滤波？**

- Surge-Cast 是工业验证过的算法，简单可靠
- 粒子滤波器提供额外的鲁棒性，特别是在风向不确定时
- 结合两者可以处理更复杂的环境

## How to apply

1. 将新的 `tracking/` 模块集成到现有 `mission_manager_node.py`
2. 更新场景配置以支持新的跟踪参数
3. 添加风向估计话题（如果还没有）
