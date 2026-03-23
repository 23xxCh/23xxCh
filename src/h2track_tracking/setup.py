from setuptools import setup

package_name = "h2track_tracking"

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
            "mapping_mission_manager_node = h2track_tracking.mapping_mission_manager_node:main",
            "exploration_manager_node = h2track_tracking.exploration_manager_node:main",
            "transition_manager_node = h2track_tracking.transition_manager_node:main",
            "autonomy_eval = h2track_tracking.autonomy_eval:main",
            "demo_prep = h2track_tracking.demo_prep:main",
            "demo_selfcheck = h2track_tracking.demo_selfcheck:main",
        ],
    },
)
