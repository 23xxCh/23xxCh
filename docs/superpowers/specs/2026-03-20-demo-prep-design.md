# Demo Prep Design

**Goal:** Add a standalone `demo_prep` command that clears stale H2track demo processes and verifies that the required ROS packages are visible before a stage-demo run.

## Scope

`demo_prep` is a small command-line utility inside `h2track_tracking`. It does not launch the demo and it does not replace `demo_selfcheck`. Its purpose is to make the environment safe to launch by handling the operational problem we have seen repeatedly in verification: stale `gzserver` and `lifecycle_manager_navigation` processes surviving a timed demo run and poisoning the next launch.

## Responsibilities

The command has two responsibilities only:

1. Find stale H2track demo processes and terminate them.
2. Confirm that the current shell can resolve the ROS packages needed for the GADEN demo path.

Everything else stays out of scope. It will not inspect TF, topics, lifecycle state, or launch anything. Those remain the responsibility of `demo_selfcheck` and the normal demo launch.

## Process Cleanup Rules

The cleanup step only targets processes that are clearly part of this project's demo stack:

- `gzserver` or `gazebo` processes whose command line includes the installed `h2track_lab.world` path under `/home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/`
- `nav2_lifecycle_manager/lifecycle_manager` processes that include `__node:=lifecycle_manager_navigation`

The utility should not kill unrelated Gazebo or Nav2 processes. Matching needs to be explicit and conservative.

## Environment Checks

The command verifies that the following packages are resolvable in the current shell:

- `h2track_sim`
- `h2track_tracking`
- `simulated_gas_sensor`
- `gaden_player`

This gives a fast signal that the user sourced both the H2track workspace and the external GADEN overlay before launch.

## CLI Behavior

Primary command:

```bash
ros2 run h2track_tracking demo_prep
```

Optional preview mode:

```bash
ros2 run h2track_tracking demo_prep --dry-run
```

Behavior:

- normal mode: print matched stale processes, terminate them, print package visibility results, end with `DEMO PREP OK` or `DEMO PREP FAILED`
- dry-run mode: print what would be killed, do not kill anything, still evaluate package visibility, and return non-zero if stale processes are present or packages are missing

## Output Format

The output should stay short and operational, for example:

- `stale process: gzserver pid=12345`
- `killed pid=12345`
- `package ok: h2track_sim`
- `missing package: gaden_player`
- `DEMO PREP OK`

## File Plan

- Create `src/h2track_tracking/h2track_tracking/demo_prep.py`
  - Pure helpers for process matching, package checks, report formatting, and CLI main
- Create `src/h2track_tracking/test/test_demo_prep.py`
  - TDD coverage for process matching, dry-run behavior, environment evaluation, and final status rules
- Modify `src/h2track_tracking/setup.py`
  - Register the `demo_prep` entry point
- Modify `README.md`
  - Document the new prep step before demo launch

## Success Criteria

The feature is done when:

- `ros2 run h2track_tracking demo_prep` can remove leftover H2track `gzserver` and `lifecycle_manager_navigation` processes
- it reports missing ROS packages clearly
- `--dry-run` shows what would happen without killing processes
- unit tests cover the matching and result logic
- the README includes the prep step in the demo workflow
