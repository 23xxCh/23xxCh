from setuptools import setup

package_name = "h2track_utils"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Utility tools and navigation helpers for the h2track system.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "demo_prep = h2track_utils.demo_prep:main",
            "demo_selfcheck = h2track_utils.demo_selfcheck:main",
            "demo_regression = h2track_utils.demo_regression:main",
            "nav2_startup_gate_node = h2track_utils.nav2_startup_gate_node:main",
            "slam_save_map = h2track_utils.slam_save_map:main",
            "activate_localization = h2track_utils.activate_localization:main",
        ],
    },
)
