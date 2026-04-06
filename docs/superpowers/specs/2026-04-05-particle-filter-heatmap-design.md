# 粒子滤波定位与气体分布热力图设计文档

> 创建时间: 2026-04-05
> 状态: 设计阶段

## 一、概述

### 1.1 目标

为 H2Track 氢气源追踪系统添加两个核心功能：

1. **粒子滤波定位** - 基于概率的气源位置估计，提供置信度和多候选源
2. **气体分布热力图** - 实时 3D 浓度分布可视化，支持历史回放

### 1.2 设计原则

- **独立模块** - 与现有状态机并行运行，不影响现有逻辑
- **渐进式集成** - 可逐步替换或增强现有功能
- **可测试性** - 纯 Python 核心逻辑，易于单元测试

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        H2Track 系统架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  现有模块                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ Gazebo 仿真 │  │ Nav2 导航   │  │ 任务状态机  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│         │                │                │                         │
│         └────────────────┴────────────────┘                         │
│                                   │                                 │
│                                   ▼                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    新增: 粒子滤波定位模块                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │   │
│  │  │ 粒子管理器  │  │ 运动模型    │  │ 观测模型    │          │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                   │                                 │
│                                   ▼                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    新增: 气体分布可视化模块                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │   │
│  │  │ 浓度网格    │  │ WebGL 渲染  │  │ 时间回放    │          │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
                    ROS Topics
                        │
    /gas_concentration ─┼─ /odom ──── /map
           │            │      │          │
           ▼            ▼      ▼          ▼
    ┌─────────────────────────────────────────┐
    │           ParticleFilterNode            │
    │  • 订阅气体浓度和里程计                  │
    │  • 运行粒子滤波算法                      │
    │  • 发布源位置估计                        │
    └─────────────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
    /estimated_source          /particle_cloud
    (PoseWithCovariance)       (PoseArray)
           │                         │
           ▼                         ▼
    ┌─────────────────────────────────────────┐
    │           ConcentrationGridNode         │
    │  • 收集浓度观测                          │
    │  • 构建 3D 网格                          │
    │  • WebSocket 推送                        │
    └─────────────────────────────────────────┘
                        │
                        ▼
              WebSocket (/ws/heatmap)
                        │
                        ▼
    ┌─────────────────────────────────────────┐
    │           Web Console (React)           │
    │  • Three.js 3D 热力图                   │
    │  • 粒子云可视化                          │
    │  • 历史回放控制                          │
    └─────────────────────────────────────────┘
```

## 三、粒子滤波定位模块

### 3.1 核心数据结构

```python
from dataclasses import dataclass
from enum import Enum, auto
import numpy as np
from typing import Protocol

class Particle:
    """单个粒子，表示一个气源位置假设。"""
    position: np.ndarray      # shape: (2,) - [x, y]
    weight: float             # 归一化权重 [0, 1]

@dataclass(frozen=True)
class ParticleFilterConfig:
    """粒子滤波器配置。"""
    num_particles: int = 500
    motion_sigma: float = 0.3       # 运动噪声标准差 (米)
    observation_sigma: float = 0.5  # 观测噪声标准差
    resample_threshold: float = 0.5 # 有效粒子数阈值
    plume_sigma: float = 2.0        # 烟羽扩散参数
    source_strength: float = 1.0    # 源强度

@dataclass
class SourceEstimate:
    """气源位置估计结果。"""
    position: tuple[float, float]
    confidence: float           # 置信度 [0, 1]
    covariance: np.ndarray      # shape: (2, 2)
    candidate_sources: list[tuple[float, float, float]]  # [(x, y, weight), ...]
```

### 3.2 核心接口

```python
class MotionModel(Protocol):
    """粒子运动模型协议。"""
    def predict(self, particle: Particle, dt: float) -> Particle:
        """预测粒子下一时刻状态。"""
        ...

class ObservationModel(Protocol):
    """观测模型协议。"""
    def likelihood(
        self,
        source_hypothesis: np.ndarray,
        robot_position: np.ndarray,
        observed_concentration: float,
    ) -> float:
        """计算观测似然。"""
        ...

class ParticleFilter:
    """粒子滤波器核心类。"""

    def __init__(self, config: ParticleFilterConfig) -> None: ...

    def initialize(self, bounds: tuple[float, float, float, float]) -> None:
        """在指定边界内均匀初始化粒子。"""
        ...

    def predict(self, dt: float) -> None:
        """预测步骤：粒子运动。"""
        ...

    def update(
        self,
        robot_position: tuple[float, float],
        concentration: float,
    ) -> None:
        """更新步骤：根据观测更新权重。"""
        ...

    def resample(self) -> None:
        """重采样：解决粒子退化问题。"""
        ...

    def estimate(self) -> SourceEstimate:
        """估计气源位置。"""
        ...
```

### 3.3 观测模型实现

基于高斯烟羽模型：

```python
class GaussianPlumeObservationModel:
    """高斯烟羽观测模型。"""

    def __init__(self, config: ParticleFilterConfig) -> None:
        self.config = config

    def expected_concentration(
        self,
        source_pos: np.ndarray,
        robot_pos: np.ndarray,
    ) -> float:
        """计算期望浓度。"""
        distance = np.linalg.norm(robot_pos - source_pos)
        if distance < 1e-6:
            return self.config.source_strength
        return self.config.source_strength * np.exp(
            -distance**2 / (2 * self.config.plume_sigma**2)
        )

    def likelihood(
        self,
        source_hypothesis: np.ndarray,
        robot_position: np.ndarray,
        observed_concentration: float,
    ) -> float:
        """计算观测似然。"""
        expected = self.expected_concentration(source_hypothesis, robot_position)
        error = observed_concentration - expected
        return np.exp(-error**2 / (2 * self.config.observation_sigma**2))
```

### 3.4 ROS 节点

```python
class ParticleFilterNode(Node):
    """粒子滤波 ROS 节点。"""

    def __init__(self) -> None:
        super().__init__("particle_filter_node")

        # 参数
        self.declare_parameter("num_particles", 500)
        self.declare_parameter("publish_rate", 2.0)

        # 订阅
        self._gas_sub = self.create_subscription(
            Float32, "/gas_concentration", self._gas_callback, 10
        )
        self._odom_sub = self.create_subscription(
            Odometry, "/odom", self._odom_callback, 10
        )

        # 发布
        self._source_pub = self.create_publisher(
            PoseWithCovarianceStamped, "/estimated_source", 10
        )
        self._particle_pub = self.create_publisher(
            PoseArray, "/particle_cloud", 10
        )

        # 粒子滤波器
        self._filter = ParticleFilter(self._load_config())

    def _gas_callback(self, msg: Float32) -> None:
        """处理气体浓度观测。"""
        if self._current_position is not None:
            self._filter.update(self._current_position, msg.data)
            self._publish_estimate()

    def _odom_callback(self, msg: Odometry) -> None:
        """处理里程计更新。"""
        self._current_position = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
        )
```

## 四、气体分布热力图模块

### 4.1 核心数据结构

```python
@dataclass
class ConcentrationGrid:
    """3D 浓度网格。"""
    resolution: float                    # 米/格子
    dimensions: tuple[int, int, int]     # (nx, ny, nz)
    origin: tuple[float, float, float]   # (x0, y0, z0)
    data: np.ndarray                     # shape: (nx, ny, nz)
    timestamps: np.ndarray               # 最后更新时间

    def update(
        self,
        position: tuple[float, float, float],
        concentration: float,
        timestamp: float,
    ) -> None:
        """更新指定位置的浓度值。"""
        ...

    def decay(self, rate: float) -> None:
        """时间衰减。"""
        self.data *= rate

    def to_dict(self) -> dict:
        """序列化为字典。"""
        ...

@dataclass(frozen=True)
class HeatmapConfig:
    """热力图配置。"""
    resolution: float = 0.5
    decay_rate: float = 0.95
    publish_rate: float = 2.0
    history_length: int = 1000
```

### 4.2 WebSocket 协议

**服务端推送格式：**

```json
{
  "type": "heatmap_update",
  "timestamp": "2026-04-05T12:00:00.000Z",
  "grid": {
    "resolution": 0.5,
    "origin": [-7.5, -10.8, 0.0],
    "dimensions": [30, 22, 5],
    "data": "base64_encoded_float32_array"
  },
  "particles": {
    "positions": [[x1, y1], [x2, y2], ...],
    "weights": [w1, w2, ...]
  },
  "estimate": {
    "position": [3.6, -3.04],
    "confidence": 0.85
  }
}
```

**历史回放请求：**

```json
{
  "type": "replay_request",
  "time_range": {
    "start": "2026-04-05T11:00:00.000Z",
    "end": "2026-04-05T12:00:00.000Z"
  },
  "speed": 2.0
}
```

### 4.3 前端组件

```jsx
// Heatmap3D.jsx
import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export function Heatmap3D({ grid, particles, estimate }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!grid || !containerRef.current) return;

    // 创建 Three.js 场景
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);

    // 创建热力图体素
    const geometry = new THREE.BoxGeometry(
      grid.resolution, grid.resolution, grid.resolution
    );

    grid.data.forEach((value, index) => {
      if (value > threshold) {
        const material = new THREE.MeshBasicMaterial({
          color: colorScale(value),
          transparent: true,
          opacity: value * 0.6,
        });
        const cube = new THREE.Mesh(geometry, material);
        cube.position.set(...indexToPosition(index, grid));
        scene.add(cube);
      }
    });

    // 渲染粒子云
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute('position',
      new THREE.Float32BufferAttribute(particles.positions.flat(), 3)
    );
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x00ff00,
      size: 0.1,
    });
    scene.add(new THREE.Points(particleGeometry, particleMaterial));

    // 渲染循环
    const renderer = new THREE.WebGLRenderer();
    const animate = () => {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    return () => renderer.dispose();
  }, [grid, particles]);

  return <div ref={containerRef} className="heatmap-3d" />;
}
```

## 五、文件结构

```
src/h2track_tracking/h2track_tracking/
├── particle_filter/
│   ├── __init__.py
│   ├── filter.py              # ParticleFilter 核心类
│   ├── motion_model.py        # 运动模型
│   ├── observation_model.py   # 观测模型
│   ├── types.py               # 数据类型定义
│   └── particle_filter_node.py # ROS 节点
│
├── heatmap/
│   ├── __init__.py
│   ├── grid.py                # ConcentrationGrid
│   ├── websocket_handler.py   # WebSocket 处理
│   ├── history_store.py       # 历史数据存储
│   └── heatmap_node.py        # ROS 节点
│
└── web_console/src/
    ├── components/
    │   ├── Heatmap3D.jsx      # 3D 热力图组件
    │   ├── ParticleCloud.jsx  # 粒子云可视化
    │   └── PlaybackControl.jsx # 回放控制
    └── hooks/
        └── useHeatmapData.js  # WebSocket 数据钩子
```

## 六、测试策略

### 6.1 单元测试

```python
# test_particle_filter.py

def test_particle_filter_initialization():
    """测试粒子初始化。"""
    config = ParticleFilterConfig(num_particles=100)
    pf = ParticleFilter(config)
    pf.initialize(bounds=(-5, -5, 5, 5))

    assert len(pf.particles) == 100
    assert all(0 <= p.weight <= 1 for p in pf.particles)
    assert abs(sum(p.weight for p in pf.particles) - 1.0) < 1e-6

def test_observation_model_likelihood():
    """测试观测似然计算。"""
    model = GaussianPlumeObservationModel(ParticleFilterConfig())

    # 源位置假设与机器人位置重合时，期望浓度最高
    likelihood_high = model.likelihood(
        np.array([0, 0]),
        np.array([0, 0]),
        observed_concentration=1.0,
    )

    # 源位置假设远离机器人时，似然较低
    likelihood_low = model.likelihood(
        np.array([10, 10]),
        np.array([0, 0]),
        observed_concentration=1.0,
    )

    assert likelihood_high > likelihood_low

def test_particle_filter_convergence():
    """测试粒子滤波收敛性。"""
    config = ParticleFilterConfig(num_particles=500)
    pf = ParticleFilter(config)
    pf.initialize(bounds=(0, 0, 10, 10))

    true_source = (5.0, 5.0)

    # 模拟观测序列
    for _ in range(100):
        robot_pos = (np.random.uniform(0, 10), np.random.uniform(0, 10))
        distance = np.linalg.norm(np.array(robot_pos) - np.array(true_source))
        concentration = np.exp(-distance**2 / 8) + np.random.normal(0, 0.1)

        pf.update(robot_pos, max(0, concentration))
        pf.predict(0.1)

    estimate = pf.estimate()
    error = np.linalg.norm(np.array(estimate.position) - np.array(true_source))

    assert error < 1.0  # 误差小于 1 米
    assert estimate.confidence > 0.5
```

### 6.2 集成测试

```python
# test_heatmap_integration.py

def test_concentration_grid_update():
    """测试浓度网格更新。"""
    grid = ConcentrationGrid(
        resolution=0.5,
        dimensions=(20, 20, 5),
        origin=(-5, -5, 0),
        data=np.zeros((20, 20, 5)),
        timestamps=np.zeros((20, 20, 5)),
    )

    grid.update((0, 0, 0), 0.8, time.time())

    # 检查更新后的值
    ix, iy, iz = grid.world_to_grid((0, 0, 0))
    assert grid.data[ix, iy, iz] == 0.8

def test_websocket_heatmap_update(client):
    """测试 WebSocket 热力图更新。"""
    with client.websocket_connect("/ws/heatmap") as ws:
        # 等待更新
        data = ws.receive_json()

        assert data["type"] == "heatmap_update"
        assert "grid" in data
        assert "particles" in data
```

## 七、性能考虑

### 7.1 粒子滤波性能

| 参数 | 默认值 | 影响 |
|------|--------|------|
| num_particles | 500 | 精度 vs 计算量 |
| publish_rate | 2 Hz | 实时性 vs CPU |
| resample_threshold | 0.5 | 粒子多样性 |

**优化策略：**
- 使用 NumPy 向量化操作
- 多线程重采样
- 自适应粒子数量

### 7.2 热力图性能

| 参数 | 默认值 | 影响 |
|------|--------|------|
| resolution | 0.5m | 精度 vs 内存 |
| decay_rate | 0.95 | 历史影响 |
| history_length | 1000 | 回放时长 |

**优化策略：**
- 稀疏网格存储
- 增量更新
- LOD (Level of Detail) 渲染

## 八、实现计划

### Phase 1: 粒子滤波核心 (1-2 天)

1. 实现 `ParticleFilter` 类
2. 实现运动模型和观测模型
3. 单元测试

### Phase 2: ROS 集成 (1 天)

1. 创建 `ParticleFilterNode`
2. 订阅/发布话题
3. 集成测试

### Phase 3: 热力图后端 (1-2 天)

1. 实现 `ConcentrationGrid`
2. WebSocket 处理
3. 历史数据存储

### Phase 4: 前端可视化 (2-3 天)

1. Three.js 热力图组件
2. 粒子云可视化
3. 回放控制

### Phase 5: 集成测试 (1 天)

1. 端到端测试
2. 性能优化
3. 文档更新

## 九、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 粒子退化 | 定位失败 | 自适应重采样 |
| 计算延迟 | 实时性差 | 降低粒子数，GPU 加速 |
| 内存占用 | 系统崩溃 | 稀疏存储，限制历史长度 |
| 前端性能 | 卡顿 | LOD 渲染，WebWorker |

## 十、参考资料

- [Particle Filters for Robot Localization](https://robots.stanford.edu/papers/thrun.pf-localization.pdf)
- [Gaussian Plume Model](https://en.wikipedia.org/wiki/Atmospheric_dispersion_modeling#Gaussian_plume_model)
- [Three.js Documentation](https://threejs.org/docs/)
- [ROS 2 Nav2 Architecture](https://navigation.ros.org/)
