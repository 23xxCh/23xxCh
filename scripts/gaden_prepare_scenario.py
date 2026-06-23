#!/usr/bin/env python3
"""Prepare a GADEN scenario for playback.

Runs preprocessing + filament simulation to generate:
  - OccupancyGrid3D.csv (environment occupancy grid)
  - occupancy.pgm / occupancy.yaml (2D nav map)
  - simulations/<sim_id>/result/iteration_* (filament snapshots)

Usage:
    python3 scripts/gaden_prepare_scenario.py <scenario_name> [sim_time_sec]

Example:
    python3 scripts/gaden_prepare_scenario.py 10x6_empty_room 60

After running this, gas_simulation.launch.py can use:
    gaden_project_path:=<gaden_ws>/install/test_env/share/test_env/scenarios/<scenario>/environment_configurations/config1
    gaden_playback_id:=scene1
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

GADEN_WS = Path("/home/user/gaden_ws")
SCENARIOS_DIR = GADEN_WS / "install/test_env/share/test_env/scenarios"


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    """Run a command, return (returncode, output)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except FileNotFoundError as e:
        return 127, str(e)


def preprocess(config1_path: Path) -> bool:
    """Run gaden_preprocessing to generate OccupancyGrid3D.csv."""
    print(f"[1/3] Preprocessing: {config1_path}")
    rc, out = run([
        "ros2", "run", "gaden_preprocessing", "preprocessing",
        "--ros-args", "-p", f"projectPath:={config1_path}",
    ], timeout=60)
    if rc != 0 or "Preprocessing done" not in out:
        print(f"  FAIL (rc={rc})")
        print(out[-500:])
        return False
    print("  OK")
    return True


def run_filament_sim(config1_path: Path, sim_id: str, sim_time_sec: float) -> bool:
    """Run gaden_filament_simulator to generate iteration files."""
    print(f"[2/3] Filament simulation: {sim_id} for {sim_time_sec}s")
    rc, out = run([
        "ros2", "run", "gaden_filament_simulator", "filament_simulator",
        "--ros-args",
        "-p", f"projectPath:={config1_path}",
        "-p", f"simulationID:={sim_id}",
        "-p", f"sim_time:={sim_time_sec}",
    ], timeout=int(sim_time_sec * 4) + 60)
    if rc != 0 or "finished correctly" not in out:
        print(f"  FAIL (rc={rc})")
        print(out[-500:])
        return False
    print("  OK")
    return True


def update_scene_loop(scene_yaml: Path, max_iteration: int) -> bool:
    """Enable looping in scene1.yaml so player cycles through available iterations."""
    print(f"[3/3] Update {scene_yaml.name}: loop 0..{max_iteration}")
    if not scene_yaml.exists():
        print(f"  SKIP (file not found: {scene_yaml})")
        return True  # not all scenarios have scene1.yaml
    text = scene_yaml.read_text()
    if "loop: true" in text and f"to: {max_iteration}" in text:
        print("  SKIP (already loop-enabled)")
        return True
    # Replace loop config
    import re
    new_text = re.sub(
        r"playback_loop:\s*\n\s*loop:\s*false\s*\n\s*from:\s*\d+\s*\n\s*to:\s*\d+",
        f"playback_loop:\n  loop: true\n  from: 0\n  to: {max_iteration}",
        text,
    )
    if new_text == text:
        print("  SKIP (loop config not found, leaving as-is)")
        return True
    scene_yaml.write_text(new_text)
    print("  OK")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    scenario = sys.argv[1]
    sim_time = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

    config1 = SCENARIOS_DIR / scenario / "environment_configurations/config1"
    if not config1.exists():
        print(f"ERROR: scenario not found: {config1}")
        return 1

    if not preprocess(config1):
        return 1
    if not run_filament_sim(config1, "sim1", sim_time):
        return 1

    # Count iterations
    result_dir = config1 / "simulations/sim1/result"
    if result_dir.exists():
        iterations = sorted([p for p in result_dir.iterdir() if p.name.startswith("iteration_")],
                            key=lambda p: int(p.name.split("_")[1]))
        if iterations:
            max_iter = int(iterations[-1].name.split("_")[1])
            update_scene_loop(config1 / "scenes/scene1.yaml", max_iter)
            print(f"\nDone. {len(iterations)} iterations generated (0..{max_iter}).")
            print(f"projectPath: {config1}")
            print(f"playbackID: scene1")
            return 0

    print("\nDone but no iterations found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
