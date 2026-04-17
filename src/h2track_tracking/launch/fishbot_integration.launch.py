"""Launch file for H2Track + Fishbot integration.

Starts:
1. Fishbot navigation stack (Nav2)
2. H2Track gas source localization
3. Gas sensor node
4. RViz visualization

Usage:
    ros2 launch h2track_tracking fishbot_integration.launch.py
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    # Launch arguments
    declared_arguments = [
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description="Use simulation time",
        ),
        DeclareLaunchArgument(
            "use_rviz",
            default_value="true",
            description="Launch RViz",
        ),
        DeclareLaunchArgument(
            "gas_type",
            default_value="H2",
            description="Gas type (H2, CH4, CO, C3H8)",
        ),
        DeclareLaunchArgument(
            "simulation_mode",
            default_value="true",
            description="Use simulation mode for gas sensor",
        ),
    ]
    
    # Fishbot Nav2 launch (optional - can be launched separately)
    # fishbot_nav2 = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource([
    #         PathJoinSubstitution([
    #             FindPackageShare("fishbot_navigation2"),
    #             "launch",
    #             "navigation.launch.py",
    #         ])
    #     ]),
    # )
    
    # Gas sensor node
    gas_sensor_node = Node(
        package="h2track_tracking",
        executable="gas_sensor_node",
        name="gas_sensor_node",
        parameters=[{
            "gas_type": LaunchConfiguration("gas_type"),
            "simulation_mode": LaunchConfiguration("simulation_mode"),
            "publish_rate": 10.0,
        }],
        output="screen",
    )
    
    # Mission manager node
    mission_manager_node = Node(
        package="h2track_tracking",
        executable="mission_manager_node",
        name="mission_manager_node",
        parameters=[{
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }],
        output="screen",
    )
    
    # RViz
    rviz_config_path = PathJoinSubstitution([
        FindPackageShare("h2track_tracking"),
        "rviz",
        "gas_tracking.rviz",
    ])
    
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", rviz_config_path],
        condition=IfCondition(LaunchConfiguration("use_rviz")),
        parameters=[{
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }],
    )
    
    return LaunchDescription(
        declared_arguments
        + [
            LogInfo(msg="Starting H2Track + Fishbot integration..."),
            gas_sensor_node,
            mission_manager_node,
            rviz_node,
        ]
    )
