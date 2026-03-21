#!/usr/bin/env python3

import os
import shutil
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
import yaml


def _load_scene_loader():
    loader_path = Path(__file__).with_name('scene_loader.py')
    spec = spec_from_file_location('h2track_scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCENE_LOADER = _load_scene_loader()
load_scene_profile = SCENE_LOADER.load_scene_profile
resolve_scene_map = SCENE_LOADER.resolve_scene_map


def prepare_runtime_files(context, *args, **kwargs):
    pkg_share = get_package_share_directory('h2track_sim')
    runtime_dir = Path('/tmp/h2track_xian_runtime_map')
    runtime_dir.mkdir(parents=True, exist_ok=True)

    scene = LaunchConfiguration('scene')
    scene_name = scene.perform(context)
    scene_profile = load_scene_profile(pkg_share, scene_name)
    initial_pose = scene_profile['mission_manager']['initial_pose']

    map_yaml_config = LaunchConfiguration('map')
    source_map_yaml = map_yaml_config.perform(context).strip() or resolve_scene_map(pkg_share, scene_name)
    source_map_yaml_path = Path(source_map_yaml)
    map_config = yaml.safe_load(source_map_yaml_path.read_text(encoding='utf-8'))

    image_name = map_config['image']
    image_source = Path(image_name)
    if not image_source.is_absolute():
        image_source = source_map_yaml_path.parent / image_name

    runtime_map_path = runtime_dir / f'{scene_name}_map.yaml'
    runtime_image_path = runtime_dir / image_source.name
    shutil.copy2(image_source, runtime_image_path)
    map_config['image'] = runtime_image_path.name
    runtime_map_path.write_text(yaml.safe_dump(map_config, sort_keys=False), encoding='utf-8')

    params_file = LaunchConfiguration('params_file')
    source_params_path = Path(params_file.perform(context))
    params_config = yaml.safe_load(source_params_path.read_text(encoding='utf-8'))
    amcl_params = params_config.setdefault('amcl', {}).setdefault('ros__parameters', {})
    amcl_params['initial_pose.x'] = float(initial_pose['x'])
    amcl_params['initial_pose.y'] = float(initial_pose['y'])
    amcl_params['initial_pose.yaw'] = float(initial_pose['yaw'])
    runtime_params_path = runtime_dir / f'{scene_name}_nav2_params.yaml'
    runtime_params_path.write_text(yaml.safe_dump(params_config, sort_keys=False), encoding='utf-8')

    return [
        SetLaunchConfiguration('map', str(runtime_map_path)),
        SetLaunchConfiguration('params_file', str(runtime_params_path)),
    ]


def generate_launch_description():
    pkg_share = get_package_share_directory('h2track_sim')
    nav2_share = get_package_share_directory('nav2_bringup')
    default_params = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    use_sim_time = LaunchConfiguration('use_sim_time')
    map_yaml = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')

    declare_scene = DeclareLaunchArgument('scene', default_value='baseline')
    declare_use_sim_time = DeclareLaunchArgument('use_sim_time', default_value='true')
    declare_map = DeclareLaunchArgument('map', default_value='')
    declare_params = DeclareLaunchArgument('params_file', default_value=default_params)
    declare_autostart = DeclareLaunchArgument('autostart', default_value='true')

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'slam': 'False',
            'map': map_yaml,
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
            declare_map,
            declare_params,
            declare_autostart,
            OpaqueFunction(function=prepare_runtime_files),
            nav2_bringup,
        ]
    )
