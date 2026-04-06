# 粒子滤波定位与气体分布热力图实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 H2Track 添加粒子滤波气源定位和 3D 气体分布热力图功能。

**Architecture:** 粒子滤波作为独立模块与现有状态机并行运行，通过 ROS 话题发布源位置估计。热力图模块收集浓度观测构建 3D 网格，通过 WebSocket 推送到前端 Three.js 渲染。

**Tech Stack:** Python 3.10, NumPy, ROS 2 Humble, Flask, WebSocket, React, Three.js

---

## 文件结构

```
src/h2track_tracking/h2track_tracking/
├── particle_filter/
│   ├── __init__.py              # 模块导出
│   ├── types.py                 # 数据类型定义
│   ├── motion_model.py          # 运动模型
│   ├── observation_model.py     # 观测模型
│   ├── filter.py                # 粒子滤波核心
│   └── particle_filter_node.py  # ROS 节点
│
├── heatmap/
│   ├── __init__.py              # 模块导出
│   ├── grid.py                  # 浓度网格
│   ├── history_store.py         # 历史存储
│   └── websocket_handler.py     # WebSocket 处理
│
└── web_console/src/
    ├── components/
    │   ├── Heatmap3D.jsx        # 3D 热力图
    │   └── ParticleCloud.jsx    # 粒子云
    └── hooks/
        └── useHeatmapData.js    # 数据钩子
```

---

## Task 1: 粒子滤波数据类型定义

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/particle_filter/__init__.py`
- Create: `src/h2track_tracking/h2track_tracking/particle_filter/types.py`
- Test: `src/h2track_tracking/test/test_particle_filter_types.py`

- [ ] **Step 1: 创建测试文件**

```python
# src/h2track_tracking/test/test_particle_filter_types.py
"""Tests for particle filter type definitions."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import (
    Particle,
    ParticleFilterConfig,
    SourceEstimate,
)


class TestParticle:
    def test_particle_creation(self):
        particle = Particle(position=np.array([1.0, 2.0]), weight=0.5)
        assert particle.position.shape == (2,)
        assert particle.weight == 0.5

    def test_particle_weight_normalization(self):
        particle = Particle(position=np.array([0.0, 0.0]), weight=1.5)
        assert particle.weight == 1.5  # 不自动归一化

    def test_particle_copy(self):
        p1 = Particle(position=np.array([1.0, 2.0]), weight=0.5)
        p2 = Particle(position=p1.position.copy(), weight=p1.weight)
        p2.position[0] = 5.0
        assert p1.position[0] == 1.0


class TestParticleFilterConfig:
    def test_default_config(self):
        config = ParticleFilterConfig()
        assert config.num_particles == 500
        assert config.motion_sigma == 0.3
        assert config.observation_sigma == 0.5

    def test_custom_config(self):
        config = ParticleFilterConfig(
            num_particles=1000,
            motion_sigma=0.5,
            observation_sigma=0.3,
        )
        assert config.num_particles == 1000

    def test_frozen_config(self):
        config = ParticleFilterConfig()
        with pytest.raises(Exception):
            config.num_particles = 2000


class TestSourceEstimate:
    def test_source_estimate_creation(self):
        estimate = SourceEstimate(
            position=(3.6, -3.04),
            confidence=0.85,
            covariance=np.array([[0.1, 0.0], [0.0, 0.1]]),
            candidate_sources=[(3.5, -3.0, 0.3), (3.7, -3.1, 0.25)],
        )
        assert estimate.position == (3.6, -3.04)
        assert estimate.confidence == 0.85

    def test_source_estimate_covariance_shape(self):
        estimate = SourceEstimate(
            position=(0.0, 0.0),
            confidence=0.5,
            covariance=np.eye(2),
            candidate_sources=[],
        )
        assert estimate.covariance.shape == (2, 2)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_particle_filter_types.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'h2track_tracking.particle_filter'"

- [ ] **Step 3: 创建模块目录和类型定义**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/__init__.py
"""Particle filter module for probabilistic gas source localization."""

from .types import Particle, ParticleFilterConfig, SourceEstimate

__all__ = ["Particle", "ParticleFilterConfig", "SourceEstimate"]
```

```python
# src/h2track_tracking/h2track_tracking/particle_filter/types.py
"""Data types for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from typing import NamedTuple


@dataclass
class Particle:
    """Single particle representing a gas source position hypothesis."""

    position: np.ndarray  # shape: (2,) - [x, y]
    weight: float  # normalized weight [0, 1]


@dataclass(frozen=True)
class ParticleFilterConfig:
    """Configuration for particle filter."""

    num_particles: int = 500
    motion_sigma: float = 0.3  # motion noise std (meters)
    observation_sigma: float = 0.5  # observation noise std
    resample_threshold: float = 0.5  # effective particle ratio threshold
    plume_sigma: float = 2.0  # plume dispersion parameter
    source_strength: float = 1.0  # source strength


@dataclass
class SourceEstimate:
    """Gas source position estimate result."""

    position: tuple[float, float]
    confidence: float  # [0, 1]
    covariance: np.ndarray  # shape: (2, 2)
    candidate_sources: list[tuple[float, float, float]]  # [(x, y, weight), ...]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_particle_filter_types.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/h2track_tracking/h2track_tracking/particle_filter/
git add src/h2track_tracking/test/test_particle_filter_types.py
git commit -m "feat(particle-filter): add type definitions for particle filter"
```

---

## Task 2: 运动模型实现

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/particle_filter/motion_model.py`
- Test: `src/h2track_tracking/test/test_motion_model.py`

- [ ] **Step 1: 创建测试文件**

```python
# src/h2track_tracking/test/test_motion_model.py
"""Tests for particle filter motion model."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import Particle, ParticleFilterConfig
from h2track_tracking.particle_filter.motion_model import RandomWalkMotionModel


class TestRandomWalkMotionModel:
    def test_motion_model_creation(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        assert model.sigma == 0.5

    def test_predict_moves_particle(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([0.0, 0.0]), weight=1.0)

        np.random.seed(42)
        new_particle = model.predict(particle, dt=1.0)

        # 粒子应该移动了
        assert not np.allclose(new_particle.position, particle.position)

    def test_predict_preserves_weight(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([0.0, 0.0]), weight=0.5)

        new_particle = model.predict(particle, dt=1.0)

        assert new_particle.weight == 0.5

    def test_predict_with_zero_sigma(self):
        config = ParticleFilterConfig(motion_sigma=0.0)
        model = RandomWalkMotionModel(config)
        particle = Particle(position=np.array([1.0, 2.0]), weight=1.0)

        new_particle = model.predict(particle, dt=1.0)

        # sigma=0 时粒子不应该移动
        assert np.allclose(new_particle.position, particle.position)

    def test_predict_multiple_particles(self):
        config = ParticleFilterConfig(motion_sigma=0.5)
        model = RandomWalkMotionModel(config)
        particles = [
            Particle(position=np.array([0.0, 0.0]), weight=0.5),
            Particle(position=np.array([1.0, 1.0]), weight=0.5),
        ]

        new_particles = [model.predict(p, dt=1.0) for p in particles]

        assert len(new_particles) == 2
        assert new_particles[0].weight == 0.5
        assert new_particles[1].weight == 0.5
```

- [ ] **Step 2: 运行测试验证失败**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_motion_model.py -v
```

Expected: FAIL with "ImportError"

- [ ] **Step 3: 实现运动模型**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/motion_model.py
"""Motion model for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .types import Particle, ParticleFilterConfig


@dataclass
class RandomWalkMotionModel:
    """Random walk motion model for particles."""

    config: ParticleFilterConfig

    @property
    def sigma(self) -> float:
        return self.config.motion_sigma

    def predict(self, particle: Particle, dt: float = 1.0) -> Particle:
        """Predict particle state using random walk.

        Args:
            particle: Current particle state
            dt: Time step (affects noise magnitude)

        Returns:
            New particle with updated position
        """
        if self.sigma <= 0.0:
            return Particle(
                position=particle.position.copy(),
                weight=particle.weight,
            )

        noise = np.random.normal(0, self.sigma * np.sqrt(dt), size=2)
        new_position = particle.position + noise

        return Particle(
            position=new_position,
            weight=particle.weight,
        )
```

- [ ] **Step 4: 更新模块导出**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/__init__.py
"""Particle filter module for probabilistic gas source localization."""

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel

__all__ = [
    "Particle",
    "ParticleFilterConfig",
    "SourceEstimate",
    "RandomWalkMotionModel",
]
```

- [ ] **Step 5: 运行测试验证通过**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_motion_model.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/h2track_tracking/h2track_tracking/particle_filter/
git add src/h2track_tracking/test/test_motion_model.py
git commit -m "feat(particle-filter): add random walk motion model"
```

---

## Task 3: 观测模型实现

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/particle_filter/observation_model.py`
- Test: `src/h2track_tracking/test/test_observation_model.py`

- [ ] **Step 1: 创建测试文件**

```python
# src/h2track_tracking/test/test_observation_model.py
"""Tests for particle filter observation model."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import ParticleFilterConfig
from h2track_tracking.particle_filter.observation_model import GaussianPlumeObservationModel


class TestGaussianPlumeObservationModel:
    def test_model_creation(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)
        assert model.plume_sigma == 2.0
        assert model.source_strength == 1.0

    def test_expected_concentration_at_source(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 机器人在源位置时浓度最高
        concentration = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([0.0, 0.0]),
        )
        assert concentration == pytest.approx(1.0, rel=0.01)

    def test_expected_concentration_far_from_source(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 机器人远离源时浓度较低
        concentration = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([10.0, 10.0]),
        )
        assert concentration < 0.1

    def test_likelihood_high_when_observation_matches(self):
        config = ParticleFilterConfig(
            plume_sigma=2.0,
            source_strength=1.0,
            observation_sigma=0.5,
        )
        model = GaussianPlumeObservationModel(config)

        # 观测值与期望值匹配时似然高
        likelihood = model.likelihood(
            source_hypothesis=np.array([0.0, 0.0]),
            robot_position=np.array([0.0, 0.0]),
            observed_concentration=1.0,
        )
        assert likelihood > 0.9

    def test_likelihood_low_when_observation_mismatched(self):
        config = ParticleFilterConfig(
            plume_sigma=2.0,
            source_strength=1.0,
            observation_sigma=0.5,
        )
        model = GaussianPlumeObservationModel(config)

        # 观测值与期望值不匹配时似然低
        likelihood = model.likelihood(
            source_hypothesis=np.array([10.0, 10.0]),
            robot_position=np.array([0.0, 0.0]),
            observed_concentration=1.0,
        )
        assert likelihood < 0.5

    def test_likelihood_symmetry(self):
        config = ParticleFilterConfig(plume_sigma=2.0, source_strength=1.0)
        model = GaussianPlumeObservationModel(config)

        # 等距位置应有相同期望浓度
        c1 = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([1.0, 0.0]),
        )
        c2 = model.expected_concentration(
            source_pos=np.array([0.0, 0.0]),
            robot_pos=np.array([0.0, 1.0]),
        )
        assert c1 == pytest.approx(c2, rel=0.01)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_observation_model.py -v
```

Expected: FAIL with "ImportError"

- [ ] **Step 3: 实现观测模型**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/observation_model.py
"""Observation model for particle filter."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .types import ParticleFilterConfig


@dataclass
class GaussianPlumeObservationModel:
    """Gaussian plume observation model for gas concentration."""

    config: ParticleFilterConfig

    @property
    def plume_sigma(self) -> float:
        return self.config.plume_sigma

    @property
    def source_strength(self) -> float:
        return self.config.source_strength

    @property
    def observation_sigma(self) -> float:
        return self.config.observation_sigma

    def expected_concentration(
        self,
        source_pos: np.ndarray,
        robot_pos: np.ndarray,
    ) -> float:
        """Calculate expected concentration at robot position.

        Uses Gaussian plume model: C = Q * exp(-d² / (2 * σ²))

        Args:
            source_pos: Hypothesized source position [x, y]
            robot_pos: Robot position [x, y]

        Returns:
            Expected concentration at robot position
        """
        distance = np.linalg.norm(robot_pos - source_pos)
        if distance < 1e-6:
            return self.source_strength

        return self.source_strength * np.exp(
            -distance**2 / (2 * self.plume_sigma**2)
        )

    def likelihood(
        self,
        source_hypothesis: np.ndarray,
        robot_position: np.ndarray,
        observed_concentration: float,
    ) -> float:
        """Calculate observation likelihood.

        Args:
            source_hypothesis: Hypothesized source position [x, y]
            robot_position: Current robot position [x, y]
            observed_concentration: Measured concentration

        Returns:
            Likelihood value [0, 1]
        """
        expected = self.expected_concentration(source_hypothesis, robot_position)
        error = observed_concentration - expected

        # Gaussian likelihood
        return np.exp(-error**2 / (2 * self.observation_sigma**2))
```

- [ ] **Step 4: 更新模块导出**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/__init__.py
"""Particle filter module for probabilistic gas source localization."""

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel
from .observation_model import GaussianPlumeObservationModel

__all__ = [
    "Particle",
    "ParticleFilterConfig",
    "SourceEstimate",
    "RandomWalkMotionModel",
    "GaussianPlumeObservationModel",
]
```

- [ ] **Step 5: 运行测试验证通过**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_observation_model.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/h2track_tracking/h2track_tracking/particle_filter/
git add src/h2track_tracking/test/test_observation_model.py
git commit -m "feat(particle-filter): add Gaussian plume observation model"
```

---

## Task 4: 粒子滤波核心实现

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/particle_filter/filter.py`
- Test: `src/h2track_tracking/test/test_particle_filter.py`

- [ ] **Step 1: 创建测试文件**

```python
# src/h2track_tracking/test/test_particle_filter.py
"""Tests for particle filter core."""

import pytest
import numpy as np

from h2track_tracking.particle_filter.types import ParticleFilterConfig
from h2track_tracking.particle_filter.filter import ParticleFilter


class TestParticleFilter:
    def test_initialization(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(-5, -5, 5, 5))

        assert len(pf.particles) == 100
        assert all(0 <= p.weight <= 1 for p in pf.particles)

    def test_weight_normalization(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(-5, -5, 5, 5))

        total_weight = sum(p.weight for p in pf.particles)
        assert total_weight == pytest.approx(1.0, rel=0.01)

    def test_particles_within_bounds(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        for p in pf.particles:
            assert 0 <= p.position[0] <= 10
            assert 0 <= p.position[1] <= 10

    def test_predict_moves_particles(self):
        config = ParticleFilterConfig(num_particles=100, motion_sigma=0.5)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        old_positions = [p.position.copy() for p in pf.particles]
        pf.predict(dt=1.0)

        # 至少有一些粒子移动了
        moved = sum(
            1 for old, p in zip(old_positions, pf.particles)
            if not np.allclose(old, p.position)
        )
        assert moved > 0

    def test_update_changes_weights(self):
        config = ParticleFilterConfig(num_particles=100, observation_sigma=0.5)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        old_weights = [p.weight for p in pf.particles]
        pf.update(robot_position=(5.0, 5.0), concentration=0.5)

        # 权重应该改变
        new_weights = [p.weight for p in pf.particles]
        assert old_weights != new_weights

    def test_resample_maintains_particle_count(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        # 人为设置权重差异
        for i, p in enumerate(pf.particles):
            p.weight = 1.0 if i == 0 else 0.001
        pf._normalize_weights()

        pf.resample()
        assert len(pf.particles) == 100

    def test_estimate_returns_result(self):
        config = ParticleFilterConfig(num_particles=100)
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        estimate = pf.estimate()

        assert estimate.position is not None
        assert 0 <= estimate.confidence <= 1
        assert estimate.covariance.shape == (2, 2)

    def test_convergence_to_source(self):
        """Test that filter converges to true source location."""
        config = ParticleFilterConfig(
            num_particles=500,
            plume_sigma=2.0,
            observation_sigma=0.3,
        )
        pf = ParticleFilter(config)
        pf.initialize(bounds=(0, 0, 10, 10))

        true_source = np.array([5.0, 5.0])

        # Simulate observations near the source
        np.random.seed(42)
        for _ in range(50):
            # Robot moves randomly
            robot_pos = np.random.uniform(0, 10, 2)
            distance = np.linalg.norm(robot_pos - true_source)
            concentration = np.exp(-distance**2 / (2 * config.plume_sigma**2))
            concentration += np.random.normal(0, 0.05)  # noise
            concentration = max(0, concentration)

            pf.update(tuple(robot_pos), concentration)
            pf.predict(dt=0.1)

        estimate = pf.estimate()
        error = np.linalg.norm(np.array(estimate.position) - true_source)

        # Should converge within 2 meters
        assert error < 2.0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_particle_filter.py -v
```

Expected: FAIL with "ImportError"

- [ ] **Step 3: 实现粒子滤波核心**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/filter.py
"""Particle filter core implementation."""

from __future__ import annotations

import math
import numpy as np
from typing import Protocol

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel
from .observation_model import GaussianPlumeObservationModel


class ParticleFilter:
    """Particle filter for gas source localization."""

    def __init__(self, config: ParticleFilterConfig) -> None:
        self.config = config
        self.particles: list[Particle] = []
        self._motion_model = RandomWalkMotionModel(config)
        self._observation_model = GaussianPlumeObservationModel(config)

    def initialize(
        self,
        bounds: tuple[float, float, float, float],
    ) -> None:
        """Initialize particles uniformly within bounds.

        Args:
            bounds: (min_x, min_y, max_x, max_y)
        """
        min_x, min_y, max_x, max_y = bounds
        n = self.config.num_particles

        # Uniform distribution
        positions = np.random.uniform(
            low=[min_x, min_y],
            high=[max_x, max_y],
            size=(n, 2),
        )

        # Equal weights
        weight = 1.0 / n

        self.particles = [
            Particle(position=pos, weight=weight)
            for pos in positions
        ]

    def predict(self, dt: float = 1.0) -> None:
        """Predict step: move particles according to motion model."""
        self.particles = [
            self._motion_model.predict(p, dt)
            for p in self.particles
        ]

    def update(
        self,
        robot_position: tuple[float, float],
        concentration: float,
    ) -> None:
        """Update step: adjust weights based on observation.

        Args:
            robot_position: Current robot position (x, y)
            concentration: Observed gas concentration
        """
        robot_pos = np.array(robot_position)

        for particle in self.particles:
            likelihood = self._observation_model.likelihood(
                source_hypothesis=particle.position,
                robot_position=robot_pos,
                observed_concentration=concentration,
            )
            particle.weight *= likelihood

        self._normalize_weights()

    def resample(self) -> None:
        """Resample particles to combat degeneracy."""
        if not self.particles:
            return

        # Systematic resampling
        weights = np.array([p.weight for p in self.particles])
        n = len(self.particles)

        # Cumulative sum
        cumsum = np.cumsum(weights)
        cumsum[-1] = 1.0  # Ensure sum is exactly 1

        # Systematic resampling positions
        positions = (np.arange(n) + np.random.uniform()) / n

        # Resample indices
        indices = np.searchsorted(cumsum, positions)

        # Create new particles
        new_particles = [
            Particle(
                position=self.particles[i].position.copy(),
                weight=1.0 / n,
            )
            for i in indices
        ]

        self.particles = new_particles

    def estimate(self) -> SourceEstimate:
        """Estimate source location from particles.

        Returns:
            SourceEstimate with position, confidence, and candidates
        """
        if not self.particles:
            return SourceEstimate(
                position=(0.0, 0.0),
                confidence=0.0,
                covariance=np.eye(2) * 1e6,
                candidate_sources=[],
            )

        # Weighted mean
        positions = np.array([p.position for p in self.particles])
        weights = np.array([p.weight for p in self.particles])

        mean = np.average(positions, axis=0, weights=weights)

        # Weighted covariance
        diff = positions - mean
        cov = np.cov(diff.T, aweights=weights)

        # Confidence based on effective particle count
        effective_count = 1.0 / np.sum(weights**2)
        max_effective = len(self.particles)
        confidence = min(1.0, effective_count / (max_effective * 0.5))

        # Top candidates (highest weight particles)
        sorted_indices = np.argsort(weights)[::-1]
        candidates = [
            (
                float(self.particles[i].position[0]),
                float(self.particles[i].position[1]),
                float(self.particles[i].weight),
            )
            for i in sorted_indices[:5]
        ]

        return SourceEstimate(
            position=(float(mean[0]), float(mean[1])),
            confidence=float(confidence),
            covariance=cov if cov.shape == (2, 2) else np.eye(2) * np.var(positions),
            candidate_sources=candidates,
        )

    def _normalize_weights(self) -> None:
        """Normalize particle weights to sum to 1."""
        total = sum(p.weight for p in self.particles)
        if total > 0:
            for p in self.particles:
                p.weight /= total

    def effective_particle_count(self) -> float:
        """Calculate effective particle count.

        Used to determine when resampling is needed.
        """
        weights = np.array([p.weight for p in self.particles])
        return 1.0 / np.sum(weights**2)
```

- [ ] **Step 4: 更新模块导出**

```python
# src/h2track_tracking/h2track_tracking/particle_filter/__init__.py
"""Particle filter module for probabilistic gas source localization."""

from .types import Particle, ParticleFilterConfig, SourceEstimate
from .motion_model import RandomWalkMotionModel
from .observation_model import GaussianPlumeObservationModel
from .filter import ParticleFilter

__all__ = [
    "Particle",
    "ParticleFilterConfig",
    "SourceEstimate",
    "RandomWalkMotionModel",
    "GaussianPlumeObservationModel",
    "ParticleFilter",
]
```

- [ ] **Step 5: 运行测试验证通过**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_particle_filter.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/h2track_tracking/h2track_tracking/particle_filter/
git add src/h2track_tracking/test/test_particle_filter.py
git commit -m "feat(particle-filter): implement particle filter core"
```

---

## Task 5: 浓度网格实现

**Files:**
- Create: `src/h2track_tracking/h2track_tracking/heatmap/__init__.py`
- Create: `src/h2track_tracking/h2track_tracking/heatmap/grid.py`
- Test: `src/h2track_tracking/test/test_concentration_grid.py`

- [ ] **Step 1: 创建测试文件**

```python
# src/h2track_tracking/test/test_concentration_grid.py
"""Tests for concentration grid."""

import pytest
import numpy as np
import time

from h2track_tracking.heatmap.grid import ConcentrationGrid, HeatmapConfig


class TestHeatmapConfig:
    def test_default_config(self):
        config = HeatmapConfig()
        assert config.resolution == 0.5
        assert config.decay_rate == 0.95

    def test_custom_config(self):
        config = HeatmapConfig(resolution=0.25, decay_rate=0.9)
        assert config.resolution == 0.25


class TestConcentrationGrid:
    def test_grid_creation(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        assert grid.dimensions == (20, 20, 5)
        assert grid.resolution == 0.5

    def test_world_to_grid_conversion(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        # Origin should map to (0, 0, 0)
        ix, iy, iz = grid.world_to_grid((-5.0, -5.0, 0.0))
        assert (ix, iy, iz) == (0, 0, 0)

        # (0, 0, 0) world should map to (10, 10, 0)
        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert (ix, iy, iz) == (10, 10, 0)

    def test_grid_to_world_conversion(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        x, y, z = grid.grid_to_world(0, 0, 0)
        assert (x, y, z) == pytest.approx((-5.0, -5.0, 0.0))

    def test_update_concentration(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        grid.update(
            position=(0.0, 0.0, 0.0),
            concentration=0.8,
            timestamp=time.time(),
        )

        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert grid.data[ix, iy, iz] == pytest.approx(0.8, rel=0.01)

    def test_decay(self):
        config = HeatmapConfig(resolution=0.5, decay_rate=0.9)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        grid.update(
            position=(0.0, 0.0, 0.0),
            concentration=1.0,
            timestamp=time.time(),
        )

        grid.decay()

        ix, iy, iz = grid.world_to_grid((0.0, 0.0, 0.0))
        assert grid.data[ix, iy, iz] == pytest.approx(0.9, rel=0.01)

    def test_to_dict_serialization(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(10, 10, 3),
            origin=(-5.0, -5.0, 0.0),
        )

        data = grid.to_dict()

        assert data["resolution"] == 0.5
        assert data["dimensions"] == (10, 10, 3)
        assert data["origin"] == (-5.0, -5.0, 0.0)
        assert "data" in data

    def test_out_of_bounds_handling(self):
        config = HeatmapConfig(resolution=0.5)
        grid = ConcentrationGrid(
            config=config,
            dimensions=(20, 20, 5),
            origin=(-5.0, -5.0, 0.0),
        )

        # Should not raise for out of bounds
        grid.update(
            position=(100.0, 100.0, 100.0),
            concentration=0.5,
            timestamp=time.time(),
        )

        # Data should remain unchanged
        assert np.sum(grid.data) == 0.0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_concentration_grid.py -v
```

Expected: FAIL with "ImportError"

- [ ] **Step 3: 实现浓度网格**

```python
# src/h2track_tracking/h2track_tracking/heatmap/__init__.py
"""Heatmap module for gas concentration visualization."""

from .grid import ConcentrationGrid, HeatmapConfig

__all__ = ["ConcentrationGrid", "HeatmapConfig"]
```

```python
# src/h2track_tracking/h2track_tracking/heatmap/grid.py
"""3D concentration grid for heatmap visualization."""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import numpy as np
import time


@dataclass(frozen=True)
class HeatmapConfig:
    """Configuration for concentration heatmap."""

    resolution: float = 0.5  # meters per cell
    decay_rate: float = 0.95  # time decay factor
    publish_rate: float = 2.0  # Hz
    history_length: int = 1000  # number of snapshots to keep


@dataclass
class ConcentrationGrid:
    """3D grid for storing gas concentration values."""

    config: HeatmapConfig
    dimensions: tuple[int, int, int]  # (nx, ny, nz)
    origin: tuple[float, float, float]  # (x0, y0, z0)
    data: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 1), dtype=np.float32))
    timestamps: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 1), dtype=np.float64))

    def __post_init__(self) -> None:
        nx, ny, nz = self.dimensions
        if self.data.shape != (nx, ny, nz):
            object.__setattr__(self, 'data', np.zeros((nx, ny, nz), dtype=np.float32))
        if self.timestamps.shape != (nx, ny, nz):
            object.__setattr__(self, 'timestamps', np.zeros((nx, ny, nz), dtype=np.float64))

    @property
    def resolution(self) -> float:
        return self.config.resolution

    def world_to_grid(
        self,
        position: tuple[float, float, float],
    ) -> tuple[int, int, int]:
        """Convert world coordinates to grid indices."""
        x, y, z = position
        x0, y0, z0 = self.origin
        res = self.resolution

        ix = int((x - x0) / res)
        iy = int((y - y0) / res)
        iz = int((z - z0) / res)

        return (ix, iy, iz)

    def grid_to_world(
        self,
        ix: int,
        iy: int,
        iz: int,
    ) -> tuple[float, float, float]:
        """Convert grid indices to world coordinates."""
        x0, y0, z0 = self.origin
        res = self.resolution

        x = x0 + ix * res + res / 2
        y = y0 + iy * res + res / 2
        z = z0 + iz * res + res / 2

        return (x, y, z)

    def update(
        self,
        position: tuple[float, float, float],
        concentration: float,
        timestamp: float,
    ) -> None:
        """Update concentration at a position."""
        ix, iy, iz = self.world_to_grid(position)

        # Check bounds
        nx, ny, nz = self.dimensions
        if not (0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz):
            return

        self.data[ix, iy, iz] = concentration
        self.timestamps[ix, iy, iz] = timestamp

    def decay(self) -> None:
        """Apply time decay to all values."""
        self.data *= self.config.decay_rate

    def to_dict(self) -> dict:
        """Serialize grid to dictionary for JSON/WebSocket."""
        # Encode data as base64 for efficient transfer
        data_bytes = self.data.tobytes()
        data_b64 = base64.b64encode(data_bytes).decode('ascii')

        return {
            "resolution": self.resolution,
            "dimensions": self.dimensions,
            "origin": self.origin,
            "data": data_b64,
            "dtype": "float32",
        }

    def clear(self) -> None:
        """Reset all concentration values to zero."""
        self.data.fill(0.0)
        self.timestamps.fill(0.0)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest src/h2track_tracking/test/test_concentration_grid.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/h2track_tracking/h2track_tracking/heatmap/
git add src/h2track_tracking/test/test_concentration_grid.py
git commit -m "feat(heatmap): add 3D concentration grid"
```

---

## Task 6: 运行所有测试验证

- [ ] **Step 1: 运行完整测试套件**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest \
  src/h2track_tracking/test/test_particle_filter_types.py \
  src/h2track_tracking/test/test_motion_model.py \
  src/h2track_tracking/test/test_observation_model.py \
  src/h2track_tracking/test/test_particle_filter.py \
  src/h2track_tracking/test/test_concentration_grid.py \
  -v
```

Expected: All tests PASS

- [ ] **Step 2: 运行现有测试确保无回归**

```bash
PYTHONPATH=src/h2track_tracking:$PYTHONPATH python3 -m pytest \
  src/h2track_tracking/test/test_mission_logic.py \
  src/h2track_tracking/test/test_gas_model.py \
  src/h2track_tracking/test/test_gaden_adapter.py \
  -v
```

Expected: All tests PASS

---

## 后续任务 (Phase 2-5)

以下任务需要在后续阶段完成：

### Phase 2: ROS 集成
- Task 7: 创建 `ParticleFilterNode` ROS 节点
- Task 8: 集成到 bringup.launch.py

### Phase 3: 热力图后端
- Task 9: 实现历史数据存储
- Task 10: WebSocket 处理器集成

### Phase 4: 前端可视化
- Task 11: Three.js 热力图组件
- Task 12: 粒子云可视化

### Phase 5: 集成测试
- Task 13: 端到端测试
- Task 14: 性能优化

---

## 检查清单

- [x] 所有文件路径明确
- [x] 每个步骤包含完整代码
- [x] 遵循 TDD 流程
- [x] 无占位符 (TBD/TODO)
- [x] 测试命令和预期输出明确
