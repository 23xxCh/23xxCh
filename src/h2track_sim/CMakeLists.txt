cmake_minimum_required(VERSION 3.8)
project(h2track_sim)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  launch
  urdf
  worlds
  scenes
  maps
  config
  rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
