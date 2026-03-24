"""Run repeated warehouse demo simulations and report source-finding success rate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess
import time
from typing import cast

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool


@dataclass(frozen=True)
class RegressionRound:
    index: int
    source_found: bool
    source_found_time: float | None
    notes: str


def parse_source_found_output(output: str) -> bool:
    text = output.lower()
    return "data: true" in text


def summarize_rounds(rounds: list[RegressionRound]) -> dict[str, float | int | None]:
    total = len(rounds)
    successes = sum(1 for r in rounds if r.source_found)
    success_rate = (successes / total) if total else 0.0
    found_times = [r.source_found_time for r in rounds if r.source_found and r.source_found_time is not None]
    mean_time = (sum(found_times) / len(found_times)) if found_times else None
    return {
        "rounds": total,
        "successes": successes,
        "success_rate": success_rate,
        "mean_source_found_time": mean_time,
    }


def _run_command(cmd: list[str], *, check: bool = False, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\n"
            f"returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _terminate_launch_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=8.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        return


def _run_demo_prep(scene: str, use_gaden: str) -> None:
    _run_command(
        ["ros2", "run", "h2track_tracking", "demo_prep", "--scene", scene, "--use-gaden", use_gaden],
        check=True,
    )


def _launch_round(scene: str, use_gaden: str, log_path: Path) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("wb")
    return subprocess.Popen(
        [
            "ros2",
            "launch",
            "h2track_sim",
            "demo.launch.py",
            f"scene:={scene}",
            f"use_gaden:={use_gaden}",
            "use_rviz:=false",
            "headless:=true",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )


def _run_single_round(
    *,
    index: int,
    scene: str,
    use_gaden: str,
    run_timeout_sec: float,
    warmup_sec: float,
    log_dir: Path,
) -> RegressionRound:
    _run_demo_prep(scene, use_gaden)
    round_start = time.monotonic()
    launch_proc = _launch_round(scene, use_gaden, log_dir / f"round_{index}.log")
    try:
        time.sleep(max(0.0, warmup_sec))
        found, found_t_abs = _wait_for_source_found(run_timeout_sec)
        found_t = (time.monotonic() - round_start) if found else None
        notes = ""
        if not found:
            notes = "timeout"
        elif found_t_abs is not None:
            found_t = max(0.0, found_t_abs + max(0.0, warmup_sec))
        return RegressionRound(index=index, source_found=found, source_found_time=found_t, notes=notes)
    finally:
        _terminate_launch_process(launch_proc)
        _run_command(
            ["ros2", "run", "h2track_tracking", "demo_prep", "--scene", scene, "--use-gaden", use_gaden],
            check=False,
        )


def _wait_for_source_found(timeout_sec: float) -> tuple[bool, float | None]:
    """Wait for /source_found==true and return (found, elapsed_sec_from_wait_start)."""

    class _Probe(Node):
        def __init__(self) -> None:
            super().__init__("demo_regression_probe")
            self.found = False
            self.found_t: float | None = None
            self.start_t = time.monotonic()
            self.create_subscription(Bool, "/source_found", self._on_source, 10)

        def _on_source(self, msg: Bool) -> None:
            if bool(msg.data) and not self.found:
                self.found = True
                self.found_t = time.monotonic() - self.start_t

    started_here = not rclpy.ok()
    if started_here:
        rclpy.init()

    probe = _Probe()
    deadline = time.monotonic() + max(0.0, timeout_sec)
    try:
        while time.monotonic() < deadline and not probe.found:
            rclpy.spin_once(probe, timeout_sec=0.2)
        return probe.found, cast(float | None, probe.found_t)
    finally:
        probe.destroy_node()
        if started_here and rclpy.ok():
            rclpy.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeated warehouse+GADEN demo regression rounds.")
    parser.add_argument("--scene", default="warehouse")
    parser.add_argument("--use-gaden", choices=("true", "false"), default="true")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--run-timeout-sec", type=float, default=110.0)
    parser.add_argument("--warmup-sec", type=float, default=4.0)
    parser.add_argument("--log-dir", default="/tmp/h2track_regression_logs")
    args = parser.parse_args(argv)

    if args.rounds <= 0:
        raise SystemExit("--rounds must be > 0")

    log_dir = Path(args.log_dir)
    results: list[RegressionRound] = []

    for i in range(1, args.rounds + 1):
        result = _run_single_round(
            index=i,
            scene=args.scene,
            use_gaden=args.use_gaden,
            run_timeout_sec=float(args.run_timeout_sec),
            warmup_sec=float(args.warmup_sec),
            log_dir=log_dir,
        )
        results.append(result)
        if result.source_found:
            print(f"round {i}: SOURCE_FOUND at {result.source_found_time:.2f}s")
        else:
            note = f" ({result.notes})" if result.notes else ""
            print(f"round {i}: NO_SOURCE_FOUND{note}")

    summary = summarize_rounds(results)
    print("---")
    print(f"rounds: {summary['rounds']}")
    print(f"successes: {summary['successes']}")
    print(f"success_rate: {summary['success_rate']:.3f}")
    if summary["mean_source_found_time"] is None:
        print("mean_source_found_time: NA")
    else:
        print(f"mean_source_found_time: {summary['mean_source_found_time']:.2f}s")
    print(f"logs: {log_dir}")

    return 0 if int(summary["successes"]) == int(summary["rounds"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
