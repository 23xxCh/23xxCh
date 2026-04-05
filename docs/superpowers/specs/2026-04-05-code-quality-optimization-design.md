# 代码质量优化设计规范

**日期**: 2026-04-05
**状态**: 待审核
**范围**: 全面代码质量优化

---

## 1. 背景

### 1.1 当前问题

| 文件 | 行数 | 问题 |
|------|------|------|
| `demo_web_server.py` | 2231 | 职责混合：HTML模板、API路由、业务逻辑、指标收集 |
| `llm_agent.py` | 906 | 职责混合：存储、客户端、控制器 |

### 1.2 目标

- 提高代码可读性和可维护性
- 降低单文件复杂度（目标 < 400 行）
- 改善测试覆盖率
- 统一代码风格

---

## 2. 架构设计

### 2.1 demo_web_server.py 拆分

**目标结构**：

```
h2track_tracking/
├── web/
│   ├── __init__.py
│   ├── config.py              # 配置常量 (~50行)
│   ├── metrics_store.py       # MetricsStore 类 (~300行)
│   ├── simulation_controller.py  # SimulationController 类 (~350行)
│   ├── topic_collector.py     # TopicMetricsCollector 类 (~80行)
│   ├── routes.py              # FastAPI 路由定义 (~400行)
│   ├── templates.py           # HTML 模板 (~1000行)
│   └── app.py                 # create_app + main (~100行)
└── demo_web_server.py         # 入口文件，仅导入启动
```

**模块职责**：

| 模块 | 职责 | 行数目标 | 依赖 |
|------|------|----------|------|
| `config.py` | 常量定义、默认配置、工具函数 | ~50 | 无 |
| `metrics_store.py` | 指标存储、阶段追踪、健康度计算 | ~300 | config |
| `simulation_controller.py` | 仿真生命周期管理、日志收集 | ~350 | config, metrics_store |
| `topic_collector.py` | ROS 话题订阅、实时数据收集 | ~80 | metrics_store |
| `routes.py` | REST API 端点定义 | ~400 | controller, llm |
| `templates.py` | HTML 页面模板 | ~1000 | 无 |
| `app.py` | FastAPI 应用组装 | ~100 | 所有模块 |

### 2.2 llm_agent.py 拆分

**目标结构**：

```
h2track_tracking/
├── llm/
│   ├── __init__.py
│   ├── profile_store.py       # LlmProfileStore 类 (~200行)
│   ├── client.py              # OpenAICompatClient 类 (~200行)
│   ├── controller.py          # LlmController 类 (~400行)
│   └── prompts.py             # 系统提示词常量 (~100行)
└── llm_agent.py               # 兼容入口
```

**模块职责**：

| 模块 | 职责 | 行数目标 | 依赖 |
|------|------|----------|------|
| `prompts.py` | SYSTEM_PROMPT 等常量 | ~100 | 无 |
| `profile_store.py` | 配置文件读写、CRUD 操作 | ~200 | 无 |
| `client.py` | HTTP 客户端、协议适配 | ~200 | 无 |
| `controller.py` | 业务逻辑、动作执行 | ~400 | profile_store, client |

---

## 3. 实施阶段

### 阶段 1：拆分 demo_web_server.py

**步骤**：

1. 创建 `web/` 目录结构
2. 提取 `config.py` - 常量和工具函数
3. 提取 `metrics_store.py` - MetricsStore 类
4. 提取 `simulation_controller.py` - SimulationController 类
5. 提取 `topic_collector.py` - TopicMetricsCollector 类
6. 提取 `templates.py` - HTML 模板
7. 提取 `routes.py` - API 路由
8. 创建 `app.py` - 应用组装
9. 更新 `demo_web_server.py` 为入口文件
10. 更新测试导入

**验证**：
- 现有测试通过
- Web 控制台功能正常

### 阶段 2：拆分 llm_agent.py

**步骤**：

1. 创建 `llm/` 目录结构
2. 提取 `prompts.py` - 常量
3. 提取 `profile_store.py` - LlmProfileStore 类
4. 提取 `client.py` - OpenAICompatClient 类
5. 提取 `controller.py` - LlmController 类
6. 更新 `llm_agent.py` 为兼容入口
7. 更新测试导入

**验证**：
- 现有测试通过
- AI 功能正常

### 阶段 3：补充测试覆盖

**新增测试文件**：

| 测试文件 | 测试目标 | 优先级 |
|----------|----------|--------|
| `test_metrics_store.py` | MetricsStore 线程安全、边界条件 | 高 |
| `test_simulation_controller.py` | 状态转换、错误处理 | 高 |
| `test_profile_store.py` | CRUD、并发安全 | 中 |
| `test_llm_client.py` | 协议切换、错误处理 | 中 |

**目标覆盖率**：核心模块 > 80%

### 阶段 4：统一代码风格

**改进项**：

1. 类型注解：所有公共函数完整类型注解
2. 文档字符串：统一 Google 风格
3. 导入顺序：isort 标准化
4. 代码格式：black 格式化

---

## 4. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 导入路径变更 | 现有代码可能失效 | 保留原文件作为兼容入口 |
| 测试遗漏 | 功能回归 | 每阶段运行完整测试 |
| 合并冲突 | 多人协作受影响 | 分支隔离，快速合并 |

---

## 5. 验收标准

- [ ] `demo_web_server.py` 拆分为 5+ 个模块，每个 < 400 行
- [ ] `llm_agent.py` 拆分为 3+ 个模块，每个 < 400 行
- [ ] 所有现有测试通过
- [ ] 新增核心模块测试覆盖率 > 80%
- [ ] Web 控制台功能正常
- [ ] AI 功能正常
