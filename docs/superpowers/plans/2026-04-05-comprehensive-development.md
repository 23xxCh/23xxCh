# H2Track-Xian 综合开发计划

> **创建日期:** 2026-04-05
> **目标:** 全面提升项目质量、自动化水平和功能完备性

---

## 总览

| 方向 | 任务数 | 预计工时 | 风险等级 |
|------|--------|----------|----------|
| CI/CD 自动化 | 6 | 2-3天 | 低 |
| 测试覆盖增强 | 5 | 2-3天 | 低 |
| 架构持续优化 | 4 | 3-4天 | 中 |
| 功能增强开发 | 5 | 5-7天 | 中 |
| 多地图支持 | 4 | 3-4天 | 中 |

**总计:** 24 任务，约 15-21 天工作量

---

## 阶段 1: CI/CD 自动化 (优先级: 高)

**目标:** 建立自动化质量门禁，确保代码质量

### Task 1.1: 创建 pyproject.toml 配置

**文件:** `pyproject.toml`

**内容:**
```toml
[project]
name = "h2track_tracking"
version = "0.2.0"
requires-python = ">=3.10"

[tool.ruff]
line-length = 100
target-version = "py310"
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]
exclude = ["install/", "build/", "log/"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["src/h2track_tracking/test"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src/h2track_tracking/h2track_tracking"]
omit = ["*/test/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 70
show_missing = true
```

**验证:** `ruff check src/` 和 `mypy src/`

---

### Task 1.2: 创建 GitHub Actions CI 工作流

**文件:** `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install ruff mypy
      - run: ruff check src/h2track_tracking/
      - run: mypy src/h2track_tracking/ --ignore-missing-imports

  test:
    runs-on: ubuntu-22.04
    container:
      image: ros:humble
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: |
          apt-get update
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          source /opt/ros/humble/setup.bash
          pytest src/h2track_tracking/test/ -v --cov --cov-report=xml
      - uses: codecov/codecov-action@v4
        with:
          files: coverage.xml

  build:
    runs-on: ubuntu-22.04
    container:
      image: ros:humble
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: |
          source /opt/ros/humble/setup.bash
          colcon build
```

**验证:** 推送后查看 Actions 标签页

---

### Task 1.3: 创建 pre-commit 配置

**文件:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
        additional_dependencies: [types-all]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**安装:** `pre-commit install`

---

### Task 1.4: 添加测试覆盖率目标

**文件:** `Makefile` (新增)

```makefile
.PHONY: test coverage lint format

test:
	pytest src/h2track_tracking/test/ -v

coverage:
	pytest src/h2track_tracking/test/ -v --cov --cov-report=term-missing --cov-fail-under=70

lint:
	ruff check src/h2track_tracking/
	mypy src/h2track_tracking/ --ignore-missing-imports

format:
	ruff format src/h2track_tracking/
```

---

### Task 1.5: 添加代码质量徽章

**文件:** `README.md` (更新)

在文件顶部添加:
```markdown
[![CI](https://github.com/user/h2track-xian/actions/workflows/ci.yml/badge.svg)](https://github.com/user/h2track-xian/actions)
[![Coverage](https://codecov.io/gh/user/h2track-xian/branch/main/graph/badge.svg)](https://codecov.io/gh/user/h2track-xian)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
```

---

### Task 1.6: 配置 Dependabot

**文件:** `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

---

## 阶段 2: 测试覆盖增强 (优先级: 高)

**目标:** 达到 80%+ 测试覆盖率

### Task 2.1: 配置 pytest-cov

**操作:**
1. 添加 `pytest-cov` 到依赖
2. 运行覆盖率报告识别未覆盖模块

```bash
pytest --cov --cov-report=html
```

---

### Task 2.2: 补充 llm/client.py 测试

**文件:** `src/h2track_tracking/test/test_llm_client.py`

**测试内容:**
- `test_endpoint_for_http()` - HTTP 端点构建
- `test_endpoint_for_https()` - HTTPS 端点构建
- `test_post_json_success()` - 成功 POST 请求
- `test_post_json_failure()` - 失败 POST 请求
- `test_extract_chat_text_with_content()` - 解析 chat 响应
- `test_extract_responses_text()` - 解析 responses API 响应
- `test_call_with_chat_protocol()` - chat 协议调用
- `test_call_with_responses_protocol()` - responses 协议调用
- `test_call_handles_timeout()` - 超时处理
- `test_call_handles_error()` - 错误处理

---

### Task 2.3: 补充 ROS 节点测试

**文件:** `src/h2track_tracking/test/test_mission_manager_node.py`

使用 `rclpy` 测试工具:
```python
import rclpy
from rclpy.node import Node
from unittest.mock import Mock, patch

@pytest.fixture
def rclpy_init():
    rclpy.init()
    yield
    rclpy.shutdown()

def test_node_publishes_mode_transition(rclpy_init):
    # Test mission state machine integration
    ...
```

---

### Task 2.4: 补充 gaden_adapter 测试

**文件:** `src/h2track_tracking/test/test_gaden_adapter.py`

**测试内容:**
- GasSensor 消息解析
- 浓度值转换
- 话题发布

---

### Task 2.5: 集成测试增强

**文件:** `src/h2track_tracking/test/test_integration.py`

**测试场景:**
- 完整仿真启动流程 (mock)
- Web API 端到端测试
- LLM 控制器集成测试

---

## 阶段 3: 架构持续优化 (优先级: 中)

**目标:** 降低复杂度，提高可维护性

### Task 3.1: 拆分 templates.py

**当前:** 1061 行单一文件

**目标结构:**
```
web/templates/
  __init__.py          # 导出 HTML_PAGE
  dashboard.py         # 仪表盘 HTML
  styles.py            # CSS 样式
  scripts.py           # JavaScript
  reports.py           # 报告生成
```

**或替代方案:** 使用 Jinja2 模板文件
```
web/templates/
  dashboard.html.j2
  styles.css
  scripts.js
```

---

### Task 3.2: 拆分 llm/controller.py

**当前:** 843 行，复杂度高

**拆分建议:**
```
llm/
  controller.py        # 主控制器 (~300 行)
  actions.py           # 动作执行 (~200 行)
  context_builder.py   # 上下文构建 (~150 行)
  chat.py              # 聊天逻辑 (~150 行)
```

---

### Task 3.3: 节点逻辑解耦

**目标文件:** `mission_manager_node.py`

**重构方法:**
1. 提取导航逻辑到 `navigation_executor.py`
2. 提取状态回调到 `state_callbacks.py`
3. 节点文件仅保留 ROS 接口层

**示例:**
```python
# navigation_executor.py (纯逻辑，可测试)
def compute_next_waypoint(current_pose, waypoints, index):
    """计算下一个导航点"""
    ...

# mission_manager_node.py (ROS 接口)
class MissionManagerNode(Node):
    def __init__(self):
        self.executor = NavigationExecutor(...)
        ...
```

---

### Task 3.4: 路径配置化

**当前问题:** `demo_prep.py` 包含硬编码路径

**解决方案:**
1. 创建 `paths.py` 配置模块
2. 支持环境变量覆盖
3. 添加配置验证

```python
# h2track_tracking/paths.py
import os
from pathlib import Path

def get_workspace_root() -> Path:
    """获取工作空间根目录"""
    env_path = os.environ.get("H2TRACK_WORKSPACE")
    if env_path:
        return Path(env_path)
    return Path(__file__).parent.parent.parent.parent

WORKSPACE_ROOT = get_workspace_root()
GADEN_WS = Path(os.environ.get("GADEN_WS", "/home/user/gaden_ws"))
```

---

## 阶段 4: 功能增强开发 (优先级: 中)

### Task 4.1: 多机器人支持

**设计:**
1. 创建 `robot_registry.py` 管理多机器人
2. 每个机器人独立的状态机
3. Web 控制台支持机器人选择

**数据结构:**
```python
@dataclass
class RobotState:
    robot_id: str
    namespace: str
    mode: str
    pose: Pose2D
    gas_reading: float

class RobotRegistry:
    def register(self, robot_id: str, namespace: str) -> None: ...
    def get_state(self, robot_id: str) -> RobotState: ...
    def list_robots(self) -> list[RobotState]: ...
```

---

### Task 4.2: 持久化存储

**方案:** SQLite 数据库

**数据模型:**
```python
# models.py
class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: int
    scene: str
    started_at: datetime
    ended_at: datetime
    source_found: bool
    metrics: JSON
```

**功能:**
- 运行历史记录
- 指标持久化
- 导出报告

---

### Task 4.3: 插件架构

**目标:** 可插拔的气体模型后端

**设计:**
```python
# gas_model_plugin.py
from abc import ABC, abstractmethod

class GasModelPlugin(ABC):
    @abstractmethod
    def get_concentration(self, x: float, y: float, z: float) -> float: ...

    @abstractmethod
    def get_name(self) -> str: ...

# 插件注册
class GasModelRegistry:
    _plugins: dict[str, GasModelPlugin] = {}

    @classmethod
    def register(cls, plugin: GasModelPlugin):
        cls._plugins[plugin.get_name()] = plugin
```

---

### Task 4.4: REST API 认证

**方案:** API Key 认证

**实现:**
```python
# web/auth.py
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
```

---

### Task 4.5: 日志回放功能

**功能:** 从日志文件回放仿真

**实现:**
1. 日志格式标准化 (JSON Lines)
2. 回放控制器
3. 时间缩放控制

---

## 阶段 5: 多地图支持 (优先级: 中)

**目标:** 支持多个预配置场景

### Task 5.1: 场景配置抽象

**当前:** `scenes/warehouse/`, `scenes/baseline/`

**增强:**
1. 场景验证脚本
2. 场景模板生成器
3. 场景依赖管理

```python
# scene_manager.py
class SceneManager:
    def list_scenes(self) -> list[str]: ...
    def validate_scene(self, scene_name: str) -> bool: ...
    def create_scene(self, template: str, name: str) -> Path: ...
```

---

### Task 5.2: 动态场景加载

**功能:** 运行时切换场景

**实现:**
1. 场景热加载接口
2. 地图切换服务
3. Nav2 参数重配置

---

### Task 5.3: 场景生成工具

**工具:** `scene_generator.py`

**功能:**
- 从 Gazebo world 自动生成场景配置
- 障碍物地图自动提取
- 巡航点自动规划

---

### Task 5.4: 多场景比较

**功能:** 并行运行多个场景，比较性能

**实现:**
```python
# benchmark.py
def run_benchmark(scenes: list[str], rounds: int = 3) -> dict:
    results = {}
    for scene in scenes:
        results[scene] = run_scene(scene, rounds)
    return compare_results(results)
```

---

## 实施顺序建议

```
Week 1: 阶段 1 (CI/CD) + 阶段 2 开始
Week 2: 阶段 2 完成 + 阶段 3 开始
Week 3: 阶段 3 完成 + 阶段 5 开始
Week 4: 阶段 4 + 阶段 5 完成
```

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| CI 环境配置复杂 | 中 | 使用 Docker 容器简化 |
| 测试覆盖目标过高 | 低 | 分阶段达标 (70%→80%→90%) |
| 架构重构引入 bug | 高 | 增量重构 + 完整测试 |
| 多机器人并发问题 | 高 | 充分的并发测试 |
| 场景兼容性 | 中 | 场景验证脚本 |

---

## 成功标准

- [ ] CI 流水线通过率 > 95%
- [ ] 测试覆盖率 > 80%
- [ ] 所有 Python 文件通过 ruff 和 mypy 检查
- [ ] 无 CRITICAL 安全漏洞
- [ ] 至少支持 3 个预配置场景
- [ ] Web 控制台支持多机器人选择
