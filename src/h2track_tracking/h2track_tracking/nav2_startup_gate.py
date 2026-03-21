"""Utilities for gating Nav2 lifecycle startup on TF and service readiness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateAction(Enum):
    WAIT = "wait"
    STARTUP = "startup"
    MONITOR = "monitor"
    COMPLETE = "complete"
    FAIL = "fail"


@dataclass(frozen=True)
class Nav2StartupGateConfig:
    timeout_sec: float = 30.0
    stable_ready_count: int = 1


class Nav2StartupGateState:
    def __init__(self, config: Nav2StartupGateConfig) -> None:
        self._config = config
        self._ready_count = 0
        self._startup_requested = False
        self._completed = False
        self._failed = False

    def step(
        self,
        *,
        tf_ready: bool,
        service_ready: bool,
        startup_result: bool | None,
        elapsed_sec: float,
    ) -> GateAction:
        if self._failed:
            return GateAction.FAIL
        if self._completed:
            return GateAction.COMPLETE
        if self._startup_requested:
            if startup_result is None:
                return GateAction.MONITOR
            if startup_result:
                self._completed = True
                return GateAction.COMPLETE
            self._failed = True
            return GateAction.FAIL

        if tf_ready and service_ready:
            self._ready_count += 1
            if self._ready_count >= self._config.stable_ready_count:
                self._startup_requested = True
                return GateAction.STARTUP
        else:
            self._ready_count = 0

        if elapsed_sec >= self._config.timeout_sec:
            self._failed = True
            return GateAction.FAIL
        return GateAction.WAIT
