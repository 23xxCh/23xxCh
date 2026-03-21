# Demo Brief

## Project Goal

This demo shows a complete closed loop for a differential-drive inspection robot in simulation: autonomous patrol, hydrogen detection, source tracking, obstacle avoidance, and final alarm/stop near the leak source.

## Live Demo Flow

1. Start with `demo_prep` to clear stale H2track demo processes and confirm the required packages are visible.
2. Launch the formal stack with `demo.launch.py`.
3. Run `demo_selfcheck` and only continue if it reports that the system is ready.
4. Explain that the robot begins in patrol mode.
5. Point out the moment hydrogen is detected and the system switches into tracking mode.
6. Highlight that navigation and obstacle avoidance continue during tracking.
7. End with the robot reaching the source area, raising the alarm, and stopping.

## What To Watch During The Demo

- Mode switching: patrol, detection confirmation, tracking, and source found.
- Concentration change: the hydrogen reading should become more meaningful as the robot approaches the source.
- Motion continuity: the robot should keep navigating and avoiding obstacles while tracking.
- Final behavior: the robot should stop near the source and report the alarm condition clearly.

## Closing Summary

- This demonstration verifies the full patrol-to-tracking closed loop in the current simulation system.
- The current system is still simulation-focused and retains some startup noise and environment sensitivity.
- The next development focus is improving demo robustness, experimental repeatability, and stronger source-tracking performance.
