cmake_minimum_required(VERSION 3.8)
project(h2track_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  launch
  config
  scenes
  maps
  rviz
  worlds
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_bringup_launch test/test_bringup_launch.py)
  ament_add_pytest_test(test_demo_launch test/test_demo_launch.py)
  ament_add_pytest_test(test_launch_timing test/test_launch_timing.py)
  ament_add_pytest_test(test_scene_config test/test_scene_config.py)
  ament_add_pytest_test(test_warehouse_map_contract test/test_warehouse_map_contract.py)
endif()

ament_package()
