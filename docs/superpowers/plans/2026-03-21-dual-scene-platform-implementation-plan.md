# Dual-Scene Platform Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `/home/user/h2track-xian` into a dual-scene research platform that keeps the current simple environment as `baseline` while adding a self-contained `warehouse` scene for more realistic navigation and gas-tracking validation.

**Architecture:** Extract scene-specific world, map, patrol, source, and launch parameters out of the current single-scene demo path and make `scene:=baseline|warehouse` an explicit runtime concept. Keep the robot model, Nav2 core chain, mission logic, GADEN adapter, and tool commands shared; duplicate only the scene assets and scene configs needed to isolate environment behavior.

**Tech Stack:** ROS 2 Humble, Gazebo Classic, Nav2, GADEN playback, Python `rclpy`, ROS 2 launch, pytest, YAML, SDF world assets.

---

## File Structure

### Existing files to modify
- `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- `/home/user/h2track-xian/src/h2track_sim/config/demo.yaml`
- `/home/user/h2track-xian/src/h2track_sim/worlds/h2track_lab.world`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py`
- `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_mission_logic.py`
- `/home/user/h2track-xian/README.md`

### New files to create
- `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/scene.yaml`
- `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/h2track_lab.world`
- `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/scene.yaml`
- `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/warehouse.world`
- `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/models/...`
- `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/materials/...`
- `/home/user/h2track-xian/src/h2track_sim/test/test_scene_config.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_scene_source_geometry.py`
- `/home/user/h2track-xian/docs/scene-runbook.md`

## Chunk 1: Promote `baseline` into an explicit scene

### Task 1: Move the current lab assets into a `baseline` scene directory

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/scene.yaml`
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/h2track_lab.world`
- Create: `/home/user/h2track-xian/src/h2track_sim/test/test_scene_config.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/worlds/h2track_lab.world`
- Modify: `/home/user/h2track-xian/src/h2track_sim/config/demo.yaml`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_baseline_scene_yaml_exists():
    path = Path("/home/user/h2track-xian/src/h2track_sim/scenes/baseline/scene.yaml")
    assert path.exists()


def test_baseline_scene_yaml_declares_world_and_source():
    text = Path("/home/user/h2track-xian/src/h2track_sim/scenes/baseline/scene.yaml").read_text(encoding="utf-8")
    assert "world:" in text
    assert "gas_source:" in text
    assert "mission_manager:" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: FAIL because the `baseline` scene files do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a `baseline` scene directory and move the current simple scene definition into it:
- copy the current lab world into `scenes/baseline/h2track_lab.world`
- create `scene.yaml` with the baseline world path, initial pose, patrol points, gas source, and mission thresholds
- keep `demo.yaml` as a thin wrapper or compatibility layer, not the long-term home of scene data

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/scenes/baseline src/h2track_sim/config/demo.yaml src/h2track_sim/test/test_scene_config.py
git -C /home/user/h2track-xian commit -m "refactor: promote baseline scene into explicit config"
```

### Task 2: Make launch accept an explicit `scene` parameter

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_bringup_declares_scene_launch_argument():
    text = _launch_text("bringup.launch.py")
    assert "scene" in text


def test_demo_launch_passes_scene_to_bringup():
    text = _launch_text("demo.launch.py")
    assert "scene" in text
    assert "baseline" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: FAIL because launch files do not expose an explicit scene yet.

- [ ] **Step 3: Write minimal implementation**

Update launch so that:
- `bringup.launch.py` accepts `scene:=baseline|warehouse`
- scene selection resolves the correct scene config and world path
- `demo.launch.py` forwards `scene` explicitly instead of hiding the environment choice in `demo.yaml`

Keep `baseline` as the default during the refactor so existing smoke tests still have a stable path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/launch/bringup.launch.py src/h2track_sim/launch/demo.launch.py src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py
git -C /home/user/h2track-xian commit -m "feat: add explicit scene selection to launch"
```

## Chunk 2: Add the self-contained warehouse environment

### Task 3: Vendor the complete warehouse world assets into the repo

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/warehouse.world`
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/models/...`
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/materials/...`
- Create: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/scene.yaml`
- Modify: `/home/user/h2track-xian/README.md`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path


def test_warehouse_scene_files_exist():
    root = Path("/home/user/h2track-xian/src/h2track_sim/scenes/warehouse")
    assert (root / "scene.yaml").exists()
    assert (root / "warehouse.world").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: FAIL because the warehouse scene has not been created yet.

- [ ] **Step 3: Write minimal implementation**

Copy the selected complete warehouse world assets into the repo under `scenes/warehouse/`:
- world file
- referenced models
- referenced materials and textures
- scene config with placeholder source and patrol geometry

Document any upstream origin in comments or README, but keep runtime self-contained inside `h2track-xian`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_scene_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/scenes/warehouse README.md
git -C /home/user/h2track-xian commit -m "feat: vendor self-contained warehouse scene assets"
```

### Task 4: Make the warehouse scene independently startable with Nav2

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/scene.yaml`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_launch_supports_warehouse_scene():
    text = _launch_text("demo.launch.py")
    assert "warehouse" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: FAIL because the launch path does not yet route scene-specific world/config values cleanly for `warehouse`.

- [ ] **Step 3: Write minimal implementation**

Wire `warehouse` scene selection through the bringup stack:
- resolve the scene-specific world path
- load warehouse patrol/source defaults
- keep baseline behavior unchanged
- ensure Gazebo receives model/material search paths for vendored warehouse assets

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/launch/bringup.launch.py src/h2track_sim/launch/demo.launch.py src/h2track_sim/scenes/warehouse/scene.yaml src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py
git -C /home/user/h2track-xian commit -m "feat: support warehouse scene startup"
```

## Chunk 3: Align gas-tracking semantics with scene geometry

### Task 5: Move source geometry and patrol defaults into per-scene configs

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/scenes/baseline/scene.yaml`
- Modify: `/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/scene.yaml`
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_scene_source_geometry.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_scene_source_geometry_is_loaded_from_scene_config():
    data = load_scene_config("baseline")
    assert tuple(data["gas_source"].values())[:2]
    assert data["mission_manager"]["patrol_points"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_scene_source_geometry.py -q`
Expected: FAIL because there is no scene-config loader abstraction yet.

- [ ] **Step 3: Write minimal implementation**

Introduce a small loader or helper that reads the selected scene config and feeds:
- initial pose
- patrol points
- gas source
- mission thresholds

into `mission_manager_node.py` without duplicating the values in multiple config files.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_scene_source_geometry.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/mission_manager_node.py src/h2track_sim/scenes/baseline/scene.yaml src/h2track_sim/scenes/warehouse/scene.yaml src/h2track_tracking/test/test_scene_source_geometry.py
git -C /home/user/h2track-xian commit -m "refactor: load source and patrol geometry from scene configs"
```

### Task 6: Keep `SOURCE_FOUND` scene-correct in both environments

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_mission_logic.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_scene_source_geometry.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_source_found_requires_actual_source_in_warehouse_scene():
    config = MissionConfig(
        patrol_points=[(0.0, 0.0)],
        enter_threshold=1.0,
        exit_threshold=0.5,
        source_threshold=4.0,
        confirm_samples=2,
        source_radius=0.8,
        source_hold_steps=2,
        actual_source=(-4.0, 1.0),
    )
    machine = MissionStateMachine(config)
    machine.mode = MissionMode.SEEK_TRACK
    machine.update(5.0, (-1.0, 1.0), False)
    machine.update(5.0, (-1.0, 1.0), False)
    assert machine.mode is not MissionMode.SOURCE_FOUND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_mission_logic.py src/h2track_tracking/test/test_scene_source_geometry.py -q`
Expected: FAIL if the scene config or loader path bypasses the real-source constraint.

- [ ] **Step 3: Write minimal implementation**

Audit the scene-driven loader path so both `baseline` and `warehouse` always wire `actual_source` through to `MissionConfig`. Do not allow per-scene launch shortcuts that bypass the real-source requirement.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_mission_logic.py src/h2track_tracking/test/test_scene_source_geometry.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/mission_logic.py src/h2track_tracking/test/test_mission_logic.py src/h2track_tracking/test/test_scene_source_geometry.py
git -C /home/user/h2track-xian commit -m "test: enforce real source geometry across scenes"
```

## Chunk 4: Document and verify the new platform

### Task 7: Document scene workflows and verification commands

**Files:**
- Create: `/home/user/h2track-xian/docs/scene-runbook.md`
- Modify: `/home/user/h2track-xian/README.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_scene_runbook_exists():
    assert Path("/home/user/h2track-xian/docs/scene-runbook.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_rehearsal_docs.py -q`
Expected: FAIL because the runbook does not exist yet or README lacks the new scene workflow.

- [ ] **Step 3: Write minimal implementation**

Document:
- how to launch `baseline`
- how to launch `warehouse`
- which commands to run before and after
- which scene to use for algorithm debugging vs realism validation

Keep the document operational and short; do not turn it into a long report.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_rehearsal_docs.py -q`
Expected: PASS after updating the doc test or adding a focused doc test for the scene runbook.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add docs/scene-runbook.md README.md
git -C /home/user/h2track-xian commit -m "docs: add dual-scene runbook"
```

### Task 8: Run final verification across both scenes

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_scene_source_geometry.py`

- [ ] **Step 1: Add final verification assertions**

```python
def test_supported_scenes_are_baseline_and_warehouse():
    scenes = discover_scene_names()
    assert scenes == {"baseline", "warehouse"}
```

- [ ] **Step 2: Run focused tests**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py src/h2track_tracking/test/test_scene_source_geometry.py -q`
Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 4: Run build verification**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && colcon build --packages-select h2track_tracking h2track_sim`
Expected: Build succeeds with both scenes present.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py src/h2track_tracking/test/test_scene_source_geometry.py
git -C /home/user/h2track-xian commit -m "test: verify dual-scene platform"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-21-dual-scene-platform-implementation-plan.md`. Ready to execute?
