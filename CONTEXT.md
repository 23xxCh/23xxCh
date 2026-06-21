# H2Track Domain Context

## Project

H2Track is a ROS 2 Humble workspace for hydrogen (H2) gas source tracking simulation. A robot patrols a Gazebo environment, detects gas concentration changes, and locates the hydrogen source using gradient-based tracking and particle filter-based source localization.

## Glossary

| Term | Definition |
|------|------------|
| **Surge-Cast** | Wind-aware two-phase algorithm: SURGE (move upwind when plume detected) + CAST (lateral search when plume lost) |
| **Particle Filter** | Probabilistic gas source localization using predict/update/resample steps |
| **Behavior Tree (BT)** | py_trees-based orchestration pipeline replacing legacy mission manager |
| **Mission Mode** | One of PATROL, SEEK_CONFIRM, SEEK_TRACK, SOURCE_FOUND |
| **Gas Field Model** | Simplified 2D plume model with downwind bias and bounded noise |
| **GADEN** | External gas dispersion simulator (filament-based) |
| **Nav2** | ROS 2 navigation stack for waypoint following |
| **AMCL** | Adaptive Monte Carlo Localization for robot pose estimation |
| **Costmap** | Nav2 occupancy grid for obstacle avoidance |
| **Tracking Fusion** | Combines Surge-Cast and Particle Filter estimates |
| **Wind Estimator** | Infers wind direction from spatial concentration gradients |
| **Plume Detector** | Detects plume boundaries using concentration thresholds |
| **Blackboard** | Shared state namespace for BT nodes (sensor, nav2, tracker, mission, safety) |

## Architecture

```
Behavior Tree (py_trees)
  ├── TrackerNode (SurgeCastTracker + Fusion + CostmapChecker)
  ├── CostmapGuardNode (safety.obstacle_detected)
  └── Nav2ClientNode (NavigateToPose action)

Mission State Machine
  PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND

Gas Simulation
  ├── Simplified (gas_field_node) — Gaussian plume model
  └── GADEN (gaden_adapter_node) — Realistic filament dispersion

Localization
  ├── AMCL (default) — map-based localization
  └── SLAM (optional) — simultaneous mapping
```

## Key ROS Topics

| Topic | Purpose |
|-------|---------|
| `/gas_concentration` | Normalized gas sensor reading |
| `/robot_mode` | Current mission mode string |
| `/source_found` | Boolean source detection signal |
| `/estimated_source` | Particle filter source estimate with covariance |
| `/estimated_wind` | Wind vector "wind_x,wind_y,confidence" |
| `/fusion_state` | Fusion mode and contributions |

## Gas Types

| Gas | Formula | Density Ratio | Diffusion Coefficient | Sensor Height |
|-----|---------|---------------|----------------------|---------------|
| Hydrogen | H2 | 0.069 | 0.61 cm²/s | 1.5m |
| Methane | CH4 | 0.554 | 0.22 cm²/s | 1.2m |
| Carbon Monoxide | CO | 0.967 | 0.21 cm²/s | 0.5m |
| Propane | C3H8 | 1.52 | 0.11 cm²/s | 0.3m |

## Scenes

| Scene | Description | Gas Source |
|-------|-------------|------------|
| `baseline` | H2Track Lab environment | (-4.0, 1.95) |
| `warehouse` | AWS RoboMaker Small Warehouse | (3.6, -3.04) |

## Decisions

See `docs/adr/` for architecture decision records.
