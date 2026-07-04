#!/usr/bin/env python3
"""Capture Gazebo world screenshots for progress report."""
from __future__ import annotations

import subprocess
import time
import sys
from pathlib import Path

OUTDIR = Path("/home/user/h2track-xian/artifacts/diagrams")
SCENES_DIR = Path("/home/user/h2track-xian/src/h2track_bringup/scenes")

WORLDS = [
    ("baseline", SCENES_DIR / "baseline/h2track_lab.world"),
    ("warehouse", SCENES_DIR / "warehouse/warehouse.world"),
    ("maze", SCENES_DIR / "maze/maze.world"),
    ("snake", SCENES_DIR / "snake/snake.world"),
    ("office", SCENES_DIR / "office/office.world"),
]

def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None

def kill_gazebo():
    run("killall -9 gzclient gzserver gazebo 2>/dev/null", timeout=5)
    time.sleep(1)

def capture_world(name, world_path):
    print(f"\n--- Capturing {name} ---")
    kill_gazebo()

    model_path = str(SCENES_DIR / name)
    if name == "warehouse":
        model_path += ":" + str(SCENES_DIR / "warehouse/models")

    env = {"GAZEBO_MODEL_PATH": model_path, "DISPLAY": ":0"}
    proc = subprocess.Popen(
        f"source /opt/ros/humble/setup.bash && gazebo {world_path}",
        shell=True, env={**__import__('os').environ, **env},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  Started PID={proc.pid}, waiting 12s...")
    time.sleep(12)

    # Find window
    r = run("xdotool search --name Gazebo 2>/dev/null | head -1", timeout=5)
    wid = r.stdout.strip() if r else ""

    if wid:
        run(f"xdotool windowactivate {wid}", timeout=3)
        time.sleep(1)
        run(f"scrot -u {OUTDIR}/gazebo_{name}.jpg", timeout=5)
        print(f"  Captured window {wid}")
    else:
        # Full screen fallback
        run(f"scrot {OUTDIR}/gazebo_{name}.jpg", timeout=5)
        print("  Captured full screen (no window found)")

    # Verify
    out = OUTDIR / f"gazebo_{name}.jpg"
    if out.exists():
        print(f"  Saved: {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    else:
        print(f"  FAILED to save screenshot!")

    proc.terminate()
    time.sleep(1)
    kill_gazebo()

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, world_path in WORLDS:
        if world_path.exists():
            capture_world(name, world_path)
        else:
            print(f"  SKIP {name}: world not found at {world_path}")

    print("\nDone capturing Gazebo screenshots.")
    for f in sorted(OUTDIR.glob("gazebo_*.jpg")):
        print(f"  {f.name} ({f.stat().st_size / 1024:.0f} KB)")

if __name__ == "__main__":
    main()
