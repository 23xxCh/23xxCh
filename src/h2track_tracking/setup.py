from setuptools import setup

package_name = "h2track_tracking"

setup(
    name=package_name,
    version="0.1.0",
    packages=[
        package_name,
        f"{package_name}.particle_filter",
        f"{package_name}.tracking",
        f"{package_name}.bt",
        f"{package_name}.bt.nodes",
        f"{package_name}.bt_node_runner",
        f"{package_name}.multi_robot",
        f"{package_name}.benchmark",
        f"{package_name}.evaluation",
        f"{package_name}.heatmap",
        f"{package_name}.llm",
    ],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Core hydrogen tracking logic for the h2track system.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "bt_node_runner = h2track_tracking.bt_node_runner:main",
            "particle_filter_node = h2track_tracking.particle_filter.particle_filter_node:main",
            "ground_truth_sampler = h2track_tracking.evaluation.ground_truth_sampler:main",
        ],
    },
)
