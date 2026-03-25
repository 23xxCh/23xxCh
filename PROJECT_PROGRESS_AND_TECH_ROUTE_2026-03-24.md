# H2Track 项目进展与技术路线说明（2026-03-24）

## 1. 文档目的
这份文档用于说明当前项目的真实进展、技术路线演进、代码结构与核心问题处理方式，帮助快速了解：
- 项目已经完成到哪一步
- 代码该从哪里看起
- 现阶段仍有哪些技术瓶颈
- 下一步应优先做什么

---

## 2. 项目目标（当前定义）
面向 ROS 2 + Gazebo 的氢气泄漏巡检与追踪系统，目标能力是：
1. 巡检与自主导航（含避障）
2. 检测到微量氢气后触发追踪模式
3. 追踪过程中持续导航避障并逼近泄漏源
4. 在源点附近判定并输出告警结果
5. 向“SLAM 建图 + 探索 + 冻结地图 + 追踪定位”的全自主闭环演进

---

## 3. 当前仓库状态与分支职责
当前仓库有 3 条主线：

### `main`（稳定基线）
- 位置：`/home/user/h2track-xian`
- 分支：`main`（`origin/main`）
- 作用：保留最初稳定基线快照（不包含后续双场景/自主探索完整链）

### `feat/dual-scene-platform`（双场景平台）
- 位置：`/home/user/h2track-xian/.worktrees/dual-scene-platform`
- 作用：完成 baseline/warehouse 双场景架构与 scene-aware 启动链
- 代表提交（节选）：
  - `e820319` baseline scene 抽离
  - `448a598` warehouse 资产接入
  - `9df7e78` scene-aware 启动参数链
  - `ae26262` scene-specific map 路由
  - `70614ff` scene-specific GADEN 默认行为
  - `aec625b` warehouse 独立 GADEN 对齐
  - `e397eb0` warehouse GADEN 全图覆盖契约测试
  - `b1f90b7` warehouse tracking 收敛优化

### `feat/slam-explore-baseline`（自主探索与 handoff 主线）
- 位置：`/home/user/h2track-xian/.worktrees/slam-explore-baseline`
- 作用：实现 SLAM 探索 -> 触发冻结 -> 切换 tracking localization 的自主链
- 最新提交（节选）：
  - `3784491` handoff 门控：AMCL active + fresh TF
  - `7898d0c` tracking 阶段 Nav2 覆盖参数（降低 handoff 后抖动）
  - `a726755` FastDDS SHM 规避与 Nav2 pacing 调整
  - `89f07c8` 状态机切换稳健性与日志可观测性增强

---

## 4. 技术路线演进（阶段化）

## 阶段 A：基础仿真闭环
- 二轮差速底盘、激光雷达、Gazebo + Nav2 导航
- 巡检 -> 检测 -> 追踪 -> 停车告警
- 先保证工程闭环可跑通，再提升真实性

## 阶段 B：GADEN 接入
- 用外部 `gaden_ws` 维护气体场，不将大体积仿真资产塞进主仓库
- `gaden_adapter_node` 统一输出 `/gas_concentration`
- 用门控节点保证 TF 准备完成后再启传感器

## 阶段 C：双场景平台
- baseline：用于快速算法回归（调试快）
- warehouse：用于真实性验证（障碍/通道复杂）
- 同一套上层任务逻辑跨场景复用，通过 `scene` 参数切换

## 阶段 D：自主探索链
- `autonomy.launch.py`：SLAM 建图 + frontier exploration
- 气体触发后冻结地图
- 关闭探索导航栈，切换到 tracking localization 子链继续追踪
- 持续修正 handoff 时序与导航稳定性

---

## 5. 代码库讲解（按包）

## 5.1 `h2track_sim`（仿真与启动编排）
核心职责：世界、地图、机器人模型、启动流程与场景参数组织。

关键文件：
- `src/h2track_sim/launch/bringup.launch.py`
  - 常规巡检/追踪启动入口
  - 处理 `use_gaden`、传感器门控、Nav2 启动链
- `src/h2track_sim/launch/demo.launch.py`
  - 演示流程入口（scene 与参数注入）
- `src/h2track_sim/launch/sim.launch.py`
  - Gazebo/机器人 spawn
- `src/h2track_sim/launch/nav2.launch.py`
  - Nav2 参数与地图 runtime 路由
- `src/h2track_sim/launch/autonomy.launch.py`（在 `feat/slam-explore-baseline`）
  - SLAM 探索 + 冻结 + handoff 总控入口
- `src/h2track_sim/launch/slam_nav2.launch.py`（在 `feat/slam-explore-baseline`）
  - 建图导航专用链
- `src/h2track_sim/launch/tracking_localization.launch.py`（在 `feat/slam-explore-baseline`）
  - 冻结后定位导航 + mission_manager tracking-only
- `src/h2track_sim/scenes/*/scene.yaml`（在 feature 分支）
  - 场景级配置中心：world/map/nav2/mission/gaden/autonomy

## 5.2 `h2track_tracking`（任务与算法逻辑）
核心职责：状态机、任务调度、传感融合、handoff 管理、运维工具。

关键文件：
- `src/h2track_tracking/h2track_tracking/mission_logic.py`
  - PATROL/SEEK/SOURCE_FOUND 状态机判定
- `src/h2track_tracking/h2track_tracking/mission_manager_node.py`
  - 导航目标下发、模式切换、追踪目标生成
- `src/h2track_tracking/h2track_tracking/gaden_adapter_node.py`
  - GADEN -> `/gas_concentration` 统一接口
- `src/h2track_tracking/h2track_tracking/gaden_sensor_gate_node.py`
  - 等 TF 连通后放行 simulated_gas_sensor
- `src/h2track_tracking/h2track_tracking/demo_prep.py`
  - 彩排前清理残留进程、清理 FastDDS 锁、依赖检查
- `src/h2track_tracking/h2track_tracking/demo_selfcheck.py`
  - 运行态自检（节点/topic/TF/Nav2）
- `src/h2track_tracking/h2track_tracking/mapping_mission_manager_node.py`（feature）
  - 探索阶段任务管理
- `src/h2track_tracking/h2track_tracking/exploration_manager_node.py`（feature）
  - frontier 探索逻辑
- `src/h2track_tracking/h2track_tracking/transition_manager_node.py`（feature）
  - 冻结地图、导航栈切换、tracking handoff

---

## 6. 已解决的关键问题（问题 -> 处理方式）

## 6.1 环境与运行稳定性
- 问题：残留 `gzserver` / Nav2 / GADEN 进程导致端口冲突、假失败
- 处理：`demo_prep` 场景化清理 stale process + FastDDS lock

- 问题：FastDDS SHM 端口锁导致不稳定
- 处理：在关键启动链禁用 SHM，强制 `UDPv4`

## 6.2 GADEN 对齐问题
- 问题：warehouse 早期出现 “outside the environment”
- 处理：重建 warehouse GADEN 资产覆盖范围，使其对齐 warehouse_map 全图；增加契约测试防回归

- 问题：scene 切换时 GADEN 仍隐式回退 baseline 配置
- 处理：scene-aware GADEN 参数解析；warehouse 默认行为与 scene 配置一致，缺配置 fail-fast

## 6.3 任务状态机与追踪语义
- 问题：SOURCE_FOUND 可能在“热点”而非真实源附近触发
- 处理：增加真实源点约束，要求估计点接近真实源才可确认

- 问题：模式切换抖动（单样本波动导致频繁回退）
- 处理：引入持续样本判定与退出迟滞，增强 SEEK 阶段稳定性

## 6.4 自主 handoff 链
- 问题：tracking handoff 过早完成，导致后续定位链不稳
- 处理：`transition_manager_node` 增加门控：
  - `amcl/get_state` ACTIVE
  - fresh `map->base_link` TF
  - 健康检查时间窗

---

## 7. 测试与质量策略
项目采用“契约测试 + 逻辑单测 + 启动链文本/结构测试 + 运行态 smoke”组合：

- `h2track_tracking/test/*`
  - 状态机逻辑、handoff 几何、门控契约、demo 运维工具
- `h2track_sim/test/*`
  - scene 配置契约、launch 参数路由、时序与入口结构约束
- 运行态验证
  - headless launch + 关键日志信号与 topic/param 读取

最近一次在 `feat/slam-explore-baseline` 的全量验证结果：
- `pytest src/h2track_tracking/test src/h2track_sim/test -q` 通过（`234 passed`）
- `colcon build --packages-select h2track_tracking h2track_sim` 通过

---

## 8. 当前剩余瓶颈（实事求是）
目前主要瓶颈已从“能否跑通”转为“稳定性与性能”：

1. tracking 阶段仍偶发 `Failed to make progress`
- 本质是局部规划/路径几何与动态障碍耦合问题
- 已通过 tracking Nav2 覆盖参数降低抖动，但仍需继续收敛

2. BT tick rate 告警在高负载场景仍会出现
- 通过 `bt_loop_duration` 与速度/进度参数可继续优化

3. 自主链路稳定性需更多长时回归
- 需要固定工况下多次重复验证（统计成功率与时间）

---

## 9. 下一步建议（优先级）

## P0（必须）
1. tracking 段导航稳定性专项优化
   - 基于失败热区调整巡检/追踪目标生成策略
   - 微调 controller/progress checker 参数
2. autonomy 长时回归基准
   - 固定场景跑多轮，记录：handoff 成功率、source_found 成功率、总时长

## P1（重要）
3. baseline vs warehouse 算法对比实验
   - 同一算法在双场景做指标对比（触发时延、定位误差、收敛时间）

## P2（增强）
4. 进一步提高 warehouse GADEN 几何真实性
   - 逐步替换近似障碍，缩小 sim-to-world 偏差

---

## 10. 你可以怎么用这份文档
- 想看“现在能做什么”：先读第 2、6、8 节
- 想看“代码从哪里入手”：看第 5 节文件索引
- 想规划下一阶段：直接按第 9 节优先级执行

