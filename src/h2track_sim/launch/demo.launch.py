#!/usr/bin/env python3

import json
import os
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
resolve_scene_model_path = SCENE_LOADER.resolve_scene_model_path
resolve_scene_world = SCENE_LOADER.resolve_scene_world


def _load_yaml(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def _flatten_patrol_points(points: list[list[float]]) -> list[float]:
    flattened: list[float] = []
    for x, y in points:
        flattened.extend([float(x), float(y)])
    return flattened


def _scene_actions(context, *, pkg_share: str, bringup_path: str, default_use_gaden: str):
    scene = LaunchConfiguration('scene')
    use_gaden = LaunchConfiguration('use_gaden')
    scene_name = scene.perform(context)
    requested_use_gaden = use_gaden.perform(context).strip()
    scene_profile = load_scene_profile(pkg_share, scene_name)
    resolved_use_gaden = requested_use_gaden if requested_use_gaden else str(scene_profile.get('use_gaden', default_use_gaden)).lower()
    mission = scene_profile['mission_manager']
    source = scene_profile['gas_source']
    initial_pose = mission['initial_pose']

    return [
        SetLaunchConfiguration('use_gaden', resolved_use_gaden),
        SetLaunchConfiguration('initial_pose_x', str(initial_pose['x'])),
        SetLaunchConfiguration('initial_pose_y', str(initial_pose['y'])),
        SetLaunchConfiguration('initial_pose_yaw', str(initial_pose['yaw'])),
        SetLaunchConfiguration('patrol_points', json.dumps(_flatten_patrol_points(mission['patrol_points']))),
        SetLaunchConfiguration('enter_threshold', str(mission['enter_threshold'])),
        SetLaunchConfiguration('exit_threshold', str(mission['exit_threshold'])),
        SetLaunchConfiguration('source_threshold', str(mission['source_threshold'])),
        SetLaunchConfiguration('confirm_samples', str(mission['confirm_samples'])),
        SetLaunchConfiguration('source_radius', str(mission['source_radius'])),
        SetLaunchConfiguration('source_hold_steps', str(mission['source_hold_steps'])),
        SetLaunchConfiguration('track_step', str(mission['track_step'])),
        SetLaunchConfiguration('sweep_angle_deg', str(mission['sweep_angle_deg'])),
        SetLaunchConfiguration('source_x', str(source['x'])),
        SetLaunchConfiguration('source_y', str(source['y'])),
        SetLaunchConfiguration('world', resolve_scene_world(pkg_share, scene_name)),
        SetLaunchConfiguration('gazebo_model_path', resolve_scene_model_path(pkg_share, scene_name)),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_path),
            launch_arguments={
                'scene': scene,
                'world': LaunchConfiguration('world'),
                'gazebo_model_path': LaunchConfiguration('gazebo_model_path'),
                'use_rviz': LaunchConfiguration('use_rviz'),
                'headless': LaunchConfiguration('headless'),
                'use_gaden': LaunchConfiguration('use_gaden'),
                'nav2_params_file': LaunchConfiguration('nav2_params_file'),
            }.items(),
        ),
    ]


def generate_launch_description():
    pkg_share = get_package_share_directory('h2track_sim')
    bringup_path = os.path.join(pkg_share, 'launch', 'bringup.launch.py')
    demo_config_path = Path(pkg_share) / 'config' / 'demo.yaml'
    demo_nav2_params_path = os.path.join(pkg_share, 'config', 'nav2_demo_params.yaml')
    demo = _load_yaml(demo_config_path)

    declare_scene = DeclareLaunchArgument('scene', default_value=demo.get('scene', 'baseline'))
    declare_use_rviz = DeclareLaunchArgument('use_rviz', default_value=str(demo.get('use_rviz', True)).lower())
    declare_headless = DeclareLaunchArgument('headless', default_value=str(demo.get('headless', False)).lower())
    default_use_gaden = str(demo.get('use_gaden', True)).lower()
    declare_use_gaden = DeclareLaunchArgument('use_gaden', default_value='')
    declare_nav2_params_file = DeclareLaunchArgument('nav2_params_file', default_value=demo_nav2_params_path)

    set_demo_values = [
        SetLaunchConfiguration('mission_manager_delay', str(demo.get('mission_manager_delay', 10.0))),
        SetLaunchConfiguration('gaden_sensor_gate_timeout', str(demo.get('gaden_sensor_gate_timeout', 30.0))),
        SetLaunchConfiguration('gaden_sensor_gate_poll_period', str(demo.get('gaden_sensor_gate_poll_period', 0.5))),
    ]

    configure_scene = OpaqueFunction(
        function=_scene_actions,
        kwargs={'pkg_share': pkg_share, 'bringup_path': bringup_path, 'default_use_gaden': default_use_gaden},
    )

    return LaunchDescription([
        declare_scene,
        declare_use_rviz,
        declare_headless,
        declare_use_gaden,
        declare_nav2_params_file,
        *set_demo_values,
        configure_scene,
    ])
