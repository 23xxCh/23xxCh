# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ROS 2 Humble workspace for hydrogen (H2) gas source tracking simulation. The robot patrols a Gazebo environment, detects gas concentration changes, and locates the hydrogen source using gradient-based tracking and particle filter-based source localization.

## Build Commands

```bash
# Source dependencies and build
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash  # Required for GADEN integration
colcon build

# Run tests
pytest src/h2track_tracking/test/ -v

# Run single test file
pytest src/h2track_tracking/test/test_surge_cast.py -v
pytest src/h2track_tracking/test/test_plume_detector.py -v
pytest src/h2track_tracking/test/test_gas_model.py -v
pytest src/h2track_tracking/test/test_navigation_executor.py -v

# Run with coverage
pytest src/h2track_tracking/test/ --cov=src/h2track_tracking/h2track_tracking --cov-report=term-missing
```

## Package Structure

Eight ROS 2 packages:

| Package | Build Type | Purpose |
|---------|------------|---------|
| `h2track_bringup` | ament_cmake | Launch files, scene configs, Gazebo worlds |
| `h2track_tracking` | ament_python | Tracking logic, gas model, mission state machine, BT pipeline |
| `h2track_interfaces` | ament_cmake | Custom message types (RobotState, SourceEstimate, RoleAssignment) |
| `h2track_description` | ament_cmake | URDF/xacro robot description |
| `h2track_gas_sim` | ament_python | Gas simulation (gas_field_node, GADEN adapter) |
| `h2track_web` | ament_python | FastAPI web console, REST/WebSocket API |
| `h2track_utils` | ament_python | Shared utilities (Nav2Lifecycle, Pose2D, demo tools) |
| `h2track_sim` | ament_cmake | Metapackage (depends on bringup + description) |

## Core Architecture

### Mission State Machine

The robot transitions through these modes (defined in `mission_logic.py`):

```
PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND
```

- **PATROL**: Navigate waypoints via Nav2
- **SEEK_CONFIRM**: Verify gas detection (enter_threshold)
- **SEEK_TRACK**: Gradient ascent toward source
- **SOURCE_FOUND**: Publish estimated source position

### Key ROS Nodes

| Node | File | Purpose |
|------|------|---------|
| `mission_manager_node` | `mission_manager_node.py` | (DEPRECATED) Legacy state machine — use `bt_node_runner` |
| `bt_node_runner` | `bt_node_runner.py` | **Primary** BT-based orchestrator — replaces mission_manager_node |
| `gas_field_node` | `gas_field_node.py` | Simplified plume simulation (use_gaden:=false) |
| `gaden_adapter_node` | `gaden_adapter_node.py` | Converts GADEN sensor readings to `/gas_concentration` |
| `gaden_sensor_gate_node` | `gaden_sensor_gate.py` | Waits for TF before launching simulated_gas_sensor |
| `nav2_startup_gate_node` | `nav2_startup_gate.py` | Waits for Nav2 lifecycle readiness |
| `particle_filter_node` | `particle_filter/particle_filter_node.py` | Probabilistic gas source localization |
| `anemometer_adapter_node` | `anemometer_adapter_node.py` | Bridges GADEN `Anemometer` → `/estimated_wind` (WindEstimate) — ground-truth wind |
| `ground_truth_sampler` | `evaluation/ground_truth_sampler.py` | Samples GADEN `/odor_value` (GasPosition) for RMSE evaluation |

### Gas Simulation

Two modes:

1. **Simplified** (`use_gaden:=false`): `gas_field_node` publishes synthetic plume data based on `GasFieldModel` in `gas_model.py`
2. **GADEN** (`use_gaden:=true`): Uses external GADEN workspace for realistic filament-based gas dispersion

### MOX Sensor Model

Complete port of GADEN's `fake_gas_sensor` Figaro TGS sensor model in `h2track_gas_sim/mox_sensor_model.py`:

- **5 sensors × 7 gases**: TGS2620/TGS2600/TGS2611/TGS2610/TGS2612 × ethanol/methane/hydrogen/propanol/chlorine/fluorine/acetone
- **Static conversion**: `Rs/R0 = A * conc^B` (line in loglog scale)
- **Dynamic response**: tau-based low-pass filter with rise/decay time constants per sensor
- **PID correction factors**: H2 = 0.0 (PID insensitive to hydrogen)

```python
from h2track_gas_sim.mox_sensor_model import (
    MoxSensorModel, MoxSensorConfig, MoxSensorType, MoxGasType, mox_raw_from_ppm
)

model = MoxSensorModel(MoxSensorConfig(
    sensor_model=MoxSensorType.TGS2600,
    gas_type=MoxGasType.HYDROGEN,
    use_dynamics=True,
    node_rate_hz=10.0,
))
rs_ohms = model.update(concentration_ppm=100.0)
```

**GADEN upstream bug fixed**: tau_value selection now uses `[gas_type]` instead of hardcoded `[0]` (ethanol). This means H2 now uses the correct tau for its gas type.

### Ground Truth Evaluation

Real-vs-estimated concentration/source comparison using `h2track_tracking/evaluation/`:

- **`ground_truth_report.py`**: Pure logic — `GroundTruthSample`, `GroundTruthMetrics`, `compute_ground_truth_metrics()`, `format_report_json()`. Computes `source_rmse`, `concentration_rmse`, `time_to_source_sec`, `path_length_m`, `success_rate`.
- **`ground_truth_sampler.py`**: ROS Node — subscribes `/amcl_pose`, `/estimated_source`, `/gas_concentration`; calls GADEN `/odor_value` (GasPosition srv) to sample truth concentration at the robot cell. Exposes `dump_to_json(path)`, `get_metrics()`, `samples` property.

Launch with `--sample-ground-truth` (writes report JSON at end of run).

### TDLAS (Deferred)

TDLAS (Tunable Diode Laser Absorption Spectroscopy) integration is **deferred** — see `docs/adr/0001-tdlas-integration.md` for the decision and trigger conditions. Current H2 use cases are covered by anemometer + MOX + GasPosition; TDLAS will be re-evaluated when hardware includes a TDLAS sensor or when 10m+ remote detection is required.

### Multi-Gas Support

The system supports multiple gas types with different physical properties:

| Gas | Formula | Behavior | Sensor Height | Alarm Threshold |
|-----|---------|----------|---------------|-----------------|
| Hydrogen | H2 | Rising (light) | 1.5m | 250 ppm |
| Methane | CH4 | Rising (light) | 1.2m | 5000 ppm |
| Carbon Monoxide | CO | Neutral | 0.5m | 50 ppm |
| Propane | C3H8 | Sinking (heavy) | 0.3m | 1000 ppm |

Configure gas type in scene.yaml:

```yaml
gas_field:
  gas_type: "H2"  # H2, CH4, CO, C3H8
  source_strength: 160.0
  decay_rate: 0.32
```

Gas properties include:
- Molecular weight and density ratio
- Diffusion coefficient
- Recommended sensor height
- Alarm thresholds

Use `gas_types.py` to access gas properties programmatically:

```python
from h2track_tracking.gas_types import GasType, get_gas_properties, get_sensor_height

# Get gas properties
props = get_gas_properties(GasType.HYDROGEN)
print(f"Sensor height: {get_sensor_height(GasType.HYDROGEN)}m")
```

### Particle Filter

Probabilistic gas source localization using `particle_filter/` module:

- **ParticleFilter**: Core filter with predict/update/resample steps. Supports vectorized operations via `method='vectorized'` parameter for 10-50x speedup on large particle counts.
- **GaussianPlumeObservationModel**: Weights particles based on gas concentration
- **RandomWalkMotionModel**: Adds noise to particle positions
- **ParticleFilterNode**: ROS wrapper, publishes to `/estimated_source` and `/particle_cloud`

### Surge-Cast Algorithm

Gas source localization using `tracking/` module with wind-aware navigation:

- **SurgeCastTracker**: Two-phase algorithm (SURGE/CAST)
  - SURGE: Move upwind when plume detected
  - CAST: Lateral search when plume lost
- **PlumeDetector**: Detects plume boundaries using concentration thresholds

State transitions:
```
PATROL → SURGE (plume detected)
SURGE → CAST (plume lost)
SURGE → SOURCE_FOUND (threshold reached)
CAST → SURGE (plume reacquired)
```

### Wind Estimation

Estimates wind direction from gas concentration gradients using `tracking/wind_estimator.py`:

- **WindEstimator**: Infers wind from spatial concentration patterns
  - Gradient-based estimation: Concentration gradient points toward source, wind is opposite
  - Plume shape analysis: Plume elongation indicates wind direction
  - Outputs: wind_x, wind_y, confidence

Key parameters:
- `estimate_wind`: Wind estimation mode (default: `"gradient"`)
  - `"off"` — disable wind estimation
  - `"gradient"` — infer wind from concentration gradients (legacy default; backward-compat: `true`)
  - `"anemometer"` — use GADEN `simulated_anemometer` ground truth (requires `use_gaden:=true` and `use_anemometer_ground_truth:=true`)
- `wind_estimation_min_samples`: Minimum samples before estimating (default: 10, gradient mode only)

**Anemometer ground-truth mode** (Phase 1): When `estimate_wind: anemometer`, the `bt_node_runner` subscribes to `/estimated_wind` (WindEstimate message) published by `anemometer_adapter_node`. The node converts GADEN's `Anemometer` msg (wind_speed, wind_direction) into a map-frame downwind vector with EMA smoothing. Backward-compat: bool `true` → `"gradient"`, `false` → `"off"`.

### Behavior Tree Pipeline

The **primary** orchestration approach uses py_trees (`bt/` module).  The legacy `mission_manager_node` is deprecated.

**Tree structure** (`tree_factory.py`):
```
MissionRoot (Selector)
├── SourceFound    → CheckMissionMode(SOURCE_FOUND)
├── SeekTrack      → CostmapGuard  →  Tracker  →  Nav2Client
└── Patrol         → CostmapGuard  →  Nav2Client         (also handles SEEK_CONFIRM)
```
SensorReaderNode and StateMachineNode are inlined into `bt_node_runner._tick()`.

**BT nodes** (`bt/nodes/`):
| Node | Purpose |
|------|---------|
| `TrackerNode` | Runs SurgeCastTracker + Fusion + CostmapChecker |
| `CostmapGuardNode` | Monitors costmap, writes `safety.obstacle_detected` |
| `Nav2ClientNode` | Sends NavigateToPose goals via ActionClient |
| `CheckMissionMode` | Gates tree branches by `mission.mode` |

**Blackboard namespaces** (`bt/blackboard.py`):
- `sensor.*` — concentration, robot_pose, robot_yaw, wind, pf_estimate, pf_confidence
- `nav2.*` — target_pose, target_yaw, status, task_complete, goal_reached_count, nav_ready
- `tracker.*` — target, heading, wind_estimate
- `mission.*` — mode, source_estimate, patrol_target
- `safety.*` — obstacle_detected

All domain objects (SurgeCastTracker, TrackingFusion, CostmapChecker, MissionStateMachine) are injected via constructor (DI), never instantiated inside nodes.

**Launch:** `ros2 run h2track_tracking bt_node_runner` (accepts same ROS params as legacy node).

### Algorithm Fusion

Combines Surge-Cast and Particle Filter estimates using `tracking/fusion.py`:

- **TrackingFusion**: Three fusion modes:
  - `weighted`: Blend targets based on confidence
  - `switching`: Select one algorithm based on conditions
  - `cascade`: PF guides region, Surge-Cast navigates

Key parameters:
- `use_fusion`: Enable algorithm fusion (default: true)
- `fusion_mode`: Fusion mode - "weighted", "switching", or "cascade" (default: "weighted")
- `fusion_pf_weight`: Base weight for particle filter estimate (default: 0.3)
- `fusion_surge_weight`: Base weight for surge-cast (default: 0.7)

Fusion improves tracking by leveraging both real-time surge-cast navigation and probabilistic source estimates.

### Usage Example: Fusion Configuration

To enable fusion in your scene configuration:

```yaml
# In scene.yaml
fusion:
  use_fusion: true
  fusion_mode: weighted  # Options: weighted, switching, cascade
  pf_weight: 0.35        # Particle filter weight (0-1)
  surge_weight: 0.65     # Surge-cast weight (0-1)
  pf_confidence_threshold: 0.3

wind_estimation:
  estimate_wind: true
  min_samples: 8         # Minimum samples before wind estimation
```

Monitor fusion state via ROS topics:

```bash
# View fusion state
ros2 topic echo /fusion_state

# View estimated wind
ros2 topic echo /estimated_wind
```

The fusion algorithm combines:
1. **Surge-Cast**: Real-time plume tracking with wind-aware navigation
2. **Particle Filter**: Probabilistic source localization
3. **Wind Estimation**: Infers wind from concentration gradients

Default fusion mode (`weighted`) blends both estimates based on confidence.

### Adaptive Step Size

The Surge-Cast algorithm supports adaptive step size adjustment:

- **High concentration**: Small steps (0.2m) for precision near source
- **Low concentration**: Large steps (1.0m) for fast exploration
- **Intermediate**: Linear interpolation

Configure in scene.yaml:

```yaml
mission_manager:
  adaptive_step: true
  min_step: 0.2
  max_step: 1.0
  concentration_threshold_high: 5.0
  concentration_threshold_low: 1.0
```

### Heatmap System

Concentration visualization using `heatmap/` module:

- **ConcentrationGrid**: 3D grid for gas concentration storage
- **TimeSeriesStore**: Historical grid snapshots for playback
- **HeatmapDataProvider**: Bridges ROS data to WebSocket streaming

### Scene Configuration

Scenes are defined in `src/h2track_sim/scenes/<scene>/scene.yaml`:

```yaml
scene_name: warehouse
world: scenes/warehouse/warehouse.world
map: scenes/warehouse/maps/warehouse_map.yaml
nav2_params: scenes/warehouse/nav2_params.yaml
use_gaden: true
use_slam: true
mission_manager:
  initial_pose: {x, y, yaw}
  patrol_points: [[x1, y1], [x2, y2], ...]
  enter_threshold: 0.65    # Gas concentration to trigger SEEK_CONFIRM
  exit_threshold: 0.4      # Below this, return to PATROL
  source_threshold: 3.4    # Concentration indicating source proximity
  source_radius: 1.0       # Meters from source for SOURCE_FOUND
gas_source: {x, y}
gaden:
  project_path: install/test_env/share/test_env/scenarios/<scenario>/environment_configurations/config1
  playback_id: scene1
```

Available scenes: `baseline`, `warehouse`, `maze`, `snake`, `office`, `benchmark`

## Console Scripts (Entry Points)

### h2track_tracking

| Command | Purpose |
|---------|---------|
| `bt_node_runner` | **Primary** BT-based orchestrator (LifecycleNode) |
| `particle_filter_node` | Probabilistic source localization (LifecycleNode) |
| `ground_truth_sampler` | GADEN GasPosition ground-truth RMSE evaluation |

### h2track_gas_sim

| Command | Purpose |
|---------|---------|
| `gas_field_node` | Simplified gas simulation (LifecycleNode) |
| `gaden_adapter_node` | GADEN integration |
| `gaden_sensor_gate_node` | TF-gated sensor launch |
| `anemometer_adapter_node` | GADEN `Anemometer` → `/estimated_wind` (WindEstimate) |
| `gas_sensor_node` | MOX gas sensor (uses `mox_sensor_model.py`) |

### h2track_utils

| Command | Purpose |
|---------|---------|
| `demo_prep` | Clear stale processes |
| `demo_selfcheck` | Stack verification |
| `demo_regression` | Multi-scene regression testing |
| `slam_save_map` | Save SLAM map |
| `activate_localization` | AMCL activation |

### h2track_web

| Command | Purpose |
|---------|---------|
| `demo_web_server` | FastAPI web console |
| `activate_localization` | `activate_localization.py` | AMCL activation |

## Launch Files

| Launch File | Purpose |
|-------------|---------|
| `demo.launch.py` | Main demo entry, loads scene config from `config/demo.yaml` |
| `bringup.launch.py` | Full stack: sim + nav2 + gas + mission |
| `slam_demo.launch.py` | SLAM mapping mode |
| `sim.launch.py` | Gazebo + robot spawn |
| `nav2.launch.py` | Nav2 stack only |

## Demo Workflow

Before formal demos, run prep and selfcheck:

```bash
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash

# 1. Clear stale processes
ros2 run h2track_utils demo_prep --scene warehouse

# 2. Launch demo
ros2 launch h2track_bringup demo.launch.py use_rviz:=true

# 3. Verify stack (separate terminal)
ros2 run h2track_utils demo_selfcheck --timeout 5.0
```

## Key Topics

| Topic | Type | Purpose |
|-------|------|---------|
| `/gas_concentration` | `Float32` | Gas sensor reading (normalized) |
| `/robot_mode` | `String` | Current mission mode |
| `/source_found` | `Bool` | Source detection signal |
| `/amcl_pose` | `PoseWithCovarianceStamped` | Robot pose from localization |
| `/estimated_source_pose` | `PoseStamped` | Estimated source position |
| `/estimated_source` | `PoseWithCovarianceStamped` | Particle filter source estimate with covariance |
| `/particle_cloud` | `PoseArray` | Particle positions for visualization |
| `/estimated_wind` | `String` (gradient mode) / `WindEstimate` (anemometer mode) | Estimated wind vector. Gradient mode publishes CSV string "wind_x,wind_y,confidence"; anemometer mode publishes typed `WindEstimate` msg from `anemometer_adapter_node` |
| `/fusion_state` | `String` | Fusion state: "mode,pf_contrib,surge_contrib,target_x,target_y" |

## External Dependencies

- **GADEN workspace**: `/home/user/gaden_ws` must be sourced for `use_gaden:=true`
- GADEN requires preprocessed environment and scenario files
- `olfaction_msgs` for `GasSensor` message type
- **py_trees**: `sudo apt install ros-humble-py-trees ros-humble-py-trees-ros` (required for BT pipeline)
- **Nav2**: `nav2_simple_commander` for legacy node; BT uses `nav2_msgs.action.NavigateToPose` directly

## Security Requirements

- **LLM Client**: Base URLs must use `https://` scheme (HTTP rejected for security)
- **URL Whitelisting**: LLM client validates URLs against allowed patterns
- **Command Execution**: Shell commands in demo_prep use parameter lists, not string interpolation

## Code Patterns

- Pure Python modules (`gas_model.py`, `mission_logic.py`, `gaden_adapter.py`) are ROS-agnostic and unit-testable
- Nodes thin wrappers around pure logic
- Scene configs use YAML; launch files load via `scene_loader.py`
- State machine in `MissionStateMachine` class uses dataclass config
- `MissionConfig` and `GasFieldParams` are frozen dataclasses for immutability
- **Canonical Pose2D**: `h2track_utils/types.py` defines the single source-of-truth `Pose2D`; other packages import from there
- **Config defaults**: `MissionConfig` and `SurgeCastConfig` dataclass defaults are the single source of truth for ROS parameter defaults
- **Factory functions**: `navigation_executor.py` houses `_gradient_search_target` (pure gradient nav) and `select_tracking_target` (high-level target selector)
- **Recovery**: Detection functions use public `controller.metrics_snapshot()` — never `controller._metrics`
- **LLM**: `SupportsSimControl` Protocol in `llm/controller.py` defines the sim interface contract

### Module Organization

```
h2track_tracking/
├── particle_filter/      # Probabilistic source localization
│   ├── types.py          # Particle, SourceEstimate dataclasses
│   ├── filter.py         # Core filter (supports vectorized ops)
│   ├── motion_model.py   # Random walk motion model
│   └── observation_model.py  # Gaussian plume observation model
├── bt/                   # Behavior Tree pipeline (primary orchestrator)
│   ├── blackboard.py     # 5-namespace shared state
│   ├── tree_factory.py   # BT assembly with DI
│   └── nodes/            # py_trees Behaviour implementations
├── bt_node_runner/       # BT-based lifecycle node
│   ├── runner.py         # Primary BTNodeRunner (LifecycleNode)
│   └── param_bridge.py   # Launch param → dataclass bridge
├── tracking/             # Gas tracking algorithms
│   ├── types.py          # TrackingState, SurgeCastConfig (Pose2D from h2track_utils)
│   ├── surge_cast.py     # Surge-Cast source localization
│   ├── plume_detector.py # Plume boundary detection
│   ├── wind_estimator.py # Wind direction from concentration gradients
│   ├── costmap_checker.py # Nav2 costmap monitoring
│   └── fusion.py         # Algorithm fusion (surge-cast + PF)
├── heatmap/              # Concentration visualization
│   ├── grid.py           # 3D concentration grid
│   └── history_store.py  # Time series snapshots
├── recovery/             # Navigation recovery policies
│   ├── policies.py       # Recovery policy definitions
│   ├── actions.py        # Recovery action execution
│   └── monitor.py        # Failure detection
├── llm/                  # LLM assistant backend
│   ├── client.py         # OpenAI-compatible client (HTTPS required)
│   ├── controller.py     # Chat and action execution
│   ├── actions.py        # LLM-triggered actions
│   └── profile_store.py  # Profile management
├── multi_robot/          # Multi-robot coordination
│   └── coordinator_node.py  # Role assignment, information fusion
├── evaluation/           # Performance metrics + ground-truth comparison
│   ├── metrics.py        # TrackingMetrics, BenchmarkResult dataclasses
│   ├── ground_truth_report.py  # Pure RMSE/report logic (Phase 3)
│   └── ground_truth_sampler.py # ROS node — samples GADEN /odor_value
└── benchmark/            # Algorithm benchmarking
    └── performance_benchmark.py  # Timing benchmarks for algorithms
```

```
h2track_gas_sim/
├── gas_model.py          # Simplified GasFieldModel
├── gas_field_node.py     # Simplified plume sim (LifecycleNode)
├── gaden_adapter.py      # GADEN sensor → /gas_concentration
├── gaden_adapter_node.py
├── gaden_sensor_gate.py  # TF-gated sensor launch
├── anemometer_adapter.py # Anemometer → WindEstimate (Phase 1, pure logic)
├── anemometer_adapter_node.py
├── mox_sensor_model.py   # Complete GADEN MOX port (Phase 2)
├── gas_sensor/           # MOX gas_sensor_node wrapper
└── wind_model.py
```

### Custom Messages (h2track_interfaces)

| Message | Fields | Purpose |
|---------|--------|---------|
| `RobotState.msg` | robot_id, x, y, yaw, mode, concentration, timestamp | Robot state for multi-robot coordination |
| `SourceEstimate.msg` | robot_id, x, y, confidence, covariance[4], timestamp | Source estimate with uncertainty |
| `RoleAssignment.msg` | robot_id, role, target_x, target_y, timestamp | Role assignment for multi-robot |
| `WindEstimate.msg` | header, wind_x, wind_y, confidence | Typed wind estimate (anemometer mode) |
| `FusionState.msg` | header, mode, pf_contrib, surge_contrib, target_x, target_y | Fusion state for visualization |

## Web Console

One-click demo launcher available at `http://<host>:18080`:

```bash
ros2 run h2track_tracking demo_web_server --host 0.0.0.0 --port 18080
```

### API Authentication

Optional API key authentication via `H2TRACK_API_KEY` environment variable:

```bash
export H2TRACK_API_KEY="your-secret-key"
```

When set, protected endpoints (`/api/sim/start`, `/api/sim/stop`, `/api/llm/*`, `/api/diag/export`, `/api/report/export`) require `X-API-Key` header.

### WebSocket Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/ws` | Real-time metrics streaming |
| `/ws/heatmap` | Real-time heatmap visualization (grid, particles, estimate) |

### API Endpoints

Key REST endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sim/start` | POST | Start simulation with profile |
| `/api/sim/stop` | POST | Stop running simulation |
| `/api/sim/status` | GET | Current simulation status |
| `/api/metrics/recent` | GET | Recent metrics snapshot |
| `/api/llm/chat` | POST | Chat with LLM assistant |

## Demo Regression Testing

Run multi-round stability checks:

```bash
ros2 run h2track_tracking demo_regression --scene warehouse --use-gaden true --rounds 3 --run-timeout-sec 110
```

## Agent skills

### Issue tracker

Issues are tracked in Gitee Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` at the repo root. See `docs/agents/domain.md`.
