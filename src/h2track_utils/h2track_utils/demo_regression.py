"""Run repeated warehouse demo simulations and report navigation robustness."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path
import os
import re
import signal
import subprocess
import time
from typing import Any, cast

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool


@dataclass(frozen=True)
class RegressionRound:
    index: int
    success: bool
    seek_track_seen: bool
    source_found: bool
    source_found_seen: bool
    source_found_time: float | None
    failed_to_make_progress: int
    patrol_timeouts: int
    goal_succeeded: int
    notes: str


def parse_source_found_output(output: str) -> bool:
    text = output.lower()
    return "data: true" in text


def extract_round_metrics(log_text: str) -> dict[str, int | bool]:
    failed_to_make_progress = len(re.findall(r"Failed to make progress", log_text))
    patrol_timeouts = len(re.findall(r"Patrol goal timed out", log_text))
    goal_succeeded = len(re.findall(r"Goal succeeded", log_text))
    seek_track_seen = bool(re.search(r"Mode transition:\s+\w+\s+->\s+SEEK_TRACK", log_text))
    source_found_seen = bool(re.search(r"Mode transition:\s+\w+\s+->\s+SOURCE_FOUND", log_text))
    return {
        "failed_to_make_progress": failed_to_make_progress,
        "patrol_timeouts": patrol_timeouts,
        "goal_succeeded": goal_succeeded,
        "seek_track_seen": seek_track_seen,
        "source_found_seen": source_found_seen,
    }


def evaluate_round_success(
    *,
    failed_to_make_progress: int,
    goal_succeeded: int,
    seek_track_seen: bool,
    source_found: bool,
    require_seek_track: bool,
    require_source_found: bool,
) -> bool:
    if failed_to_make_progress > 0:
        return False
    if goal_succeeded <= 0:
        return False
    if require_seek_track and not seek_track_seen:
        return False
    if require_source_found and not source_found:
        return False
    return True


def summarize_rounds(rounds: list[RegressionRound]) -> dict[str, float | int | None]:
    total = len(rounds)
    successes = sum(1 for r in rounds if r.success)
    success_rate = (successes / total) if total else 0.0
    found_times = [r.source_found_time for r in rounds if r.source_found and r.source_found_time is not None]
    mean_time = (sum(found_times) / len(found_times)) if found_times else None
    seek_track_rounds = sum(1 for r in rounds if r.seek_track_seen)
    source_found_rounds = sum(1 for r in rounds if r.source_found)
    total_failed_progress = sum(r.failed_to_make_progress for r in rounds)
    total_patrol_timeouts = sum(r.patrol_timeouts for r in rounds)
    mean_goal_succeeded = (sum(r.goal_succeeded for r in rounds) / total) if total else 0.0
    return {
        "rounds": total,
        "successes": successes,
        "success_rate": success_rate,
        "seek_track_rounds": seek_track_rounds,
        "source_found_rounds": source_found_rounds,
        "total_failed_to_make_progress": total_failed_progress,
        "total_patrol_timeouts": total_patrol_timeouts,
        "mean_goal_succeeded": mean_goal_succeeded,
        "mean_source_found_time": mean_time,
    }


def extract_failure_hotspots(log_text: str, *, top_k: int = 5) -> list[dict[str, float | int]]:
    pose_from_nav_re = re.compile(
        r"Begin navigating from current location\s*\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)"
    )
    pose_from_mode_re = re.compile(
        r"pose=\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)"
    )
    fail_re = re.compile(r"Failed to make progress")
    counts: dict[tuple[float, float], int] = defaultdict(int)
    last_pose: tuple[float, float] | None = None

    for line in log_text.splitlines():
        nav_match = pose_from_nav_re.search(line)
        mode_match = pose_from_mode_re.search(line)
        if nav_match:
            last_pose = (float(nav_match.group(1)), float(nav_match.group(2)))
        elif mode_match:
            last_pose = (float(mode_match.group(1)), float(mode_match.group(2)))

        if fail_re.search(line) and last_pose is not None:
            key = (round(last_pose[0], 1), round(last_pose[1], 1))
            counts[key] += 1

    hotspots = [
        {"x": xy[0], "y": xy[1], "count": count}
        for xy, count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]
    return hotspots[: max(1, top_k)]


def write_rounds_csv(rounds: list[RegressionRound], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "round",
                "success",
                "seek_track_seen",
                "source_found",
                "source_found_seen",
                "source_found_time_sec",
                "failed_to_make_progress",
                "patrol_timeouts",
                "goal_succeeded",
                "notes",
            ]
        )
        for round_result in rounds:
            writer.writerow(
                [
                    round_result.index,
                    int(round_result.success),
                    int(round_result.seek_track_seen),
                    int(round_result.source_found),
                    int(round_result.source_found_seen),
                    "" if round_result.source_found_time is None else f"{round_result.source_found_time:.3f}",
                    round_result.failed_to_make_progress,
                    round_result.patrol_timeouts,
                    round_result.goal_succeeded,
                    round_result.notes,
                ]
            )


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


def build_demo_launch_command(*, scene: str, use_gaden: str, use_slam: str) -> list[str]:
    cmd = [
        "ros2",
        "launch",
        "h2track_sim",
        "demo.launch.py",
        f"scene:={scene}",
        f"use_gaden:={use_gaden}",
        "use_rviz:=false",
        "headless:=true",
    ]
    if use_slam in ("true", "false"):
        cmd.append(f"use_slam:={use_slam}")
    return cmd


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


def _launch_round(scene: str, use_gaden: str, use_slam: str, log_path: Path) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("wb")
    return subprocess.Popen(
        build_demo_launch_command(scene=scene, use_gaden=use_gaden, use_slam=use_slam),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )


def _run_single_round(
    *,
    index: int,
    scene: str,
    use_gaden: str,
    use_slam: str,
    require_seek_track: bool,
    require_source_found: bool,
    run_timeout_sec: float,
    warmup_sec: float,
    log_dir: Path,
) -> RegressionRound:
    _run_demo_prep(scene, use_gaden)
    round_start = time.monotonic()
    round_log = log_dir / f"round_{index}.log"
    launch_proc = _launch_round(scene, use_gaden, use_slam, round_log)
    try:
        time.sleep(max(0.0, warmup_sec))
        found, found_t_abs = _wait_for_source_found(run_timeout_sec)
        found_t = (time.monotonic() - round_start) if found else None
        if found and found_t_abs is not None:
            found_t = max(0.0, found_t_abs + max(0.0, warmup_sec))
    finally:
        _terminate_launch_process(launch_proc)
        _run_command(
            ["ros2", "run", "h2track_tracking", "demo_prep", "--scene", scene, "--use-gaden", use_gaden],
            check=False,
        )
    metrics = extract_round_metrics(round_log.read_text(encoding="utf-8", errors="replace"))
    source_found = found or bool(metrics["source_found_seen"])
    notes: list[str] = []
    if not source_found:
        notes.append("timeout")
    if int(metrics["failed_to_make_progress"]) > 0:
        notes.append("progress_fail")
    success = evaluate_round_success(
        failed_to_make_progress=int(metrics["failed_to_make_progress"]),
        goal_succeeded=int(metrics["goal_succeeded"]),
        seek_track_seen=bool(metrics["seek_track_seen"]),
        source_found=source_found,
        require_seek_track=require_seek_track,
        require_source_found=require_source_found,
    )
    return RegressionRound(
        index=index,
        success=success,
        seek_track_seen=bool(metrics["seek_track_seen"]),
        source_found=source_found,
        source_found_seen=bool(metrics["source_found_seen"]),
        source_found_time=found_t if source_found else None,
        failed_to_make_progress=int(metrics["failed_to_make_progress"]),
        patrol_timeouts=int(metrics["patrol_timeouts"]),
        goal_succeeded=int(metrics["goal_succeeded"]),
        notes=",".join(notes),
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
    parser.add_argument("--use-slam", choices=("auto", "true", "false"), default="auto")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--run-timeout-sec", type=float, default=240.0)
    parser.add_argument("--warmup-sec", type=float, default=4.0)
    parser.add_argument("--require-seek-track", action="store_true")
    parser.add_argument("--require-source-found", action="store_true")
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
            use_slam=args.use_slam,
            require_seek_track=bool(args.require_seek_track),
            require_source_found=bool(args.require_source_found),
            run_timeout_sec=float(args.run_timeout_sec),
            warmup_sec=float(args.warmup_sec),
            log_dir=log_dir,
        )
        results.append(result)
        if result.success:
            print(
                f"round {i}: OK"
                f" source_found={int(result.source_found)}"
                f" seek_track={int(result.seek_track_seen)}"
                f" progress_fail={result.failed_to_make_progress}"
                f" goals={result.goal_succeeded}"
            )
        else:
            note = f" ({result.notes})" if result.notes else ""
            print(
                f"round {i}: FAIL"
                f" source_found={int(result.source_found)}"
                f" seek_track={int(result.seek_track_seen)}"
                f" progress_fail={result.failed_to_make_progress}"
                f" goals={result.goal_succeeded}{note}"
            )

    summary = summarize_rounds(results)
    hotspot_counts: dict[tuple[float, float], int] = defaultdict(int)
    for i in range(1, args.rounds + 1):
        round_log = log_dir / f"round_{i}.log"
        if not round_log.exists():
            continue
        for spot in extract_failure_hotspots(round_log.read_text(encoding="utf-8", errors="replace"), top_k=20):
            key = (float(spot["x"]), float(spot["y"]))
            hotspot_counts[key] += int(spot["count"])
    summary["failure_hotspots"] = [
        {"x": xy[0], "y": xy[1], "count": count}
        for xy, count in sorted(hotspot_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:5]
    ]
    rounds_csv = log_dir / "rounds.csv"
    summary_json = log_dir / "summary.json"
    write_rounds_csv(results, rounds_csv)
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("---")
    print(f"rounds: {summary['rounds']}")
    print(f"successes: {summary['successes']}")
    print(f"success_rate: {summary['success_rate']:.3f}")
    print(f"seek_track_rounds: {summary['seek_track_rounds']}")
    print(f"source_found_rounds: {summary['source_found_rounds']}")
    print(f"total_failed_to_make_progress: {summary['total_failed_to_make_progress']}")
    print(f"total_patrol_timeouts: {summary['total_patrol_timeouts']}")
    print(f"mean_goal_succeeded: {summary['mean_goal_succeeded']:.2f}")
    if summary["mean_source_found_time"] is None:
        print("mean_source_found_time: NA")
    else:
        print(f"mean_source_found_time: {summary['mean_source_found_time']:.2f}s")
    print(f"logs: {log_dir}")
    print(f"rounds_csv: {rounds_csv}")
    print(f"summary_json: {summary_json}")

    return 0 if int(summary["successes"]) == int(summary["rounds"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
