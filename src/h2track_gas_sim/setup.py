from setuptools import setup

package_name = "h2track_gas_sim"

setup(
    name=package_name,
    version="0.1.0",
    packages=[
        package_name,
        f"{package_name}.gas_sensor",
    ],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Gas simulation nodes for the h2track system.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gas_field_node = h2track_gas_sim.gas_field_node:main",
            "gaden_adapter_node = h2track_gas_sim.gaden_adapter_node:main",
            "gaden_sensor_gate_node = h2track_gas_sim.gaden_sensor_gate_node:main",
            "anemometer_adapter_node = h2track_gas_sim.anemometer_adapter_node:main",
            "gas_sensor_node = h2track_gas_sim.gas_sensor.gas_sensor_node:main",
        ],
    },
)
