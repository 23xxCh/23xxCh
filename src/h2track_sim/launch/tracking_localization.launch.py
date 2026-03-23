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
from launch_ros.parameter_descriptions import ParameterValue
import yaml


def _load_scene_loader():
    loader_path = Path(__file__).with_name("scene_loader.py")
    spec = spec_from_file_location("h2track_scene_loader", loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCENE_LOADER = _load_scene_loader()
load_scene_profile = SCENE_LOADER.load_scene_profile
resolve_scene_nav2_params = SCENE_LOADER.resolve_scene_nav2_params


def _prepare_tracking_localization(context):
    pkg_share = get_package_share_directory("h2track_sim")
    runtime_dir = Path("/tmp/h2track_xian_runtime_map")
    runtime_dir.mkdir(parents=True, exist_ok=True)

    scene_name = LaunchConfiguration("scene").perform(context)
    scene_profile = load_scene_profile(pkg_share, scene_name)
    mission = scene_profile["mission_manager"]
    gas_source = scene_profile.get("gas_source", {})
    resolved_source_x = (
        LaunchConfiguration("source_x").perform(context).strip() or str(gas_source.get("x", -4.0))
    )
    resolved_source_y = (
        LaunchConfiguration("source_y").perform(context).strip() or str(gas_source.get("y", 1.95))
    )

    runtime_map = LaunchConfiguration("runtime_map").perform(context).strip()
    if not runtime_map:
        runtime_map = f"/tmp/h2track_runtime_maps/{scene_name}_freeze_map.yaml"

    source_params_path = Path(
        LaunchConfiguration("params_file").perform(context).strip()
        or resolve_scene_nav2_params(pkg_share, scene_name)
    )
    params_config = yaml.safe_load(source_params_path.read_text(encoding="utf-8"))
    amcl_params = params_config.setdefault("amcl", {}).setdefault("ros__parameters", {})
    amcl_params["initial_pose.x"] = float(
        LaunchConfiguration("initial_pose_x").perform(context).strip() or mission["initial_pose"]["x"]
    )
    amcl_params["initial_pose.y"] = float(
        LaunchConfiguration("initial_pose_y").perform(context).strip() or mission["initial_pose"]["y"]
    )
    amcl_params["initial_pose.yaw"] = float(
        LaunchConfiguration("initial_pose_yaw").perform(context).strip() or mission["initial_pose"]["yaw"]
    )
    runtime_params_path = runtime_dir / f"{scene_name}_tracking_nav2_params.yaml"
    runtime_params_path.write_text(yaml.safe_dump(params_config, sort_keys=False), encoding="utf-8")

    return [
        SetLaunchConfiguration("runtime_map", runtime_map),
        SetLaunchConfiguration("params_file", str(runtime_params_path)),
        SetLaunchConfiguration("patrol_points", str(mission["patrol_points"])),
        SetLaunchConfiguration("enter_threshold", str(mission["enter_threshold"])),
        SetLaunchConfiguration("exit_threshold", str(mission["exit_threshold"])),
        SetLaunchConfiguration("source_threshold", str(mission["source_threshold"])),
        SetLaunchConfiguration("confirm_samples", str(mission["confirm_samples"])),
        SetLaunchConfiguration("track_exit_samples", str(mission.get("track_exit_samples", mission["confirm_samples"]))),
        SetLaunchConfiguration("source_radius", str(mission["source_radius"])),
        SetLaunchConfiguration("source_hold_steps", str(mission["source_hold_steps"])),
        SetLaunchConfiguration("track_step", str(mission["track_step"])),
        SetLaunchConfiguration("sweep_angle_deg", str(mission["sweep_angle_deg"])),
        SetLaunchConfiguration("source_x", resolved_source_x),
        SetLaunchConfiguration("source_y", resolved_source_y),
    ]


def generate_launch_description():
    nav2_share = get_package_share_directory("nav2_bringup")

    use_sim_time = LaunchConfiguration("use_sim_time")
    runtime_map = LaunchConfiguration("runtime_map")
    params_file = LaunchConfiguration("params_file")
    initial_pose_x = LaunchConfiguration("initial_pose_x")
    initial_pose_y = LaunchConfiguration("initial_pose_y")
    initial_pose_yaw = LaunchConfiguration("initial_pose_yaw")
    patrol_points = LaunchConfiguration("patrol_points")
    enter_threshold = LaunchConfiguration("enter_threshold")
    exit_threshold = LaunchConfiguration("exit_threshold")
    source_threshold = LaunchConfiguration("source_threshold")
    confirm_samples = LaunchConfiguration("confirm_samples")
    track_exit_samples = LaunchConfiguration("track_exit_samples")
    source_radius = LaunchConfiguration("source_radius")
    source_hold_steps = LaunchConfiguration("source_hold_steps")
    track_step = LaunchConfiguration("track_step")
    sweep_angle_deg = LaunchConfiguration("sweep_angle_deg")
    source_x = LaunchConfiguration("source_x")
    source_y = LaunchConfiguration("source_y")

    declare_scene = DeclareLaunchArgument("scene", default_value="baseline")
    declare_use_sim_time = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_runtime_map = DeclareLaunchArgument("runtime_map", default_value="")
    declare_params_file = DeclareLaunchArgument("params_file", default_value="")
    declare_initial_pose_x = DeclareLaunchArgument("initial_pose_x", default_value="")
    declare_initial_pose_y = DeclareLaunchArgument("initial_pose_y", default_value="")
    declare_initial_pose_yaw = DeclareLaunchArgument("initial_pose_yaw", default_value="")
    declare_patrol_points = DeclareLaunchArgument("patrol_points", default_value="")
    declare_enter_threshold = DeclareLaunchArgument("enter_threshold", default_value="")
    declare_exit_threshold = DeclareLaunchArgument("exit_threshold", default_value="")
    declare_source_threshold = DeclareLaunchArgument("source_threshold", default_value="")
    declare_confirm_samples = DeclareLaunchArgument("confirm_samples", default_value="")
    declare_track_exit_samples = DeclareLaunchArgument("track_exit_samples", default_value="")
    declare_source_radius = DeclareLaunchArgument("source_radius", default_value="")
    declare_source_hold_steps = DeclareLaunchArgument("source_hold_steps", default_value="")
    declare_track_step = DeclareLaunchArgument("track_step", default_value="")
    declare_sweep_angle_deg = DeclareLaunchArgument("sweep_angle_deg", default_value="")
    declare_source_x = DeclareLaunchArgument("source_x", default_value="")
    declare_source_y = DeclareLaunchArgument("source_y", default_value="")

    tracking_defaults = OpaqueFunction(function=_prepare_tracking_localization)

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, "launch", "localization_launch.py")),
        launch_arguments={
            "map": runtime_map,
            "use_sim_time": use_sim_time,
            "params_file": params_file,
            "autostart": "true",
            "use_composition": "False",
            "use_respawn": "False",
        }.items(),
    )

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, "launch", "navigation_launch.py")),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "params_file": params_file,
            "autostart": "true",
            "use_composition": "False",
            "use_respawn": "False",
        }.items(),
    )

    mission_manager = Node(
        package="h2track_tracking",
        executable="mission_manager_node",
        name="mission_manager_node",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {
                "start_in_tracking_mode": True,
                "tracking_only_mode": True,
                "initial_pose_x": initial_pose_x,
                "initial_pose_y": initial_pose_y,
                "initial_pose_yaw": initial_pose_yaw,
                "patrol_points": ParameterValue(patrol_points, value_type=str),
                "enter_threshold": enter_threshold,
                "exit_threshold": exit_threshold,
                "source_threshold": source_threshold,
                "confirm_samples": confirm_samples,
                "track_exit_samples": track_exit_samples,
                "source_radius": source_radius,
                "source_hold_steps": source_hold_steps,
                "track_step": track_step,
                "sweep_angle_deg": sweep_angle_deg,
                "source_x": source_x,
                "source_y": source_y,
            },
        ],
    )

    return LaunchDescription(
        [
            declare_scene,
            declare_use_sim_time,
            declare_runtime_map,
            declare_params_file,
            declare_initial_pose_x,
            declare_initial_pose_y,
            declare_initial_pose_yaw,
            declare_patrol_points,
            declare_enter_threshold,
            declare_exit_threshold,
            declare_source_threshold,
            declare_confirm_samples,
            declare_track_exit_samples,
            declare_source_radius,
            declare_source_hold_steps,
            declare_track_step,
            declare_sweep_angle_deg,
            declare_source_x,
            declare_source_y,
            tracking_defaults,
            localization,
            navigation,
            mission_manager,
        ]
    )
