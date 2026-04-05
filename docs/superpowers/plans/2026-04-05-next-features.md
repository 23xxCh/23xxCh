# Next Features Roadmap for H2Track-Xian

**Date**: 2026-04-05
**Status**: Analysis Complete
**Scope**: Feature identification across 5 categories

---

## Executive Summary

The h2track-xian project has achieved significant maturity with:
- Modern web console architecture (FastAPI, modular design)
- LLM agent integration for autonomous operations
- Multi-robot registry support
- SQLite persistence layer
- Scene management system
- Gas model plugin architecture
- Comprehensive CI/CD (ruff, mypy, pre-commit, GitHub Actions)
- 31 test files with 667+ tests

---

## Feature Priority Matrix

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Prometheus Metrics Export | S | High | ⭐⭐⭐ |
| Automatic Recovery System | L | High | ⭐⭐⭐ |
| E2E Testing Framework | L | High | ⭐⭐⭐ |
| WebSocket Real-Time Updates | M | High | ⭐⭐ |
| Multi-Robot Fleet View | M | High | ⭐⭐ |
| Async Route Migration | M | High | ⭐⭐ |
| Graceful Degradation | M | High | ⭐⭐ |
| Structured Logging | S | Medium | ⭐ |
| Caching Layer | S | Medium | ⭐ |
| External Alerting | M | Medium | ⭐ |

---

## Recommended Implementation Order

### Phase 1: Foundation (高优先级)
1. **Prometheus Metrics Export** - Prometheus 指标导出
2. **Structured Logging** - 结构化日志
3. **Caching Layer** - 缓存层

### Phase 2: Reliability (高优先级)
4. **Automatic Recovery System** - 自动恢复系统
5. **Graceful Degradation** - 优雅降级
6. **E2E Testing Framework** - E2E 测试框架

### Phase 3: Performance (中优先级)
7. **Async Route Migration** - 异步路由迁移
8. **WebSocket Real-Time Updates** - WebSocket 实时更新

### Phase 4: User Experience (中优先级)
9. **Multi-Robot Fleet View** - 多机器人舰队视图
10. **External Alerting Integration** - 外部告警集成

---

## 详细功能描述

### 1. Prometheus Metrics Export (优先级最高)

**描述**: 导出 Prometheus 格式指标用于外部监控集成

**实现内容**:
- 创建 `/metrics` 端点
- 跟踪: 仿真运行时间、模式转换、气体读数、导航成功率
- 添加 LLM API 延迟和令牌使用量

**示例指标**:
```
h2track_simulation_state{scene="warehouse"} 1
h2track_gas_concentration 2.5
h2track_navigation_success_total 42
h2track_llm_api_latency_seconds 0.85
```

---

### 2. Automatic Recovery System (优先级最高)

**描述**: 自动从常见故障场景中恢复

**恢复策略**:
| 故障类型 | 恢复动作 | 最大重试 |
|---------|---------|---------|
| Nav2 超时 | 重启生命周期节点 | 2 |
| GADEN 不发布 | 重启 GADEN player | 1 |
| AMCL 丢失 | 重置到初始位置 | 1 |
| 仿真崩溃 | 自动重启 | 1 |

---

### 3. E2E Testing Framework (优先级最高)

**描述**: 关键用户旅程的自动化端到端测试

**测试场景**:
- 启动仿真 → 等待找到源 → 停止
- LLM 聊天 → 动作执行
- 错误场景和恢复

---

### 4. WebSocket Real-Time Updates

**描述**: 用 WebSocket 替换 SSE 实现双向实时通信

**功能**:
- 客户端命令 (暂停、恢复、切换场景)
- 心跳和重连处理
- 多订阅复用

---

### 5. Multi-Robot Fleet View

**描述**: 同时监控多个机器人的仪表板

**功能**:
- 舰队概览 API 端点
- 舰队状态卡片网格
- 每个机器人的气体浓度迷你图
- 舰队级指标 (平均气体、已找到的源)

---

## Technical Debt Items

1. **无响应验证**: API 响应缺少 schema 验证
2. **硬编码超时**: 许多超时是硬编码的，不可配置
3. **缺失类型注解**: 部分模块缺少完整的类型注解
4. **测试覆盖缺口**: `llm/actions.py` 测试覆盖有限
5. **文档缺口**: API 文档不完整

---

## Success Criteria

- [ ] Prometheus 抓取使用标准 `/metrics` 端点
- [ ] 结构化 JSON 日志可被日志聚合器解析
- [ ] 缓存命中率 > 80%
- [ ] 自动恢复成功处理 Nav2 超时场景
- [ ] WebSocket 提供实时更新 < 100ms 延迟
- [ ] 多机器人仪表板无性能问题显示 5+ 机器人
- [ ] E2E 测试覆盖 90% 关键用户旅程
- [ ] 所有路由有 Pydantic 请求/响应模型
