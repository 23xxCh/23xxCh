from importlib.util import module_from_spec, spec_from_file_location
import math
from pathlib import Path
import yaml


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


def test_scene_profiles_declare_use_slam_and_localizer_defaults():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    baseline = loader.load_scene_profile(pkg_share, 'baseline')
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert baseline['use_slam'] is False
    assert baseline['localizer_node'] == 'amcl'
    assert baseline.get('nav2_autostart', True) is True
    assert warehouse['use_slam'] is True
    assert warehouse['localizer_node'] == 'none'
    assert warehouse.get('nav2_autostart', True) is False


def _scene_loader_module():
    loader_path = Path(__file__).resolve().parents[1] / 'launch' / 'scene_loader.py'
    spec = spec_from_file_location('scene_loader', loader_path)
    module = module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module




def test_scene_profiles_declare_scene_specific_gas_field_parameters():
    for scene_name in ('baseline', 'warehouse', 'maze', 'snake'):
        scene_path = Path(__file__).resolve().parents[1] / 'scenes' / scene_name / 'scene.yaml'
        if not scene_path.exists():
            continue
        scene_text = scene_path.read_text(encoding='utf-8')
        assert 'gas_field:' in scene_text
        assert 'source_strength:' in scene_text
        assert 'decay_rate:' in scene_text
        assert 'plume_stddev:' in scene_text
        assert 'wind_x:' in scene_text
        assert 'wind_y:' in scene_text
        assert 'gas_type:' in scene_text


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


def test_warehouse_scene_uses_stable_gas_sensor_frame():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert warehouse['gaden']['sensor_frame'] == 'gas_sensor_link'


def test_robot_urdf_declares_elevated_gas_sensor_link():
    # URDF moved to h2track_description package
    try:
        from ament_index_python.packages import get_package_share_directory
        urdf_dir = Path(get_package_share_directory("h2track_description")) / "urdf"
    except Exception:
        urdf_dir = Path(__file__).resolve().parents[2] / "h2track_description" / "urdf"
    urdf = (urdf_dir / 'h2track_bot.urdf.xacro').read_text(encoding='utf-8')

    assert '<link name="gas_sensor_link">' in urdf
    assert '<joint name="gas_sensor_joint" type="fixed">' in urdf
    # Sensor elevated to 1.5m to detect rising H2 gas
    assert '<origin xyz="0 0 1.5"/>' in urdf


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

    assert baseline_nav2.endswith('scenes/baseline/nav2_params.yaml')
    assert warehouse_nav2.endswith('scenes/warehouse/nav2_params.yaml')

def test_scene_loader_resolves_map_paths_from_selected_scene():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()

    baseline_map = loader.resolve_scene_map(pkg_share, 'baseline')
    warehouse_map = loader.resolve_scene_map(pkg_share, 'warehouse')

    assert baseline_map.endswith('scenes/baseline/maps/baseline_map.yaml')


def test_warehouse_nav2_enables_rotate_to_heading_for_rpp_stability():
    pkg_share = Path(__file__).resolve().parents[1]
    warehouse_scene = yaml.safe_load((pkg_share / 'scenes' / 'warehouse' / 'scene.yaml').read_text(encoding='utf-8'))
    nav2_params = yaml.safe_load((pkg_share / warehouse_scene['nav2_params']).read_text(encoding='utf-8'))
    follow_path = nav2_params['controller_server']['ros__parameters']['FollowPath']

    assert follow_path['plugin'] == 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController'
    assert follow_path['use_rotate_to_heading'] is True
    # Verify the map path in the scene config points to the correct location
    assert 'maps/warehouse_map.yaml' in warehouse_scene['map']


def test_warehouse_patrol_points_use_progressive_step_lengths_for_slam_mapping():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    patrol_points = warehouse['mission_manager']['patrol_points']

    # Keep consecutive waypoint jumps moderate in SLAM mode to avoid planning
    # across large unmapped regions early in the run.
    max_step = 3.0
    for i in range(len(patrol_points) - 1):
        x1, y1 = patrol_points[i]
        x2, y2 = patrol_points[i + 1]
        step = math.hypot(x2 - x1, y2 - y1)
        assert step <= max_step, f'patrol step {i}->{i+1} too large: {step:.2f}m'


def test_warehouse_scene_declares_patrol_goal_timeout_for_skip_logic():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')
    timeout_sec = float(warehouse['mission_manager']['patrol_goal_timeout_sec'])
    assert timeout_sec >= 60.0


def test_warehouse_nav2_progress_checker_is_tuned_for_slow_cluttered_aisles():
    nav2_path = Path(__file__).resolve().parents[1] / 'scenes' / 'warehouse' / 'nav2_params.yaml'
    nav2 = yaml.safe_load(nav2_path.read_text(encoding='utf-8'))
    checker = nav2['controller_server']['ros__parameters']['progress_checker']

    assert float(checker['required_movement_radius']) <= 0.06
    assert float(checker['movement_time_allowance']) >= 35.0


def test_warehouse_nav2_controller_speed_is_tuned_for_long_aisle_reachability():
    nav2_path = Path(__file__).resolve().parents[1] / 'scenes' / 'warehouse' / 'nav2_params.yaml'
    nav2 = yaml.safe_load(nav2_path.read_text(encoding='utf-8'))
    follow = nav2['controller_server']['ros__parameters']['FollowPath']

    assert float(follow['desired_linear_vel']) >= 0.2
    assert float(follow['lookahead_dist']) >= 0.4
    assert float(follow['rotate_to_heading_angular_vel']) >= 0.8


# -- Maze scene tests ---------------------------------------------------------

def _maze_scene_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'scenes' / 'maze' / 'scene.yaml'


def test_maze_scene_yaml_exists():
    assert _maze_scene_path().exists()


def test_maze_scene_declares_world_and_gaden():
    text = _maze_scene_path().read_text(encoding='utf-8')
    assert 'world: scenes/maze/maze.world' in text
    assert 'gas_source:' in text
    assert 'gaden:' in text
    assert '10x6_maze' in text
    assert 'use_gaden: true' in text


def test_maze_scene_world_and_map_exist():
    maze_root = _maze_scene_path().parent
    assert (maze_root / 'maze.world').exists()
    assert (maze_root / 'maps' / 'maze_map.yaml').exists()
    assert (maze_root / 'maps' / 'maze_map.pgm').exists()
    assert (maze_root / 'nav2_params.yaml').exists()


def test_maze_scene_uses_amcl_not_slam():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    maze = loader.load_scene_profile(pkg_share, 'maze')
    assert maze['use_gaden'] is True
    assert maze['use_slam'] is False
    assert maze['localizer_node'] == 'amcl'


# -- Snake scene tests ---------------------------------------------------------

def _snake_scene_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'scenes' / 'snake' / 'scene.yaml'


def test_snake_scene_yaml_exists():
    assert _snake_scene_path().exists()


def test_snake_scene_declares_world_and_gaden():
    text = _snake_scene_path().read_text(encoding='utf-8')
    assert 'world: scenes/snake/snake.world' in text
    assert 'gas_source:' in text
    assert 'gaden:' in text
    assert '10x6_snake' in text
    assert 'use_gaden: true' in text


def test_snake_scene_world_and_map_exist():
    snake_root = _snake_scene_path().parent
    assert (snake_root / 'snake.world').exists()
    assert (snake_root / 'maps' / 'snake_map.yaml').exists()
    assert (snake_root / 'maps' / 'snake_map.pgm').exists()
    assert (snake_root / 'nav2_params.yaml').exists()


def test_snake_scene_uses_amcl_not_slam():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    snake = loader.load_scene_profile(pkg_share, 'snake')
    assert snake['use_gaden'] is True
    assert snake['use_slam'] is False
    assert snake['localizer_node'] == 'amcl'


# -- Office scene (GADEN disabled) tests ----------------------------------------

def _office_scene_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'scenes' / 'office' / 'scene.yaml'


def test_office_scene_disables_gaden_due_to_geometry_mismatch():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    office = loader.load_scene_profile(pkg_share, 'office')
    assert office['use_gaden'] is False
