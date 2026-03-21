# Rehearsal Flow Design

**Goal:** Add a standard pre-demo rehearsal flow that tells the operator, quickly and consistently, whether the H2track stage demo is ready to present.

## Scope

This feature is documentation-first. It does not add a new launch script or orchestration service. Instead, it formalizes the three commands the operator should run before a formal demo and captures the pass/fail rules in a reusable checklist.

The standard rehearsal flow is:

1. `demo_prep`
2. `demo.launch.py`
3. `demo_selfcheck`

If any step fails, the system is treated as not ready for a formal demonstration.

## Responsibilities

The new documentation must do two jobs:

1. Put the official command order into the README so the workflow is visible from the project entry point.
2. Provide a short checklist document that the operator can follow during rehearsal or immediately before a live demo.

The checklist should be operational, not explanatory. It should focus on actions, pass conditions, and stop conditions.

## Standard Pass/Fail Rules

The workflow uses strict, binary criteria.

### Step 1: `demo_prep`
Pass when the command prints `DEMO PREP OK`.

Fail when it prints `DEMO PREP FAILED`, cannot clear stale H2track demo processes, or reports missing required ROS packages. If this step fails, do not launch the demo.

### Step 2: `demo.launch.py`
Pass when Gazebo starts, the robot is spawned, and the launch remains running normally.

Fail when Gazebo reports `Address already in use`, the robot does not spawn, or the launch exits immediately. If this step fails, return to step 1 rather than repeatedly relaunching blindly.

### Step 3: `demo_selfcheck`
Pass when the command prints `DEMO SELFCHECK OK`.

Fail when required nodes, topics, TF edges, or Nav2 lifecycle states are missing. If this step fails, the system is still considered not ready for a live demo even if Gazebo is running.

## Deliverables

- Update `README.md` with a new “Standard Demo Rehearsal Flow” section.
- Add `docs/rehearsal-checklist.md` as a concise operator checklist.
- Add light regression tests to keep the documented workflow stable.

## File Plan

- Modify `README.md`
  - Add the three-step rehearsal flow and the stop rule for failures.
- Create `docs/rehearsal-checklist.md`
  - One-page operator checklist with commands and pass/fail criteria.
- Create `src/h2track_tracking/test/test_rehearsal_docs.py`
  - Verify the README and checklist both preserve the official command order and success criteria.

## Success Criteria

The feature is complete when:

- the README documents the official three-step rehearsal flow
- a standalone checklist exists under `docs/`
- tests protect the existence of the checklist and the key workflow text
- the docs clearly distinguish between “ready for demo” and “not ready for demo”
