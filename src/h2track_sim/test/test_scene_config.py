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


def test_warehouse_scene_declares_dedicated_gaden_block():
    warehouse = _warehouse_scene_path().read_text(encoding='utf-8')
    assert 'gaden:' in warehouse
    assert 'project_path:' in warehouse
    assert 'playback_id:' in warehouse
    assert 'sensor_topic:' in warehouse
    assert 'fixed_frame:' in warehouse


def test_warehouse_scene_defaults_to_gaden_enabled():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    assert warehouse['use_gaden'] is True
    assert '10x6_empty_room' not in warehouse['gaden']['project_path']


def _scene_loader_module():
    loader_path = Path(__file__).resolve().parents[1] / 'launch' / 'scene_loader.py'
    spec = spec_from_file_location('scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module




def test_scene_profiles_declare_scene_specific_gas_field_parameters():
    for scene_name in ('baseline', 'warehouse'):
        scene_path = Path(__file__).resolve().parents[1] / 'scenes' / scene_name / 'scene.yaml'
        scene_text = scene_path.read_text(encoding='utf-8')
        assert 'gas_field:' in scene_text
        assert 'source_strength:' in scene_text
        assert 'decay_rate:' in scene_text
        assert 'plume_stddev:' in scene_text
        assert 'wind_x:' in scene_text
        assert 'wind_y:' in scene_text


def test_warehouse_scene_gas_field_differs_from_baseline_defaults():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    baseline = loader.load_scene_profile(pkg_share, 'baseline')
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert baseline['gas_field'] != warehouse['gas_field']

def test_scene_loader_reads_requested_scene_profile():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    baseline = loader.load_scene_profile(pkg_share, 'baseline')

    assert warehouse['scene_name'] == 'warehouse'
    assert baseline['scene_name'] == 'baseline'
    assert warehouse['mission_manager']['initial_pose']['x'] != baseline['mission_manager']['initial_pose']['x']


def test_scene_loader_reads_warehouse_gaden_settings():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert warehouse['gaden']['project_path'].endswith('h2track_warehouse/environment_configurations/config1')
    assert warehouse['gaden']['playback_id'] == 'scene1'
    assert warehouse['gaden']['player_freq'] == 0.5


def test_warehouse_scene_uses_dedicated_gas_sensor_frame():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert warehouse['gaden']['sensor_frame'] == 'gas_sensor_link'


def test_robot_urdf_declares_elevated_gas_sensor_link():
    urdf = (Path(__file__).resolve().parents[1] / 'urdf' / 'h2track_bot.urdf.xacro').read_text(encoding='utf-8')

    assert '<link name="gas_sensor_link">' in urdf
    assert '<joint name="gas_sensor_joint" type="fixed">' in urdf
    assert '<origin xyz="0 0 0.45"/>' in urdf


def test_scene_loader_resolves_world_and_model_paths_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    warehouse_world = loader.resolve_scene_world(pkg_share, 'warehouse')
    warehouse_model_path = loader.resolve_scene_model_path(pkg_share, 'warehouse')
    baseline_world = loader.resolve_scene_world(pkg_share, 'baseline')

    assert warehouse_world.endswith('scenes/warehouse/warehouse.world')
    assert warehouse_model_path.endswith('scenes/warehouse/models')
    assert baseline_world.endswith('scenes/baseline/h2track_lab.world')




def test_scene_loader_resolves_nav2_params_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    baseline_nav2 = loader.resolve_scene_nav2_params(pkg_share, 'baseline')
    warehouse_nav2 = loader.resolve_scene_nav2_params(pkg_share, 'warehouse')

    assert baseline_nav2.endswith('config/nav2_demo_params.yaml')
    assert warehouse_nav2.endswith('scenes/warehouse/nav2_params.yaml')

def test_scene_loader_resolves_map_paths_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    baseline_map = loader.resolve_scene_map(pkg_share, 'baseline')
    warehouse_map = loader.resolve_scene_map(pkg_share, 'warehouse')

    assert baseline_map.endswith('maps/h2track_map.yaml')
    assert warehouse_map.endswith('scenes/warehouse/maps/warehouse_map.yaml')


def test_baseline_scene_declares_autonomy_config_for_slam_exploration():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    baseline = loader.load_scene_profile(pkg_share, 'baseline')

    assert 'autonomy' in baseline
    assert baseline['autonomy']['slam_nav2_params'].endswith('config/nav2_slam_baseline_params.yaml')
    assert 'exploration' in baseline['autonomy']
    assert 'mapping_detection' in baseline['autonomy']
    assert baseline['autonomy']['mapping_detection']['min_explore_samples'] > 0
    assert baseline['autonomy']['mapping_detection']['min_explore_samples'] <= 100
    assert 'startup_gates' in baseline['autonomy']
    assert baseline['autonomy']['startup_gates']['nav2_startup_gate_timeout'] >= 45.0
    assert baseline['autonomy']['startup_gates']['gaden_sensor_gate_timeout'] >= 45.0
    assert baseline['autonomy']['exploration']['frontier_min_cluster_size'] >= 4
    assert baseline['autonomy']['exploration']['min_goal_distance'] > 0.0
    assert baseline['autonomy']['exploration']['min_goal_x'] < baseline['autonomy']['exploration']['max_goal_x']
    assert baseline['autonomy']['exploration']['min_goal_y'] < baseline['autonomy']['exploration']['max_goal_y']
    assert baseline['mission_manager']['track_exit_samples'] >= baseline['mission_manager']['confirm_samples']
    assert baseline['autonomy']['tracking_handoff']['track_exit_samples'] >= baseline['autonomy']['tracking_handoff']['confirm_samples']


def test_baseline_scene_declares_tracking_nav2_overrides_for_handoff_stability():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    baseline = loader.load_scene_profile(pkg_share, 'baseline')

    overrides = baseline['autonomy'].get('tracking_nav2_overrides')
    assert overrides is not None
    assert int(overrides['bt_loop_duration']) >= 30
    assert float(overrides['required_movement_radius']) <= 0.2
    assert float(overrides['movement_time_allowance']) >= 20.0
    assert float(overrides['desired_linear_vel']) <= 0.2


def test_warehouse_scene_declares_autonomy_startup_gates_for_launch_timing():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert 'autonomy' in warehouse
    assert 'startup_gates' in warehouse['autonomy']
    startup = warehouse['autonomy']['startup_gates']
    assert startup['nav2_launch_delay'] > 0.0
    assert startup['mission_manager_delay'] >= 3.0
    assert startup['gaden_sensor_gate_timeout'] >= 30.0
    assert startup['gaden_sensor_gate_poll_period'] > 0.0
    assert startup['gaden_sensor_gate_stable_ready_count'] >= 2


def test_warehouse_scene_patrol_path_and_thresholds_support_detection_then_tracking():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    mission = warehouse['mission_manager']
    source = warehouse['gas_source']

    patrol_points = mission['patrol_points']
    assert len(patrol_points) >= 5

    def _distance(a, b):
        dx = float(a[0]) - float(b[0])
        dy = float(a[1]) - float(b[1])
        return (dx * dx + dy * dy) ** 0.5

    src_xy = (float(source['x']), float(source['y']))
    assert _distance(patrol_points[0], src_xy) > 4.0
    assert _distance(patrol_points[1], src_xy) > 3.5
    assert _distance(patrol_points[-1], src_xy) < 0.4

    enter_threshold = float(mission['enter_threshold'])
    source_threshold = float(mission['source_threshold'])
    exit_threshold = float(mission['exit_threshold'])
    assert 0.3 <= enter_threshold <= 0.8
    assert source_threshold > enter_threshold
    assert exit_threshold < enter_threshold
