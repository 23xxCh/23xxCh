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
