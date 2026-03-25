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
