# SourceEstimate.msg
uint8 robot_id
float32 x
float32 y
float32 confidence
float32[4] covariance  # [var_x, var_xy, var_yx, var_y]
builtin_interfaces/Time timestamp
