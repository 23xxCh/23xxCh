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
