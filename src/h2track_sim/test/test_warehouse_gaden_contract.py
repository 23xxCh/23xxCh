from pathlib import Path


SCENARIO_ROOT = Path('/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse')


def test_warehouse_gaden_scenario_files_exist():
    assert (SCENARIO_ROOT / 'gaden.gproj').exists()
    assert (SCENARIO_ROOT / 'cad_models' / 'h2track_warehouse_shell.stl').exists()
    assert (SCENARIO_ROOT / 'cad_models' / 'h2track_warehouse_racks.stl').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'config.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'scenes' / 'scene1.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'simulations' / 'sim1' / 'sim.yaml').exists()
