from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import math
import xml.etree.ElementTree as ET

import pytest
import yaml


def _launch_text(name: str) -> str:
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    return launch_path.read_text(encoding="utf-8")


def _load_launch_module(name: str):
    launch_path = Path(__file__).resolve().parents[1] / "launch" / name
    spec = spec_from_file_location(name.replace('.', '_'), launch_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _demo_profile() -> dict:
    profile_path = Path(__file__).resolve().parents[1] / 'config' / 'demo.yaml'
    return yaml.safe_load(profile_path.read_text(encoding='utf-8'))


def _scene_profile(profile: dict) -> dict:
    scene_path = Path(__file__).resolve().parents[1] / profile['scene_config']
    return yaml.safe_load(scene_path.read_text(encoding='utf-8'))


def _point(x: float, y: float) -> dict:
    return {"x": float(x), "y": float(y)}


def _distance(point_a: dict, point_b: dict) -> float:
    return math.hypot(float(point_a["x"]) - float(point_b["x"]), float(point_a["y"]) - float(point_b["y"]))


def _source_point(profile: dict) -> dict:
    source = profile['gas_source']
    return _point(source['x'], source['y'])


def test_demo_profile_contains_fixed_demo_defaults():
    text = (Path(__file__).resolve().parents[1] / 'config' / 'demo.yaml').read_text(encoding='utf-8')
    assert 'use_gaden: true' in text
    assert 'use_slam: true' in text
    assert 'scene_config: scenes/warehouse/scene.yaml' in text
    assert 'mission_manager:' not in text
    assert 'gas_source:' not in text



def test_demo_initial_pose_is_not_inside_world_obstacles():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    world_path = Path(__file__).resolve().parents[1] / scene['world']
    world = ET.fromstring(world_path.read_text(encoding="utf-8"))

    # Warehouse scene should include a visible marker for the configured source.
    assert world.find(".//model[@name='h2_gas_source_marker']") is not None

    # Initial pose should stay inside the warehouse scene working area.
    assert -7.5 <= float(initial_pose["x"]) <= 7.5
    assert -10.8 <= float(initial_pose["y"]) <= 10.8

    for model in world.findall('.//model'):
        name = model.attrib.get("name", "")
        if not name.startswith("obstacle_"):
            continue
        pose = [float(v) for v in model.findtext("pose", default="0 0 0 0 0 0").split()]
        size = [float(v) for v in model.findtext('.//collision/geometry/box/size', default="0 0 0").split()]
        half_x = size[0] / 2.0
        half_y = size[1] / 2.0
        inside_x = abs(float(initial_pose["x"]) - pose[0]) < half_x
        inside_y = abs(float(initial_pose["y"]) - pose[1]) < half_y
        assert not (inside_x and inside_y), name



def test_demo_profile_stays_inside_gaden_query_window():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    points = [initial_pose, *({'x': x, 'y': y} for x, y in scene['mission_manager']['patrol_points'])]

    for point in points:
        assert abs(float(point["x"])) < 7.6
        assert abs(float(point["y"])) < 10.9



def test_demo_nav2_initial_pose_matches_demo_profile():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    nav2_params_path = Path(__file__).resolve().parents[1] / scene["nav2_params"]
    nav2_params = yaml.safe_load(nav2_params_path.read_text(encoding="utf-8"))
    amcl = nav2_params["amcl"]["ros__parameters"]

    # Scene-specific launch logic rewrites AMCL initial pose at runtime.
    # Static nav2 params only need to expose the keys.
    assert "initial_pose.x" in amcl
    assert "initial_pose.y" in amcl
    assert "initial_pose.yaw" in amcl
    assert float(initial_pose["x"]) == pytest.approx(0.5, abs=1e-6)
    assert float(initial_pose["y"]) == pytest.approx(1.0, abs=1e-6)



def test_demo_profile_has_staged_patrol_path_for_live_demo():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    patrol_points = [_point(x, y) for x, y in _scene_profile(profile)['mission_manager']["patrol_points"]]
    source = _source_point(scene)

    assert len(patrol_points) >= 4

    # First legs are pure patrol in upper aisle.
    first_leg = _distance(initial_pose, patrol_points[0])
    assert first_leg >= 1.5
    assert first_leg <= 1.6
    assert patrol_points[0]["y"] > 2.0
    assert patrol_points[1]["y"] > 2.0
    assert _distance(patrol_points[0], source) > 4.0

    # Later points should descend toward the source shelf.
    assert patrol_points[2]["y"] < patrol_points[1]["y"]
    assert patrol_points[3]["y"] < patrol_points[2]["y"]
    assert _distance(patrol_points[-1], source) < 0.4



def test_demo_profile_source_stays_off_patrol_points_but_near_early_route():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    patrol_points = [_point(x, y) for x, y in _scene_profile(profile)['mission_manager']["patrol_points"]]
    source = _source_point(scene)

    early_points = [initial_pose, *patrol_points[:2]]
    for point in early_points:
        assert _distance(point, source) > 3.5
    assert _distance(patrol_points[-1], source) < 0.4
    assert _distance(patrol_points[-2], source) < 0.8



def test_demo_profile_keeps_early_demo_points_clear_of_obstacles():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = _point(scene['mission_manager']['initial_pose']['x'], scene['mission_manager']['initial_pose']['y'])
    patrol_points = [_point(x, y) for x, y in scene['mission_manager']['patrol_points'][:2]]
    for candidate in [initial_pose, *patrol_points]:
        assert -7.5 <= candidate["x"] <= 7.5
        assert -10.8 <= candidate["y"] <= 10.8


def test_demo_profile_approaches_source_from_above_obstacle_one():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    patrol_points = [_point(x, y) for x, y in scene['mission_manager']['patrol_points']]
    source = _source_point(scene)
    fourth_point = patrol_points[2]
    final_point = patrol_points[-1]

    assert fourth_point["y"] < 0.0
    assert final_point["y"] < fourth_point["y"]
    assert final_point["x"] <= 3.5
    assert _distance(final_point, source) < _distance(fourth_point, source)
    assert _distance(final_point, source) < 0.4


def test_demo_profile_balances_background_rejection_with_source_entry():
    mission = _scene_profile(_demo_profile())["mission_manager"]

    assert 0.6 <= float(mission["enter_threshold"]) <= 1.2
    assert int(mission["confirm_samples"]) == 1
    assert 3.0 <= float(mission["source_threshold"]) <= 3.6
    assert float(mission["source_threshold"]) > float(mission["enter_threshold"])
    assert 0.35 <= float(mission["exit_threshold"]) < float(mission["enter_threshold"])
    assert int(mission["track_exit_samples"]) >= int(mission["confirm_samples"])
    assert float(mission["track_step"]) <= 0.5
    assert float(mission["source_radius"]) >= 1.0
    assert int(mission["source_hold_steps"]) == 1



def test_demo_launch_includes_bringup_with_demo_defaults():
    text = _launch_text("demo.launch.py")
    assert "IncludeLaunchDescription" in text
    assert "use_gaden" in text
    assert "use_slam" in text
    assert "demo.yaml" in text


def test_demo_launch_module_imports_without_launch_pythonpath_side_effects():
    module = _load_launch_module("demo.launch.py")
    assert hasattr(module, 'generate_launch_description')


def test_demo_launch_passes_scene_to_bringup():
    text = _launch_text("demo.launch.py")
    assert "scene" in text
    assert "load_scene_profile" in text


def test_demo_launch_resolves_selected_scene_profile_instead_of_fixed_demo_scene():
    text = _launch_text("demo.launch.py")
    assert 'load_scene_profile' in text
    assert 'scene.perform(context)' in text or "LaunchConfiguration('scene').perform(context)" in text
    assert "demo['scene_config']" not in text


def test_demo_launch_resolves_scene_specific_use_gaden_default():
    text = _launch_text("demo.launch.py")
    assert "scene_profile.get('use_gaden'" in text or 'scene_profile.get("use_gaden"' in text
    assert "use_gaden.perform(context)" in text or 'LaunchConfiguration("use_gaden").perform(context)' in text
    assert "SetLaunchConfiguration('use_gaden'" in text or 'SetLaunchConfiguration("use_gaden"' in text


def test_demo_launch_resolves_scene_specific_use_slam_default():
    text = _launch_text("demo.launch.py")
    assert "scene_profile.get('use_slam'" in text or 'scene_profile.get("use_slam"' in text
    assert "use_slam.perform(context)" in text or 'LaunchConfiguration("use_slam").perform(context)' in text
    assert "SetLaunchConfiguration('use_slam'" in text or 'SetLaunchConfiguration("use_slam"' in text

def test_demo_launch_prefers_scene_gaden_defaults_for_warehouse():
    text = _launch_text("demo.launch.py")
    assert "scene_profile.get('use_gaden'" in text or 'scene_profile.get("use_gaden"' in text




def test_demo_launch_resolves_scene_specific_nav2_params():
    text = _launch_text("demo.launch.py")
    assert 'resolve_scene_nav2_params' in text
    assert "SetLaunchConfiguration('nav2_params_file'" in text or 'SetLaunchConfiguration("nav2_params_file"' in text


def test_bringup_uses_slow_enough_gaden_playback_for_live_demo_margin():
    text = _launch_text("bringup.launch.py")
    assert 'gaden_player_freq' in text
    assert '{"player_freq": gaden_player_freq}' in text or '"player_freq": gaden_player_freq' in text



def test_demo_launch_flattens_patrol_points_for_launch_parameters():
    text = _launch_text("demo.launch.py")
    assert "_flatten_patrol_points" in text
    assert "json.dumps(_flatten_patrol_points(mission[\'patrol_points\']))" in text



def test_demo_launch_sets_mission_values_as_launch_configurations():
    text = _launch_text("demo.launch.py")
    assert "SetLaunchConfiguration('mission_manager_delay'" in text
    assert "SetLaunchConfiguration('patrol_points'" in text
    assert "SetLaunchConfiguration('patrol_goal_timeout_sec'" in text
    assert "SetLaunchConfiguration('track_exit_samples'" in text


def test_demo_launch_forwards_optional_nav2_map_override():
    text = _launch_text("demo.launch.py")
    assert "DeclareLaunchArgument('nav2_map_file'" in text or 'DeclareLaunchArgument("nav2_map_file"' in text
    assert "'nav2_map_file': nav2_map_file" in text or '"nav2_map_file": nav2_map_file' in text


def test_slam_demo_launch_forces_use_slam_true():
    text = _launch_text("slam_demo.launch.py")
    assert '"use_slam": "true"' in text
    assert '"nav2_map_file": nav2_map_file' in text
    assert "IncludeLaunchDescription" in text
