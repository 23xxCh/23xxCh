# Stable Demo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-command, stage-demo-focused H2 leak tracking flow in `/home/user/h2track-xian` that reliably completes patrol -> detection -> tracking -> source found within `3-5` minutes with no manual intervention.

**Architecture:** Add a dedicated demo profile and demo launch path on top of the current `bringup.launch.py`, then stabilize the existing `Nav2 + GADEN + mission_manager` chain with stronger readiness checks, mission guard rails, and demo-specific observability. Keep `/gas_concentration`, `/robot_mode`, `/source_found`, and `use_gaden` as the stable interfaces; add narrow, demo-oriented modules rather than rewriting the whole stack.

**Tech Stack:** ROS 2 Humble, Gazebo Classic, Nav2, GADEN playback, Python `rclpy`, ROS 2 launch, pytest, RViz2.

---

## File Structure

### Existing files to modify
- `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- `/home/user/h2track-xian/src/h2track_sim/launch/nav2.launch.py`
- `/home/user/h2track-xian/src/h2track_sim/config/nav2_params.yaml`
- `/home/user/h2track-xian/src/h2track_sim/rviz/h2track_nav2.rviz`
- `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/gaden_sensor_gate.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/gaden_sensor_gate_node.py`
- `/home/user/h2track-xian/src/h2track_tracking/setup.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_mission_logic.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_gaden_sensor_gate.py`
- `/home/user/h2track-xian/README.md`

### New files to create
- `/home/user/h2track-xian/src/h2track_sim/config/demo.yaml`
- `/home/user/h2track-xian/src/h2track_sim/config/nav2_demo_params.yaml`
- `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_visualization_node.py`
- `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_selfcheck.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_visualization.py`
- `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_selfcheck.py`
- `/home/user/h2track-xian/docs/demo_runbook.md`

## Chunk 1: Freeze the demo baseline

### Task 1: Add a dedicated demo profile

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_sim/config/demo.yaml`
- Create: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_demo_profile_contains_fixed_demo_defaults():
    text = (Path(__file__).resolve().parents[1] / "config" / "demo.yaml").read_text(encoding="utf-8")
    assert "use_gaden: true" in text
    assert "patrol_points:" in text
    assert "mission_manager:" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py -q`
Expected: FAIL because `demo.yaml` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `demo.yaml` with a single stable demo profile:
- fixed robot initial pose
- fixed patrol point sequence
- fixed source position
- demo thresholds for `enter_threshold`, `exit_threshold`, `source_threshold`
- `use_gaden: true`
- demo timing values such as mission start delay and sensor gate timeout

Refactor `mission_manager_node.py` only as needed so these values can be passed cleanly as parameters without hard-coded duplication.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/config/demo.yaml src/h2track_sim/test/test_demo_launch.py src/h2track_sim/launch/bringup.launch.py src/h2track_tracking/h2track_tracking/mission_manager_node.py
git -C /home/user/h2track-xian commit -m "feat: add stable demo profile"
```

### Task 2: Add a dedicated demo launch entrypoint

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/nav2.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_launch_timing.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_launch_includes_bringup_with_demo_defaults():
    text = _launch_text("demo.launch.py")
    assert 'IncludeLaunchDescription' in text
    assert 'use_gaden' in text
    assert 'demo.yaml' in text


def test_demo_launch_uses_demo_nav2_params():
    text = _launch_text("demo.launch.py")
    assert 'nav2_demo_params.yaml' in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: FAIL because `demo.launch.py` and `nav2_demo_params.yaml` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a narrow `demo.launch.py` wrapper that:
- calls `bringup.launch.py`
- forces demo defaults from `demo.yaml`
- uses `use_gaden:=true` unless explicitly overridden for debugging
- points Nav2 at `nav2_demo_params.yaml`

Update `nav2.launch.py` so a demo-specific params file can be injected cleanly without breaking the existing integration path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/launch/demo.launch.py src/h2track_sim/launch/bringup.launch.py src/h2track_sim/launch/nav2.launch.py src/h2track_sim/test/test_demo_launch.py src/h2track_sim/test/test_launch_timing.py
git -C /home/user/h2track-xian commit -m "feat: add dedicated demo launch entrypoint"
```

## Chunk 2: Make startup deterministic

### Task 3: Strengthen GADEN sensor readiness

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/gaden_sensor_gate.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/gaden_sensor_gate_node.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_gaden_sensor_gate.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/bringup.launch.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_gate_requires_multiple_ready_checks_before_launch():
    state = SensorGateState(config=SensorGateConfig(timeout_sec=30.0, poll_period_sec=0.5, stable_ready_count=3))
    assert state.record_transform_ready() is False
    assert state.record_transform_ready() is False
    assert state.record_transform_ready() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_gaden_sensor_gate.py -q`
Expected: FAIL because the gate currently launches after the first successful readiness check.

- [ ] **Step 3: Write minimal implementation**

Extend the gate to require a short stability window before launching the child sensor process:
- add `stable_ready_count` to the gate config
- reset the counter on failed transform checks
- only launch the sensor after `N` consecutive successful checks
- expose the new parameter through `bringup.launch.py`

This targets the remaining first-frame extrapolation warning without reintroducing hard-coded blind delays.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_gaden_sensor_gate.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/gaden_sensor_gate.py src/h2track_tracking/h2track_tracking/gaden_sensor_gate_node.py src/h2track_tracking/test/test_gaden_sensor_gate.py src/h2track_sim/launch/bringup.launch.py
git -C /home/user/h2track-xian commit -m "fix: require stable tf readiness before launching gaden sensor"
```

### Task 4: Add a demo self-check utility

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_selfcheck.py`
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_selfcheck.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/setup.py`
- Modify: `/home/user/h2track-xian/README.md`

- [ ] **Step 1: Write the failing tests**

```python
def test_selfcheck_reports_missing_requirements():
    result = evaluate_demo_health(nodes=[], topics=[], tf_edges=[])
    assert result.ok is False
    assert "nav2" in result.errors[0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_demo_selfcheck.py -q`
Expected: FAIL because the self-check module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a focused demo self-check command that verifies:
- critical nodes exist
- critical topics exist
- critical TF edges are available
- Nav2 is active

Expose it as a console entry point from `h2track_tracking/setup.py` and document the command in `README.md`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_demo_selfcheck.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/demo_selfcheck.py src/h2track_tracking/test/test_demo_selfcheck.py src/h2track_tracking/setup.py README.md
git -C /home/user/h2track-xian commit -m "feat: add demo self-check utility"
```

## Chunk 3: Make the closed loop more reliable

### Task 5: Add mission guard rails for the demo path

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_logic.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/mission_manager_node.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_mission_logic.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_tracking_times_out_back_to_patrol_after_no_progress():
    machine = MissionStateMachine(MissionConfig(..., track_timeout_steps=5, retry_limit=1))
    machine.mode = MissionMode.SEEK_TRACK
    for _ in range(6):
        machine.update(concentration=5.0, robot_position=(0.0, 0.0), goal_reached=False)
    assert machine.mode is MissionMode.PATROL
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_mission_logic.py -q`
Expected: FAIL because the state machine currently has no timeout / retry guard rails.

- [ ] **Step 3: Write minimal implementation**

Extend the mission logic with demo-focused protection only:
- tracking timeout steps
- retry limit before falling back to patrol
- optional cooldown after a failed tracking attempt
- stricter source convergence handling near the goal

Keep the public mode names unchanged so existing launch and visualization wiring remains compatible.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_mission_logic.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/mission_logic.py src/h2track_tracking/h2track_tracking/mission_manager_node.py src/h2track_tracking/test/test_mission_logic.py
git -C /home/user/h2track-xian commit -m "feat: add demo-oriented mission guard rails"
```

### Task 6: Tune the demo Nav2 profile conservatively

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_sim/config/nav2_demo_params.yaml`
- Modify: `/home/user/h2track-xian/src/h2track_sim/test/test_demo_launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/config/nav2_params.yaml`

- [ ] **Step 1: Write the failing test**

```python
def test_demo_nav2_profile_is_more_conservative_than_default_profile():
    default_text = Path("src/h2track_sim/config/nav2_params.yaml").read_text(encoding="utf-8")
    demo_text = Path("src/h2track_sim/config/nav2_demo_params.yaml").read_text(encoding="utf-8")
    assert "desired_linear_vel: 0.20" in demo_text
    assert "inflation_radius: 0.55" in demo_text
    assert demo_text != default_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py -q`
Expected: FAIL because the demo Nav2 profile does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `nav2_demo_params.yaml` as a demo-only profile with conservative settings:
- slower `desired_linear_vel`
- slightly larger inflation radius
- stricter progress checker for stuck detection
- no broad structural changes to the Nav2 stack

Keep `nav2_params.yaml` as the general integration baseline.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_sim/test/test_demo_launch.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_sim/config/nav2_demo_params.yaml src/h2track_sim/config/nav2_params.yaml src/h2track_sim/test/test_demo_launch.py
git -C /home/user/h2track-xian commit -m "tune: add conservative nav2 demo profile"
```

## Chunk 4: Make the demo easy to understand on screen

### Task 7: Add a focused demo visualization node

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_visualization_node.py`
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_visualization.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/setup.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/launch/demo.launch.py`
- Modify: `/home/user/h2track-xian/src/h2track_sim/rviz/h2track_nav2.rviz`

- [ ] **Step 1: Write the failing tests**

```python
def test_visualizer_builds_marker_labels_from_demo_state():
    marker = build_mode_marker(mode="SEEK_TRACK", concentration=6.2, source_found=False)
    assert "SEEK_TRACK" in marker.text
    assert "6.2" in marker.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_demo_visualization.py -q`
Expected: FAIL because the visualization module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a visualization node that subscribes to the existing stable interfaces:
- `/robot_mode`
- `/gas_concentration`
- `/source_found`
- `/estimated_source_pose`

Publish a small set of RViz markers/text overlays:
- current mode
- current concentration
- source-found state
- estimated source pose

Keep this as a separate node so the mission manager remains focused on control logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test/test_demo_visualization.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add src/h2track_tracking/h2track_tracking/demo_visualization_node.py src/h2track_tracking/test/test_demo_visualization.py src/h2track_tracking/setup.py src/h2track_sim/launch/demo.launch.py src/h2track_sim/rviz/h2track_nav2.rviz
git -C /home/user/h2track-xian commit -m "feat: add on-screen demo visualization"
```

### Task 8: Add a demo runbook and rehearsal flow

**Files:**
- Create: `/home/user/h2track-xian/docs/demo_runbook.md`
- Modify: `/home/user/h2track-xian/README.md`

- [ ] **Step 1: Write the failing test**

```python
def test_demo_runbook_documents_primary_and_fallback_commands():
    text = Path("/home/user/h2track-xian/docs/demo_runbook.md").read_text(encoding="utf-8")
    assert "ros2 launch h2track_sim demo.launch.py" in text
    assert "use_gaden:=false" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian && python3 -m pytest -q -k demo_runbook`
Expected: FAIL because the runbook does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Document:
- primary stage-demo launch command
- fallback simplified-gas command
- pre-demo self-check command
- expected timeline of the demo
- operator checklist before meeting the advisor

Keep the runbook short and operational, not conceptual.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/user/h2track-xian && python3 -m pytest -q -k demo_runbook`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /home/user/h2track-xian add docs/demo_runbook.md README.md
git -C /home/user/h2track-xian commit -m "docs: add stable demo runbook"
```

## Verification Checklist
- Run unit tests after each task, not just at the end.
- After Chunks 1-3, run: `cd /home/user/h2track-xian && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking' python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
- After Chunk 2 and after the final chunk, run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && colcon build`
- Final runtime verification target:
  - `cd /home/user/h2track-xian`
  - `source /opt/ros/humble/setup.bash`
  - `source /home/user/gaden_ws/install/setup.bash`
  - `source install/setup.bash`
  - `timeout 300s ros2 launch h2track_sim demo.launch.py use_rviz:=false headless:=true`
- Final acceptance target:
  - the demo launch reaches patrol
  - detects gas and switches modes automatically
  - continues navigating safely
  - reaches `SOURCE_FOUND`
  - produces readable on-screen or log-visible state transitions
