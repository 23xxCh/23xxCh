#!/usr/bin/env python3

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
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
load_scene_profile = SCENE_LOADER.load_scene_profile
resolve_scene_model_path = SCENE_LOADER.resolve_scene_model_path
resolve_scene_world = SCENE_LOADER.resolve_scene_world


def _scene_defaults(context):
    pkg_share = get_package_share_directory('h2track_sim')
    scene = LaunchConfiguration('scene')
    world = LaunchConfiguration('world')
    gazebo_model_path = LaunchConfiguration('gazebo_model_path')
    use_gaden = LaunchConfiguration('use_gaden')
    initial_pose_x = LaunchConfiguration('initial_pose_x')
    initial_pose_y = LaunchConfiguration('initial_pose_y')
    initial_pose_yaw = LaunchConfiguration('initial_pose_yaw')
    source_x = LaunchConfiguration('source_x')
    source_y = LaunchConfiguration('source_y')
    tracking_source_x = LaunchConfiguration('tracking_source_x')
    tracking_source_y = LaunchConfiguration('tracking_source_y')
    tracking_enter_threshold = LaunchConfiguration('tracking_enter_threshold')
    tracking_exit_threshold = LaunchConfiguration('tracking_exit_threshold')
    tracking_source_threshold = LaunchConfiguration('tracking_source_threshold')
    tracking_confirm_samples = LaunchConfiguration('tracking_confirm_samples')
    tracking_track_exit_samples = LaunchConfiguration('tracking_track_exit_samples')
    tracking_source_radius = LaunchConfiguration('tracking_source_radius')
    tracking_source_hold_steps = LaunchConfiguration('tracking_source_hold_steps')
    tracking_track_step = LaunchConfiguration('tracking_track_step')
    tracking_source_seed_max_distance = LaunchConfiguration('tracking_source_seed_max_distance')
    gas_source_strength = LaunchConfiguration('gas_source_strength')
    gas_decay_rate = LaunchConfiguration('gas_decay_rate')
    gas_plume_stddev = LaunchConfiguration('gas_plume_stddev')
    gas_wind_x = LaunchConfiguration('gas_wind_x')
    gas_wind_y = LaunchConfiguration('gas_wind_y')
    gas_noise_stddev = LaunchConfiguration('gas_noise_stddev')
    gas_publish_rate_hz = LaunchConfiguration('gas_publish_rate_hz')
    gaden_project_path = LaunchConfiguration('gaden_project_path')
    gaden_playback_id = LaunchConfiguration('gaden_playback_id')
    gaden_player_freq = LaunchConfiguration('gaden_player_freq')
    gaden_sensor_topic = LaunchConfiguration('gaden_sensor_topic')
    gaden_sensor_frame = LaunchConfiguration('gaden_sensor_frame')
    gaden_fixed_frame = LaunchConfiguration('gaden_fixed_frame')
    gaden_map_offset_x = LaunchConfiguration('gaden_map_offset_x')
    gaden_map_offset_y = LaunchConfiguration('gaden_map_offset_y')
    gaden_map_offset_z = LaunchConfiguration('gaden_map_offset_z')
    gaden_map_roll = LaunchConfiguration('gaden_map_roll')
    gaden_map_pitch = LaunchConfiguration('gaden_map_pitch')
    gaden_map_yaw = LaunchConfiguration('gaden_map_yaw')
    frontier_min_cluster_size = LaunchConfiguration('frontier_min_cluster_size')
    min_goal_distance = LaunchConfiguration('min_goal_distance')
    no_frontier_relaxed_after_cycles = LaunchConfiguration('no_frontier_relaxed_after_cycles')
    no_frontier_relaxed_cluster_size = LaunchConfiguration('no_frontier_relaxed_cluster_size')
    no_frontier_relaxed_min_goal_distance = LaunchConfiguration('no_frontier_relaxed_min_goal_distance')
    control_period_sec = LaunchConfiguration('control_period_sec')
    min_goal_x = LaunchConfiguration('min_goal_x')
    max_goal_x = LaunchConfiguration('max_goal_x')
    min_goal_y = LaunchConfiguration('min_goal_y')
    max_goal_y = LaunchConfiguration('max_goal_y')
    stuck_timeout_sec = LaunchConfiguration('stuck_timeout_sec')
    stuck_movement_epsilon = LaunchConfiguration('stuck_movement_epsilon')
    stuck_goal_tolerance = LaunchConfiguration('stuck_goal_tolerance')
    blocked_goal_ttl_sec = LaunchConfiguration('blocked_goal_ttl_sec')
    blocked_goal_radius = LaunchConfiguration('blocked_goal_radius')
    nav2_startup_gate_timeout = LaunchConfiguration('nav2_startup_gate_timeout')
    gaden_sensor_gate_timeout = LaunchConfiguration('gaden_sensor_gate_timeout')
    enter_threshold = LaunchConfiguration('enter_threshold')
    exit_threshold = LaunchConfiguration('exit_threshold')
    confirm_samples = LaunchConfiguration('confirm_samples')
    min_explore_samples = LaunchConfiguration('min_explore_samples')

    scene_name = scene.perform(context)
    scene_profile = load_scene_profile(pkg_share, scene_name)
    gas_field = scene_profile.get('gas_field', {})
    gaden = scene_profile.get('gaden')
    autonomy = scene_profile.get('autonomy')
    mission = scene_profile['mission_manager']
    gas_source = scene_profile.get('gas_source', {})

    if not autonomy:
        raise RuntimeError(f"Scene '{scene_name}' is missing an autonomy configuration block")

    resolved_world = world.perform(context).strip() or resolve_scene_world(pkg_share, scene_name)
    resolved_model_path = gazebo_model_path.perform(context).strip() or resolve_scene_model_path(pkg_share, scene_name)
    resolved_use_gaden = use_gaden.perform(context).strip().lower() or str(scene_profile.get('use_gaden', False)).lower()
    resolved_source_x = source_x.perform(context).strip() or str(gas_source.get('x', -4.0))
    resolved_source_y = source_y.perform(context).strip() or str(gas_source.get('y', 1.95))
    resolved_gas_source_strength = gas_source_strength.perform(context).strip() or str(gas_field.get('source_strength', 120.0))
    resolved_gas_decay_rate = gas_decay_rate.perform(context).strip() or str(gas_field.get('decay_rate', 0.55))
    resolved_gas_plume_stddev = gas_plume_stddev.perform(context).strip() or str(gas_field.get('plume_stddev', 1.2))
    resolved_gas_wind_x = gas_wind_x.perform(context).strip() or str(gas_field.get('wind_x', 0.4))
    resolved_gas_wind_y = gas_wind_y.perform(context).strip() or str(gas_field.get('wind_y', 0.0))
    resolved_gas_noise_stddev = gas_noise_stddev.perform(context).strip() or str(gas_field.get('noise_stddev', 0.05))
    resolved_gas_publish_rate_hz = gas_publish_rate_hz.perform(context).strip() or str(gas_field.get('publish_rate_hz', 5.0))

    if resolved_use_gaden in ('1', 'true', 'yes', 'on'):
        if not gaden:
            raise RuntimeError(f"Scene '{scene_name}' is missing a gaden configuration block")
        scene_gaden_project_path = str(gaden.get('project_path', '')).strip()
        if not scene_gaden_project_path:
            raise RuntimeError(f"Scene '{scene_name}' GADEN config is missing project_path")
        resolved_gaden_project_path = gaden_project_path.perform(context).strip() or scene_gaden_project_path
        resolved_gaden_playback_id = gaden_playback_id.perform(context).strip() or str(gaden.get('playback_id', 'scene1'))
        resolved_gaden_player_freq = gaden_player_freq.perform(context).strip() or str(gaden.get('player_freq', 1.0))
        resolved_gaden_sensor_topic = gaden_sensor_topic.perform(context).strip() or str(gaden.get('sensor_topic', '/gaden/sensor_reading'))
        resolved_gaden_sensor_frame = gaden_sensor_frame.perform(context).strip() or str(gaden.get('sensor_frame', 'base_link'))
        resolved_gaden_fixed_frame = gaden_fixed_frame.perform(context).strip() or str(gaden.get('fixed_frame', 'gaden_map'))
        resolved_gaden_map_offset_x = gaden_map_offset_x.perform(context).strip() or str(gaden.get('map_offset_x', 0.0))
        resolved_gaden_map_offset_y = gaden_map_offset_y.perform(context).strip() or str(gaden.get('map_offset_y', 0.0))
        resolved_gaden_map_offset_z = gaden_map_offset_z.perform(context).strip() or str(gaden.get('map_offset_z', 0.0))
        resolved_gaden_map_roll = gaden_map_roll.perform(context).strip() or str(gaden.get('map_roll', 0.0))
        resolved_gaden_map_pitch = gaden_map_pitch.perform(context).strip() or str(gaden.get('map_pitch', 0.0))
        resolved_gaden_map_yaw = gaden_map_yaw.perform(context).strip() or str(gaden.get('map_yaw', 0.0))
    else:
        resolved_gaden_project_path = ''
        resolved_gaden_playback_id = ''
        resolved_gaden_player_freq = ''
        resolved_gaden_sensor_topic = ''
        resolved_gaden_sensor_frame = ''
        resolved_gaden_fixed_frame = ''
        resolved_gaden_map_offset_x = ''
        resolved_gaden_map_offset_y = ''
        resolved_gaden_map_offset_z = ''
        resolved_gaden_map_roll = ''
        resolved_gaden_map_pitch = ''
        resolved_gaden_map_yaw = ''

    explore = autonomy.get('exploration', {})
    startup_gates = autonomy.get('startup_gates', {})
    mapping_detection = autonomy.get('mapping_detection', {})
    tracking_handoff = autonomy.get('tracking_handoff', {})
    default_enter_threshold = mapping_detection.get('enter_threshold', mission['enter_threshold'])
    default_exit_threshold = mapping_detection.get('exit_threshold', mission['exit_threshold'])
    default_confirm_samples = mapping_detection.get('confirm_samples', mission['confirm_samples'])
    default_min_explore_samples = mapping_detection.get('min_explore_samples', 0)
    default_stuck_timeout_sec = explore.get('stuck_timeout_sec', 15.0)
    default_stuck_movement_epsilon = explore.get('stuck_movement_epsilon', 0.08)
    default_stuck_goal_tolerance = explore.get('stuck_goal_tolerance', 0.45)
    default_blocked_goal_ttl_sec = explore.get('blocked_goal_ttl_sec', 60.0)
    default_blocked_goal_radius = explore.get('blocked_goal_radius', 0.9)
    default_tracking_source_x = tracking_handoff.get('source_x', gas_source.get('x', -4.0))
    default_tracking_source_y = tracking_handoff.get('source_y', gas_source.get('y', 1.95))
    default_tracking_enter = tracking_handoff.get('enter_threshold', mission['enter_threshold'])
    default_tracking_exit = tracking_handoff.get('exit_threshold', mission['exit_threshold'])
    default_tracking_source = tracking_handoff.get('source_threshold', mission['source_threshold'])
    default_tracking_confirm = tracking_handoff.get('confirm_samples', mission['confirm_samples'])
    default_tracking_track_exit = tracking_handoff.get(
        'track_exit_samples',
        mission.get('track_exit_samples', mission['confirm_samples']),
    )
    default_tracking_radius = tracking_handoff.get('source_radius', mission['source_radius'])
    default_tracking_hold_steps = tracking_handoff.get('source_hold_steps', mission['source_hold_steps'])
    default_tracking_track_step = tracking_handoff.get('track_step', mission['track_step'])
    default_tracking_seed_max_distance = tracking_handoff.get('source_seed_max_distance', 2.0)
    default_nav2_startup_gate_timeout = startup_gates.get('nav2_startup_gate_timeout', 60.0)
    default_gaden_sensor_gate_timeout = startup_gates.get('gaden_sensor_gate_timeout', 60.0)
    return [
        SetLaunchConfiguration('world', resolved_world),
        SetLaunchConfiguration('gazebo_model_path', resolved_model_path),
        SetLaunchConfiguration('use_gaden', resolved_use_gaden),
        SetLaunchConfiguration('initial_pose_x', str(mission['initial_pose']['x'])),
        SetLaunchConfiguration('initial_pose_y', str(mission['initial_pose']['y'])),
        SetLaunchConfiguration('initial_pose_yaw', str(mission['initial_pose']['yaw'])),
        SetLaunchConfiguration('source_x', resolved_source_x),
        SetLaunchConfiguration('source_y', resolved_source_y),
        SetLaunchConfiguration(
            'tracking_source_x',
            tracking_source_x.perform(context).strip() or str(default_tracking_source_x),
        ),
        SetLaunchConfiguration(
            'tracking_source_y',
            tracking_source_y.perform(context).strip() or str(default_tracking_source_y),
        ),
        SetLaunchConfiguration(
            'tracking_enter_threshold',
            tracking_enter_threshold.perform(context).strip() or str(default_tracking_enter),
        ),
        SetLaunchConfiguration(
            'tracking_exit_threshold',
            tracking_exit_threshold.perform(context).strip() or str(default_tracking_exit),
        ),
        SetLaunchConfiguration(
            'tracking_source_threshold',
            tracking_source_threshold.perform(context).strip() or str(default_tracking_source),
        ),
        SetLaunchConfiguration(
            'tracking_confirm_samples',
            tracking_confirm_samples.perform(context).strip() or str(default_tracking_confirm),
        ),
        SetLaunchConfiguration(
            'tracking_track_exit_samples',
            tracking_track_exit_samples.perform(context).strip() or str(default_tracking_track_exit),
        ),
        SetLaunchConfiguration(
            'tracking_source_radius',
            tracking_source_radius.perform(context).strip() or str(default_tracking_radius),
        ),
        SetLaunchConfiguration(
            'tracking_source_hold_steps',
            tracking_source_hold_steps.perform(context).strip() or str(default_tracking_hold_steps),
        ),
        SetLaunchConfiguration(
            'tracking_track_step',
            tracking_track_step.perform(context).strip() or str(default_tracking_track_step),
        ),
        SetLaunchConfiguration(
            'tracking_source_seed_max_distance',
            tracking_source_seed_max_distance.perform(context).strip() or str(default_tracking_seed_max_distance),
        ),
        SetLaunchConfiguration('gas_source_strength', resolved_gas_source_strength),
        SetLaunchConfiguration('gas_decay_rate', resolved_gas_decay_rate),
        SetLaunchConfiguration('gas_plume_stddev', resolved_gas_plume_stddev),
        SetLaunchConfiguration('gas_wind_x', resolved_gas_wind_x),
        SetLaunchConfiguration('gas_wind_y', resolved_gas_wind_y),
        SetLaunchConfiguration('gas_noise_stddev', resolved_gas_noise_stddev),
        SetLaunchConfiguration('gas_publish_rate_hz', resolved_gas_publish_rate_hz),
        SetLaunchConfiguration('gaden_project_path', resolved_gaden_project_path),
        SetLaunchConfiguration('gaden_playback_id', resolved_gaden_playback_id),
        SetLaunchConfiguration('gaden_player_freq', resolved_gaden_player_freq),
        SetLaunchConfiguration('gaden_sensor_topic', resolved_gaden_sensor_topic),
        SetLaunchConfiguration('gaden_sensor_frame', resolved_gaden_sensor_frame),
        SetLaunchConfiguration('gaden_fixed_frame', resolved_gaden_fixed_frame),
        SetLaunchConfiguration('gaden_map_offset_x', resolved_gaden_map_offset_x),
        SetLaunchConfiguration('gaden_map_offset_y', resolved_gaden_map_offset_y),
        SetLaunchConfiguration('gaden_map_offset_z', resolved_gaden_map_offset_z),
        SetLaunchConfiguration('gaden_map_roll', resolved_gaden_map_roll),
        SetLaunchConfiguration('gaden_map_pitch', resolved_gaden_map_pitch),
        SetLaunchConfiguration('gaden_map_yaw', resolved_gaden_map_yaw),
        SetLaunchConfiguration('frontier_min_cluster_size', str(explore.get('frontier_min_cluster_size', 6))),
        SetLaunchConfiguration('min_goal_distance', str(explore.get('min_goal_distance', 0.8))),
        SetLaunchConfiguration(
            'no_frontier_relaxed_after_cycles',
            str(explore.get('no_frontier_relaxed_after_cycles', 8)),
        ),
        SetLaunchConfiguration(
            'no_frontier_relaxed_cluster_size',
            str(explore.get('no_frontier_relaxed_cluster_size', 1)),
        ),
        SetLaunchConfiguration(
            'no_frontier_relaxed_min_goal_distance',
            str(explore.get('no_frontier_relaxed_min_goal_distance', 0.35)),
        ),
        SetLaunchConfiguration('control_period_sec', str(explore.get('control_period_sec', 1.0))),
        SetLaunchConfiguration('min_goal_x', str(explore.get('min_goal_x', -1.0e9))),
        SetLaunchConfiguration('max_goal_x', str(explore.get('max_goal_x', 1.0e9))),
        SetLaunchConfiguration('min_goal_y', str(explore.get('min_goal_y', -1.0e9))),
        SetLaunchConfiguration('max_goal_y', str(explore.get('max_goal_y', 1.0e9))),
        SetLaunchConfiguration(
            'stuck_timeout_sec',
            stuck_timeout_sec.perform(context).strip() or str(default_stuck_timeout_sec),
        ),
        SetLaunchConfiguration(
            'stuck_movement_epsilon',
            stuck_movement_epsilon.perform(context).strip() or str(default_stuck_movement_epsilon),
        ),
        SetLaunchConfiguration(
            'stuck_goal_tolerance',
            stuck_goal_tolerance.perform(context).strip() or str(default_stuck_goal_tolerance),
        ),
        SetLaunchConfiguration(
            'blocked_goal_ttl_sec',
            blocked_goal_ttl_sec.perform(context).strip() or str(default_blocked_goal_ttl_sec),
        ),
        SetLaunchConfiguration(
            'blocked_goal_radius',
            blocked_goal_radius.perform(context).strip() or str(default_blocked_goal_radius),
        ),
        SetLaunchConfiguration(
            'nav2_startup_gate_timeout',
            nav2_startup_gate_timeout.perform(context).strip() or str(default_nav2_startup_gate_timeout),
        ),
        SetLaunchConfiguration(
            'gaden_sensor_gate_timeout',
            gaden_sensor_gate_timeout.perform(context).strip() or str(default_gaden_sensor_gate_timeout),
        ),
        SetLaunchConfiguration('enter_threshold', enter_threshold.perform(context).strip() or str(default_enter_threshold)),
        SetLaunchConfiguration('exit_threshold', exit_threshold.perform(context).strip() or str(default_exit_threshold)),
        SetLaunchConfiguration('confirm_samples', confirm_samples.perform(context).strip() or str(default_confirm_samples)),
        SetLaunchConfiguration(
            'min_explore_samples',
            min_explore_samples.perform(context).strip() or str(default_min_explore_samples),
        ),
    ]


def generate_launch_description():
    pkg_share = get_package_share_directory('h2track_sim')

    scene = LaunchConfiguration('scene')
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')
    headless = LaunchConfiguration('headless')
    world = LaunchConfiguration('world')
    gazebo_model_path = LaunchConfiguration('gazebo_model_path')
    initial_pose_x = LaunchConfiguration('initial_pose_x')
    initial_pose_y = LaunchConfiguration('initial_pose_y')
    initial_pose_yaw = LaunchConfiguration('initial_pose_yaw')
    source_x = LaunchConfiguration('source_x')
    source_y = LaunchConfiguration('source_y')
    tracking_source_x = LaunchConfiguration('tracking_source_x')
    tracking_source_y = LaunchConfiguration('tracking_source_y')
    tracking_enter_threshold = LaunchConfiguration('tracking_enter_threshold')
    tracking_exit_threshold = LaunchConfiguration('tracking_exit_threshold')
    tracking_source_threshold = LaunchConfiguration('tracking_source_threshold')
    tracking_confirm_samples = LaunchConfiguration('tracking_confirm_samples')
    tracking_track_exit_samples = LaunchConfiguration('tracking_track_exit_samples')
    tracking_source_radius = LaunchConfiguration('tracking_source_radius')
    tracking_source_hold_steps = LaunchConfiguration('tracking_source_hold_steps')
    tracking_track_step = LaunchConfiguration('tracking_track_step')
    tracking_source_seed_max_distance = LaunchConfiguration('tracking_source_seed_max_distance')
    use_gaden = LaunchConfiguration('use_gaden')
    frontier_min_cluster_size = LaunchConfiguration('frontier_min_cluster_size')
    min_goal_distance = LaunchConfiguration('min_goal_distance')
    no_frontier_relaxed_after_cycles = LaunchConfiguration('no_frontier_relaxed_after_cycles')
    no_frontier_relaxed_cluster_size = LaunchConfiguration('no_frontier_relaxed_cluster_size')
    no_frontier_relaxed_min_goal_distance = LaunchConfiguration('no_frontier_relaxed_min_goal_distance')
    control_period_sec = LaunchConfiguration('control_period_sec')
    min_goal_x = LaunchConfiguration('min_goal_x')
    max_goal_x = LaunchConfiguration('max_goal_x')
    min_goal_y = LaunchConfiguration('min_goal_y')
    max_goal_y = LaunchConfiguration('max_goal_y')
    stuck_timeout_sec = LaunchConfiguration('stuck_timeout_sec')
    stuck_movement_epsilon = LaunchConfiguration('stuck_movement_epsilon')
    stuck_goal_tolerance = LaunchConfiguration('stuck_goal_tolerance')
    blocked_goal_ttl_sec = LaunchConfiguration('blocked_goal_ttl_sec')
    blocked_goal_radius = LaunchConfiguration('blocked_goal_radius')
    nav2_startup_gate_timeout = LaunchConfiguration('nav2_startup_gate_timeout')
    gaden_sensor_gate_timeout = LaunchConfiguration('gaden_sensor_gate_timeout')
    enter_threshold = LaunchConfiguration('enter_threshold')
    exit_threshold = LaunchConfiguration('exit_threshold')
    confirm_samples = LaunchConfiguration('confirm_samples')
    min_explore_samples = LaunchConfiguration('min_explore_samples')
    gas_source_strength = LaunchConfiguration('gas_source_strength')
    gas_decay_rate = LaunchConfiguration('gas_decay_rate')
    gas_plume_stddev = LaunchConfiguration('gas_plume_stddev')
    gas_wind_x = LaunchConfiguration('gas_wind_x')
    gas_wind_y = LaunchConfiguration('gas_wind_y')
    gas_noise_stddev = LaunchConfiguration('gas_noise_stddev')
    gas_publish_rate_hz = LaunchConfiguration('gas_publish_rate_hz')
    gaden_project_path = LaunchConfiguration('gaden_project_path')
    gaden_playback_id = LaunchConfiguration('gaden_playback_id')
    gaden_player_freq = LaunchConfiguration('gaden_player_freq')
    gaden_sensor_topic = LaunchConfiguration('gaden_sensor_topic')
    gaden_sensor_frame = LaunchConfiguration('gaden_sensor_frame')
    gaden_fixed_frame = LaunchConfiguration('gaden_fixed_frame')
    gaden_map_offset_x = LaunchConfiguration('gaden_map_offset_x')
    gaden_map_offset_y = LaunchConfiguration('gaden_map_offset_y')
    gaden_map_offset_z = LaunchConfiguration('gaden_map_offset_z')
    gaden_map_roll = LaunchConfiguration('gaden_map_roll')
    gaden_map_pitch = LaunchConfiguration('gaden_map_pitch')
    gaden_map_yaw = LaunchConfiguration('gaden_map_yaw')

    declare_scene = DeclareLaunchArgument('scene', default_value='baseline')
    declare_use_sim_time = DeclareLaunchArgument('use_sim_time', default_value='true')
    declare_use_rviz = DeclareLaunchArgument('use_rviz', default_value='false')
    declare_headless = DeclareLaunchArgument('headless', default_value='false')
    declare_world = DeclareLaunchArgument('world', default_value='')
    declare_gazebo_model_path = DeclareLaunchArgument('gazebo_model_path', default_value='')
    declare_initial_pose_x = DeclareLaunchArgument('initial_pose_x', default_value='0.0')
    declare_initial_pose_y = DeclareLaunchArgument('initial_pose_y', default_value='0.0')
    declare_initial_pose_yaw = DeclareLaunchArgument('initial_pose_yaw', default_value='0.0')
    declare_source_x = DeclareLaunchArgument('source_x', default_value='')
    declare_source_y = DeclareLaunchArgument('source_y', default_value='')
    declare_tracking_source_x = DeclareLaunchArgument('tracking_source_x', default_value='')
    declare_tracking_source_y = DeclareLaunchArgument('tracking_source_y', default_value='')
    declare_tracking_enter_threshold = DeclareLaunchArgument('tracking_enter_threshold', default_value='')
    declare_tracking_exit_threshold = DeclareLaunchArgument('tracking_exit_threshold', default_value='')
    declare_tracking_source_threshold = DeclareLaunchArgument('tracking_source_threshold', default_value='')
    declare_tracking_confirm_samples = DeclareLaunchArgument('tracking_confirm_samples', default_value='')
    declare_tracking_track_exit_samples = DeclareLaunchArgument('tracking_track_exit_samples', default_value='')
    declare_tracking_source_radius = DeclareLaunchArgument('tracking_source_radius', default_value='')
    declare_tracking_source_hold_steps = DeclareLaunchArgument('tracking_source_hold_steps', default_value='')
    declare_tracking_track_step = DeclareLaunchArgument('tracking_track_step', default_value='')
    declare_tracking_source_seed_max_distance = DeclareLaunchArgument(
        'tracking_source_seed_max_distance',
        default_value='',
    )
    declare_use_gaden = DeclareLaunchArgument('use_gaden', default_value='')
    declare_frontier_min_cluster_size = DeclareLaunchArgument('frontier_min_cluster_size', default_value='')
    declare_min_goal_distance = DeclareLaunchArgument('min_goal_distance', default_value='')
    declare_no_frontier_relaxed_after_cycles = DeclareLaunchArgument(
        'no_frontier_relaxed_after_cycles',
        default_value='',
    )
    declare_no_frontier_relaxed_cluster_size = DeclareLaunchArgument(
        'no_frontier_relaxed_cluster_size',
        default_value='',
    )
    declare_no_frontier_relaxed_min_goal_distance = DeclareLaunchArgument(
        'no_frontier_relaxed_min_goal_distance',
        default_value='',
    )
    declare_control_period_sec = DeclareLaunchArgument('control_period_sec', default_value='')
    declare_min_goal_x = DeclareLaunchArgument('min_goal_x', default_value='')
    declare_max_goal_x = DeclareLaunchArgument('max_goal_x', default_value='')
    declare_min_goal_y = DeclareLaunchArgument('min_goal_y', default_value='')
    declare_max_goal_y = DeclareLaunchArgument('max_goal_y', default_value='')
    declare_stuck_timeout_sec = DeclareLaunchArgument('stuck_timeout_sec', default_value='')
    declare_stuck_movement_epsilon = DeclareLaunchArgument('stuck_movement_epsilon', default_value='')
    declare_stuck_goal_tolerance = DeclareLaunchArgument('stuck_goal_tolerance', default_value='')
    declare_blocked_goal_ttl_sec = DeclareLaunchArgument('blocked_goal_ttl_sec', default_value='')
    declare_blocked_goal_radius = DeclareLaunchArgument('blocked_goal_radius', default_value='')
    declare_nav2_startup_gate_timeout = DeclareLaunchArgument('nav2_startup_gate_timeout', default_value='')
    declare_gaden_sensor_gate_timeout = DeclareLaunchArgument('gaden_sensor_gate_timeout', default_value='')
    declare_enter_threshold = DeclareLaunchArgument('enter_threshold', default_value='')
    declare_exit_threshold = DeclareLaunchArgument('exit_threshold', default_value='')
    declare_confirm_samples = DeclareLaunchArgument('confirm_samples', default_value='')
    declare_min_explore_samples = DeclareLaunchArgument('min_explore_samples', default_value='')
    declare_gas_source_strength = DeclareLaunchArgument('gas_source_strength', default_value='')
    declare_gas_decay_rate = DeclareLaunchArgument('gas_decay_rate', default_value='')
    declare_gas_plume_stddev = DeclareLaunchArgument('gas_plume_stddev', default_value='')
    declare_gas_wind_x = DeclareLaunchArgument('gas_wind_x', default_value='')
    declare_gas_wind_y = DeclareLaunchArgument('gas_wind_y', default_value='')
    declare_gas_noise_stddev = DeclareLaunchArgument('gas_noise_stddev', default_value='')
    declare_gas_publish_rate_hz = DeclareLaunchArgument('gas_publish_rate_hz', default_value='')
    declare_gaden_project_path = DeclareLaunchArgument('gaden_project_path', default_value='')
    declare_gaden_playback_id = DeclareLaunchArgument('gaden_playback_id', default_value='')
    declare_gaden_player_freq = DeclareLaunchArgument('gaden_player_freq', default_value='')
    declare_gaden_sensor_topic = DeclareLaunchArgument('gaden_sensor_topic', default_value='')
    declare_gaden_sensor_frame = DeclareLaunchArgument('gaden_sensor_frame', default_value='')
    declare_gaden_fixed_frame = DeclareLaunchArgument('gaden_fixed_frame', default_value='')
    declare_gaden_map_offset_x = DeclareLaunchArgument('gaden_map_offset_x', default_value='')
    declare_gaden_map_offset_y = DeclareLaunchArgument('gaden_map_offset_y', default_value='')
    declare_gaden_map_offset_z = DeclareLaunchArgument('gaden_map_offset_z', default_value='')
    declare_gaden_map_roll = DeclareLaunchArgument('gaden_map_roll', default_value='')
    declare_gaden_map_pitch = DeclareLaunchArgument('gaden_map_pitch', default_value='')
    declare_gaden_map_yaw = DeclareLaunchArgument('gaden_map_yaw', default_value='')

    scene_defaults = OpaqueFunction(function=_scene_defaults)

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, 'launch', 'sim.launch.py')),
        launch_arguments={
            'scene': scene,
            'world': world,
            'gazebo_model_path': gazebo_model_path,
            'use_sim_time': use_sim_time,
            'headless': headless,
            'spawn_x': initial_pose_x,
            'spawn_y': initial_pose_y,
            'spawn_yaw': initial_pose_yaw,
        }.items(),
    )

    slam_nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_share, 'launch', 'slam_nav2.launch.py')),
        launch_arguments={
            'scene': scene,
            'use_sim_time': use_sim_time,
            'autostart': 'false',
            'map_saver_autostart': 'true',
        }.items(),
    )

    nav2_startup_gate = Node(
        package='h2track_tracking',
        executable='nav2_startup_gate_node',
        name='nav2_startup_gate_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'target_frame': 'odom',
                'source_frame': 'base_link',
                'lifecycle_manager_service': '/lifecycle_manager_navigation/manage_nodes',
                'timeout_sec': nav2_startup_gate_timeout,
                'poll_period_sec': 0.5,
                'stable_ready_count': 2,
            },
        ],
    )

    gas_field = Node(
        condition=UnlessCondition(use_gaden),
        package='h2track_tracking',
        executable='gas_field_node',
        name='gas_field_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'source_x': source_x,
                'source_y': source_y,
                'source_strength': gas_source_strength,
                'decay_rate': gas_decay_rate,
                'plume_stddev': gas_plume_stddev,
                'wind_x': gas_wind_x,
                'wind_y': gas_wind_y,
                'noise_stddev': gas_noise_stddev,
                'publish_rate_hz': gas_publish_rate_hz,
                'pose_source': 'auto',
            },
        ],
    )

    gaden_environment = Node(
        condition=IfCondition(use_gaden),
        package='gaden_environment',
        executable='environment',
        name='gaden_environment',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}, {'projectPath': gaden_project_path}],
    )

    gaden_player = Node(
        condition=IfCondition(use_gaden),
        package='gaden_player',
        executable='player',
        name='gaden_player',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'projectPath': gaden_project_path},
            {'playbackID': gaden_playback_id},
            {'player_freq': gaden_player_freq},
        ],
    )

    gaden_map_tf = Node(
        condition=IfCondition(use_gaden),
        package='tf2_ros',
        executable='static_transform_publisher',
        name='gaden_map_tf',
        output='screen',
        arguments=[
            '--x', gaden_map_offset_x,
            '--y', gaden_map_offset_y,
            '--z', gaden_map_offset_z,
            '--roll', gaden_map_roll,
            '--pitch', gaden_map_pitch,
            '--yaw', gaden_map_yaw,
            '--frame-id', gaden_fixed_frame,
            '--child-frame-id', 'map',
        ],
    )

    gaden_sensor_gate = Node(
        condition=IfCondition(use_gaden),
        package='h2track_tracking',
        executable='gaden_sensor_gate_node',
        name='gaden_sensor_gate_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'fixed_frame': gaden_fixed_frame,
                'sensor_frame': gaden_sensor_frame,
                'timeout_sec': gaden_sensor_gate_timeout,
                'poll_period_sec': 0.5,
                'stable_ready_count': 3,
                'sensor_node_name': 'gaden_pid_sensor',
                'topic': gaden_sensor_topic,
                'sensor_model': 30,
                'rate': 5.0,
                'use_pid_correction_factors': False,
            },
        ],
    )

    gaden_adapter = Node(
        condition=IfCondition(use_gaden),
        package='h2track_tracking',
        executable='gaden_adapter_node',
        name='gaden_adapter_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'gas_sensor_topic': gaden_sensor_topic,
                'gas_concentration_topic': '/gas_concentration',
                'sensor_model': -1,
                'fallback_ohm_scale': 0.001,
                'voltage_scale': 1.0,
                'minimum_concentration_ppm': 0.0,
                'maximum_concentration_ppm': 0.0,
            },
        ],
    )

    exploration_manager = Node(
        package='h2track_tracking',
        executable='exploration_manager_node',
        name='exploration_manager_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'frontier_min_cluster_size': frontier_min_cluster_size,
                'min_goal_distance': min_goal_distance,
                'no_frontier_relaxed_after_cycles': no_frontier_relaxed_after_cycles,
                'no_frontier_relaxed_cluster_size': no_frontier_relaxed_cluster_size,
                'no_frontier_relaxed_min_goal_distance': no_frontier_relaxed_min_goal_distance,
                'control_period_sec': control_period_sec,
                'min_goal_x': min_goal_x,
                'max_goal_x': max_goal_x,
                'min_goal_y': min_goal_y,
                'max_goal_y': max_goal_y,
                'stuck_timeout_sec': stuck_timeout_sec,
                'stuck_movement_epsilon': stuck_movement_epsilon,
                'stuck_goal_tolerance': stuck_goal_tolerance,
                'blocked_goal_ttl_sec': blocked_goal_ttl_sec,
                'blocked_goal_radius': blocked_goal_radius,
            },
        ],
    )

    mapping_mission_manager = Node(
        package='h2track_tracking',
        executable='mapping_mission_manager_node',
        name='mapping_mission_manager_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'enter_threshold': enter_threshold,
                'exit_threshold': exit_threshold,
                'confirm_samples': confirm_samples,
                'min_explore_samples': min_explore_samples,
            },
        ],
    )

    transition_manager = Node(
        package='h2track_tracking',
        executable='transition_manager_node',
        name='transition_manager_node',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {
                'scene_name': scene,
                'source_x': tracking_source_x,
                'source_y': tracking_source_y,
                'tracking_enter_threshold': tracking_enter_threshold,
                'tracking_exit_threshold': tracking_exit_threshold,
                'tracking_source_threshold': tracking_source_threshold,
                'tracking_confirm_samples': tracking_confirm_samples,
                'tracking_track_exit_samples': tracking_track_exit_samples,
                'tracking_source_radius': tracking_source_radius,
                'tracking_source_hold_steps': tracking_source_hold_steps,
                'tracking_track_step': tracking_track_step,
                'tracking_source_seed_max_distance': tracking_source_seed_max_distance,
            },
        ],
    )

    rviz = Node(
        condition=IfCondition(use_rviz),
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(pkg_share, 'rviz', 'h2track_nav2.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    return LaunchDescription([
        declare_scene,
        declare_use_sim_time,
        declare_use_rviz,
        declare_headless,
        declare_world,
        declare_gazebo_model_path,
        declare_initial_pose_x,
        declare_initial_pose_y,
        declare_initial_pose_yaw,
        declare_source_x,
        declare_source_y,
        declare_tracking_source_x,
        declare_tracking_source_y,
        declare_tracking_enter_threshold,
        declare_tracking_exit_threshold,
        declare_tracking_source_threshold,
        declare_tracking_confirm_samples,
        declare_tracking_track_exit_samples,
        declare_tracking_source_radius,
        declare_tracking_source_hold_steps,
        declare_tracking_track_step,
        declare_tracking_source_seed_max_distance,
        declare_use_gaden,
        declare_frontier_min_cluster_size,
        declare_min_goal_distance,
        declare_no_frontier_relaxed_after_cycles,
        declare_no_frontier_relaxed_cluster_size,
        declare_no_frontier_relaxed_min_goal_distance,
        declare_control_period_sec,
        declare_min_goal_x,
        declare_max_goal_x,
        declare_min_goal_y,
        declare_max_goal_y,
        declare_stuck_timeout_sec,
        declare_stuck_movement_epsilon,
        declare_stuck_goal_tolerance,
        declare_blocked_goal_ttl_sec,
        declare_blocked_goal_radius,
        declare_nav2_startup_gate_timeout,
        declare_gaden_sensor_gate_timeout,
        declare_enter_threshold,
        declare_exit_threshold,
        declare_confirm_samples,
        declare_min_explore_samples,
        declare_gas_source_strength,
        declare_gas_decay_rate,
        declare_gas_plume_stddev,
        declare_gas_wind_x,
        declare_gas_wind_y,
        declare_gas_noise_stddev,
        declare_gas_publish_rate_hz,
        declare_gaden_project_path,
        declare_gaden_playback_id,
        declare_gaden_player_freq,
        declare_gaden_sensor_topic,
        declare_gaden_sensor_frame,
        declare_gaden_fixed_frame,
        declare_gaden_map_offset_x,
        declare_gaden_map_offset_y,
        declare_gaden_map_offset_z,
        declare_gaden_map_roll,
        declare_gaden_map_pitch,
        declare_gaden_map_yaw,
        scene_defaults,
        sim,
        slam_nav2,
        nav2_startup_gate,
        gas_field,
        gaden_environment,
        gaden_player,
        gaden_map_tf,
        gaden_sensor_gate,
        gaden_adapter,
        mapping_mission_manager,
        transition_manager,
        exploration_manager,
        rviz,
    ])
