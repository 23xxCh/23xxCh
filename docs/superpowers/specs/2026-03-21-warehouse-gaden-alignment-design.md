# Warehouse GADEN Alignment Design

## Summary
The `warehouse` scene in `/home/user/h2track-xian/.worktrees/dual-scene-platform` should stop defaulting to the baseline room-style GADEN setup and instead own a scene-specific GADEN configuration backed by external assets in `/home/user/gaden_ws`. The first iteration is intentionally a runnable approximation: it uses a simplified warehouse geometry in GADEN that preserves the main aisles, cross-aisles, dominant rack blockages, and leak-source placement without trying to reproduce every AWS warehouse mesh in CFD.

The goal of this change is not “perfect warehouse plume physics.” The goal is to make `scene:=warehouse` a genuinely separate gas-tracking environment: different map, different obstacle geometry, different source semantics, and different GADEN playback path from `baseline`.

## Goals
- Make `warehouse` default to its own external GADEN project instead of falling back to `10x6_empty_room`.
- Keep GADEN assets and results in `/home/user/gaden_ws`, not in `h2track-xian`.
- Express all warehouse-specific GADEN settings in `warehouse/scene.yaml`.
- Keep the existing `gaden_adapter_node` and `/gas_concentration` interface unchanged for the mission layer.
- Preserve `use_gaden:=false` as an explicit fallback to the simplified gas field.

## Non-Goals
- Rebuilding a full-fidelity CFD representation of the AWS warehouse mesh.
- Changing the mission-state machine or gas-tracking algorithm in this step.
- Removing the simplified gas field fallback.
- Migrating baseline to the warehouse GADEN assets.

## Architecture
The design introduces a dedicated external GADEN scenario rooted at `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse`. That scenario mirrors the existing `test_env` layout used by GADEN today:
- `gaden.gproj`
- `cad_models/`
- `wind_simulations/`
- `environment_configurations/config1/config.yaml`
- `environment_configurations/config1/scenes/scene1.yaml`
- `environment_configurations/config1/simulations/sim1/sim.yaml`

The `warehouse` scene inside `h2track-xian` gains a `gaden:` configuration block that declares:
- whether GADEN is the default for this scene
- the external project path to use
- playback id and sensor topic/frame names
- `gaden_map -> map` alignment values
- any scene-level notes needed to relate the simplified warehouse GADEN geometry to the Gazebo warehouse world

The launch stack remains scene-driven. `demo.launch.py` and `bringup.launch.py` continue to select one logical scene, but the GADEN defaults for that scene come from `scene.yaml`, not from generic launch fallbacks. `baseline` and `warehouse` may both use GADEN, but they must do so through independent scene-local configuration.

## External GADEN Asset Strategy
The first warehouse-aligned GADEN scenario uses a simplified geometry rather than the full AWS warehouse meshes. The simplification should preserve the structures that materially affect the plume and robot motion:
- outer boundary walls
- main longitudinal aisle
- at least one transverse aisle
- a small number of large rack blocks representing the dominant shelving rows
- leak-source neighborhood geometry near the intended warehouse source location

This gives the project a GADEN scene that is geometrically consistent with the Gazebo warehouse narrative without creating an unmaintainable asset-conversion project on day one. The external scenario still needs real GADEN inputs and outputs; it is only the scene geometry that is simplified.

## Scene Configuration Model
`/home/user/h2track-xian/.worktrees/dual-scene-platform/src/h2track_sim/scenes/warehouse/scene.yaml` should gain a top-level `gaden:` block. It should own the warehouse scene’s default GADEN settings, including:
- `enabled`
- `project_path`
- `playback_id`
- `sensor_topic`
- `sensor_frame`
- `fixed_frame`
- `map_offset_x`
- `map_offset_y`
- `map_offset_z`
- `map_roll`
- `map_pitch`
- `map_yaw`

`warehouse` should switch to `use_gaden: true` once this configuration is present and the external scenario exists. `baseline` keeps its own scene-local behavior.

## Launch and Data Flow
For `scene:=warehouse` the data flow becomes:
- Gazebo warehouse world publishes robot motion and laser data
- scene loader reads `warehouse/scene.yaml`
- bringup resolves warehouse GADEN settings from `scene_profile['gaden']`
- `gaden_environment` / `gaden_player` use the warehouse project path
- `gaden_sensor_gate_node` waits on the warehouse GADEN transform path
- `gaden_adapter_node` converts warehouse GADEN sensor messages into `/gas_concentration`
- `mission_manager_node` continues consuming `/gas_concentration` without any GADEN-specific coupling

The mission layer remains unchanged. The scene boundary sits below it.

## Error Handling and Safety
The launch system should fail fast when `scene:=warehouse` resolves to an invalid or incomplete GADEN configuration. Specifically:
- if `use_gaden` resolves true and the scene has no `gaden` block, launch should error
- if the configured `project_path` does not exist, launch should error
- if warehouse GADEN is enabled, launch must not silently substitute the baseline `10x6_empty_room` path

`use_gaden:=false` remains the only supported way to intentionally fall back to the simplified gas field for `warehouse`.

## Testing Strategy
Validation should cover four layers.

### 1. Configuration tests
- warehouse scene declares a full `gaden:` block
- warehouse scene defaults to `use_gaden: true`
- warehouse scene does not reference the baseline room GADEN path

### 2. Launch wiring tests
- `demo.launch.py` keeps scene-driven `use_gaden` resolution
- `bringup.launch.py` reads warehouse `gaden` settings from the scene profile
- warehouse GADEN startup fails if the scene config is incomplete
- `scene:=warehouse use_gaden:=false` still routes to `gas_field_node`

### 3. External asset validation
- `/home/user/gaden_ws/src/gaden/test_env/scenarios/h2track_warehouse` exists with the expected files
- the GADEN scenario contains a valid `config.yaml`, `scene1.yaml`, and `sim.yaml`
- the external workspace can be rebuilt after adding the warehouse scenario

### 4. Runtime verification
- warehouse default launch starts `gaden_environment`, `gaden_player`, `gaden_sensor_gate_node`, and `gaden_adapter_node`
- live parameters show the warehouse GADEN project path rather than the baseline room path
- a warehouse live run produces non-zero gas readings when the robot enters the intended plume region
- `scene:=warehouse use_gaden:=false` still passes through the simplified gas-field fallback path

## Expected Outcome
After this change, `baseline` remains the fast regression scene, while `warehouse` becomes a genuinely separate GADEN-driven validation scene. That makes later algorithm comparisons meaningful because the two scenes differ in both geometry and gas-field source, not just obstacle layout.
