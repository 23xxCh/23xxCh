# H2Track 下一步迭代组员分工计划

## 项目现状总结

**当前状态（截至 2026-06-30）：**
- 总代码行数：20,772 行（源文件）+ 12,254 行（测试）= 33,026 行
- ROS 包数量：8 个（bringup/tracking/interfaces/description/gas_sim/web/utils/sim）
- 场景数量：6 个（baseline/warehouse/maze/snake/office/benchmark）
- 测试文件数：44 个，~490 个测试函数
- Git 提交数：131 次
- 回归测试成功率：90%（10 轮 baseline 场景）
- 核心成果：Surge-Cast + 粒子滤波双算法融合、GADEN CFD 集成、FastAPI Web 控制台

**已有设计文档：**
- `docs/multi_robot_design.md`：多机器人协作设计（角色分配、信息融合、冲突解决）
- `docs/adr/0001-tdlas-integration.md`：TDLAS 集成决策记录（延后实施）
- `docs/research_roadmap.md`：研究路线图（5 个 Phase，目标顶刊发表）
- `.github/workflows/ci.yml`：CI 流水线（lint/test/build）

---

## 迭代目标

基于项目现状和研究路线图，制定 **6 个月（26 周）** 的迭代计划，目标：
1. **多机器人协调**：实现 2-3 机器人分布式气体源定位
2. **算法性能基准**：建立自动调参体系，提升成功率至 ≥ 95%
3. **TDLAS 集成**：实现远程激光传感器融合（条件触发）
4. **Gazebo Ignition 迁移**：完成向 Gz Sim 的迁移
5. **Web 数据持久化**：实现历史回放和智能分析
6. **论文准备**：完成理论分析和实验验证，投稿顶刊

---

## 组员分工计划

### 陈熙贤（组长）— 系统架构与多机器人协调

**核心职责：**
- 多机器人协调系统架构设计
- 跨模块接口设计与代码审查
- 项目进度把控与风险管控
- 论文整体框架设计

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 设计多机器人通信协议（基于 DDS QoS） | `docs/multi_robot_protocol.md` |
| Week 3-4 | 实现 coordinator_node 角色分配算法 | `coordinator_node.py v1.0` |
| Week 5-6 | 实现多机器人信息融合（分布式粒子滤波） | `multi_robot/fusion.py` |
| Week 7-8 | 实现防碰撞机制（距离 < 2m 避让） | `collision_avoidance.py` |
| Week 9-10 | 多机器人回归测试（2 机器人 warehouse 场景） | `test_multi_robot.py` |
| Week 11-12 | 论文框架设计 + 理论分析章节 | `paper/outline.md` |
| Week 13-14 | 论文实验设计 + 对比算法实现 | `paper/experiments.md` |
| Week 15-16 | 论文初稿撰写（引言 + 方法） | `paper/draft_v1.tex` |
| Week 17-18 | 论文修改 + 图表制作 | `paper/draft_v2.tex` |
| Week 19-20 | 论文投稿准备 + 补充材料 | `paper/submission.zip` |
| Week 21-22 | 审稿意见回复 + 修改 | `paper/rebuttal.md` |
| Week 23-24 | 项目总结 + 技术报告更新 | `docs/final_report.md` |
| Week 25-26 | 知识转移 + 文档归档 | `docs/handover.md` |

**关键技能要求：** ROS 2 DDS、分布式系统、粒子滤波、学术论文写作

---

### 刘瑞洁 — 算法优化与理论分析

**核心职责：**
- Surge-Cast 算法优化（自适应步长、风向突变检测）
- 算法收敛性证明
- 复杂度分析
- 对比算法实现（Baseline）

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 优化 Surge-Cast 自适应步长策略 | `surge_cast.py v2.0` |
| Week 3-4 | 实现风向突变检测和羽流断裂恢复 | `wind_estimator.py v2.0` |
| Week 5-6 | Surge-Cast 收敛性证明（数学推导） | `paper/surge_cast_proof.tex` |
| Week 7-8 | 实现对比算法（梯度上升、随机搜索） | `baseline_algorithms.py` |
| Week 9-10 | 算法消融实验（Surge-Cast vs PF vs 融合） | `paper/ablation.md` |
| Week 11-12 | 复杂度分析（时间/空间） | `paper/complexity.tex` |
| Week 13-14 | 参数敏感性分析 | `paper/sensitivity.md` |
| Week 15-16 | 论文方法章节撰写 | `paper/methods.tex` |
| Week 17-18 | 论文实验章节撰写 | `paper/experiments.tex` |
| Week 19-20 | 论文修改 + 图表优化 | `paper/figures/` |
| Week 21-22 | 审稿意见回复 | `paper/rebuttal.md` |
| Week 23-24 | 算法文档更新 | `docs/algorithms.md` |
| Week 25-26 | 知识转移 | `docs/handover.md` |

**关键技能要求：** 数学分析、算法设计、LaTeX、Python

---

### 余锦华 — 粒子滤波优化与自动调参

**核心职责：**
- 粒子滤波性能优化（向量化、并行化）
- 自动调参系统（网格搜索、贝叶斯优化）
- 基准测试框架
- CI/CD 集成

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 补充粒子滤波基准测试（100/500/1000/5000 粒子） | `benchmark_particle_filter.py` |
| Week 3-4 | 实现参数网格搜索脚本 | `scripts/tune_params.py` |
| Week 5-6 | 集成贝叶斯优化（Optuna） | `scripts/tune_bayesian.py` |
| Week 7-8 | 粒子滤波并行化（多线程/多进程） | `filter_parallel.py` |
| Week 9-10 | CI 流水线优化（并行测试、缓存） | `.github/workflows/ci_v2.yml` |
| Week 11-12 | 性能基准报告（JSON 历史对比） | `benchmarks/report.json` |
| Week 13-14 | 自动调参结果分析 | `paper/tuning_results.md` |
| Week 15-16 | 论文方法章节（PF 优化部分） | `paper/methods_pf.tex` |
| Week 17-18 | 论文实验章节（性能对比） | `paper/experiments_pf.tex` |
| Week 19-20 | 论文修改 + 图表优化 | `paper/figures/` |
| Week 21-22 | 审稿意见回复 | `paper/rebuttal.md` |
| Week 23-24 | 工具文档更新 | `docs/benchmarking.md` |
| Week 25-26 | 知识转移 | `docs/handover.md` |

**关键技能要求：** NumPy、并行计算、Optuna、CI/CD

---

### 张青源 — 传感器融合与仿真环境

**核心职责：**
- TDLAS 传感器集成（条件触发）
- GADEN 场景扩展（新场景、新气体）
- 传感器噪声建模
- Sim-to-Real 适配

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 调研 TDLAS 硬件方案 | `docs/tdlas_hardware.md` |
| Week 3-4 | 实现 TDLAS 适配器节点（方案 A：预警模式） | `tdlas_adapter_node.py` |
| Week 5-6 | TDLAS 与 MOX 融合实验 | `tdlas_fusion.py` |
| Week 7-8 | 新场景设计（工业管廊） | `scenes/industrial_pipe/` |
| Week 9-10 | 传感器噪声建模（高斯/泊松） | `sensor_noise_model.py` |
| Week 11-12 | Sim-to-Real 适配层（域随机化） | `sim2real_adapter.py` |
| Week 13-14 | 真实传感器数据接口设计 | `docs/real_sensor_api.md` |
| Week 15-16 | 论文方法章节（传感器融合） | `paper/methods_sensor.tex` |
| Week 17-18 | 论文实验章节（传感器对比） | `paper/experiments_sensor.tex` |
| Week 19-20 | 论文修改 + 图表优化 | `paper/figures/` |
| Week 21-22 | 审稿意见回复 | `paper/rebuttal.md` |
| Week 23-24 | 传感器文档更新 | `docs/sensors.md` |
| Week 25-26 | 知识转移 | `docs/handover.md` |

**关键技能要求：** 传感器原理、信号处理、GADEN、ROS 2

---

### 黄鹏轩 — Web 平台迁移与数据持久化

**核心职责：**
- Gazebo Ignition 迁移
- Web 数据持久化（SQLite + 历史回放）
- LLM 助手完善
- 可视化优化

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 调研 Gz Sim 插件 API | `docs/gz_sim_migration.md` |
| Week 3-4 | 转换 .world 到 SDF 格式 | `scenes/*/gz_sim.sdf` |
| Week 5-6 | 实现 Gz Sim 传感器插件 | `gz_sensor_plugin.cpp` |
| Week 7-8 | 双模式 launch（Classic/Gz Sim） | `gz_sim.launch.py` |
| Week 9-10 | SQLite 数据库设计 + 实现 | `db/schema.sql` |
| Week 11-12 | 历史回放功能（轨迹 + 热力图） | `web/replay.py` |
| Week 13-14 | LLM 助手完善（Claude API） | `llm/report_generator.py` |
| Week 15-16 | 论文方法章节（可视化） | `paper/methods_viz.tex` |
| Week 17-18 | 论文实验章节（可视化对比） | `paper/experiments_viz.tex` |
| Week 19-20 | 论文修改 + 图表优化 | `paper/figures/` |
| Week 21-22 | 审稿意见回复 | `paper/rebuttal.md` |
| Week 23-24 | Web 文档更新 | `docs/web_console.md` |
| Week 25-26 | 知识转移 | `docs/handover.md` |

**关键技能要求：** Gz Sim、FastAPI、SQLite、Three.js/Canvas

---

### 夏炜皓 — 测试验证与文档管理

**核心职责：**
- 多场景回归测试
- Ground Truth 评估体系完善
- 文档管理（技术文档、论文、报告）
- 演示工具维护

**具体任务：**
| 周次 | 任务 | 交付物 |
|------|------|--------|
| Week 1-2 | 多场景回归测试自动化（6 场景） | `scripts/regression_all_scenes.py` |
| Week 3-4 | Ground Truth 评估体系扩展 | `evaluation/extended_metrics.py` |
| Week 5-6 | 性能退化检测（基准对比） | `scripts/performance_regression.py` |
| Week 7-8 | 测试覆盖率提升（目标 90%） | `coverage_report.html` |
| Week 9-10 | 多机器人测试场景设计 | `test_multi_robot_scenarios.py` |
| Week 11-12 | 论文数据整理（实验结果汇总） | `paper/data/` |
| Week 13-14 | 论文图表生成（自动化） | `scripts/generate_figures.py` |
| Week 15-16 | 论文方法章节（评估指标） | `paper/methods_eval.tex` |
| Week 17-18 | 论文实验章节（评估结果） | `paper/experiments_eval.tex` |
| Week 19-20 | 论文修改 + 格式检查 | `paper/format_check.md` |
| Week 21-22 | 审稿意见回复 | `paper/rebuttal.md` |
| Week 23-24 | 项目文档归档 | `docs/archive/` |
| Week 25-26 | 知识转移 + 培训材料 | `docs/training.md` |

**关键技能要求：** pytest、覆盖率分析、LaTeX、数据可视化

---

## 迭代里程碑

| 阶段 | 时间 | 里程碑 | 验收标准 |
|------|------|--------|----------|
| Phase 1 | Week 1-4 | 算法优化完成 | 回归成功率 ≥ 95% |
| Phase 2 | Week 5-8 | 多机器人原型 | 2 机器人协调运行 |
| Phase 3 | Week 9-12 | 传感器融合 | TDLAS 预警功能可用 |
| Phase 4 | Week 13-16 | 平台迁移 | Gz Sim 双模式运行 |
| Phase 5 | Week 17-20 | 论文初稿 | 完成 draft_v1 |
| Phase 6 | Week 21-26 | 论文投稿 | 提交至目标期刊 |

---

## 协作机制

### 会议制度
- **每日站会**：15 分钟，同步进度和阻塞问题
- **每周复盘会**：1 小时，回顾本周成果，调整下周计划
- **每月里程碑评审**：2 小时，检查里程碑完成情况

### 代码审查
- 所有 PR 必须经过至少 1 人审查
- 关键模块（多机器人、传感器融合）需组长审批
- 使用 GitHub Actions 自动运行测试和覆盖率检查

### 文档同步
- 技术文档：CLAUDE.md 实时更新
- 设计决策：docs/adr/ 记录
- 论文进展：paper/ 目录每周更新
- 会议记录：docs/meetings/ 归档

### 风险管理
| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| Gz Sim 插件 API 不兼容 | 高 | 高 | 提前调研，预留 2 周缓冲 |
| TDLAS 硬件未到位 | 中 | 中 | 先用仿真数据验证算法 |
| 论文审稿周期长 | 中 | 高 | 同时投稿多个会议/期刊 |
| 团队成员时间冲突 | 中 | 中 | 每周同步，必要时调整任务 |

---

## 预期成果

### 技术成果
- 多机器人协调系统（2-3 机器人）
- 自动调参系统（成功率 ≥ 95%）
- TDLAS 传感器融合（条件触发）
- Gz Sim 双模式支持
- Web 历史回放和智能分析

### 学术成果
- 1 篇顶刊论文（IEEE T-RO / Autonomous Robots / RA-L）
- 1 篇会议论文（ICRA / IROS）
- 开源代码库（GitHub Stars 目标：100+）

### 工程成果
- 完整的多机器人气体源定位系统
- 可复用的仿真平台（6 场景）
- 自动化测试和回归框架
- 详细的文档和教程

---

## 附录：技能矩阵

| 技能 | 陈熙贤 | 刘瑞洁 | 余锦华 | 张青源 | 黄鹏轩 | 夏炜皓 |
|------|--------|--------|--------|--------|--------|--------|
| ROS 2 | ★★★ | ★★☆ | ★★☆ | ★★★ | ★★☆ | ★★☆ |
| Python | ★★★ | ★★★ | ★★★ | ★★☆ | ★★★ | ★★☆ |
| C++ | ★★☆ | ★★☆ | ★★☆ | ★★★ | ★★☆ | ★☆☆ |
| 算法设计 | ★★★ | ★★★ | ★★★ | ★★☆ | ★★☆ | ★★☆ |
| 传感器 | ★★☆ | ★☆☆ | ★☆☆ | ★★★ | ★★☆ | ★☆☆ |
| Web 开发 | ★★☆ | ★☆☆ | ★☆☆ | ★☆☆ | ★★★ | ★☆☆ |
| 论文写作 | ★★★ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★★ |
| 测试验证 | ★★☆ | ★★☆ | ★★★ | ★★☆ | ★★☆ | ★★★ |

---

*计划制定日期：2026-06-30*
*计划版本：v1.0*
*下次评审：2026-07-07*