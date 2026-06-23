# ADR 0001: TDLAS Integration Decision

## Status

Proposed — 2026-06-23

## Context

h2track-xian 当前使用 GADEN 的 `gaden_player` + `gaden_adapter_node` 提供点浓度
传感器（olfaction_msgs/GasSensor）模拟。GADEN 还提供 `simulated_tdlas` 节点
模拟可调谐半导体激光器光谱（TDLAS）传感器，输出线积分浓度（ppmxm）。

**问题**：是否应将 TDLAS 作为 h2track 的第二传感器，用于远距离氢气检测？

## TDLAS 节点参数清单

来源：`/home/user/gaden_ws/src/gaden/simulated_tdlas/src/simulated_tdlas.{h,cpp}`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `measurementFrequency` | 2.0 Hz | 测量频率 |
| `rayMarchResolution` | 0.1 m | DDA 射线步进分辨率 |
| `maxRayDistance` | 10.0 m | 最大射线距离 |
| `fixedFrame` | "map" | 固定参考坐标系 |
| `sensorFrame` | "tdlas_frame" | 传感器坐标系 |
| `reflectorLocTopic` | "/reflector/amcl_pose" | 反射器位姿话题（多机器人场景） |
| `reflector_radius` | 0.3 m | 反射器圆柱半径 |
| `reflector_height` | 2.0 m | 反射器圆柱高度 |
| `verbose` | false | 详细日志 |

**依赖服务**：
- `/odor_value`（GasPosition）：查询射线沿途各单元格的浓度真值
- `/gaden_environment/occupancyMap3D`（Occupancy）：获取 3D 占用网格用于射线碰撞检测

**发布话题**：
- `tdlas/reading`（olfaction_msgs/TDLAS）：`average_ppmxm` + 5 次连续读数 `ppmxm[]`
- `tdlas/arrow`（visualization_msgs/Marker）：射线可视化

**算法**：DDA（Digital Differential Analyzer）3D 射线步进，每步查询 GasPosition
服务累加 `concentration × cell_length`，输出 ppmxm = ppm × meter。

## 氢气场景适用性分析

### 优势

1. **远距离检测**：maxRayDistance=10m 可在机器人到达前预警
2. **积分浓度**：对稀疏羽流更敏感（路径积分放大信号）
3. **定向性**：射线方向可控，可用于扫描式源定位

### 劣势（针对 H2）

1. **H2 上升特性**：氢气密度 0.0899 kg/m³ 远低于空气 1.225 kg/m³，羽流快速
   上升，而 TDLAS 射线默认水平方向（沿 sensor_frame 的 +X 轴），可能错过
   高空羽流
2. **ppmxm 单位不兼容**：现有 PF（GaussianPlumeObservationModel）和 Surge-Cast
   假设点浓度 ppm，TDLAS 输出 ppmxm 需要新观测模型
3. **多机器人假设**：反射器模式假设第二机器人持反射板，h2track 当前单机器人
4. **PID 不敏感**：GADEN 的 PID 校正因子中 H2 = 0.0（TDLAS 不使用 PID 因子
   但共享传感器模型假设，H2 的点传感器路径已验证可用）

## 三种融合方案对比

### 方案 A：TDLAS 作为远距离预警（最低改动）

- **改动**：在 `bt_node_runner` 增加 TDLAS 订阅，当 `ppmxm > 阈值` 时
  boost PF 权重或触发 Surge-Cast 加速
- **优点**：不改变 PF 观测模型，风险低
- **缺点**：未充分利用 TDLAS 线积分信息，仅作二值预警
- **复杂度**：Low（~1 天）
- **PF 改动量**：无

### 方案 B：TDLAS 线积分观测模型（高保真）

- **改动**：新建 `TdlasObservationModel`，沿射线积分 expected_concentration，
  似然 = exp(-(measured_ppmxm - expected_ppmxm)² / (2σ²))
- **优点**：物理一致，充分利用线积分信息
- **缺点**：每粒子需沿线采样多个点，计算成本高（N 粒子 × M 射线点）
- **复杂度**：High（5-7 天）
- **PF 改动量**：新增 ObservationModel 子类，PF 需支持多观测模型

### 方案 C：级联（TDLAS 粗定位 + Surge-Cast 精细导航）

- **改动**：TDLAS 扫描确定源区域（扇形扫描找最大 ppmxm 方向），
  导航到该区域后切换 Surge-Cast 精细追踪
- **优点**：结合 TDLAS 远距离 + Surge-Cast 近距离优势
- **缺点**：需要扫描机制（机器人原地旋转或 TDLAS 旋转云台），场景复杂
- **复杂度**：Medium-High（3-5 天）
- **PF 改动量**：无（TDLAS 输出直接驱动导航）

## scene.yaml 配置草案

```yaml
tdlas:
  enabled: false              # 默认关闭
  measurement_frequency: 2.0 # Hz
  ray_march_resolution: 0.1  # m
  max_ray_distance: 10.0    # m
  sensor_frame: tdlas_frame  # 需在 URDF 添加
  ppmxm_threshold: 50.0      # 预警阈值（方案 A）
```

## 决策

**建议：延后实施**

### 理由

1. **H2 场景不匹配**：氢气上升特性与 TDLAS 水平射线矛盾，需要传感器俯角
   调整或反射器模式，增加机械复杂度
2. **硬件未定型**：h2track 硬件方案未确定是否包含 TDLAS，过早集成可能浪费
3. **ROI 低于其他方向**：Anemometer（已完成）+ MOX 动态（已完成）+ GasPosition
   真值评估（已完成）已覆盖仿真主要差距
4. **ppmxm 转换成本**：需要新观测模型，破坏现有 PF/Surge-Cast 接口一致性

### 触发条件（重新评估）

- 硬件方案确定包含 TDLAS 传感器
- 需要在 10m+ 距离检测氢气泄漏（如工业管线巡检场景）
- 引入第二机器人作为反射器（多机器人协作场景）

## 后续行动

- 记录此决策，等硬件方案定型后重新评估
- 优先推进已完成 Phase 1-3 的集成测试（demo_regression + anemometer + MOX）
- 若未来引入 TDLAS，优先方案 A（预警模式），验证 ROI 后再考虑方案 B/C

## 参考

- GADEN `simulated_tdlas` 源码：`/home/user/gaden_ws/src/gaden/simulated_tdlas/`
- olfaction_msgs/TDLAS.msg：`average_ppmxm` + `ppmxm[]`（5 次连续读数）
- h2track PF 观测模型：`src/h2track_tracking/h2track_tracking/particle_filter/observation_model.py`
- h2track 融合模块：`src/h2track_tracking/h2track_tracking/tracking/fusion.py`
