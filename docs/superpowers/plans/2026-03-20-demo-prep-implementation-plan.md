# Demo Prep Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone `demo_prep` CLI that kills stale H2track demo processes and verifies required ROS packages before launch.

**Architecture:** Implement `demo_prep` as a small Python CLI inside `h2track_tracking`, centered on pure helper functions for process matching and package visibility so the behavior is easy to test. Keep launch/runtime checks out of this command; it complements `demo_selfcheck` rather than replacing it.

**Tech Stack:** Python 3, ROS 2 `ament_python`, `ament_index_python`, `pytest`, standard library `argparse`, `os`, `signal`, and `subprocess`.

---

## Chunk 1: Add Process Matching and Report Logic

### Task 1: Add failing tests for process matching and status rules

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_matches_only_h2track_demo_processes():
    ...

def test_dry_run_reports_not_ready_when_stale_processes_exist():
    ...

def test_missing_packages_fail_the_report():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: FAIL because `h2track_tracking.demo_prep` does not exist yet.

### Task 2: Implement minimal demo_prep helpers

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_prep.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Implement minimal pure helpers**

```python
def find_stale_processes(ps_output: str) -> list[MatchedProcess]:
    ...

def evaluate_prep_result(...):
    ...
```

- [ ] **Step 2: Run the focused test file**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: PASS.

## Chunk 2: Add CLI Behavior and Wiring

### Task 3: Add failing tests for package checks and kill behavior plumbing

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Add tests for package visibility and dry-run output**

```python
def test_package_check_marks_missing_packages():
    ...

def test_cli_dry_run_does_not_kill_processes():
    ...
```

- [ ] **Step 2: Run the focused test file to confirm RED**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: FAIL on missing CLI behavior.

### Task 4: Implement CLI main and package checks

**Files:**
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_prep.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/setup.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Implement CLI main**

```python
def main(argv: list[str] | None = None) -> int:
    ...
```

- [ ] **Step 2: Add entry point**

```python
"demo_prep = h2track_tracking.demo_prep:main",
```

- [ ] **Step 3: Run focused tests**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_prep.py -q`
Expected: PASS.

## Chunk 3: Document and Verify the Workflow

### Task 5: Update README and run full verification

**Files:**
- Modify: `/home/user/h2track-xian/README.md`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/setup.py`
- Modify: `/home/user/h2track-xian/src/h2track_tracking/h2track_tracking/demo_prep.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_prep.py`

- [ ] **Step 1: Document the prep command in the README**

```bash
ros2 run h2track_tracking demo_prep
ros2 run h2track_tracking demo_prep --dry-run
```

- [ ] **Step 2: Run the full test suite**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 3: Rebuild the affected packages**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && colcon build --packages-select h2track_tracking h2track_sim`
Expected: build succeeds.

- [ ] **Step 4: Smoke-test the command**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && source /home/user/h2track-xian/install/setup.bash && ros2 run h2track_tracking demo_prep --dry-run`
Expected: command prints package status and any matching stale processes without killing them.
