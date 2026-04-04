# h2track-xian

A clean ASCII-path rebuild of the H2 hydrogen tracking simulation workspace.

## Layout

- Project root: `/home/user/h2track-xian`
- External GADEN workspace: `/home/user/gaden_ws`

## Build

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
colcon build
```

## Launch with the simplified gas field

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch h2track_sim bringup.launch.py use_gaden:=false
```

## Launch with GADEN playback

The external GADEN workspace is expected to have preprocessing and `sim1` results already generated under the official `test_env` sample project.

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 launch h2track_sim bringup.launch.py use_gaden:=true use_rviz:=true
```

## Launch with SLAM mapping + GADEN (warehouse)

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 launch h2track_sim slam_demo.launch.py use_rviz:=true headless:=false
```

## Save map from SLAM

After SLAM run is stable, save the built map:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run h2track_tracking slam_save_map --output /home/user/h2track-xian/src/h2track_sim/scenes/warehouse/maps/warehouse_slam_map
```

## Switch back to static-map navigation with the saved map

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_slam:=false nav2_map_file:=/home/user/h2track-xian/src/h2track_sim/scenes/warehouse/maps/warehouse_slam_map.yaml use_rviz:=true
```


## Demo prep

Run this before launching the stage demo to clear stale H2track Gazebo/Nav2 processes and confirm the required ROS packages are visible in the current shell.

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_prep
```

Preview mode:

```bash
ros2 run h2track_tracking demo_prep --dry-run
```

## Web Console (Warehouse One-Click)

Install the web runtime dependencies once (Ubuntu/Debian recommended):

```bash
sudo apt-get update
sudo apt-get install -y python3-fastapi python3-uvicorn
```

Alternative (if you use a Python venv):

```bash
python -m pip install fastapi uvicorn
```

Start the web console:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080
```

Open in browser:

```text
http://<your-machine-ip>:18080
```

Frontend is now served from a built React bundle (`h2track_tracking/static_console`) by default.  
If you modify UI code under `src/h2track_tracking/web_console`, rebuild with:

```bash
cd /home/user/h2track-xian/src/h2track_tracking/web_console
npm install
npm run build
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
colcon build --packages-select h2track_tracking
```

The page provides:

- `Start Simulation`: runs `demo_prep` then launches simulation with the selected launch profile
- `Stop Simulation`: sends SIGINT to the current launch process group
- `Export Diagnostics`: writes a zip artifact to `artifacts/diag/`
- `Export Run Report`: writes JSON + Markdown run reports to `artifacts/reports/`
- live logs via SSE (`/api/logs/stream`)
- phase timeline panel
- topic health panel (`/gas_concentration`, `/robot_mode`, `/source_found`, `/odom`)
- node health panel (core Nav2 + mission + GADEN nodes)
- real-time metric cards (mode, gas concentration trend, source_found, nav quality)
- AI assistant panel:
  - configure multiple OpenAI-compatible model profiles (`URL/API key/model/protocol`)
  - natural-language chat with structured system context (status + metrics + logs + recent reports)
  - suggested actions with manual execution
  - one-cycle auto loop (`analyze -> suggest -> execute`)
  - execution audit table for AI-triggered actions

The upgraded React console is organized into three tabs:

- `总览`: simulation control, KPI cards, gas trend, phase timeline
- `AI 策略`: model profile management, AI suggestions, action execution audit
- `诊断日志`: topic/node health tables and live filtered logs

Additional API:

- `GET /api/metrics/recent?limit=120`: returns in-memory metric snapshot and short history for dashboard rendering
- `GET /api/health/nodes`: returns latest node-health snapshot
- `POST /api/diag/export`: creates a diagnostic bundle and returns the artifact path
- `POST /api/report/export`: creates a JSON+Markdown run report and returns artifact paths
- `GET /api/llm/profiles`: list model profiles (API key masked)
- `POST /api/llm/profiles`: create/update a model profile
- `POST /api/llm/profiles/{id}/activate`: set active profile
- `POST /api/llm/profiles/{id}/check`: connectivity check for a profile
- `DELETE /api/llm/profiles/{id}`: delete a profile
- `POST /api/llm/chat`: AI analysis + structured suggested actions
- `POST /api/llm/action/execute`: execute one suggested action
- `POST /api/llm/loop/run-once`: run one AI cycle
- `GET /api/llm/history`: read AI conversation history
- `GET /api/llm/audit`: read action execution audit logs

LLM profile storage (plaintext by design):

- `~/.config/h2track/llm_profiles.json`


## Demo self-check

Run this after bringup to confirm the stage-demo stack has the expected nodes, topics, TF edges, and active Nav2 lifecycle nodes.


## Standard Demo Rehearsal Flow

Use this exact sequence before a formal demo.

1. Clear stale H2track demo processes and verify package visibility:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_prep
```

2. Launch the formal demo stack:

```bash
ros2 launch h2track_sim demo.launch.py use_rviz:=true headless:=false
```

3. Verify the runtime stack after bringup:

```bash
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
```

## Demo regression

Run multi-round stability checks for the current scene profile and report source-finding success rate.

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_regression --scene warehouse --use-gaden true --rounds 3 --run-timeout-sec 110
```

Compare SLAM vs non-SLAM regression behavior:

```bash
# Scene default SLAM behavior
ros2 run h2track_tracking demo_regression --scene warehouse --use-gaden true --use-slam auto --rounds 1 --run-timeout-sec 180

# Force static-map localization behavior
ros2 run h2track_tracking demo_regression --scene warehouse --use-gaden true --use-slam false --rounds 1 --run-timeout-sec 180
```

If any step fails, do not start the formal demo. Return to step 1 and fix the issue first.

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
```

## Scene Assets

- `src/h2track_sim/scenes/warehouse/` vendors the AWS RoboMaker Small Warehouse World runtime assets from `aws-robotics/aws-robomaker-small-warehouse-world` under the upstream `MIT-0` license.
- The vendored warehouse scene keeps only the runtime world/models needed by Gazebo; upstream docs/images/launch helpers are not copied into the project.

## Notes

- `use_gaden:=false` uses `gas_field_node` to publish `/gas_concentration`.
- `use_gaden:=true` starts `gaden_environment`, `gaden_player`, `gaden_sensor_gate_node`, `gaden_adapter_node`, and a static `gaden_map -> map` transform; the gate node waits for TF connectivity before launching `simulated_gas_sensor`.
- `use_slam:=true` routes Nav2 bringup through `slam_toolbox`; `mission_manager_node` switches to TF-based pose refresh (`map <- base_link`) and does not require `/amcl_pose` to become available.
- The Nav2 configuration is limited to `navigate_to_pose` to avoid the old `ComputePathThroughPoses` BT issue from the previous repo.
