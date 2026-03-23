"""Prepare the H2track demo environment by clearing stale processes and checking package visibility."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
from typing import Callable

from ament_index_python.packages import (
    PackageNotFoundError,
    get_package_prefix,
    get_package_share_directory,
)
import yaml


BASELINE_WORLD_PATH = Path(
    "/home/user/h2track-xian/install/h2track_sim/share/h2track_sim/worlds/h2track_lab.world"
)
CORE_REQUIRED_PACKAGES = (
    "h2track_sim",
    "h2track_tracking",
)
GADEN_REQUIRED_PACKAGES = (
    "simulated_gas_sensor",
    "gaden_player",
)
REQUIRED_PACKAGES = CORE_REQUIRED_PACKAGES + GADEN_REQUIRED_PACKAGES


@dataclass(frozen=True)
class MatchedProcess:
    pid: int
    kind: str
    command: str


@dataclass(frozen=True)
class PrepReport:
    ok: bool
    errors: list[str] = field(default_factory=list)


def find_stale_processes(ps_output: str, demo_world_path: Path = BASELINE_WORLD_PATH) -> list[MatchedProcess]:
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
        if _is_h2track_gazebo_process(command, demo_world_path):
            matches.append(MatchedProcess(pid=pid, kind="gazebo", command=command))
            continue
        if _is_h2track_nav2_lifecycle_process(command):
            matches.append(MatchedProcess(pid=pid, kind="nav2_lifecycle_manager", command=command))
            continue
        if _is_h2track_nav2_startup_gate_process(command):
            matches.append(MatchedProcess(pid=pid, kind="nav2_startup_gate", command=command))
            continue
        if _is_h2track_gaden_sensor_gate_process(command):
            matches.append(MatchedProcess(pid=pid, kind="gaden_sensor_gate", command=command))
    return matches


def check_required_packages(
    resolve_package: Callable[[str], str | None],
    required_packages: tuple[str, ...] = REQUIRED_PACKAGES,
) -> dict[str, bool]:
    return {name: bool(resolve_package(name)) for name in required_packages}


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


def resolve_use_gaden(mode: str, scene_profile: dict) -> bool:
    if mode == "true":
        return True
    if mode == "false":
        return False
    return bool(scene_profile.get("use_gaden", False))


def required_packages_for_scene(*, use_gaden: bool) -> tuple[str, ...]:
    if use_gaden:
        return REQUIRED_PACKAGES
    return CORE_REQUIRED_PACKAGES


def resolve_scene_world_path(scene_profile: dict, package_share: str | Path) -> Path:
    world_path = Path(scene_profile["world"])
    if world_path.is_absolute():
        return world_path
    return Path(package_share) / world_path


def default_scene_profile(scene_name: str) -> dict:
    if scene_name == "baseline":
        return {
            "scene_name": "baseline",
            "world": str(BASELINE_WORLD_PATH),
            "use_gaden": True,
        }
    raise PackageNotFoundError(f"scene '{scene_name}' requires an installed h2track_sim package")


def load_scene_profile(scene_name: str, package_share_resolver: Callable[[str], str] | None = None) -> dict:
    resolver = package_share_resolver or get_package_share_directory
    package_share = Path(resolver("h2track_sim"))
    scene_path = package_share / "scenes" / scene_name / "scene.yaml"
    return yaml.safe_load(scene_path.read_text(encoding="utf-8"))


def find_fastdds_lock_paths(shm_root: Path = Path("/dev/shm")) -> list[Path]:
    try:
        return sorted(shm_root.glob("fastrtps_port*"))
    except OSError:
        return []


def main(
    argv: list[str] | None = None,
    *,
    ps_output: str | None = None,
    kill_process: Callable[[int], None] | None = None,
    package_resolver: Callable[[str], str | None] | None = None,
    scene_profile_loader: Callable[[str], dict] | None = None,
    package_share_resolver: Callable[[str], str] | None = None,
    fastdds_lock_paths: list[Path] | None = None,
    remove_path: Callable[[Path], None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Prepare the H2track demo environment.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be cleaned without killing processes.")
    parser.add_argument("--scene", default="baseline", help="Scene name to validate and clean for.")
    parser.add_argument(
        "--use-gaden",
        choices=("auto", "true", "false"),
        default="auto",
        help="Whether to require GADEN packages. auto follows the selected scene config.",
    )
    args = parser.parse_args(argv)

    share_resolver = package_share_resolver or get_package_share_directory
    try:
        package_share = Path(share_resolver("h2track_sim"))
    except PackageNotFoundError:
        package_share = Path("/")

    scene_loader = scene_profile_loader or (
        lambda scene_name: load_scene_profile(scene_name, package_share_resolver=share_resolver)
    )
    try:
        scene_profile = scene_loader(args.scene)
    except PackageNotFoundError:
        scene_profile = default_scene_profile(args.scene)
    use_gaden = resolve_use_gaden(args.use_gaden, scene_profile)
    demo_world_path = resolve_scene_world_path(scene_profile, package_share)
    required_packages = required_packages_for_scene(use_gaden=use_gaden)

    processes = find_stale_processes(
        ps_output if ps_output is not None else _read_process_table(),
        demo_world_path=demo_world_path,
    )
    resolver = package_resolver or _resolve_package
    package_status = check_required_packages(resolver, required_packages)
    kill = kill_process or _kill_process
    remove = remove_path or _remove_path
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

    lock_paths = fastdds_lock_paths if fastdds_lock_paths is not None else find_fastdds_lock_paths()
    for lock_path in lock_paths:
        lock_str = str(lock_path)
        print(f"stale fastdds lock: {lock_str}")
        if args.dry_run:
            print(f"would remove lock: {lock_str}")
            continue
        try:
            remove(lock_path)
            print(f"removed lock: {lock_str}")
        except OSError as exc:
            kill_failures.append(f"Failed to remove lock {lock_str}: {exc}")
    if args.dry_run and lock_paths:
        kill_failures.append("dry-run found fastdds locks")

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


def _is_h2track_gazebo_process(command: str, demo_world_path: Path) -> bool:
    return (
        (command.startswith("gzserver ") or command.startswith("gazebo "))
        and str(demo_world_path) in command
    )


def _is_h2track_nav2_lifecycle_process(command: str) -> bool:
    return "nav2_lifecycle_manager/lifecycle_manager" in command and "__node:=lifecycle_manager_navigation" in command


def _is_h2track_nav2_startup_gate_process(command: str) -> bool:
    return (
        "h2track_tracking/nav2_startup_gate_node" in command
        and "__node:=nav2_startup_gate_node" in command
    )


def _is_h2track_gaden_sensor_gate_process(command: str) -> bool:
    return (
        "h2track_tracking/gaden_sensor_gate_node" in command
        and "__node:=gaden_sensor_gate_node" in command
    )


def _read_process_table() -> str:
    return subprocess.check_output(["ps", "-ef"], text=True)


def _kill_process(pid: int) -> None:
    os.kill(pid, signal.SIGKILL)


def _remove_path(path: Path) -> None:
    path.unlink(missing_ok=True)


def _resolve_package(package_name: str) -> str | None:
    try:
        return get_package_prefix(package_name)
    except PackageNotFoundError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
