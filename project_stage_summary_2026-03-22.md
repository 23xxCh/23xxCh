# H2Track-Xian 项目现阶段成果、问题与解决方案总结

更新日期：2026-03-22

## 1. 文档目的

这份文档用于系统总结项目截至当前阶段已经完成的成果、开发过程中遇到的主要问题、每类问题的根因与解决方法、当前仍然存在的不足，以及接下来可继续推进的方向。

它的定位不是一份简短周报，而是一份偏“项目档案”的阶段总结，便于：

- 向导师汇报项目发展脉络
- 回顾哪些问题已经真正解决，哪些只是暂时绕开
- 区分稳定版本与开发版本
- 为下一阶段的优化与研究提供清晰起点

## 2. 项目目标与当前定位

### 2.1 总体目标

本项目面向“氢气泄漏巡检与源头追踪”问题，目标是在仿真环境中构建一套可迭代、可验证、可扩展的移动机器人系统，使机器人能够：

1. 在已知环境中自主巡检
2. 通过气体浓度输入检测异常
3. 从巡检模式切换到追踪模式
4. 在追踪过程中继续避障与规划
5. 尽量逼近真实泄漏源并输出结果

### 2.2 当前工程定位

项目已经不再只是一个“单场景 demo”，而是逐步演化成一个双场景研究平台：

- `baseline` 场景：用于快速回归、调试任务逻辑、验证状态机与参数
- `warehouse` 场景：用于更真实的障碍布局、导航耦合与 GADEN 驱动验证

当前工程的职责划分是：

- `h2track_sim`
  - 场景、地图、URDF、Gazebo、Nav2、launch
- `h2track_tracking`
  - 任务状态机、巡检/追踪管理、简化气体场、GADEN 适配、工具节点
- 外部 `gaden_ws`
  - GADEN 预处理、风场、playback、气体传感器仿真

## 3. 当前成果概览

### 3.1 工程基础已经完成的重建

项目已经从旧的中文路径工程中剥离，重建到纯 ASCII 路径：

- 主工程：`/home/user/h2track-xian`
- 双场景开发 worktree：`/home/user/h2track-xian/.worktrees/dual-scene-platform`
- 外部 GADEN 工作区：`/home/user/gaden_ws`

当前 GitHub 远程已经连通：

- `origin = git@github.com:23xxCh/23xxCh.git`

已推送的分支状态：

- `main`
  - 提交：`ec1d280`
  - 含义：稳定基线快照，适合作为阶段性可运行版本
- `feat/dual-scene-platform`
  - 最新已推送提交：`b1f90b7`
  - 含义：双场景平台、warehouse 场景、scene-aware 启动链、仓库 GADEN 对齐、warehouse 巡检/追踪优化

### 3.2 已完成的系统能力

当前项目已经具备以下能力：

1. 机器人仿真底座
   - 二轮差速机器人
   - 激光雷达
   - Gazebo Classic
   - Nav2

2. 两种气体场来源
   - `use_gaden:=false`：简化气体场
   - `use_gaden:=true`：GADEN playback + adapter

3. 任务状态机闭环
   - `PATROL`
   - `SEEK_CONFIRM`
   - `SEEK_TRACK`
   - `SOURCE_FOUND`

4. 双场景工程化能力
   - `scene:=baseline`
   - `scene:=warehouse`
   - 每个场景独立拥有：
     - world
     - map
     - Nav2 参数
     - 巡检点
     - 源点
     - GADEN 配置
     - 简化气体场参数

5. 演示与运维工具
   - `demo_prep`
   - `demo_selfcheck`
   - rehearsal checklist
   - demo brief
   - 2 分钟口头讲稿

### 3.3 当前验证结果

#### 主分支稳定版

主分支对应的是较早的稳定版本，最近一次明确验证结果为：

- `pytest`：`77 passed`
- `colcon build`：成功
- 已推送到 GitHub `main`

#### 双场景开发版

双场景 worktree 当前是更先进的研发分支，最近一次完整验证结果为：

- `pytest src/h2track_tracking/test src/h2track_sim/test -q`：`125 passed`
- `colcon build --packages-select h2track_tracking h2track_sim`：成功

#### warehouse 运行态关键证据

在 `scene:=warehouse` 的 GADEN 模式下，已经拿到完整链路证据：

- `PATROL` 正常开始
- 进入 `SEEK_CONFIRM`
- 进入 `SEEK_TRACK`
- 最终进入 `SOURCE_FOUND`

一次已验证的关键时间线为：

- `PATROL` at `9.83s`
- `SEEK_CONFIRM` at `85.27s`
- `SEEK_TRACK` at `86.24s`
- `SOURCE_FOUND` at `88.32s`

后续一轮更严格的本地精度调优中，也再次出现了完整闭环：

- `PATROL` at `11.99s`
- `SEEK_CONFIRM` at `87.79s`
- `SEEK_TRACK` at `88.74s`
- `SOURCE_FOUND` at `91.90s`

这一轮 `SOURCE_FOUND` 对应的机器人位姿约为：

- `(3.3587, -2.5964)`

与 warehouse 场景真实源点：

- `(3.6, -3.038551)`

之间的当前定位误差约为：

- `0.504 m`

这说明：

- 闭环已经打通
- 真实性语义已经比早期版本更正确
- 但“最终贴近真实源点的精度”仍有继续优化空间

### 3.4 当前文档与运行材料

项目中已经有一批较完整的文档材料：

- `advisor_report.md`
- `docs/rehearsal-checklist.md`
- `docs/demo-brief.md`
- `docs/demo-script-2min.md`
- `docs/warehouse-gaden-runbook.md`
- `docs/superpowers/specs/...`
- `docs/superpowers/plans/...`

这些文档已经覆盖了：

- 项目阶段汇报
- 演示彩排流程
- 运行手册
- 双场景设计文档
- warehouse GADEN 对齐计划

## 4. 项目过程中遇到的主要问题、根因与解决办法

下面按问题类别汇总。

### 4.1 中文路径导致 ROS / 第三方工具链不稳定

#### 现象

最初项目位于中文路径目录下。这个问题早期并不总是直接报错，但在以下环节里陆续暴露：

- ROS 包构建
- 第三方依赖路径拼接
- GADEN 消息生成
- launch / CMake 路径处理

#### 根因

ROS 生态和部分第三方 CMake / Python / rosidl 工具对非 ASCII 路径兼容性并不稳，尤其当路径继续传入外部包、生成文件和消息代码时，问题会放大。

#### 解决办法

直接停止在旧路径上继续堆功能，改为重建新工程：

- 旧工程保留参考
- 新工程统一迁移到 `/home/user/h2track-xian`

#### 当前效果

当前主工程、worktree 和外部 GADEN 工作区都已经建立在 ASCII 路径上，这一类路径级问题基本被根治。

#### 经验

路径规范是 ROS 项目里非常值得尽早统一的基础条件，不应该拖到后期再处理。

### 4.2 仓库管理一开始不规范，无法直接使用 worktree

#### 现象

在需要引入双场景开发分支时，发现主仓库还是 unborn 状态，没有初始提交，无法直接建立标准 git worktree。

#### 根因

前期项目重建阶段更关注“先跑起来”，Git 历史管理没有同步规范化。

#### 解决办法

按工程卫生先补齐仓库基础：

- 增加 `.gitignore`
- 建立初始提交
- 再从主仓库切出 `.worktrees/dual-scene-platform`

#### 当前效果

现在有了清晰的版本分层：

- `main`：稳定快照
- `feat/dual-scene-platform`：持续开发

#### 经验

一旦项目要进入多阶段开发、分支审查和回归验证，Git 结构必须尽早补正，否则后续迭代成本会快速上升。

### 4.3 Nav2 启动失败，行为树插件与 XML 不匹配

#### 现象

`bt_navigator` 一度无法正常激活，错误集中在：

- `ComputePathThroughPoses`
- `RemovePassedGoals`

等行为树节点无法识别。

#### 根因

不是导航算法本身坏了，而是 Humble 下默认行为树 XML 与插件库配置不匹配。

#### 解决办法

采用系统化排查流程：

1. 重现问题
2. 核对默认 BT XML
3. 对照 Humble 默认插件列表
4. 在 Nav2 参数中补齐缺失插件与默认 BT 路径

#### 当前效果

这个问题已经解决，`bt_navigator` 可以正常激活。

#### 经验

ROS 2 中很多“导航起不来”的问题，本质是配置层契约破坏，不应上来就怀疑业务逻辑。

### 4.4 launch、安装态与源码态不一致

#### 现象

有一段时间里，源码文件明明已经改对，但 `ros2 launch` 运行时仍然表现得像旧逻辑，尤其体现在：

- `demo.launch.py`
- `bringup.launch.py`
- patrol 点位

这些修改在运行时不生效。

#### 根因

`ros2 launch` 实际使用的是 `install/` 安装态文件，而不是当前 `src/` 中未重新构建的源码文件。

#### 解决办法

建立一个更严格的验证顺序：

1. 修改源码
2. 跑聚焦测试
3. `colcon build`
4. 再做安装态 smoke test

#### 当前效果

现在遇到 launch 行为异常时，已经优先检查“是不是安装态没同步”，这个问题不再反复出现。

#### 经验

在 ROS 2 工程里，源码态与安装态分离是非常真实的运行层变量，必须纳入调试思路。

### 4.5 GADEN 初次接入时，外部依赖链非常脆弱

#### 现象

GADEN 接入阶段连续暴露出多类问题：

- 仓库子模块走 SSH，机器没有 key
- `olfaction_msgs` 的 `package.xml` 含非法内容
- 非 ASCII 路径导致 rosidl 生成路径异常
- `gaden_core` 相关第三方依赖没拉全
- GUI 相关依赖与当前阶段需求不匹配
- 链接策略导致下游包构建失败

#### 根因

GADEN 是研究型工程，不是“拎来即用”的生产依赖：

- 默认假设子模块与 SSH 环境完善
- 默认假设路径与编译环境较理想
- 对包依赖、链接方式、第三方库存在较强隐式前提

#### 解决办法

这一块采用了“最小可运行集”策略，而不是硬啃全部：

1. 子模块 URL 从 SSH 改成 HTTPS
2. 修复 `olfaction_msgs` 的明显问题
3. 把 GADEN 工作区放到 ASCII 路径
4. 先只构建第二阶段真正需要的包：
   - `gaden_environment`
   - `gaden_player`
   - `simulated_gas_sensor`
   - `gaden_preprocessing`
   - `gaden_filament_simulator`
5. 对不必要的 GUI 链条不强求接通

#### 当前效果

GADEN 主链已经能稳定构建并运行，但这块依赖依然属于“研究型外部依赖”，不能把它误当成完全无摩擦的工业包。

#### 经验

第三方科研工具接入时，最重要的是先明确“最小运行闭环”，而不是试图一次性接通全部功能。

### 4.6 GADEN 传感器启动时序导致 TF 断树

#### 现象

`simulated_gas_sensor` 过早启动时会报：

- `gaden_map -> base_link` 不连通
- `lookupTransform` 失败
- 首帧 TF 缓存不足

#### 根因

GADEN 传感器启动早于机器人 TF 树完整建立，尤其在：

- Gazebo 刚起来
- odom 还未稳定
- static transform 还未全部发布

的时候最明显。

#### 解决办法

项目中新增了 `gaden_sensor_gate_node`：

- 等待 TF 条件满足
- 再启动 `simulated_gas_sensor`
- 超时则 fail fast

后面又进一步强化为：

- 连续多次 ready 才放行
- 尽量减少首帧不稳定

#### 当前效果

早期大面积 TF 断树错误已经被压掉，只剩极少数第三方节点启动期的轻量日志噪声。

#### 经验

对 ROS 多组件系统，靠“拍脑袋延时”并不稳，应该尽量改成“等条件满足再继续”。

### 4.7 `SOURCE_FOUND` 早期语义错误：找到的是热点，不是真实源点

#### 现象

早期版本里，机器人在高浓度热点附近就会宣告 `SOURCE_FOUND`，但位置往往离真实泄漏源还较远。

例如在简单场景中，热点可能出现在：

- `(-1.4, 3.1)`

而真实泄漏源其实在：

- `(-4.0, 1.95)`

#### 根因

状态机最初的完成条件偏向“高浓度 + 局部稳定”，但没有把“真实源点几何约束”纳入判定。

#### 解决办法

在 `MissionConfig` 中加入 `actual_source` 语义：

- `source_x`
- `source_y`

并要求：

- 只有当估计源点也接近真实配置源点时，才允许进入 `SOURCE_FOUND`

#### 当前效果

现在系统不会再因为靠近羽流热点就误判“找到源头”。

#### 经验

“检测到最高浓度点”与“定位到真实源头”不是同一个语义，必须显式区分。

### 4.8 巡检和追踪目标的坐标系曾经混用

#### 现象

warehouse 场景下，追踪目标曾出现明显错误方向跳变，看起来像机器人被突然拉向不合理目标。

#### 根因

任务层中一段历史样本和当前位姿推理曾混用了：

- `/odom`
- `/amcl_pose`

这会导致用 odom 系历史去生成 map 系导航目标。

#### 解决办法

在 `mission_manager_node` 中改成以 `/amcl_pose` 作为 map 系跟踪基准，避免把 odom 历史直接用于 map 目标生成。

#### 当前效果

追踪目标方向已经明显更合理，warehouse 场景中追踪目标会继续向真实源区推进，而不是横向跳走。

#### 经验

只要任务层要直接下发 map 系导航目标，就必须非常严格地区分 TF / 位姿消息的坐标系语义。

### 4.9 追踪阶段曾出现“热点锁死”

#### 现象

进入 `SEEK_TRACK` 后，机器人容易反复停在最近窗口里的局部最高浓度点附近，不再继续向真实源点推进。

#### 根因

`select_tracking_target()` 早期策略是：

- 只要历史窗口里出现高浓度峰值，就回到那个 strongest pose

这会导致：

- 当前点本身已是 strongest sample 时，机器人继续“守热点”
- 而不是继续沿梯度向真实源点推进

#### 解决办法

重写 `select_tracking_target()` 的决策逻辑：

- 只有 strongest sample 不是最新样本时，才回访它
- 如果当前样本已经是 strongest，则继续调用梯度搜索逻辑前探

#### 当前效果

tracking 目标已经能继续推进到更靠近真实源点的位置，例如：

- `3.3936, -2.3616`
- `3.3123, -2.5228`

而不是一直停在旧热点。

#### 经验

热点回访是有价值的，但不能让“回访机制”吞掉“继续搜索”的能力。

### 4.10 warehouse 场景 world、map 与真实 clutter 一度不一致

#### 现象

warehouse 场景第二个巡检点长期报：

- `Failed to make progress`

探针显示机器人会稳定卡在一片看起来“地图自由、实际世界却有 clutter”的区域。

#### 根因

静态占据图 `warehouse_map` 与 Gazebo world 的障碍布局不一致：

- global planner 认为可行
- 但局部感知和 local costmap 实际发现障碍

#### 解决办法

采取了两步：

1. 修补缺失的关键静态障碍
2. 更保守地重构 warehouse 的上半段巡检路线，让它避开左侧容易卡死的通道，改走中右通道

#### 当前效果

warehouse 的上半段 patrol route 已明显更稳定，之前第二个 waypoint 处的 `Failed to make progress` 已被压下。

#### 经验

在复杂场景中，地图语义不一致带来的问题，往往会伪装成 Nav2 参数问题，但根因可能是场景本体。

### 4.11 双场景平台早期只是“接口有 scene”，实际上仍偷吃 baseline 默认值

#### 现象

最初即便已经引入 `scene:=baseline|warehouse`，运行态仍有多处偷偷吃 baseline 默认：

- world
- map
- AMCL 初始位姿
- GADEN 默认路径
- 简化气体场参数

#### 根因

scene 参数一开始只停留在 launch 表层，没有真正进入：

- Gazebo world 路由
- Nav2 runtime map
- scene-specific GADEN
- scene-specific gas field

#### 解决办法

逐步把 scene 变成真正的正式资源层：

- `scene_loader.py`
- `scene.yaml`
- `nav2.launch.py`
- `bringup.launch.py`
- `sim.launch.py`
- `demo_prep`

都改成按 scene 配置驱动。

#### 当前效果

现在 scene 已经是一个真正的工程边界：

- baseline 和 warehouse 各自有自己的 world/map/nav2/gaden/gas_field/mission

#### 经验

只有把配置、地图、启动链和运行参数都变成 scene-owned，双场景平台才算真的成立。

### 4.12 warehouse 默认 GADEN 一开始并不存在，只能回退简化场

#### 现象

最初 `scene:=warehouse` 虽然 world 已经切换成功，但默认还没有自己的 GADEN 资产，系统只能诚实地回退到简化气体场。

#### 根因

当时只有：

- warehouse world
- warehouse map

但没有：

- warehouse 自己的 GADEN project
- warehouse 自己的 occupancy / wind / playback

#### 解决办法

在外部 `gaden_ws` 中新增：

- `test_env/scenarios/h2track_warehouse`

并建立独立的：

- `gaden.gproj`
- `config1/config.yaml`
- `scene1.yaml`
- `sim1/sim.yaml`
- STL 几何
- preprocessing 结果
- filament simulation 结果

同时把 warehouse `scene.yaml` 改成默认 `use_gaden: true`，并要求缺失配置时 fail fast。

#### 当前效果

warehouse 已经有自己独立的 GADEN 场景，不再默默回退 baseline 房间路径。

#### 经验

如果一个场景默认依赖外部仿真资产，就必须把这份资产做成 scene 的正式资源，而不是 launch 里的一组散参数。

### 4.13 warehouse GADEN 曾出现大面积 `outside the environment`

#### 现象

早期 warehouse GADEN 运行时连续报：

- `Requested gas concentration at a point outside the environment`

一旦进入第二段巡检或恢复行为，就容易越界。

#### 根因

近似仓库 GADEN 场景最初只覆盖了仓库地图右上局部区域，而 Nav2 的实际地图覆盖范围远大于它。

更具体地说：

- `warehouse_map` 覆盖整张仓库图
- 初版 GADEN 几何只对上了一个子区域

#### 解决办法

这个问题分两轮解决：

1. 先通过偏移把局部覆盖勉强对齐到巡检区域
2. 再彻底重建近似仓库几何，使：
   - occupancy
   - wind
   - playback
   - source 坐标
   - world / map

都直接按仓库世界坐标生成，覆盖整张 warehouse_map

#### 当前效果

最新 warehouse GADEN 运行中，这类越界错误已经消失。

#### 经验

GADEN 对齐不能只看“几个 patrol 点”，而要看是否覆盖整个导航地图与恢复行为可能到达的区域。

### 4.14 GADEN playback 长度不够，导致追踪中途数据耗尽

#### 现象

warehouse 场景运行到后半段时，`gaden_player` 会开始报缺少后续 `iteration_XXX` 文件，导致源点判定前后可能失去气体输入。

#### 根因

外部 warehouse `sim1/result` 结果文件数量有限，而 player 回放频率最初是固定 `1.0 Hz`，对 warehouse 的较长巡检时长来说太快。

#### 解决办法

把 `player_freq` 做成 scene-specific 参数：

- baseline：`1.0`
- warehouse：`0.5`

由 scene 配置驱动，而不是写死在 launch 中。

#### 当前效果

在 warehouse 场景中，GADEN playback 已能支撑到完整检出、追踪和 `SOURCE_FOUND` 的主任务过程；缺少 iteration 的错误被推迟到任务完成之后更靠后的位置。

#### 经验

GADEN playback 不仅是“能不能启动”的问题，还直接决定任务链能否在有效气体输入下走完。

### 4.15 `demo_prep` 早期不是 scene-aware，容易误报

#### 现象

最初 `demo_prep` 会把 GADEN 依赖、world 检查逻辑等写死成默认场景规则，因此：

- `warehouse + use_gaden:=false` 时会误报
- stale process 匹配也不够准确

#### 根因

工具命令仍然停留在单场景假设，没有跟上双场景架构。

#### 解决办法

把 `demo_prep` 改成 scene-aware：

- 支持 `--scene`
- 支持 `--use-gaden auto|true|false`
- 按 scene 决定所需包和 world

#### 当前效果

`demo_prep --scene warehouse --use-gaden false --dry-run` 已能正确通过。

#### 经验

双场景平台建立后，连运维工具都必须跟着 scene-aware，否则表面上架构升级了，实际工具链还停留在旧假设。

## 5. 当前仍然存在的不足与未完全解决的问题

虽然系统已经比最初阶段成熟很多，但仍有几类问题没有彻底做完。

### 5.1 warehouse 的源点定位精度仍有提升空间

当前最新一轮 tighter convergence 调整后，warehouse `SOURCE_FOUND` 位姿与真实源点之间误差约为：

- `0.504 m`

这说明：

- 已经进入“几何上基本合理”的区间
- 但距离“更优、更稳、更可研究化”的结果还有空间

### 5.2 最新一轮精度调优还没入库

当前双场景 worktree 里还有两处未提交改动：

- `src/h2track_sim/scenes/warehouse/scene.yaml`
- `src/h2track_sim/test/test_warehouse_map_contract.py`

它们对应的是：

- `source_radius = 0.6`
- `source_hold_steps = 3`
- `track_step = 0.3`

这轮调优已通过本地验证，但还没形成新的 Git 提交。

### 5.3 warehouse 场景的 GADEN 资产仍是“可运行近似版”

当前 warehouse GADEN 已经是本地生成资产，而不是占位 symlink，但它仍然不是完全精细的仓库 CFD 场景：

- 几何是近似重建
- 重点是和 world/map 对齐、能支持研究
- 还不是高保真完整仓库空气流动建模

### 5.4 还缺少系统化指标统计

虽然已经有大量单次运行证据，但还没有形成系统性实验统计，例如：

- 巡检成功率
- 检出时间分布
- 追踪成功率
- 源点定位误差统计
- baseline 与 warehouse 的对比表

### 5.5 外部 GADEN 资产不在主仓库版本控制内

这一点是设计选择，不是错误：

- 外部资产放在 `/home/user/gaden_ws`
- 主仓库只保存配置与运行手册

但这也意味着：

- 如果迁移机器，必须重建或复制外部场景资产
- 需要更清楚的 runbook 和再生成脚本

## 6. 当前形成的项目方法论与经验

项目推进到现在，已经形成了几条比较明确的方法论。

### 6.1 先把工程边界做清楚，再提升真实性

如果一开始就追求最真实的 CFD、最复杂算法，系统很容易卡死在集成细节中。

项目实际走通的顺序是：

1. 先重建干净工作区
2. 先做稳定的导航和任务状态机
3. 再接 GADEN
4. 再做 demo 与 scene-aware 工程化
5. 再提升 warehouse 真实性
6. 最后再追求算法精度与研究指标

### 6.2 明确区分“导航问题”“场景问题”“气体场问题”“状态机问题”

这个项目里，很多表面现象都很像，但根因不同：

- `Failed to make progress` 可能是 Nav2 参数问题，也可能是静态地图缺障碍
- `SOURCE_FOUND` 错误可能是状态机过松，也可能是热点与真实源点语义没分开
- `outside the environment` 看起来像传感器错误，本质可能是 GADEN 几何覆盖不足

这也是为什么后期调试越来越依赖：

- 运行日志
- 位姿探针
- 浓度探针
- scene contract test

### 6.3 尽量用 scene-owned 配置，而不是全局硬编码

双场景平台成立后，最关键的工程经验是：

- 一个场景的 world/map/nav2/gaden/gas_field/mission 应该属于同一份 scene 配置

这样才能保证：

- baseline 是快速研发入口
- warehouse 是真实性验证入口
- 两者可以独立演进

### 6.4 保留 fallback 路径很重要

以下回退路径都被证明很有价值：

- `use_gaden:=false`
- `demo_prep`
- `demo_selfcheck`
- baseline 场景保底

这使得项目在复杂 GADEN/warehouse 调试阶段，仍然不会丢失原有稳定基线。

### 6.5 TDD 与 contract test 对这种项目特别重要

本项目后期大量问题不是“函数错没错”，而是“工程契约有没有被破坏”，例如：

- scene 是否真正驱动 world/map/nav2/gaden
- warehouse 是否有独立 GADEN 配置
- 地图是否标出关键 clutter
- warehouse 场景是否使用了自己的 route / map / source / gas field

这类问题很适合转成 contract test。

## 7. 对当前阶段的总判断

截至现在，项目已经明显跨过了“只是在搭框架”的阶段，进入到了“可运行、可扩展、可研究”的中期阶段。

可以用一句话概括当前状态：

**主工程已经从单场景演示原型，推进成了一个具备 baseline/warehouse 双场景、支持 Nav2、GADEN、巡检与追踪闭环的研究型仿真平台。**

进一步拆开看：

- `main`
  - 可以视为稳定快照
- `feat/dual-scene-platform`
  - 可以视为当前真正的研发主线
- `gaden_ws`
  - 承担外部场景资产与 playback 结果

项目最大的阶段性跨越主要有三次：

1. 从中文路径旧工程迁移到干净的 ASCII 新工程
2. 从简化气体场推进到 GADEN 集成
3. 从单场景 demo 推进到双场景研究平台

## 8. 建议的下一步开发方向

在写这份总结时，不先替下一步拍板，只给出当前最合理的几个方向。

### 方向 A：继续压 warehouse 的源点定位精度

适合如果你当前最重视：

- “SOURCE_FOUND 是否更靠近真实源点”
- warehouse 场景的研究可信度

重点会落在：

- `track_step`
- `source_radius`
- `source_hold_steps`
- source estimate 稳定性
- tracking 末段的目标生成逻辑

### 方向 B：做 baseline / warehouse 的系统对比实验

适合如果你当前最重视：

- 研究数据
- 汇报指标
- 后续论文型材料

重点会落在：

- 检出时间
- 追踪时间
- 成功率
- 源点误差
- 双场景退化分析

### 方向 C：继续提升 warehouse 环境真实性

适合如果你当前最重视：

- 更真实的障碍布局
- 更复杂的通道规划
- 更贴近真实环境的 GADEN 资产

重点会落在：

- 更精细的 occupancy / geometry
- 更合理的巡检路线
- 更真实的源点与羽流关系

## 9. 当前你可以直接引用的阶段结论

如果你要对外简短描述当前项目状态，可以直接用下面这段话：

> 目前项目已经完成了从单场景仿真原型到双场景研究平台的升级。系统在 baseline 场景和 warehouse 场景下都能够完成自主巡检、避障、气体检出与追踪闭环；warehouse 场景已经接入独立的 GADEN 气体场，不再依赖 baseline 房间示例。当前工作的重点已经从“系统能否跑起来”转向“追踪精度、环境真实性与双场景对比评估”。  

## 10. 附录：关键路径与关键文件

### 10.1 关键目录

- 主工程：`/home/user/h2track-xian`
- 双场景开发分支：`/home/user/h2track-xian/.worktrees/dual-scene-platform`
- 外部 GADEN 工作区：`/home/user/gaden_ws`

### 10.2 关键分支

- `main`
- `feat/dual-scene-platform`

### 10.3 当前最关键的场景文件

- `src/h2track_sim/scenes/baseline/scene.yaml`
- `src/h2track_sim/scenes/warehouse/scene.yaml`
- `src/h2track_sim/scenes/warehouse/maps/warehouse_map.yaml`
- `src/h2track_sim/scenes/warehouse/nav2_params.yaml`

### 10.4 当前最关键的 tracking / launch 文件

- `src/h2track_tracking/h2track_tracking/mission_logic.py`
- `src/h2track_tracking/h2track_tracking/mission_manager_node.py`
- `src/h2track_sim/launch/demo.launch.py`
- `src/h2track_sim/launch/bringup.launch.py`
- `src/h2track_sim/launch/nav2.launch.py`
- `src/h2track_sim/launch/scene_loader.py`

