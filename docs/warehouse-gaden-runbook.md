# Warehouse GADEN Runbook

## Environment Setup

Run commands from the dual-scene worktree:

```bash
cd /home/user/h2track-xian/.worktrees/dual-scene-platform
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
```

## External Warehouse Scenario

The warehouse scene now defaults to the external GADEN project at:

```text
/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1
```

Key runtime assets under that path:
- `OccupancyGrid3D.csv`
- `wind/`
- `simulations/sim1/result/`
- `scenes/scene1.yaml`
- `simulations/sim1/sim.yaml`

## Default Warehouse Launch

```bash
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_rviz:=false headless:=true
```

Expected GADEN-side nodes:
- `/gaden_environment`
- `/gaden_player`
- `/gaden_sensor_gate_node`
- `/gaden_pid_sensor`
- `/gaden_adapter_node`

Expected non-GADEN behavior:
- `gas_field_node` should not start in the default warehouse launch
- `gaden_environment` and `gaden_player` should both report `projectPath` under `h2track_warehouse`
- `gaden_player` should use `playbackID = scene1`

Useful checks while the launch is running:

```bash
ros2 node list
ros2 param get /gaden_environment projectPath
ros2 param get /gaden_player projectPath
ros2 param get /gaden_player playbackID
```

## Explicit Simplified-Field Fallback

To force the old simplified gas field instead of GADEN:

```bash
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_gaden:=false use_rviz:=false headless:=true
```

For a quick preflight check without requiring GADEN packages:

```bash
ros2 run h2track_tracking demo_prep --scene warehouse --use-gaden false --dry-run
```

Expected output when no stale processes are active:

```text
package ok: h2track_sim
package ok: h2track_tracking
DEMO PREP OK
```

## Common Failure Modes

### 1. `gaden_environment` or `gaden_player` exits with `File could not be found`

Root cause in this integration was missing scenario assets under `projectPath`, especially:
- `OccupancyGrid3D.csv`
- `wind/`
- `simulations/sim1/result/`

If this happens, inspect:

```bash
find -L /home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse/environment_configurations/config1 -maxdepth 4 \( -type f -o -type l \) | sort
```

### 2. `ros2 param get /gaden_environment ...` returns the wrong project path

Root cause was stale old GADEN processes from another scenario using the same node names, for example an old `Exp_C` launch.

Check for collisions:

```bash
ps -ef | rg "gaden_environment|gaden_player"
```

Stop stale processes before trusting runtime queries.

### 3. `demo_prep --dry-run` fails during an active launch

This is expected. `demo_prep` treats active Gazebo/Nav2 processes as stale and returns:

```text
DEMO PREP FAILED
- dry-run found stale processes
```

Stop the running demo first, then rerun `demo_prep`.

### 4. TF gate waits on `gaden_map -> base_link`

This is expected during early startup. The sensor gate should eventually log:

```text
TF ready; launching simulated_gas_sensor
```

If it never does, inspect the static `gaden_map -> map` transform and the robot spawn / odom chain.

## Notes

This first warehouse GADEN integration is intentionally approximate:
- warehouse geometry is custom and simplified
- wind and playback assets are currently reused to keep the scene runnable
- the scene is now scene-owned and no longer falls back to the baseline room path by default
