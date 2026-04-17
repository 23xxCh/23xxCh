# h2track-xian

A clean ASCII-path rebuild of the H2 hydrogen tracking simulation workspace.

## Features

- **Hydrogen Source Tracking**: Gradient-based tracking with particle filter localization
- **GADEN Gas Simulation**: Realistic filament-based gas dispersion modeling
- **SLAM/AMCL Navigation**: Autonomous mapping and localization with Nav2
- **Obstacle Avoidance**: Full Nav2 stack with costmap-based collision avoidance

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

## Quick Start

### Launch with GADEN gas simulation (recommended)

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_rviz:=true
```

### Launch with simplified gas field (no GADEN dependency)

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch h2track_sim demo.launch.py scene:=warehouse use_gaden:=false use_rviz:=true
```

## GADEN Gas Simulation Notes

### Hydrogen Gas Behavior

Hydrogen (H₂) is 14x lighter than air, causing it to rapidly rise toward the ceiling. The GADEN simulation correctly models this physical phenomenon:

- Gas source at floor level (z=0.3m)
- Filaments rise to ceiling level (z≈1.8-1.9m)
- Gas sensor must be positioned at elevated height to detect rising gas

### Sensor Configuration

The gas sensor is positioned at 1.5m height in the robot URDF to detect the rising H₂ plume. Scene configurations use `gas_sensor_link` as the sensor frame:

```yaml
gaden:
  sensor_frame: gas_sensor_link  # Elevated sensor for H2 detection
  fixed_frame: gaden_map
```

If you need to modify the sensor height, edit `src/h2track_sim/urdf/h2track_bot.urdf.xacro`:

```xml
<joint name="gas_sensor_joint" type="fixed">
  <parent link="base_link"/>
  <child link="gas_sensor_link"/>
  <origin xyz="0 0 1.5"/>  <!-- Adjust z-value as needed -->
</joint>
```

## Launch with SLAM mapping

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 launch h2track_sim slam_demo.launch.py use_rviz:=true
```

## Save map from SLAM

After SLAM run is stable, save the built map:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run h2track_tracking slam_save_map --output /home/user/h2track-xian/src/h2track_sim/scenes/warehouse/maps/warehouse_slam_map
```

## Demo Prep

Run this before launching the demo to clear stale processes:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_prep --scene warehouse
```

Preview mode (no changes):

```bash
ros2 run h2track_tracking demo_prep --scene warehouse --dry-run
```

## Web Console

Install dependencies:

```bash
sudo apt-get update
sudo apt-get install -y python3-fastapi python3-uvicorn
```

Start the web console:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080
```

Open in browser: `http://<your-machine-ip>:18080`

### Web Console Features

- One-click simulation start/stop
- Real-time gas concentration monitoring
- Topic and node health panels
- Phase timeline visualization
- AI assistant integration (OpenAI-compatible)
- Diagnostic export and run reports

## Demo Self-Check

Verify the stack after bringup:

```bash
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
```

## Demo Regression Testing

Run multi-round stability checks:

```bash
ros2 run h2track_tracking demo_regression --scene warehouse --use-gaden true --rounds 3 --run-timeout-sec 110
```

## Available Scenes

| Scene | GADEN | SLAM | Description |
|-------|-------|------|-------------|
| `warehouse` | ✅ | ✅ | AWS RoboMaker Small Warehouse |
| `baseline` | ✅ | ❌ | H2Track Lab environment |

## Key Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/gas_concentration` | `Float32` | Normalized gas sensor reading |
| `/robot_mode` | `String` | Current mission state |
| `/source_found` | `Bool` | Source detection signal |
| `/estimated_source` | `PoseWithCovarianceStamped` | Particle filter estimate |
| `/map` | `OccupancyGrid` | SLAM/localization map |

## Scene Assets

- `src/h2track_sim/scenes/warehouse/` vendors assets from `aws-robotics/aws-robomaker-small-warehouse-world` under MIT-0 license.

## Configuration Notes

- `use_gaden:=false` uses simplified `gas_field_node` for gas simulation
- `use_gaden:=true` starts full GADEN stack with realistic filament-based dispersion
- `use_slam:=true` enables `slam_toolbox` for mapping
- `use_slam:=false` uses AMCL with pre-existing map

## Troubleshooting

### Gas concentration always zero

If using GADEN mode, ensure:
1. Sensor frame is `gas_sensor_link` (not `base_link`)
2. GADEN workspace is sourced: `source /home/user/gaden_ws/install/setup.bash`
3. Preprocessed GADEN data exists for the scene

### TF tree disconnected

Verify TF chain: `gaden_map` → `map` → `odom` → `base_link` → `gas_sensor_link`

```bash
ros2 run tf2_ros tf2_echo gaden_map gas_sensor_link
```

### Nav2 not navigating

Check lifecycle nodes are active:

```bash
ros2 lifecycle list /controller_server
ros2 lifecycle list /planner_server
```

## Project Statistics

- **Total Lines of Code**: ~15,000+
- **Test Coverage**: 117 tests, 100% pass rate
- **Packages**: 2 (h2track_sim, h2track_tracking)
- **Supported Gases**: 4 (H2, CH4, CO, C3H8)
- **Algorithms**: 4 (Surge-Cast, Particle Filter, Gradient, Random Walk, Spiral)

## Algorithm Performance

| Algorithm | Avg Time | Description |
|-----------|----------|-------------|
| Surge-Cast | < 0.1ms | Wind-aware navigation |
| Particle Filter | < 1ms | Probabilistic localization |
| Wind Estimator | < 0.2ms | Gradient-based estimation |
| Fusion | < 0.05ms | Algorithm combination |

## Citation

If you use this project in your research, please cite:

```bibtex
@software{h2track2026,
  title = {H2Track: Hydrogen Gas Source Localization with ROS2},
  author = {H2Track Team},
  year = {2026},
  url = {https://github.com/your-repo/h2track-xian}
}
```

## License

MIT License

## Acknowledgments

- GADEN gas dispersion simulation
- Nav2 navigation stack
- ROS2 community

## Contact

For questions or collaboration opportunities, please open an issue on GitHub.
