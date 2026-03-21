# h2track-xian 双场景研究平台设计文档

## 1. 设计目标
本轮开发的目标不再是继续围绕单一演示工况做局部调参，而是把 `h2track-xian` 重构成一个同时支持 `baseline` 和 `warehouse` 两套场景的研究平台。

新的平台目标有两条主线：
- `地图与环境真实性`：引入完整仓库世界，验证更真实的障碍、通道和遮挡关系下的巡检、避障和气体追踪表现。
- `气体追踪算法质量`：保留一个简单、可重复的基线场景，用于快速验证状态机、阈值和局部目标生成逻辑，并为复杂场景迁移提供回归基准。

这意味着项目以后不再围绕“单次 demo 是否好看”设计，而是围绕“是否能形成稳定的双场景研究闭环”设计。

## 2. 当前系统基线
当前工程已经具备以下能力：
- [`bringup.launch.py`](/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py) 可以拉起 Gazebo、Nav2、GADEN 相关节点和任务节点。
- [`mission_manager_node.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py) 已实现 `PATROL -> SEEK_CONFIRM -> SEEK_TRACK -> SOURCE_FOUND` 主闭环。
- [`mission_logic.py`](/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py) 已支持“真实源点附近才允许 `SOURCE_FOUND`”的约束。
- 当前场景 [`h2track_lab.world`](/home/user/h2track-xian/src/h2track_sim/worlds/h2track_lab.world) 结构非常简单，只适合作为基线调试场景，不适合作为唯一研究环境。
- 当前配置 [`demo.yaml`](/home/user/h2track-xian/src/h2track_sim/config/demo.yaml) 仍以单场景演示工况为中心，尚未抽象出“场景”这一一级概念。

当前阶段的核心问题不是“系统能不能跑”，而是“工程结构是否能同时支撑快速算法迭代和更真实环境验证”。

## 3. 设计原则
### 3.1 双场景分工明确
后续平台必须同时保留两套场景，但两者不能承担相同职责：
- `baseline` 负责快速算法验证、回归测试和问题隔离。
- `warehouse` 负责真实性验证、复杂环境导航与追踪评估。

### 3.2 场景应成为一级配置对象
不再让单个 `demo.yaml` 管所有运行配置。后续所有场景相关参数都应按场景拆分，包括：
- world
- map
- 初始位姿
- 巡检点
- 泄漏源位置
- 演示或实验专用阈值
- Nav2 参数入口

### 3.3 共用核心与场景资源解耦
机器人模型、Nav2 主启动链、mission logic、GADEN adapter、彩排工具等能力应尽量保持场景无关；world、map、patrol points 和 source geometry 等内容应下沉到场景层。

### 3.4 真实性提升优先于花哨功能扩展
本轮优先级是：
1. 建立双场景架构
2. 接入完整仓库世界
3. 让仓库场景的导航、GADEN 和真实源点几何关系成立
4. 在此基础上再升级追踪算法

不在本轮继续扩展多泄漏源、在线 CFD、SLAM 或实物联调。

## 4. 平台架构设计
### 4.1 共用核心层
该层尽量保持不分场景，继续作为整个平台的稳定骨架。主要包括：
- 机器人模型与控制接口
- Nav2 共用启动链
- GADEN adapter 与 sensor gate
- mission manager / mission logic
- `demo_prep`、`demo_selfcheck` 等运行工具

这一层的目标是保持接口稳定，避免每引入一个新场景就复制一套逻辑。

### 4.2 场景资源层
该层新增显式场景目录，并把场景相关资产拆开管理。建议至少包含：
- `baseline`
- `warehouse`

每个场景各自拥有：
- world
- map
- scene config
- patrol/source 参数
- 必要的 RViz / launch 覆盖参数

推荐目录形态如下：
- `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/`
- `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/`

其中 `baseline` 初期可以复用现有 `h2track_lab` 资产并做轻量清理；`warehouse` 将引入完整仓库世界资源。

### 4.3 实验入口层
运行入口应显式接收 `scene:=baseline|warehouse` 参数，而不是继续隐式绑定单一默认场景。

推荐做法：
- 保留通用 bringup 入口
- 在 bringup 中增加 `scene` 参数
- 由 `scene` 参数决定加载哪套 world、map 和 scene config
- 所有彩排、自检和后续实验脚本都显式声明当前场景

这样一来，用户能够清楚知道当前是在做：
- 基线算法验证
- 还是仓库真实性验证

## 5. 两套场景的职责边界
### 5.1 baseline 场景
`baseline` 不追求复杂和真实，而追求：
- 可重复
- 运行快
- 调试快
- 回归稳定

它主要用于：
- 快速验证状态机切换
- 快速调节检测阈值
- 快速验证局部目标生成策略
- 为复杂场景迁移提供对照基准

### 5.2 warehouse 场景
`warehouse` 的目标是更接近真实问题，重点验证：
- 更复杂障碍布局下的全局规划和局部避障
- 货架通道、遮挡和通行约束下的追踪表现
- 真实源点附近的几何收敛合理性
- 算法从 baseline 迁移到真实场景后的退化与改进空间

`warehouse` 不是简单换一张更大地图，而是项目真实性的主要承载环境。

## 6. 仓库世界集成策略
本轮采用“完整原版仓库世界”路线，但资源将被直接整理进 `h2track-xian`，而不是保持为外部 GitHub 运行时依赖。

设计要求如下：
- 仓库世界所需 world、models、materials 和相关资源复制进工程内的场景目录。
- 项目运行时不依赖额外下载该仓库世界。
- GADEN 坐标、Gazebo 世界坐标和任务层 source geometry 必须重新对齐。
- 新仓库场景下的泄漏源位置要与真实货架/通道结构匹配，不能再沿用旧 lab world 的几何关系。

## 7. 开发顺序
### 7.1 先冻结 baseline
先把现有简单场景正式定义为 `baseline`，停止继续向其中叠加新需求，只做必要的结构清理。

### 7.2 再搭 scene 框架
先完成工程结构重构，让项目能显式区分 `baseline` 和 `warehouse` 两套场景，再开始导入仓库世界。

### 7.3 再接 warehouse 环境
把完整仓库世界资源整理进工程，优先验证：
- Gazebo 能启动
- 机器人能生成
- Nav2 能在仓库环境中工作
- 世界资源路径稳定

### 7.4 再对齐 GADEN 与 source geometry
在新仓库场景里重新标定：
- 泄漏源坐标
- 羽流边缘接触路径
- 巡检点与障碍物关系
- `SOURCE_FOUND` 的真实几何约束

### 7.5 最后升级算法
等双场景都稳定后，再继续升级追踪算法本身，例如：
- 更稳的确认逻辑
- 更好的局部目标生成
- 更合理的热点回访策略
- 更强的真实源点收敛判定

## 8. 成功标准
完成本轮平台重构后，至少满足以下标准：
- 项目能通过显式 `scene` 参数启动 `baseline` 和 `warehouse` 两套场景。
- `baseline` 仍能作为快速回归台稳定运行。
- `warehouse` 场景能完成 Gazebo、Nav2、GADEN 和 mission manager 的基础闭环启动。
- 仓库场景中的 `SOURCE_FOUND` 判定与真实泄漏源几何位置一致，不再只是羽流热点。
- 后续算法改动能在两套场景上做对照验证。

## 9. 风险与应对
### 风险 1：完整仓库世界引入过多变量
应对：保留 baseline 作为稳定对照，不在仓库场景里直接调所有算法参数。

### 风险 2：仓库世界资源路径和 Gazebo 依赖复杂
应对：把资源直接整理进仓库目录，并新增场景级 launch/config 封装，避免运行时隐式依赖外部仓库。

### 风险 3：GADEN 与新世界几何关系不一致
应对：把 source geometry 和 scene config 明确拆到场景层，逐场景标定，而不是复用旧 demo 参数。

## 10. 结论
后续最正确的发展方向不是继续围绕单一 demo 收敛，而是把 `h2track-xian` 升级成一个双场景研究平台：
- `baseline` 提供快速、稳定的算法验证环境
- `warehouse` 提供更真实的环境与导航约束

只有先把这个平台搭起来，后续的追踪算法优化才有研究意义和工程抓手。
