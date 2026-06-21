cmake_minimum_required(VERSION 3.8)
project(h2track_sim)

find_package(ament_cmake REQUIRED)

# h2track_sim is now a metapackage — all assets have been moved to:
# - h2track_description (URDF, meshes)
# - h2track_bringup (launch, config, scenes, maps, rviz, worlds)

ament_package()
