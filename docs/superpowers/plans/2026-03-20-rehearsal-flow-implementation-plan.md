# Rehearsal Flow Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document and protect the standard H2track pre-demo rehearsal flow in the README and a dedicated operator checklist.

**Architecture:** Keep this change documentation-focused. Update the README with the official three-step sequence and add a short checklist under `docs/`. Add light pytest coverage that asserts the command order and pass/fail language remain in place.

**Tech Stack:** Markdown, Python 3, pytest.

---

## Chunk 1: Add Regression Tests for the Rehearsal Docs

### Task 1: Add failing tests for the README and checklist

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_rehearsal_docs.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_rehearsal_docs.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_readme_documents_standard_demo_rehearsal_flow():
    ...

def test_rehearsal_checklist_exists_with_stop_rules():
    ...
```

- [ ] **Step 2: Run the focused test file to confirm it fails**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_rehearsal_docs.py -q`
Expected: FAIL because the new README section and checklist file do not exist yet.

## Chunk 2: Write the Documentation

### Task 2: Update the README with the official rehearsal flow

**Files:**
- Modify: `/home/user/h2track-xian/README.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_rehearsal_docs.py`

- [ ] **Step 1: Add the new README section**

```markdown
## Standard Demo Rehearsal Flow
1. Run `demo_prep`
2. Launch `demo.launch.py`
3. Run `demo_selfcheck`
```

- [ ] **Step 2: Re-run the focused test file**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_rehearsal_docs.py -q`
Expected: still FAIL because the checklist file is missing.

### Task 3: Add the operator checklist

**Files:**
- Create: `/home/user/h2track-xian/docs/rehearsal-checklist.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_rehearsal_docs.py`

- [ ] **Step 1: Write the checklist**

```markdown
# Rehearsal Checklist
- Step 1: `demo_prep`
- Step 2: `demo.launch.py`
- Step 3: `demo_selfcheck`
```

- [ ] **Step 2: Re-run the focused test file**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_rehearsal_docs.py -q`
Expected: PASS.

## Chunk 3: Full Verification

### Task 4: Run the full test suite

**Files:**
- Modify: `/home/user/h2track-xian/README.md`
- Create: `/home/user/h2track-xian/docs/rehearsal-checklist.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_rehearsal_docs.py`

- [ ] **Step 1: Run the full test suite**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 2: Review the rendered docs text for the final command order**

Check: `README.md` and `docs/rehearsal-checklist.md` both show `demo_prep -> demo.launch.py -> demo_selfcheck` and clearly state that any failure means the system is not ready for a live demo.
