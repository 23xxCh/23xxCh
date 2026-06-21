from pathlib import Path

import yaml


MAP_YAML = Path('/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_bringup/scenes/warehouse/maps/warehouse_map.yaml')
SCENE_YAML = Path('/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_bringup/scenes/warehouse/scene.yaml')


def _load_map():
    config = yaml.safe_load(MAP_YAML.read_text(encoding='utf-8'))
    image_path = MAP_YAML.with_name(config['image'])
    with image_path.open('rb') as handle:
        magic = handle.readline().strip()
        assert magic == b'P5'
        line = handle.readline()
        while line.startswith(b'#'):
            line = handle.readline()
        width, height = map(int, line.split())
        _ = int(handle.readline().strip())
        data = handle.read()
    return config, width, height, data


def _sample(wx: float, wy: float) -> int:
    config, width, height, data = _load_map()
    origin_x, origin_y, _ = config['origin']
    resolution = config['resolution']
    px = int((wx - origin_x) / resolution)
    py = int((wy - origin_y) / resolution)
    iy = height - 1 - py
    idx = iy * width + px
    return data[idx]


def test_warehouse_map_marks_left_corridor_clutter():
    assert _sample(-1.491287, 5.222435) < 80


def test_warehouse_patrol_reaches_detectable_source_approach_route():
    scene = yaml.safe_load(SCENE_YAML.read_text(encoding='utf-8'))
    patrol = scene['mission_manager']['patrol_points']
    source = scene['gas_source']
    first, second, third, fourth, fifth = patrol

    assert first == [0.5, 2.8]
    assert second == [2.0, 2.8]
    assert third == [3.0, 1.0]
    assert fourth == [3.4, -2.2]
    assert fifth == [3.5, -2.8]
    assert scene['mission_manager']['enter_threshold'] == 0.6
    assert second[1] == first[1]
    assert third[0] > second[0]
    assert third[1] < second[1]
    assert fourth[1] < third[1]
    assert fifth[0] >= fourth[0]
    assert fifth[1] < fourth[1]
    assert abs(fifth[0] - source['x']) <= 0.2
    assert abs(fifth[1] - source['y']) <= 0.3
