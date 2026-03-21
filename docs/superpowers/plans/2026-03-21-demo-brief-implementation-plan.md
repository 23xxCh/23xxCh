# Demo Brief Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-page live demo brief for advisor-facing use and protect its section structure with a lightweight test.

**Architecture:** Keep the change documentation-only. Write the brief under `docs/` with four short sections and add a small pytest file that checks the document exists and preserves the expected structure.

**Tech Stack:** Markdown, Python 3, pytest.

---

## Chunk 1: Add Regression Test

### Task 1: Add a failing test for the demo brief

**Files:**
- Create: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_brief_docs.py`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_brief_docs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_demo_brief_exists_with_required_sections():
    ...
```

- [ ] **Step 2: Run the focused test file to confirm it fails**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_brief_docs.py -q`
Expected: FAIL because `docs/demo-brief.md` does not exist yet.

## Chunk 2: Write the Demo Brief

### Task 2: Create the brief document

**Files:**
- Create: `/home/user/h2track-xian/docs/demo-brief.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_brief_docs.py`

- [ ] **Step 1: Write the one-page brief**

```markdown
# Demo Brief
## Project Goal
## Live Demo Flow
## What To Watch During The Demo
## Closing Summary
```

- [ ] **Step 2: Re-run the focused test file**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test/test_demo_brief_docs.py -q`
Expected: PASS.

## Chunk 3: Full Verification

### Task 3: Run the full test suite and review the final brief

**Files:**
- Create: `/home/user/h2track-xian/docs/demo-brief.md`
- Test: `/home/user/h2track-xian/src/h2track_tracking/test/test_demo_brief_docs.py`

- [ ] **Step 1: Run the full test suite**

Run: `cd /home/user/h2track-xian && source /opt/ros/humble/setup.bash && PYTHONPATH='/home/user/h2track-xian/src/h2track_tracking:'"$PYTHONPATH" python3 -m pytest src/h2track_tracking/test src/h2track_sim/test -q`
Expected: PASS.

- [ ] **Step 2: Review the final brief text**

Check: `docs/demo-brief.md` is concise, advisor-facing, and keeps the approved four-part structure.
