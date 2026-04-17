# 多机器人协作气体源定位设计

## 1. 系统架构

### 1.1 多机器人框架

```
┌─────────────────────────────────────────────────────────┐
│                    协调器 (Coordinator)                   │
│  - 任务分配                                              │
│  - 信息融合                                              │
│  - 冲突解决                                              │
└───────────────────────┬─────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌─────────┐       ┌─────────┐       ┌─────────┐
│ Robot 1 │       │ Robot 2 │       │ Robot 3 │
│ Surge   │       │ Explore │       │ Verify  │
└─────────┘       └─────────┘       └─────────┘
```

### 1.2 通信协议

**共享信息**:
- 当前位置和状态
- 气体浓度测量
- 估计的源位置
- 探索覆盖区域

**消息类型**:
```python
# RobotState.msg
uint8 robot_id
geometry_msgs/Pose2D position
string mode  # PATROL, SURGE, CAST, VERIFY
float32 concentration

# SourceEstimate.msg
uint8 robot_id
geometry_msgs/Pose2D estimated_position
float32 confidence
float32[] covariance  # [var_x, var_y, cov_xy]

# CoverageUpdate.msg
uint8 robot_id
geometry_msgs/Pose2D[] covered_positions
float32[] concentrations
```

## 2. 协作策略

### 2.1 角色分配

| 角色 | 任务 | 优先级 |
|------|------|--------|
| Tracker | 执行 Surge-Cast 追踪 | 高 |
| Explorer | 探索未覆盖区域 | 中 |
| Verifier | 验证估计的源位置 | 高 |

### 2.2 信息融合

**分布式粒子滤波**:
- 每个机器人维护本地粒子集
- 周期性交换高权重粒子
- 全局估计 = 加权平均

**覆盖地图融合**:
- 合并各机器人的探索区域
- 避免重复探索
- 最大化信息增益

### 2.3 冲突解决

- 多机器人同时追踪同一源 → 优先级高的继续，其他切换角色
- 路径冲突 → 重新规划或等待
- 估计冲突 → 加权融合或启动验证

## 3. 算法设计

### 3.1 分布式源定位

```python
class MultiRobotTracker:
    def __init__(self, robot_id: int, num_robots: int):
        self.robot_id = robot_id
        self.local_particles = []
        self.shared_particles = {}  # robot_id -> particles
        self.role = Role.EXPLORER
        
    def update(self, observation):
        # 1. 本地更新
        self.local_update(observation)
        
        # 2. 广播状态
        self.broadcast_state()
        
        # 3. 接收其他机器人信息
        self.receive_updates()
        
        # 4. 角色调整
        self.adjust_role()
        
        # 5. 全局估计
        return self.global_estimate()
    
    def global_estimate(self):
        # 融合所有机器人的估计
        estimates = []
        for rid, particles in self.shared_particles.items():
            est = self.estimate_from_particles(particles)
            estimates.append(est)
        
        # 加权融合
        return self.weighted_fusion(estimates)
```

### 3.2 覆盖控制

```python
class CoverageController:
    def __init__(self):
        self.covered_map = CoverageMap()
        self.frontier = []
        
    def select_exploration_target(self, current_pose):
        # 找到信息增益最大的未探索区域
        candidates = self.frontier
        scores = []
        for pos in candidates:
            # 信息增益 = 未探索程度 - 到其他机器人距离
            gain = self.information_gain(pos)
            cost = self.travel_cost(current_pose, pos)
            scores.append(gain - cost)
        
        return candidates[argmax(scores)]
```

## 4. ROS2 节点设计

### 4.1 节点结构

```
multi_robot_coordinator_node
├── 订阅:
│   ├── /robot_{id}/state (RobotState)
│   ├── /robot_{id}/source_estimate (SourceEstimate)
│   └── /robot_{id}/coverage (CoverageUpdate)
├── 发布:
│   ├── /coordinator/role_assignment (RoleAssignment)
│   └── /coordinator/global_estimate (SourceEstimate)
└── 服务:
    └── /coordinator/request_role (RequestRole)
```

### 4.2 Launch 配置

```python
# multi_robot.launch.py
def generate_launch_description():
    return LaunchDescription([
        # 启动 N 个机器人
        *[Node(
            package='h2track_tracking',
            executable='mission_manager_node',
            namespace=f'robot_{i}',
            parameters=[{'robot_id': i}]
        ) for i in range(num_robots)],
        
        # 启动协调器
        Node(
            package='h2track_tracking',
            executable='multi_robot_coordinator',
            parameters=[{'num_robots': num_robots}]
        ),
    ])
```

## 5. 性能指标

### 5.1 协作效率

- 源定位时间 vs 单机器人
- 覆盖率 vs 时间
- 通信开销

### 5.2 鲁棒性

- 单机器人故障恢复
- 通信延迟容忍度
- 估计一致性

## 6. 实现计划

### Phase 1: 基础框架 (1周)
- [ ] 消息类型定义
- [ ] 协调器节点骨架
- [ ] 多机器人 launch 文件

### Phase 2: 信息共享 (1周)
- [ ] 状态广播
- [ ] 粒子交换
- [ ] 覆盖地图融合

### Phase 3: 角色分配 (1周)
- [ ] 角色分配策略
- [ ] 冲突解决
- [ ] 动态角色切换

### Phase 4: 测试验证 (1周)
- [ ] 仿真测试
- [ ] 性能对比
- [ ] 鲁棒性测试
