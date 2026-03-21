"""Utilities for gating the GADEN simulated gas sensor on TF availability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateAction(Enum):
    WAIT = "wait"
    LAUNCH = "launch"
    RUNNING = "running"
    FAIL = "fail"


@dataclass(frozen=True)
class SensorGateConfig:
    timeout_sec: float = 30.0
    poll_period_sec: float = 0.5
    stable_ready_count: int = 1


class SensorGateState:
    def __init__(self, config: SensorGateConfig) -> None:
        self._config = config
        self._launched = False
        self._failed = False
        self._ready_count = 0

    def step(self, *, has_transform: bool, elapsed_sec: float) -> GateAction:
        if self._failed:
            return GateAction.FAIL
        if self._launched:
            return GateAction.RUNNING
        if has_transform:
            self._ready_count += 1
            if self._ready_count >= self._config.stable_ready_count:
                self._launched = True
                return GateAction.LAUNCH
            return GateAction.WAIT
        self._ready_count = 0
        if elapsed_sec >= self._config.timeout_sec:
            self._failed = True
            return GateAction.FAIL
        return GateAction.WAIT


def build_sensor_process_command(
    *,
    executable_path: str,
    use_sim_time: bool,
    topic: str,
    fixed_frame: str,
    sensor_frame: str,
    sensor_model: int,
    rate: float,
    use_pid_correction_factors: bool,
    sensor_node_name: str,
) -> list[str]:
    return [
        executable_path,
        "--ros-args",
        "-r",
        f"__node:={sensor_node_name}",
        "-p",
        f"use_sim_time:={'true' if use_sim_time else 'false'}",
        "-p",
        f"topic:={topic}",
        "-p",
        f"fixed_frame:={fixed_frame}",
        "-p",
        f"sensor_frame:={sensor_frame}",
        "-p",
        f"sensor_model:={sensor_model}",
        "-p",
        f"rate:={rate}",
        "-p",
        f"use_PID_correction_factors:={'true' if use_pid_correction_factors else 'false'}",
    ]
