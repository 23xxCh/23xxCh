# H2Track + Fishbot 集成方案

## 概述

将 H2Track 气体源定位系统与 Fishbot 二轮差速移动机器人集成，实现真实环境下的气源定位功能。

## 系统架构

### 分层设计

```
┌─────────────────────────────────┐
│    H2Track (决策/感知层)          │
│  - 气体浓度检测                   │
│  - 源定位算法 (Surge-Cast + PF)  │
│  - 全局路径规划                   │
├─────────────────────────────────┤
│   Fishbot Nav2 (导航执行层)       │
│  - 局部路径规划                   │
│  - 动态避障                       │
│  - 状态估计 (EKF)                 │
├─────────────────────────────────┤
│   Fishbot Hardware (硬件层)      │
│  - 底盘控制 (Micro-ROS)          │
│  - 激光雷达 (YDLidar X2)         │
│  - IMU + 里程计                  │
└─────────────────────────────────┘
```

## 通信接口

### 话题接口

| 话题 | 类型 | 方向 | 说明 |
|------|------|------|------|
| /cmd_vel | geometry_msgs/Twist | → Fishbot | 速度指令 |
| /odom | nav_msgs/Odometry | ← Fishbot | 里程计 |
| /scan | sensor_msgs/LaserScan | ← Fishbot | 激光扫描 |
| /imu | sensor_msgs/Imu | ← Fishbot | IMU数据 |
| /gas_concentration | std_msgs/Float32 | H2Track | 气体浓度 |
| /source_estimate | geometry_msgs/PoseStamped | H2Track | 源估计位置 |

### TF 树

```
map
 └── odom (Fishbot EKF)
      └── base_link
           ├── laser_frame
           ├── imu_frame
           └── gas_sensor_frame (新增)
```

## 硬件需求

### Fishbot 现有硬件
- 差速底盘
- YDLidar X2 激光雷达
- IMU 传感器
- 编码器里程计

### 需要新增
- **气体传感器** (如 MQ-8 氢气传感器)
  - 接口: I2C/UART
  - 安装位置: base_link 上方 0.3-1.5m (根据气体类型)
- **风速风向传感器**
  - 用于风向估计
  - 接口: I2C/模拟

## 集成步骤

### 阶段 1: 环境准备

```bash
# Source 所有工作空间
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source /home/user/fishbot/fishbot_ws/install/setup.bash
source /home/user/h2track-xian/install/setup.bash
```

### 阶段 2: 传感器集成

1. 添加气体传感器驱动节点
2. 发布 /gas_concentration 话题
3. 配置传感器坐标系

### 阶段 3: 导航集成

1. H2Track 发布目标点 → Nav2
2. Nav2 执行导航 → Fishbot
3. 传感器数据反馈 → H2Track

### 阶段 4: 测试验证

1. 仿真环境测试
2. 实车测试
3. 性能优化

## 配置文件

### fishbot_h2track.launch.py

```python
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    return LaunchDescription([
        # Fishbot 导航
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                '/home/user/fishbot/fishbot_ws/install/fishbot_navigation2/share/',
                'fishbot_navigation2/launch/navigation.launch.py'
            ])
        ),
        # H2Track 气体追踪
        # ...
    ])
```

## 注意事项

1. **环境变量**: 确保 ROS_DOMAIN_ID 一致
2. **时间同步**: 使用 /clock 或 NTP 同步
3. **安全限速**: 气体追踪时限制最大速度
4. **传感器标定**: 气体传感器需要标定
