# 2-Minute Demo Script Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chinese-only two-minute live demo speaking script and protect its structure with a lightweight regression test.

**Architecture:** Keep the change documentation-only. Add a small pytest file that locks in the three required sections and required demo terms, then write the final script under `docs/` using concise spoken Chinese.

**Tech Stack:** Markdown, Python 3, pytest.

---

## Chunk 1: Add Regression Test

### Task 1: Add a failing test for the demo script

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_script_docs.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_script_docs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_demo_script_exists_with_required_sections():
    ...
```

- [ ] **Step 2: Run the focused test file to confirm it fails**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_script_docs.py -q`
Expected: FAIL because `docs/demo-script-2min.md` does not exist yet.

## Chunk 2: Write the Script

### Task 2: Create the two-minute speaking script

**Files:**
- Create: `/home/user/h2track-xian/docs/demo-script-2min.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_script_docs.py`

- [ ] **Step 1: Write the Chinese script**

```markdown
# 2-Minute Demo Script
## 开场
## 演示过程
## 结束总结
```

- [ ] **Step 2: Re-run the focused test file**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_script_docs.py -q`
Expected: PASS.

## Chunk 3: Full Verification

### Task 3: Run the full test suite and review the final script

**Files:**
- Create: `/home/user/h2track-xian/docs/demo-script-2min.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_script_docs.py`

- [ ] **Step 1: Run the full test suite**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 2: Review the final script text**

Check: `docs/demo-script-2min.md` is concise, Chinese-only, easy to read aloud, and keeps the approved three-part structure.
