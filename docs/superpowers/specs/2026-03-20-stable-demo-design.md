# h2track-xian 稳定演示版设计文档

## 1. 设计目标
本轮开发的目标不是继续扩展功能边界，而是把当前 `h2track-xian` 收敛成一套适合阶段汇报/验收的稳定演示系统。

目标演示必须满足以下条件：
- 一条命令启动
- 全流程无需人工干预
- 现场可清楚看出“巡检 -> 检测 -> 追踪 -> 找到源头”的模式变化
- 单次演示总时长控制在 `3-5` 分钟
- 演示失败时能够快速判断是启动问题、导航问题还是追踪问题

## 2. 当前系统基线
当前系统已经具备以下基础：
- [`bringup.launch.py`](/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py) 能拉起 Gazebo、Nav2、GADEN 相关节点和任务节点
- [`mission_manager_node.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py) 已经实现 `PATROL -> SEEK_CONFIRM -> SEEK_TRACK -> SOURCE_FOUND` 的主闭环
- [`mission_logic.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py) 已经具备基本状态机
- [`nav2_params.yaml`](/home/user/h2track-xian/src/h2track_sim/config/nav2_params.yaml) 已能支撑当前差速机器人导航
- GADEN 集成已通过 `gaden_adapter_node` 和 `gaden_sensor_gate_node` 接入上层系统

这意味着当前项目已经从“功能拼装”进入“演示产品化”阶段。后续工作重点应当是稳定性、可控性、可观测性，而不是继续发散功能。

## 3. 演示版范围定义
### 3.1 演示主目标
现场演示突出“闭环完整性”，具体流程固定为：
1. 启动系统
2. 机器人自动进入巡检
3. 机器人进入泄漏影响区域后检测到氢气
4. 系统自动切换到追踪模式
5. 追踪过程中继续执行避障与规划
6. 到达源头附近后自动停车并报警

### 3.2 演示边界
本轮演示版明确只覆盖以下范围：
- 单机器人
- 单泄漏源
- 已知静态地图
- 固定障碍物布局
- 固定巡检路径
- 默认 `use_gaden:=true`
- `use_gaden:=false` 仅作为回退模式保留

本轮演示版明确不做以下内容：
- 多泄漏源
- SLAM
- 在线 CFD
- 研究型复杂源定位算法
- 实物联调
- 大规模场景随机化

## 4. 设计原则
### 4.1 先收敛，再增强
当前阶段的成功标准是“稳定演示”，不是“算法最优”。因此所有改动都必须优先回答一个问题：它是否直接提升现场演示成功率。

### 4.2 把启动问题、导航问题、追踪问题分开
系统调试必须按层次推进：
- 启动链是否稳定
- Nav2 是否稳定激活并执行目标
- 追踪状态机是否稳定切换
- GADEN 传感器链是否稳定提供浓度输入

只有这样，现场失败时才能迅速定位根因。

### 4.3 用“条件满足后继续”代替“猜一个延时”
`gaden_sensor_gate_node` 已经验证，基于条件的门控比固定延时更可靠。后续演示版应继续沿这个原则推进：凡是依赖关系明确的地方，优先做 readiness / self-check / gate，而不是继续堆固定秒数。

### 4.4 保留回退路径
`use_gaden:=false/true` 的双模式必须保留。现场正式演示走 `GADEN`，但开发、彩排和故障定位时必须能快速切回简化气体场，以隔离问题来源。

## 5. 演示版架构设计
### 5.1 Demo Profile 层
新增一套专用 demo 配置，而不是继续复用通用调试参数。

该层负责集中描述：
- 机器人初始位姿
- 巡检点序列
- 泄漏源位置
- 演示阈值参数
- 默认导航参数文件
- 默认 RViz 配置
- 默认使用 `GADEN`

推荐新增文件：
- `/home/user/h2track-xian/src/h2track_sim/config/demo.yaml`
- `/home/user/h2track-xian/src/h2track_sim/config/nav2_demo_params.yaml`
- `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`

设计意图是把“稳定演示”从“通用 bringup”里分离出来，形成单独的演示产品入口。

### 5.2 启动编排层
当前 [`bringup.launch.py`](/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py) 已经可用，但它仍偏向集成入口。演示版需要一个更保守、更窄的启动路径。

推荐做法：
- 保留 `bringup.launch.py` 作为通用入口
- 新增 `demo.launch.py` 作为正式演示入口
- `demo.launch.py` 以固定 demo 配置封装 `bringup.launch.py`
- 演示入口默认打开 `use_gaden:=true`
- 演示入口使用独立的 Nav2 demo 参数
- 演示入口默认带上任务、GADEN、RViz、可视化所需节点

### 5.3 任务稳定层
当前状态机已经成型，但还偏“工程可运行版本”。演示版需要在现有结构上补齐保护逻辑。

重点改进方向：
- 为 `PATROL -> SEEK_CONFIRM -> SEEK_TRACK -> SOURCE_FOUND` 增加更明确的退出/回退条件
- 在 `SEEK_TRACK` 加入超时、重试、卡死保护
- 对“高浓度区附近反复震荡”增加收敛判定
- 对巡检目标和追踪目标做保守化约束，优先稳，不追求激进逼近

现有实现主要落点：
- [`mission_logic.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py)
- [`mission_manager_node.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py)

### 5.4 演示可观测性层
当前系统已经有 `/robot_mode`、`/source_found`、`/estimated_source_pose`，但现场演示仍然不够“看得懂”。

演示版建议增加：
- 当前模式可视化
- 当前浓度与阈值状态可视化
- 当前巡检目标 / 局部追踪目标可视化
- 估计源点 marker
- 一条更易讲解的日志流

推荐实现为一个独立的 demo 可视化节点，而不是继续把可视化逻辑塞进 mission manager。

### 5.5 自检与兜底层
正式演示不能只靠“启动后看运气”。必须增加自检与回退能力。

推荐补充：
- 一个 demo 自检工具，检查关键 topic、关键 TF、Nav2 是否激活
- 一个固定的 demo 运行文档和演示顺序
- 一套标准彩排流程
- 一条备用的 `use_gaden:=false` 启动命令

## 6. 成功标准
演示版开发完成后，至少满足以下标准：
- 同一条正式命令可以连续成功启动 `5` 次
- 在固定标准场景下，连续运行 `10` 次中至少 `8` 次完成完整闭环
- 单次完整流程时长稳定在 `3-5` 分钟
- 演示过程中无明显撞障、长时间原地空转或人工补救
- 现场观察者不看代码也能理解当前阶段处于巡检、确认、追踪还是找到源头

## 7. 开发优先级
按优先级分为四层：
1. `P0 启动稳定性`：保证系统一键启动成功
2. `P1 演示可控性`：固定场景、固定路径、固定参数
3. `P2 闭环行为稳定性`：保证大概率走完整条链
4. `P3 现场表达与兜底`：让演示可讲、可看、可回退

## 8. 里程碑
### M1：演示底座冻结
- 固定标准场景
- 固定巡检与泄漏配置
- 固定正式启动命令

### M2：一键启动稳定
- 梳理 launch 依赖
- 增加 readiness / gate / 自检
- 失败时能够快速诊断

### M3：闭环行为稳定
- 调整巡检路径
- 调整状态机阈值与保护逻辑
- 调整 Nav2 参数

### M4：演示表达与兜底
- 增加 RViz/日志可视化
- 准备演示脚本与备用模式

## 9. 风险与应对
### 风险 1：GADEN 链路仍有启动早期异常
应对：继续增强 gate 节点与 readiness 判断，把第三方节点的启动前置条件显式化。

### 风险 2：追踪行为在高浓度区震荡
应对：增加状态机超时、收敛阈值、失败重试和保守化局部目标策略。

### 风险 3：现场无法讲清当前系统状态
应对：增加演示可视化层和固定讲解顺序。

## 10. 结论
当前最正确的开发方向不是继续横向扩功能，而是围绕“稳定演示闭环完整性”做产品化收敛。

后续所有开发都应服从这一目标：
- 一键启动
- 全自动运行
- 行为清楚
- 高成功率
- 失败可诊断
