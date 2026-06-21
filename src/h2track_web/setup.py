from setuptools import setup
from pathlib import Path


package_name = "h2track_web"


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
    packages=[
        package_name,
        f"{package_name}.web",
        f"{package_name}.llm",
        f"{package_name}.heatmap",
    ],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ] + _collect_static_files(),
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Web console and LLM assistant for the h2track system.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "demo_web_server = h2track_web.demo_web_server:main",
        ],
    },
)
