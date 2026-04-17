# RobotState.msg
uint8 robot_id
float32 x
float32 y
float32 yaw
string mode  # PATROL, SURGE, CAST, VERIFY
float32 concentration
builtin_interfaces/Time timestamp
