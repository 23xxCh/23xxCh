from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import math
import xml.etree.ElementTree as ET

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
    assert 'scene_config: scenes/baseline/scene.yaml' in text
    assert 'mission_manager:' not in text
    assert 'gas_source:' not in text



def test_demo_initial_pose_is_not_inside_world_obstacles():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    world_path = Path(__file__).resolve().parents[1] / 'worlds' / 'h2track_lab.world'
    world = ET.fromstring(world_path.read_text(encoding="utf-8"))

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
        assert abs(float(point["x"])) < 5.0
        assert abs(float(point["y"])) < 3.0



def test_demo_nav2_initial_pose_matches_demo_profile():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    nav2_params_path = Path(__file__).resolve().parents[1] / "config" / "nav2_demo_params.yaml"
    nav2_params = yaml.safe_load(nav2_params_path.read_text(encoding="utf-8"))
    amcl = nav2_params["amcl"]["ros__parameters"]

    assert float(amcl["initial_pose.x"]) == float(initial_pose["x"])
    assert float(amcl["initial_pose.y"]) == float(initial_pose["y"])
    assert float(amcl["initial_pose.yaw"]) == float(initial_pose["yaw"])



def test_demo_profile_has_staged_patrol_path_for_live_demo():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    patrol_points = [_point(x, y) for x, y in _scene_profile(profile)['mission_manager']["patrol_points"]]
    source = _source_point(scene)

    assert len(patrol_points) >= 3

    first_leg = _distance(initial_pose, patrol_points[0])
    second_leg = _distance(patrol_points[0], patrol_points[1])
    third_point_distance_to_source = _distance(patrol_points[2], source)

    assert 0.4 <= first_leg <= 1.0
    assert second_leg > first_leg
    assert _distance(patrol_points[1], source) > 3.0
    assert 1.5 < third_point_distance_to_source < 3.0
    assert third_point_distance_to_source < _distance(patrol_points[1], source)



def test_demo_profile_source_stays_off_patrol_points_but_near_early_route():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = scene['mission_manager']['initial_pose']
    patrol_points = [_point(x, y) for x, y in _scene_profile(profile)['mission_manager']["patrol_points"]]
    source = _source_point(scene)

    early_points = [initial_pose, *patrol_points[:3]]

    for point in early_points:
        assert _distance(point, source) > 1.2

    assert min(_distance(point, source) for point in patrol_points[:3]) < 3.0



def test_demo_profile_keeps_early_demo_points_clear_of_obstacles():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    initial_pose = _point(
        scene['mission_manager']['initial_pose']['x'],
        scene['mission_manager']['initial_pose']['y'],
    )
    patrol_points = [_point(x, y) for x, y in scene['mission_manager']['patrol_points'][:2]]
    world_path = Path(__file__).resolve().parents[1] / "worlds" / "h2track_lab.world"
    world = ET.fromstring(world_path.read_text(encoding="utf-8"))

    for candidate in [initial_pose, *patrol_points]:
        for model in world.findall('.//model'):
            name = model.attrib.get("name", "")
            if not name.startswith("obstacle_"):
                continue
            pose = [float(v) for v in model.findtext("pose", default="0 0 0 0 0 0").split()]
            size = [float(v) for v in model.findtext('.//collision/geometry/box/size', default="0 0 0").split()]
            half_x = size[0] / 2.0
            half_y = size[1] / 2.0
            inside_x = abs(candidate["x"] - pose[0]) < half_x
            inside_y = abs(candidate["y"] - pose[1]) < half_y
            assert not (inside_x and inside_y), (candidate, name)


def test_demo_profile_approaches_source_from_above_obstacle_one():
    profile = _demo_profile()
    scene = _scene_profile(profile)
    patrol_points = [_point(x, y) for x, y in scene['mission_manager']['patrol_points']]
    source = _source_point(scene)
    fourth_point = patrol_points[3]

    assert fourth_point["y"] > 2.35
    assert fourth_point["x"] < patrol_points[2]["x"]
    assert 0.7 <= _distance(fourth_point, source) <= 1.5


def test_demo_profile_balances_background_rejection_with_source_entry():
    mission = _scene_profile(_demo_profile())["mission_manager"]

    assert 1.4 <= float(mission["enter_threshold"]) <= 2.0
    assert int(mission["confirm_samples"]) == 2
    assert float(mission["source_threshold"]) >= 4.5
    assert float(mission["source_threshold"]) > float(mission["enter_threshold"])
    assert 0.6 <= float(mission["exit_threshold"]) < float(mission["enter_threshold"])
    assert float(mission["track_step"]) <= 0.5
    assert float(mission["source_radius"]) >= 1.0
    assert int(mission["source_hold_steps"]) == 2



def test_demo_launch_includes_bringup_with_demo_defaults():
    text = _launch_text("demo.launch.py")
    assert "IncludeLaunchDescription" in text
    assert "use_gaden" in text
    assert "demo.yaml" in text


def test_demo_launch_module_imports_without_launch_pythonpath_side_effects():
    module = _load_launch_module("demo.launch.py")
    assert hasattr(module, 'generate_launch_description')


def test_demo_launch_passes_scene_to_bringup():
    text = _launch_text("demo.launch.py")
    assert "scene" in text
    assert "baseline" in text


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



def test_demo_launch_uses_demo_nav2_params():
    text = _launch_text("demo.launch.py")
    assert "nav2_demo_params.yaml" in text


def test_bringup_uses_slow_enough_gaden_playback_for_live_demo_margin():
    text = _launch_text("bringup.launch.py")
    assert '{"player_freq": 1.0}' in text or '"player_freq": 1.0' in text



def test_demo_launch_flattens_patrol_points_for_launch_parameters():
    text = _launch_text("demo.launch.py")
    assert "_flatten_patrol_points" in text
    assert "json.dumps(_flatten_patrol_points(mission[\'patrol_points\']))" in text



def test_demo_launch_sets_mission_values_as_launch_configurations():
    text = _launch_text("demo.launch.py")
    assert "SetLaunchConfiguration('mission_manager_delay'" in text
    assert "SetLaunchConfiguration('patrol_points'" in text
