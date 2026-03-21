"""Prepare the H2track demo environment by clearing stale processes and checking package visibility."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
from typing import Callable

from ament_index_python.packages import PackageNotFoundError, get_package_prefix


DEMO_WORLD_PATH = Path(
    "/home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/h2track_lab.world"
)
REQUIRED_PACKAGES = (
    "h2track_sim",
    "h2track_tracking",
    "simulated_gas_sensor",
    "gaden_player",
)


@dataclass(frozen=True)
class MatchedProcess:
    pid: int
    kind: str
    command: str


@dataclass(frozen=True)
class PrepReport:
    ok: bool
    errors: list[str] = field(default_factory=list)


def find_stale_processes(ps_output: str) -> list[MatchedProcess]:
    matches: list[MatchedProcess] = []
    for line in ps_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        command = parts[7]
        if _is_h2track_gazebo_process(command):
            matches.append(MatchedProcess(pid=pid, kind="gazebo", command=command))
            continue
        if _is_h2track_nav2_lifecycle_process(command):
            matches.append(MatchedProcess(pid=pid, kind="nav2_lifecycle_manager", command=command))
    return matches


def check_required_packages(resolve_package: Callable[[str], str | None]) -> dict[str, bool]:
    return {name: bool(resolve_package(name)) for name in REQUIRED_PACKAGES}


def evaluate_prep_result(
    *,
    processes: list[MatchedProcess],
    package_status: dict[str, bool],
    dry_run: bool,
    kill_failures: list[str],
) -> PrepReport:
    errors: list[str] = []

    missing_packages = [name for name, ok in package_status.items() if not ok]
    if missing_packages:
        errors.append(f"Missing packages: {', '.join(missing_packages)}")

    if kill_failures:
        errors.extend(kill_failures)

    if dry_run and processes:
        errors.append("dry-run found stale processes")

    return PrepReport(ok=not errors, errors=errors)


def main(
    argv: list[str] | None = None,
    *,
    ps_output: str | None = None,
    kill_process: Callable[[int], None] | None = None,
    package_resolver: Callable[[str], str | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Prepare the H2track demo environment.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be cleaned without killing processes.")
    args = parser.parse_args(argv)

    processes = find_stale_processes(ps_output if ps_output is not None else _read_process_table())
    resolver = package_resolver or _resolve_package
    package_status = check_required_packages(resolver)
    kill = kill_process or _kill_process
    kill_failures: list[str] = []

    for process in processes:
        print(f"stale process: {process.kind} pid={process.pid}")
        if args.dry_run:
            print(f"would kill pid={process.pid}")
            continue
        try:
            kill(process.pid)
            print(f"killed pid={process.pid}")
        except OSError as exc:
            kill_failures.append(f"Failed to kill pid {process.pid}: {exc}")

    for package_name, ok in package_status.items():
        if ok:
            print(f"package ok: {package_name}")
        else:
            print(f"missing package: {package_name}")

    report = evaluate_prep_result(
        processes=processes,
        package_status=package_status,
        dry_run=args.dry_run,
        kill_failures=kill_failures,
    )
    if report.ok:
        print("DEMO PREP OK")
        return 0

    print("DEMO PREP FAILED")
    for error in report.errors:
        print(f"- {error}")
    return 1


def _is_h2track_gazebo_process(command: str) -> bool:
    return (
        (command.startswith("gzserver ") or command.startswith("gazebo "))
        and str(DEMO_WORLD_PATH) in command
    )


def _is_h2track_nav2_lifecycle_process(command: str) -> bool:
    return "nav2_lifecycle_manager/lifecycle_manager" in command and "__node:=lifecycle_manager_navigation" in command


def _read_process_table() -> str:
    return subprocess.check_output(["ps", "-ef"], text=True)


def _kill_process(pid: int) -> None:
    os.kill(pid, signal.SIGKILL)


def _resolve_package(package_name: str) -> str | None:
    try:
        return get_package_prefix(package_name)
    except PackageNotFoundError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
