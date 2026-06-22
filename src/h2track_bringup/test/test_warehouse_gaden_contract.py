import os
from pathlib import Path

import pytest
import yaml


_GADEN_WS = Path(os.environ.get("GADEN_WS", "/home/user/gaden_ws"))
SCENARIO_ROOT = _GADEN_WS / 'src' / 'gaden' / 'test_env' / 'scenarios' / 'h2track_warehouse'
try:
    from ament_index_python.packages import get_package_share_directory
    _BRINGUP_DIR = Path(get_package_share_directory("h2track_bringup"))
except Exception:
    _BRINGUP_DIR = Path(__file__).resolve().parents[1]  # h2track_bringup/
WAREHOUSE_SCENE = _BRINGUP_DIR / 'scenes' / 'warehouse' / 'scene.yaml'


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def _warehouse_scene():
    return _load_yaml(WAREHOUSE_SCENE)


def _pgm_size(path: Path) -> tuple[int, int]:
    with path.open('rb') as handle:
        magic = handle.readline().strip()
        assert magic in {b'P5', b'P2'}
        line = handle.readline()
        while line.startswith(b'#'):
            line = handle.readline()
        width, height = map(int, line.split())
        _ = int(handle.readline().strip())
    return width, height


def _aligned_occupancy_bounds() -> tuple[float, float, float, float]:
    scene = _warehouse_scene()
    occupancy = _load_yaml(SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'occupancy.yaml')
    width, height = _pgm_size(SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'occupancy.pgm')
    origin_x, origin_y, _ = occupancy['origin']
    resolution = occupancy['resolution']
    offset_x = scene['gaden']['map_offset_x']
    offset_y = scene['gaden']['map_offset_y']
    min_x = origin_x + offset_x
    min_y = origin_y + offset_y
    max_x = min_x + width * resolution
    max_y = min_y + height * resolution
    return (min_x, min_y, max_x, max_y)




def _warehouse_map_bounds() -> tuple[float, float, float, float]:
    scene = _warehouse_scene()
    map_yaml = _load_yaml(_BRINGUP_DIR / scene['map'])
    width, height = _pgm_size((_BRINGUP_DIR / scene['map']).with_name(map_yaml['image']))
    origin_x, origin_y, _ = map_yaml['origin']
    resolution = map_yaml['resolution']
    return (origin_x, origin_y, origin_x + width * resolution, origin_y + height * resolution)


def test_warehouse_gaden_scenario_files_exist():
    assert (SCENARIO_ROOT / 'gaden.gproj').exists()
    assert (SCENARIO_ROOT / 'cad_models' / 'h2track_warehouse_shell.stl').exists()
    assert (SCENARIO_ROOT / 'cad_models' / 'h2track_warehouse_racks.stl').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'config.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'scenes' / 'scene1.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'simulations' / 'sim1' / 'sim.yaml').exists()


def test_warehouse_gaden_runtime_assets_are_local_and_not_symlinks():
    config_root = SCENARIO_ROOT / 'environment_configurations' / 'config1'
    occupancy = config_root / 'OccupancyGrid3D.csv'
    wind_dir = config_root / 'wind'
    result_dir = config_root / 'simulations' / 'sim1' / 'result'

    assert occupancy.exists()
    assert wind_dir.exists()
    assert result_dir.exists()
    assert not occupancy.is_symlink()
    assert not wind_dir.is_symlink()
    assert not result_dir.is_symlink()
    assert any(wind_dir.iterdir())
    assert any(result_dir.iterdir())


def test_warehouse_gaden_source_matches_warehouse_scene_source_after_alignment():
    scene = _warehouse_scene()
    sim = _load_yaml(SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'simulations' / 'sim1' / 'sim.yaml')
    offset_x = scene['gaden']['map_offset_x']
    offset_y = scene['gaden']['map_offset_y']

    aligned_source_x = sim['source']['position'][0] + offset_x
    aligned_source_y = sim['source']['position'][1] + offset_y

    assert aligned_source_x == pytest.approx(scene['gas_source']['x'], abs=0.25)
    assert aligned_source_y == pytest.approx(scene['gas_source']['y'], abs=0.25)


def test_warehouse_gaden_aligned_bounds_cover_patrol_and_source():
    scene = _warehouse_scene()
    min_x, min_y, max_x, max_y = _aligned_occupancy_bounds()
    points = [tuple(point) for point in scene['mission_manager']['patrol_points']]
    points.append((scene['gas_source']['x'], scene['gas_source']['y']))

    for x, y in points:
        assert min_x <= x <= max_x
        assert min_y <= y <= max_y


def test_warehouse_gaden_aligned_bounds_cover_warehouse_map_extents():
    gaden_min_x, gaden_min_y, gaden_max_x, gaden_max_y = _aligned_occupancy_bounds()
    map_min_x, map_min_y, map_max_x, map_max_y = _warehouse_map_bounds()

    assert gaden_min_x <= map_min_x
    assert gaden_min_y <= map_min_y
    assert gaden_max_x >= map_max_x
    assert gaden_max_y >= map_max_y
