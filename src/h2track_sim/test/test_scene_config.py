from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _baseline_scene_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'scenes' / 'baseline' / 'scene.yaml'


def test_baseline_scene_yaml_exists():
    assert _baseline_scene_path().exists()


def test_baseline_scene_yaml_declares_world_and_source():
    text = _baseline_scene_path().read_text(encoding='utf-8')
    assert 'world: scenes/baseline/h2track_lab.world' in text
    assert 'gas_source:' in text
    assert 'mission_manager:' in text


def test_cmakelists_installs_scenes_directory():
    cmake = (Path(__file__).resolve().parents[1] / 'CMakeLists.txt').read_text(encoding='utf-8')
    assert 'install(DIRECTORY' in cmake
    assert 'scenes' in cmake


def _warehouse_scene_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'scenes' / 'warehouse' / 'scene.yaml'


def test_warehouse_scene_yaml_exists():
    assert _warehouse_scene_path().exists()


def test_warehouse_scene_uses_portable_world_path_and_assets_exist():
    scene_text = _warehouse_scene_path().read_text(encoding='utf-8')
    assert 'world: scenes/warehouse/warehouse.world' in scene_text
    assert 'model_path: scenes/warehouse/models' in scene_text
    warehouse_root = _warehouse_scene_path().parent
    assert (warehouse_root / 'warehouse.world').exists()
    assert (warehouse_root / 'models' / 'aws_robomaker_warehouse_ShelfF_01' / 'model.sdf').exists()
    assert (warehouse_root / 'UPSTREAM_LICENSE_MIT-0.txt').exists()


def test_warehouse_scene_disables_gaden_by_default_until_scene_alignment_exists():
    scene_text = _warehouse_scene_path().read_text(encoding='utf-8')
    assert 'use_gaden: false' in scene_text


def _scene_loader_module():
    loader_path = Path(__file__).resolve().parents[1] / 'launch' / 'scene_loader.py'
    spec = spec_from_file_location('scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_scene_loader_reads_requested_scene_profile():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    baseline = loader.load_scene_profile(pkg_share, 'baseline')

    assert warehouse['scene_name'] == 'warehouse'
    assert baseline['scene_name'] == 'baseline'
    assert warehouse['mission_manager']['initial_pose']['x'] != baseline['mission_manager']['initial_pose']['x']


def test_scene_loader_resolves_world_and_model_paths_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    warehouse_world = loader.resolve_scene_world(pkg_share, 'warehouse')
    warehouse_model_path = loader.resolve_scene_model_path(pkg_share, 'warehouse')
    baseline_world = loader.resolve_scene_world(pkg_share, 'baseline')

    assert warehouse_world.endswith('scenes/warehouse/warehouse.world')
    assert warehouse_model_path.endswith('scenes/warehouse/models')
    assert baseline_world.endswith('scenes/baseline/h2track_lab.world')


def test_scene_loader_resolves_map_paths_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    baseline_map = loader.resolve_scene_map(pkg_share, 'baseline')
    warehouse_map = loader.resolve_scene_map(pkg_share, 'warehouse')

    assert baseline_map.endswith('maps/h2track_map.yaml')
    assert warehouse_map.endswith('scenes/warehouse/maps/warehouse_map.yaml')
