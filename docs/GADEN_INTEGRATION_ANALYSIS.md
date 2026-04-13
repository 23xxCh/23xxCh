# GADEN 与 h2track-xian 集成分析报告

> 生成时间: 2026-04-05
> 分析范围: gaden_ws 与 h2track-xian 的集成问题

## 一、系统关系概述

```
┌─────────────────────────────────────────────────────────────────┐
│                    h2track-xian                                 │
│  (ROS 2 氢气源追踪仿真)                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Gazebo 仿真   │    │ Nav2 导航    │    │ 任务状态机   │      │
│  │ (warehouse)  │───▶│ (路径规划)   │───▶│ (PATROL→    │      │
│  │              │    │              │    │  SEEK_TRACK) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                                        │              │
│         │                                        ▼              │
│         │           ┌──────────────────────────────────┐       │
│         │           │        gas_concentration         │       │
│         │           │     (归一化气体浓度 0-1)          │       │
│         │           └──────────────┬───────────────────┘       │
│         │                          │                           │
│         │                          ▼                           │
│         │           ┌──────────────────────────────────┐       │
│         │           │      gaden_adapter_node          │       │
│         │           │  (GasSensor → 浓度转换)          │       │
│         │           └──────────────┬───────────────────┘       │
│         │                          │                           │
│         │                          ▼                           │
│         │           ┌──────────────────────────────────┐       │
│         │           │   simulated_gas_sensor (GADEN)   │       │
│         │           │   (氢气传感器模拟)               │       │
│         │           └──────────────┬───────────────────┘       │
│         │                          │                           │
│         │                          ▼                           │
│         └──────────────▶ /gaden/sensor_reading                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       gaden_ws                                  │
│  (GADEN 气体扩散仿真)                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ gaden_player │◀───│ gaden_env    │◀───│ gaden_sim    │      │
│  │ (播放结果)   │    │ (环境加载)   │    │ (丝状体仿真) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                                                       │
│         ▼                                                       │
│  /gaden/sensor_reading (GasSensor消息)                         │
│  /gas_distribution (可视化)                                    │
│                                                                 │
│  场景: h2track_warehouse                                        │
│  路径: /home/user/gaden_ws/src/gaden/test_env/scenarios/       │
│        h2track_warehouse                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 二、发现的问题

### 问题 1: 气源位置不匹配 (严重)

**状态**: ✅ 已解决 (2026-04-05)

| 项目 | X | Y | Z |
|------|---|---|---|
| GADEN sim.yaml | 3.5 | -2.0 | 0.8 |
| h2track scene.yaml | 3.6 | -3.038551 | - |

**影响**:
- 测试 `test_warehouse_gaden_source_matches_warehouse_scene_source_after_alignment` 失败
- 机器人可能在错误位置寻找气源
- 追踪算法可能无法正确收敛

**修复方案**:
1. 修改 GADEN sim.yaml: `source.position: [3.6, -3.038551, 0.8]`
2. 重新运行 GADEN 仿真 (`gaden_filament_simulator`)

**已执行的修复** (2026-04-05):
- 更新 `sim.yaml` 中的 `source.position` 为 `[3.6, -3.038551, 0.8]`
- 更新 `lineEnd` 为 `[3.7, -3.038551, 0.8]`
- 重新运行 GADEN 仿真，生成 566 个迭代结果
- 复制仿真结果到 src 目录
- 契约测试 `test_warehouse_gaden_source_matches_warehouse_scene_source_after_alignment` 通过

---

### 问题 2: 气体类型配置错误 (严重)

**状态**: ✅ 已解决 (2026-04-05)

| 项目 | 值 | 比重 (相对空气) | 行为 |
|------|---|----------------|------|
| GADEN gasType | 0 (乙醇) | 1.0378 | 比空气重，向下沉 |
| h2track 目标 | 氢气 | 0.0696 | 非常轻，快速上升 |

**影响**:
- 仿真结果不能准确反映氢气的扩散行为
- 氢气会快速上升，乙醇会下沉
- 传感器读数可能不准确

**修复方案**:
1. 修改 GADEN sim.yaml: `gasType: 2` (氢气)
2. 重新运行 GADEN 仿真

**已执行的修复** (2026-04-05):
- 更新 `sim.yaml` 中的 `gasType` 为 `2` (氢气)
- 重新运行 GADEN 仿真
- 氢气特性: 比重 0.0696，非常轻，快速上升

---

### 问题 3: 坐标系统验证 (已确认)

**状态**: 已验证正常

两个系统的地图具有相同的原点 `[-7.5, -10.8, 0]`:
- warehouse_map.pgm: 150x216, resolution=0.1m
- GADEN occupancy.pgm: 75x108, resolution=0.2m

地图边界完全一致:
- X: [-7.5, 7.5]
- Y: [-10.8, 10.8]

---

### 问题 4: Web Console 静态 Bundle 过期 (次要)

**状态**: 未解决

App.jsx 最后修改时间: 2026-03-30 21:30:20
静态 Bundle 构建时间: 2026-03-30 20:48:44

**修复方案**:
```bash
cd src/h2track_tracking/web_console
npm run build
# 将 dist/ 内容复制到 static_console/
```

---

### 问题 5: 未提交的代码更改 (次要)

**状态**: 未解决

Git status 显示以下未跟踪文件:
```
?? src/h2track_tracking/h2track_tracking/static_console/
?? src/h2track_tracking/web_console/
?? src/h2track_tracking/test/test_llm_agent.py
?? src/h2track_tracking/test/test_web_console_source.py
```

**修复方案**:
1. 重新构建前端 bundle
2. 创建 commit 保存更改

## 三、GADEN 场景配置详情

### h2track_warehouse 场景结构

```
/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/
├── gaden.gproj                    # GADEN 项目文件
├── cad_models/
│   ├── h2track_warehouse_shell.stl  # 仓库外壳模型
│   └── h2track_warehouse_racks.stl  # 货架模型
├── wind_simulations/
│   └── dynamic/
│       └── wind_at_cell_centers.csv  # 动态风场数据
└── environment_configurations/
    └── config1/
        ├── config.yaml            # 环境配置
        ├── OccupancyGrid3D.csv    # 3D 占用网格
        ├── occupancy.pgm          # 2D 占用地图
        ├── occupancy.yaml         # 地图元数据
        ├── scenes/
        │   └── scene1.yaml        # 播放场景配置
        ├── simulations/
        │   └── sim1/
        │       ├── sim.yaml       # 仿真参数
        │       └── result/        # 仿真结果
        └── wind/                  # 预处理后的风场
```

### 关键仿真参数

```yaml
# sim.yaml 当前值
source:
  position: [3.5, -2.0, 0.8]   # ❌ 应改为 [3.6, -3.038551, 0.8]
  gasType: 0                    # ❌ 应改为 2 (氢气)
  filamentPPMcenter: 150
  numFilaments_sec: 30
  expectedNumIterations: 600
```

### h2track 场景参数

```yaml
# scene.yaml
gas_source:
  x: 3.6
  y: -3.038551

mission_manager:
  enter_threshold: 0.65      # 气体检测阈值
  exit_threshold: 0.4        # 退出追踪阈值
  source_threshold: 3.4      # 源点确认阈值
  source_radius: 1.0         # 源点半径 (米)

gaden:
  player_freq: 0.5           # 播放频率 (Hz)
  sensor_topic: /gaden/sensor_reading
  fixed_frame: gaden_map
```

## 四、修复步骤

### 步骤 1: 修复 GADEN 配置

```bash
# 编辑 sim.yaml
nano /home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1/simulations/sim1/sim.yaml

# 修改以下内容:
# source.position: [3.6, -3.038551, 0.8]
# source.gasType: 2
```

### 步骤 2: 重新运行 GADEN 仿真

```bash
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash

ros2 launch test_env gaden_sim_launch.py \
  scenario:=h2track_warehouse \
  simulation:=sim1
```

### 步骤 3: 验证修复

```bash
# 运行契约测试
PYTHONPATH=src/h2track_tracking:$PYTHONPATH \
python3 -m pytest src/h2track_sim/test/test_warehouse_gaden_contract.py -v
```

## 五、测试覆盖

| 测试文件 | 测试数量 | 状态 |
|----------|----------|------|
| test_gaden_adapter.py | 30+ | ✅ 通过 |
| test_gaden_sensor_gate.py | 20+ | ✅ 通过 |
| test_warehouse_gaden_contract.py | 5 | ✅ 全部通过 |
| test_llm_agent.py | 11 | ✅ 通过 |

---

## 六、Wind文件问题 (关键发现)

**问题描述**: GADEN player需要wind文件来播放仿真结果，但当前只有25个wind文件，而仿真有566个迭代。

**错误日志**:
```
[ERROR] [player-5]: process has died [pid 104971, exit code -6]
terminate called after throwing an instance of 'rclcpp::exceptions::RCLError'
```

**解决方案**:
1. 生成更多wind文件（需要CFD仿真）
2. 或使用简化气体场（use_gaden=false）

**验证结果** (2026-04-06):
- 简化气体场测试成功: `source_found=1, seek_track=1`
- 追踪算法本身正常工作
- GADEN需要更多wind文件才能正常使用

## 七、下一步行动

1. **已完成**: 修复 GADEN 气源位置和气体类型 ✅
2. **已完成**: 重新运行 GADEN 仿真 ✅
3. **已完成**: 验证追踪算法（简化气体场） ✅
4. **待解决**: 生成更多wind文件以支持GADEN播放
5. **优先级中**: 重新构建 Web Console bundle
6. **优先级中**: 提交未跟踪的代码更改
