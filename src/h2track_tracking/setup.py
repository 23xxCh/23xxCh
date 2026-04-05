from setuptools import setup
from pathlib import Path


package_name = "h2track_tracking"


def _collect_static_files() -> list[tuple[str, list[str]]]:
    repo_root = Path(__file__).resolve().parent
    root = repo_root / package_name / "static_console"
    if not root.exists():
        return []
    rows: list[tuple[str, list[str]]] = []
    for directory in sorted({path.parent for path in root.rglob("*") if path.is_file()}):
        rel = directory.relative_to(root)
        target = str(Path("share") / package_name / "static_console" / rel)
        files = [str(path.relative_to(repo_root)) for path in sorted(directory.glob("*")) if path.is_file()]
        if files:
            rows.append((target, files))
    return rows

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name, f"{package_name}.web", f"{package_name}.llm", f"{package_name}.recovery"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ] + _collect_static_files(),
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Hydrogen tracking logic for the h2track-xian simulation workspace.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gas_field_node = h2track_tracking.gas_field_node:main",
            "gaden_adapter_node = h2track_tracking.gaden_adapter_node:main",
            "gaden_sensor_gate_node = h2track_tracking.gaden_sensor_gate_node:main",
            "nav2_startup_gate_node = h2track_tracking.nav2_startup_gate_node:main",
            "mission_manager_node = h2track_tracking.mission_manager_node:main",
            "demo_prep = h2track_tracking.demo_prep:main",
            "demo_selfcheck = h2track_tracking.demo_selfcheck:main",
            "demo_regression = h2track_tracking.demo_regression:main",
            "slam_save_map = h2track_tracking.slam_save_map:main",
            "demo_web_server = h2track_tracking.demo_web_server:main",
        ],
    },
)
