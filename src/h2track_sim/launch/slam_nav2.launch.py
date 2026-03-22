#!/usr/bin/env python3

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _load_scene_loader():
    loader_path = Path(__file__).with_name('scene_loader.py')
    spec = spec_from_file_location('h2track_scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCENE_LOADER = _load_scene_loader()
resolve_scene_slam_nav2_params = SCENE_LOADER.resolve_scene_slam_nav2_params
resolve_scene_map = SCENE_LOADER.resolve_scene_map


def _scene_defaults(context):
    pkg_share = get_package_share_directory('h2track_sim')
    scene = LaunchConfiguration('scene')
    params_file = LaunchConfiguration('params_file')
    map_yaml = LaunchConfiguration('map')

    scene_name = scene.perform(context)
    resolved_params = params_file.perform(context).strip() or resolve_scene_slam_nav2_params(pkg_share, scene_name)
    resolved_map = map_yaml.perform(context).strip() or resolve_scene_map(pkg_share, scene_name)
    return [
        SetLaunchConfiguration('params_file', resolved_params),
        SetLaunchConfiguration('map', resolved_map),
    ]


def generate_launch_description():
    nav2_share = get_package_share_directory('nav2_bringup')
    slam_toolbox_share = get_package_share_directory('slam_toolbox')

    scene = LaunchConfiguration('scene')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    map_yaml = LaunchConfiguration('map')
    autostart = LaunchConfiguration('autostart')
    map_saver_autostart = LaunchConfiguration('map_saver_autostart')

    declare_scene = DeclareLaunchArgument('scene', default_value='baseline')
    declare_use_sim_time = DeclareLaunchArgument('use_sim_time', default_value='true')
    declare_params_file = DeclareLaunchArgument('params_file', default_value='')
    declare_map = DeclareLaunchArgument('map', default_value='')
    declare_autostart = DeclareLaunchArgument('autostart', default_value='true')
    declare_map_saver_autostart = DeclareLaunchArgument('map_saver_autostart', default_value='true')

    slam_defaults = OpaqueFunction(function=_scene_defaults)

    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(slam_toolbox_share, 'launch', 'online_async_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'slam_params_file': params_file,
        }.items(),
    )

    map_saver_server = Node(
        package='nav2_map_server',
        executable='map_saver_server',
        name='map_saver_server',
        output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )

    lifecycle_manager_slam = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_slam',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': map_saver_autostart},
            {'node_names': ['map_saver_server']},
        ],
    )

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': params_file,
            'autostart': autostart,
            'use_composition': 'False',
            'use_respawn': 'False',
        }.items(),
    )

    return LaunchDescription(
        [
            declare_scene,
            declare_use_sim_time,
            declare_params_file,
            declare_map,
            declare_autostart,
            declare_map_saver_autostart,
            slam_defaults,
            slam_toolbox,
            map_saver_server,
            lifecycle_manager_slam,
            navigation,
        ]
    )
