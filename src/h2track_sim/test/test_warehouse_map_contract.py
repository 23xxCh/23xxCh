from pathlib import Path

import yaml


MAP_YAML = Path('/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/maps/warehouse_map.yaml')


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
    # This clutter exists in warehouse.world and sits near the old second-patrol corridor.
    assert _sample(-1.491287, 5.222435) < 80


def test_warehouse_patrol_uses_conservative_l_shaped_upper_route():
    scene = yaml.safe_load(Path('/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/scene.yaml').read_text(encoding='utf-8'))
    second = scene['mission_manager']['patrol_points'][1]
    third = scene['mission_manager']['patrol_points'][2]

    assert second == [2.4, 3.2]
    assert third == [2.4, 4.6]
    assert abs(second[1] - 3.0) <= 0.3
    assert third[0] == second[0]
    assert third[1] > second[1]
