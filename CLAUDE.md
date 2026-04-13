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
pytest src/h2track_tracking/test/test_pf_integrator.py -v

# Run with coverage
pytest src/h2track_tracking/test/ --cov=src/h2track_tracking/h2track_tracking --cov-report=term-missing
```

## Package Structure

Two ROS 2 packages:

| Package | Build Type | Purpose |
|---------|------------|---------|
| `h2track_sim` | ament_cmake | Launch files, scene configs, Gazebo worlds, URDF |
| `h2track_tracking` | ament_python | Tracking logic, gas model, mission state machine |

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
| `mission_manager_node` | `mission_manager_node.py` | State machine, Nav2 goal management |
| `gas_field_node` | `gas_field_node.py` | Simplified plume simulation (use_gaden:=false) |
| `gaden_adapter_node` | `gaden_adapter_node.py` | Converts GADEN sensor readings to `/gas_concentration` |
| `gaden_sensor_gate_node` | `gaden_sensor_gate.py` | Waits for TF before launching simulated_gas_sensor |
| `nav2_startup_gate_node` | `nav2_startup_gate.py` | Waits for Nav2 lifecycle readiness |
| `particle_filter_node` | `particle_filter/particle_filter_node.py` | Probabilistic gas source localization |

### Gas Simulation

Two modes:

1. **Simplified** (`use_gaden:=false`): `gas_field_node` publishes synthetic plume data based on `GasFieldModel` in `gas_model.py`
2. **GADEN** (`use_gaden:=true`): Uses external GADEN workspace for realistic filament-based gas dispersion

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
- **PfIntegrator**: Integrates particle filter estimates with surge-cast navigation

State transitions:
```
PATROL → SURGE (plume detected)
SURGE → CAST (plume lost)
SURGE → SOURCE_FOUND (threshold reached)
CAST → SURGE (plume reacquired)
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
  project_path: /path/to/gaden/scenario
  playback_id: scene1
```

Available scenes: `baseline`, `warehouse`

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
ros2 run h2track_tracking demo_prep --scene warehouse

# 2. Launch demo
ros2 launch h2track_sim demo.launch.py use_rviz:=true

# 3. Verify stack (separate terminal)
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
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

## External Dependencies

- **GADEN workspace**: `/home/user/gaden_ws` must be sourced for `use_gaden:=true`
- GADEN requires preprocessed environment and scenario files
- `olfaction_msgs` for `GasSensor` message type

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

### Module Organization

```
h2track_tracking/
├── particle_filter/      # Probabilistic source localization
│   ├── types.py          # Particle, SourceEstimate dataclasses
│   ├── filter.py         # Core filter (supports vectorized ops)
│   ├── motion_model.py   # Random walk motion model
│   └── observation_model.py  # Gaussian plume observation model
├── tracking/             # Gas tracking algorithms
│   ├── types.py          # Pose2D, TrackingState, TrackingAction
│   ├── surge_cast.py     # Surge-Cast source localization
│   ├── plume_detector.py # Plume boundary detection
│   └── pf_integrator.py  # Particle filter integration
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
└── web/                  # FastAPI web console
    ├── app.py            # Application factory
    ├── routes.py         # REST and WebSocket endpoints
    ├── websocket.py      # Connection manager, heatmap streaming
    ├── auth.py           # API key authentication
    └── simulation_controller.py  # Simulation lifecycle
```

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
