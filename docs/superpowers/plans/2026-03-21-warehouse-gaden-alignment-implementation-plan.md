# Warehouse GADEN Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scene:=warehouse` default to its own external GADEN scenario in `/home/user/gaden_ws` instead of falling back to the baseline room setup, while preserving `use_gaden:=false` as an explicit simplified-field fallback.

**Architecture:** Keep the GADEN adapter and mission layer unchanged, but move all warehouse-specific GADEN defaults into `warehouse/scene.yaml` and route them through the scene-driven launch stack. Create a dedicated approximate warehouse GADEN scenario under `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse`, then verify that the warehouse scene launches against that external project path and no longer references `10x6_empty_room` by default.

**Tech Stack:** ROS 2 Humble, Gazebo Classic, Nav2, GADEN `test_env`, Python launch files, YAML, pytest, colcon.

---

## File Structure

### Existing files to modify
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/scene.yaml`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/scene_loader.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/demo.launch.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/bringup.launch.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_scene_config.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_demo_launch.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_launch_timing.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking/h2track_tracking/demo_prep.py`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking/test/test_demo_prep.py`

### New files to create
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_warehouse_gaden_contract.py`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/gaden.gproj`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/cad_models/h2track_warehouse_shell.stl`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/cad_models/h2track_warehouse_racks.stl`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1/config.yaml`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1/scenes/scene1.yaml`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1/simulations/sim1/sim.yaml`
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/wind_simulations/README.md`
- `/home/user/h2track-xian/.worktrees/dual-scene-platform/docs/warehouse-gaden-runbook.md`

## Chunk 1: Make warehouse scene own its GADEN configuration

### Task 1: Add failing scene-config tests for warehouse GADEN defaults

**Files:**
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_scene_config.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/scene.yaml`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: FAIL because `warehouse/scene.yaml` does not yet declare a `gaden:` block or default `use_gaden: true`.

- [ ] **Step 3: Write minimal implementation**

Update `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/scene.yaml` to add a full `gaden:` block with:
- `enabled: true`
- `project_path: /home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1`
- `playback_id: scene1`
- `sensor_topic: /gaden/sensor_reading`
- `sensor_frame: base_link`
- `fixed_frame: gaden_map`
- `map_offset_x/y/z`
- `map_roll/pitch/yaw`

Also switch `use_gaden` to `true` for `warehouse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_sim/scenes/warehouse/scene.yaml src/h2track_sim/test/test_scene_config.py
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "feat: add warehouse GADEN scene defaults"
```

### Task 2: Add a loader contract for scene GADEN configuration

**Files:**
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/scene_loader.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_scene_config.py`

- [ ] **Step 1: Write the failing test**

```python
def test_scene_loader_reads_warehouse_gaden_settings():
    pkg_share = str(Path(__file__).resolve().parents[1])
    loader = _scene_loader_module()
    warehouse = loader.load_scene_profile(pkg_share, 'warehouse')

    assert warehouse['gaden']['project_path'].endswith('h2track_warehouse/environment_configurations/config1')
    assert warehouse['gaden']['playback_id'] == 'scene1'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: FAIL until the loader-facing scene data is present and stable.

- [ ] **Step 3: Write minimal implementation**

Keep `load_scene_profile()` as the single source of truth. If needed, add helper functions in `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/scene_loader.py` for warehouse GADEN resolution, but do not duplicate parsing logic outside the loader.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_sim/launch/scene_loader.py src/h2track_sim/test/test_scene_config.py
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "refactor: expose scene-driven warehouse GADEN config"
```

## Chunk 2: Route warehouse GADEN through launch and fail fast on bad config

### Task 3: Add failing launch tests for warehouse GADEN routing

**Files:**
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_launch_timing.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/demo.launch.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/bringup.launch.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_launch_prefers_scene_gaden_defaults_for_warehouse():
    text = _launch_text('demo.launch.py')
    assert 'scene_profile.get("use_gaden"' in text or "scene_profile.get('use_gaden'" in text


def test_bringup_launch_reads_scene_specific_gaden_block():
    text = _launch_text('bringup.launch.py')
    assert 'scene_profile.get("gaden"' in text or "scene_profile.get('gaden'" in text
    assert 'gaden_project_path' in text
    assert 'gaden_playback_id' in text
    assert 'gaden_sensor_topic' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: FAIL until bringup routes the warehouse `gaden:` block.

- [ ] **Step 3: Write minimal implementation**

Update `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/bringup.launch.py` so that `_scene_defaults()`:
- reads `scene_profile['gaden']` when `use_gaden` resolves true
- sets launch configurations for `gaden_project_path`, `gaden_playback_id`, `gaden_sensor_topic`, `gaden_sensor_frame`, `gaden_fixed_frame`, and map alignment values from the scene
- no longer silently falls back to `test_env/scenarios/10x6_empty_room/...` for `warehouse`

Keep `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/demo.launch.py` scene-driven. Manual `use_gaden:=false` should still override the scene default.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_sim/launch/demo.launch.py src/h2track_sim/launch/bringup.launch.py src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "feat: route warehouse scene GADEN through launch"
```

### Task 4: Add fail-fast validation for invalid warehouse GADEN config

**Files:**
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/bringup.launch.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_launch_timing.py`

- [ ] **Step 1: Write the failing test**

```python
def test_bringup_launch_fails_fast_if_scene_gaden_config_is_missing():
    text = _launch_text('bringup.launch.py')
    assert 'raise RuntimeError' in text
    assert 'project_path' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_launch_timing.py -q`
Expected: FAIL until the fail-fast branch exists.

- [ ] **Step 3: Write minimal implementation**

In `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/launch/bringup.launch.py`, when `use_gaden` resolves true:
- error if `scene_profile` has no `gaden` block
- error if `project_path` is missing
- error if the resolved project path does not exist on disk

Do not auto-substitute the baseline room path in these cases.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_launch_timing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_sim/launch/bringup.launch.py src/h2track_sim/test/test_launch_timing.py
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "fix: fail fast on invalid warehouse GADEN config"
```

## Chunk 3: Add the external approximate warehouse GADEN scenario

### Task 5: Add failing contract tests for the external warehouse GADEN scenario

**Files:**
- Create: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/test/test_warehouse_gaden_contract.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

SCENARIO_ROOT = Path('/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse')


def test_warehouse_gaden_scenario_files_exist():
    assert (SCENARIO_ROOT / 'gaden.gproj').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'config.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'scenes' / 'scene1.yaml').exists()
    assert (SCENARIO_ROOT / 'environment_configurations' / 'config1' / 'simulations' / 'sim1' / 'sim.yaml').exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_warehouse_gaden_contract.py -q`
Expected: FAIL because the scenario does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the external warehouse scenario files under `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/`:
- `gaden.gproj`
- `cad_models/h2track_warehouse_shell.stl`
- `cad_models/h2track_warehouse_racks.stl`
- `environment_configurations/config1/config.yaml`
- `environment_configurations/config1/scenes/scene1.yaml`
- `environment_configurations/config1/simulations/sim1/sim.yaml`

Use the existing `10x6_empty_room` files as format references only. Keep the geometry approximate but warehouse-shaped.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_warehouse_gaden_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_sim/test/test_warehouse_gaden_contract.py
git -C /home/user/gaden_ws add src/gaden/test_env/scenarios/h2track_warehouse
git -C /home/user/gaden_ws commit -m "feat: add approximate h2track warehouse GADEN scenario"
```

### Task 6: Rebuild external GADEN workspace and prepare warehouse playback assets

**Files:**
- Modify as needed under: `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/...`

- [ ] **Step 1: Build the external workspace**

Run: `cd /home/user/gaden_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select test_env gaden_environment gaden_player simulated_gas_sensor`
Expected: PASS.

- [ ] **Step 2: Generate or copy the warehouse configuration assets**

Make sure the external scenario contains a valid approximate warehouse config with:
- `config.yaml` pointing at the warehouse CAD/STL files and wind source prefix
- `scene1.yaml` referencing `sim1`
- `sim.yaml` pointing at the intended warehouse leak source position

- [ ] **Step 3: Run a lightweight contract check**

Run: `find /home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse -maxdepth 4 -type f | sort`
Expected: shows `gaden.gproj`, `config.yaml`, `scene1.yaml`, and `sim.yaml`.

- [ ] **Step 4: Commit**

```bash
git -C /home/user/gaden_ws add src/gaden/test_env/scenarios/h2track_warehouse
git -C /home/user/gaden_ws commit -m "chore: prepare warehouse GADEN playback assets"
```

## Chunk 4: Verify warehouse runtime behavior and operational tooling

### Task 7: Make demo_prep reflect warehouse GADEN defaults in auto mode

**Files:**
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking/h2track_tracking/demo_prep.py`
- Modify: `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_warehouse_auto_mode_requires_gaden_packages_when_scene_defaults_true(capsys):
    exit_code = main(
        ['--scene', 'warehouse'],
        ps_output='',
        package_resolver=lambda name: None if name in ('simulated_gas_sensor', 'gaden_player') else f'/prefix/{name}',
        scene_profile_loader=lambda scene_name: {'world': 'scenes/warehouse/warehouse.world', 'use_gaden': True},
        package_share_resolver=lambda package_name: '/tmp/h2track',
    )
    assert exit_code == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: FAIL until warehouse defaults to `use_gaden: true` and demo prep follows that path.

- [ ] **Step 3: Write minimal implementation**

If needed, update `/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking/h2track_tracking/demo_prep.py` so that `--scene warehouse --use-gaden auto` requires GADEN packages once the scene default is enabled.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add src/h2track_tracking/h2track_tracking/demo_prep.py src/h2track_tracking/test/test_demo_prep.py
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "fix: align demo prep with warehouse GADEN defaults"
```

### Task 8: Perform end-to-end warehouse verification and document the runbook

**Files:**
- Create: `/home/user/h2track-xian/.worktrees/dual-scene-platform/docs/warehouse-gaden-runbook.md`

- [ ] **Step 1: Verify full test suite stays green**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 2: Rebuild both workspaces**

Run:
- `cd /home/user/gaden_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select test_env gaden_environment gaden_player simulated_gas_sensor`
- `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && colcon build --packages-select h2track_tracking h2track_sim`
Expected: PASS for both.

- [ ] **Step 3: Verify warehouse default GADEN launch**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && source install/setup.bash && ros2 launch h2track_sim demo.launch.py scene:=warehouse use_rviz:=false headless:=true`
Expected: `gaden_environment`, `gaden_player`, `gaden_sensor_gate_node`, and `gaden_adapter_node` start; `gas_field_node` does not.

- [ ] **Step 4: Verify live runtime parameters**

Run:
- `ros2 param get /gaden_environment projectPath`
- `ros2 param get /gaden_player projectPath`
- `ros2 param get /gaden_player playbackID`

Expected: project path points into `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1` and playback id is `scene1`.

- [ ] **Step 5: Verify fallback path still works**

Run: `cd /home/user/h2track-xian/.worktrees/dual-scene-platform && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run h2track_tracking demo_prep --scene warehouse --use-gaden false --dry-run`
Expected: `DEMO PREP OK` without requiring GADEN packages.

- [ ] **Step 6: Write runbook**

Create `/home/user/h2track-xian/.worktrees/dual-scene-platform/docs/warehouse-gaden-runbook.md` documenting:
- required environment sourcing order
- warehouse GADEN scene path
- default and fallback launch commands
- expected runtime nodes
- common failure modes for missing external scenario assets or bad frame alignment

- [ ] **Step 7: Commit**

```bash
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform add docs/warehouse-gaden-runbook.md
git -C /home/user/h2track-xian/.worktrees/dual-scene-platform commit -m "docs: add warehouse GADEN runbook"
```
