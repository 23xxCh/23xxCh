from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess

from nav_msgs.msg import OccupancyGrid
import rclpy
from nav2_msgs.srv import ManageLifecycleNodes, SaveMap
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Bool, Float32
from tf2_ros import Buffer, TransformException, TransformListener


def transform_point_into_map_frame(
    point_xy: tuple[float, float],
    translation_xy: tuple[float, float],
    yaw: float,
) -> tuple[float, float]:
    x, y = point_xy
    tx, ty = translation_xy
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    return (
        tx + cos_yaw * x - sin_yaw * y,
        ty + sin_yaw * x + cos_yaw * y,
    )


def freeze_gate_ready(
    map_ready: bool,
    valid_map_samples: int,
    first_valid_map_time_sec: float | None,
    now_sec: float,
    min_map_samples: int,
    min_map_age_sec: float,
) -> bool:
    if not map_ready:
        return False
    if valid_map_samples < min_map_samples:
        return False
    if first_valid_map_time_sec is None:
        return False
    return (now_sec - first_valid_map_time_sec) >= min_map_age_sec


def resolve_tracking_source_point(
    source_xy: tuple[float, float],
    source_frame: str,
    map_to_odom_transform: tuple[tuple[float, float], float] | None,
) -> tuple[float, float] | None:
    if source_frame == "map":
        return source_xy
    if source_frame == "odom":
        if map_to_odom_transform is None:
            return None
        return transform_point_into_map_frame(source_xy, map_to_odom_transform[0], map_to_odom_transform[1])
    raise ValueError(f"Unsupported source frame: {source_frame}")


def clamp_tracking_source_seed(
    source_xy: tuple[float, float],
    current_xy: tuple[float, float],
    max_distance: float,
) -> tuple[float, float]:
    if max_distance <= 0.0:
        return source_xy
    dx = source_xy[0] - current_xy[0]
    dy = source_xy[1] - current_xy[1]
    distance = math.hypot(dx, dy)
    if distance <= max_distance or distance <= 1e-9:
        return source_xy
    scale = max_distance / distance
    return (
        current_xy[0] + dx * scale,
        current_xy[1] + dy * scale,
    )


def snap_tracking_source_to_free_space(
    source_xy: tuple[float, float],
    occupancy_grid: OccupancyGrid | None,
    max_search_cells: int,
) -> tuple[float, float]:
    if occupancy_grid is None:
        return source_xy

    info = occupancy_grid.info
    resolution = float(info.resolution)
    width = int(info.width)
    height = int(info.height)
    if resolution <= 0.0 or width <= 0 or height <= 0:
        return source_xy

    origin_x = float(info.origin.position.x)
    origin_y = float(info.origin.position.y)
    data = occupancy_grid.data

    def world_to_grid(point_xy: tuple[float, float]) -> tuple[int, int]:
        gx = int(math.floor((point_xy[0] - origin_x) / resolution))
        gy = int(math.floor((point_xy[1] - origin_y) / resolution))
        return gx, gy

    def grid_to_world(gx: int, gy: int) -> tuple[float, float]:
        return (
            origin_x + (gx + 0.5) * resolution,
            origin_y + (gy + 0.5) * resolution,
        )

    def in_bounds(gx: int, gy: int) -> bool:
        return 0 <= gx < width and 0 <= gy < height

    def is_free(gx: int, gy: int) -> bool:
        if not in_bounds(gx, gy):
            return False
        value = data[gy * width + gx]
        return 0 <= value < 50

    source_gx, source_gy = world_to_grid(source_xy)
    source_gx = min(max(source_gx, 0), width - 1)
    source_gy = min(max(source_gy, 0), height - 1)

    if is_free(source_gx, source_gy):
        return source_xy

    search_limit = max(1, int(max_search_cells))
    for radius in range(1, search_limit + 1):
        best: tuple[float, int, int] | None = None
        for gx in range(source_gx - radius, source_gx + radius + 1):
            for gy in range(source_gy - radius, source_gy + radius + 1):
                if max(abs(gx - source_gx), abs(gy - source_gy)) != radius:
                    continue
                if not is_free(gx, gy):
                    continue
                distance = math.hypot(gx - source_gx, gy - source_gy)
                if best is None or distance < best[0]:
                    best = (distance, gx, gy)
        if best is not None:
            return grid_to_world(best[1], best[2])

    return source_xy


class TransitionManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("transition_manager_node")
        self.declare_parameter("scene_name", "baseline")
        self.declare_parameter("source_x", -4.0)
        self.declare_parameter("source_y", 1.95)
        self.declare_parameter("source_frame", "map")
        self.declare_parameter("tracking_enter_threshold", -1.0)
        self.declare_parameter("tracking_exit_threshold", -1.0)
        self.declare_parameter("tracking_source_threshold", -1.0)
        self.declare_parameter("tracking_confirm_samples", -1)
        self.declare_parameter("tracking_track_exit_samples", -1)
        self.declare_parameter("tracking_source_radius", -1.0)
        self.declare_parameter("tracking_source_hold_steps", -1)
        self.declare_parameter("save_map_service", "/map_saver_server/save_map")
        self.declare_parameter(
            "lifecycle_manager_service",
            "/lifecycle_manager_navigation/manage_nodes",
        )
        self.declare_parameter("runtime_map_dir", "/tmp/h2track_runtime_maps")
        self.declare_parameter("tracking_launch_file", "tracking_localization.launch.py")
        self.declare_parameter("tracking_disable_fastdds_shm", True)
        self.declare_parameter("tracking_launch_healthcheck_sec", 5.0)
        self.declare_parameter("tracking_source_seed_max_distance", 2.0)
        self.declare_parameter("tracking_source_snap_max_cells", 25)
        self.declare_parameter("tracking_source_from_peak", False)
        self.declare_parameter("tracking_source_peak_min_concentration", 0.8)
        self.declare_parameter("freeze_ready_min_map_samples", 2)
        self.declare_parameter("freeze_ready_min_map_age_sec", 2.0)

        service_name = str(self.get_parameter("save_map_service").value)
        lifecycle_service_name = str(self.get_parameter("lifecycle_manager_service").value)
        self._runtime_map_dir = Path(str(self.get_parameter("runtime_map_dir").value))
        self._tracking_launch_file = str(self.get_parameter("tracking_launch_file").value)
        self._tracking_launch_healthcheck_sec = float(
            self.get_parameter("tracking_launch_healthcheck_sec").value
        )
        self._tracking_source_seed_max_distance = float(
            self.get_parameter("tracking_source_seed_max_distance").value
        )
        self._tracking_source_snap_max_cells = int(
            self.get_parameter("tracking_source_snap_max_cells").value
        )
        self._tracking_source_from_peak = bool(
            self.get_parameter("tracking_source_from_peak").value
        )
        self._tracking_source_peak_min_concentration = float(
            self.get_parameter("tracking_source_peak_min_concentration").value
        )
        self._freeze_ready_min_map_samples = int(
            self.get_parameter("freeze_ready_min_map_samples").value
        )
        self._freeze_ready_min_map_age_sec = float(
            self.get_parameter("freeze_ready_min_map_age_sec").value
        )
        self._save_map_client = self.create_client(SaveMap, service_name)
        self._lifecycle_manager_client = self.create_client(
            ManageLifecycleNodes,
            lifecycle_service_name,
        )
        self._map_frozen_pub = self.create_publisher(Bool, "/map_frozen", 10)
        self._tracking_handoff_complete_pub = self.create_publisher(
            Bool, "/tracking_handoff_complete", 10
        )
        self._tracking_handoff_failed_pub = self.create_publisher(
            Bool, "/tracking_handoff_failed", 10
        )
        self._tf_buffer = Buffer(cache_time=Duration(seconds=5.0))
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._save_requested = False
        self._freeze_pending = False
        self._save_future = None
        self._shutdown_future = None
        self._pending_tracking_pose: tuple[float, float, float] | None = None
        self._pending_tracking_source: tuple[float, float] | None = None
        self._pending_tracking_model_source: tuple[float, float] | None = None
        self._current_map_path: Path | None = None
        self._tracking_process: subprocess.Popen[str] | None = None
        self._tracking_launch_started_sec: float | None = None
        self._tracking_handoff_announced = False
        self._tracking_handoff_failed = False
        self._valid_map_samples = 0
        self._first_valid_map_time_sec: float | None = None
        self._last_freeze_wait_log_sec = 0.0
        self._latest_map: OccupancyGrid | None = None
        self._peak_concentration = float("-inf")
        self._peak_source_xy: tuple[float, float] | None = None

        self.create_subscription(Bool, "/freeze_map_requested", self._freeze_callback, 10)
        self.create_subscription(OccupancyGrid, "/map", self._map_callback, 10)
        self.create_subscription(Float32, "/gas_concentration", self._gas_callback, 10)
        self.create_timer(0.25, self._poll_save_future)

    def _freeze_callback(self, msg: Bool) -> None:
        if not msg.data or self._save_requested or self._freeze_pending:
            return
        self._freeze_pending = True
        self.get_logger().info("Freeze requested; waiting for map_saver/save_map service")

    def _map_callback(self, msg: OccupancyGrid) -> None:
        self._latest_map = msg
        if msg.info.width <= 0 or msg.info.height <= 0:
            return
        self._valid_map_samples += 1
        now_sec = self.get_clock().now().nanoseconds / 1e9
        if self._first_valid_map_time_sec is None:
            self._first_valid_map_time_sec = now_sec

    def _gas_callback(self, msg: Float32) -> None:
        if not self._tracking_source_from_peak:
            return
        concentration = float(msg.data)
        if concentration < self._tracking_source_peak_min_concentration:
            return
        pose = self._lookup_current_map_pose(log_errors=False)
        if pose is None:
            return
        if concentration > self._peak_concentration:
            self._peak_concentration = concentration
            self._peak_source_xy = (pose[0], pose[1])
            self.get_logger().info(
                "Updated tracking source peak candidate to "
                f"({pose[0]:.3f}, {pose[1]:.3f}) @ {concentration:.3f}"
            )

    def _freeze_map_ready(self) -> bool:
        now_sec = self.get_clock().now().nanoseconds / 1e9
        map_ready = self._lookup_current_map_pose() is not None
        ready = freeze_gate_ready(
            map_ready=map_ready,
            valid_map_samples=self._valid_map_samples,
            first_valid_map_time_sec=self._first_valid_map_time_sec,
            now_sec=now_sec,
            min_map_samples=self._freeze_ready_min_map_samples,
            min_map_age_sec=self._freeze_ready_min_map_age_sec,
        )
        if not ready and (now_sec - self._last_freeze_wait_log_sec) >= 2.0:
            self.get_logger().info(
                "Freeze gate waiting for SLAM map readiness "
                f"(samples={self._valid_map_samples}/{self._freeze_ready_min_map_samples}, "
                f"first_map_age={0.0 if self._first_valid_map_time_sec is None else now_sec - self._first_valid_map_time_sec:.2f}s)"
            )
            self._last_freeze_wait_log_sec = now_sec
        return ready

    def _lookup_current_map_pose(self, *, log_errors: bool = True) -> tuple[float, float, float] | None:
        try:
            transform = self._tf_buffer.lookup_transform(
                "map",
                "base_link",
                Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException as exc:
            if log_errors:
                self.get_logger().error(f"Failed to look up robot pose for relocalization: {exc}")
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z),
        )
        return translation.x, translation.y, yaw

    def _stop_slam_toolbox(self) -> None:
        subprocess.run(
            ["pkill", "-f", "async_slam_toolbox_node"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_primary_navigation_processes(self) -> None:
        process_patterns = (
            "/nav2_controller/controller_server",
            "/nav2_smoother/smoother_server",
            "/nav2_planner/planner_server",
            "/nav2_behaviors/behavior_server",
            "/nav2_bt_navigator/bt_navigator",
            "/nav2_waypoint_follower/waypoint_follower",
            "/nav2_velocity_smoother/velocity_smoother",
            "__node:=lifecycle_manager_navigation",
        )
        for pattern in process_patterns:
            subprocess.run(
                ["pkill", "-f", pattern],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _lookup_map_to_odom_transform(self) -> tuple[tuple[float, float], float] | None:
        try:
            transform = self._tf_buffer.lookup_transform(
                "map",
                "odom",
                Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException as exc:
            self.get_logger().error(f"Failed to look up map->odom transform for source projection: {exc}")
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z),
        )
        return (translation.x, translation.y), yaw

    def _resolve_tracking_source(self) -> tuple[float, float] | None:
        if self._tracking_source_from_peak and self._peak_source_xy is not None:
            self.get_logger().info(
                "Using observed peak concentration position as tracking source "
                f"({self._peak_source_xy[0]:.3f}, {self._peak_source_xy[1]:.3f})"
            )
            return self._peak_source_xy

        source_point = (
            float(self.get_parameter("source_x").value),
            float(self.get_parameter("source_y").value),
        )
        source_frame = str(self.get_parameter("source_frame").value)
        map_to_odom_transform = None
        if source_frame == "odom":
            map_to_odom_transform = self._lookup_map_to_odom_transform()
            if map_to_odom_transform is None:
                return None
        return resolve_tracking_source_point(source_point, source_frame, map_to_odom_transform)

    def _request_navigation_shutdown(self) -> bool:
        if self._shutdown_future is not None:
            return True
        if not self._lifecycle_manager_client.wait_for_service(timeout_sec=0.0):
            self.get_logger().error(
                "Cannot hand off to tracking: lifecycle manager service is unavailable"
            )
            return False
        request = ManageLifecycleNodes.Request()
        request.command = ManageLifecycleNodes.Request.SHUTDOWN
        self._shutdown_future = self._lifecycle_manager_client.call_async(request)
        self.get_logger().info("Requested navigation lifecycle shutdown before tracking handoff")
        return True

    def _complete_handoff_after_shutdown(self) -> None:
        if self._shutdown_future is None or not self._shutdown_future.done():
            return
        response = self._shutdown_future.result()
        if response is not None and response.success:
            if (
                self._pending_tracking_pose is None
                or self._pending_tracking_source is None
                or self._pending_tracking_model_source is None
            ):
                self.get_logger().error("Tracking handoff data missing after navigation shutdown")
            else:
                self._stop_primary_navigation_processes()
                self._stop_slam_toolbox()
                self._launch_tracking_localization(
                    self._pending_tracking_pose,
                    self._pending_tracking_source,
                    self._pending_tracking_model_source,
                )
                self._map_frozen_pub.publish(Bool(data=True))
                self.get_logger().info("Frozen map saved successfully")
        else:
            self.get_logger().error(
                "Failed to shut down navigation lifecycle stack before tracking handoff"
            )
        self._shutdown_future = None
        self._pending_tracking_pose = None
        self._pending_tracking_source = None
        self._pending_tracking_model_source = None

    def _launch_tracking_localization(
        self,
        pose: tuple[float, float, float],
        actual_source_xy: tuple[float, float],
        model_source_xy: tuple[float, float],
    ) -> None:
        if self._tracking_process is not None and self._tracking_process.poll() is None:
            self.get_logger().info("Tracking localization launch is already running")
            return
        if self._current_map_path is None:
            self.get_logger().error("Cannot launch tracking localization without a frozen runtime map")
            return

        scene_name = str(self.get_parameter("scene_name").value)
        use_sim_time = "true" if bool(self.get_parameter("use_sim_time").value) else "false"
        launch_cmd = [
            "ros2",
            "launch",
            "h2track_sim",
            self._tracking_launch_file,
            f"scene:={scene_name}",
            f"use_sim_time:={use_sim_time}",
            f"runtime_map:={self._current_map_path}",
            f"initial_pose_x:={pose[0]}",
            f"initial_pose_y:={pose[1]}",
            f"initial_pose_yaw:={pose[2]}",
            f"source_x:={actual_source_xy[0]}",
            f"source_y:={actual_source_xy[1]}",
        ]
        launch_cmd.append(f"model_source_x:={model_source_xy[0]}")
        launch_cmd.append(f"model_source_y:={model_source_xy[1]}")

        tracking_enter_threshold = float(self.get_parameter("tracking_enter_threshold").value)
        tracking_exit_threshold = float(self.get_parameter("tracking_exit_threshold").value)
        tracking_source_threshold = float(self.get_parameter("tracking_source_threshold").value)
        tracking_confirm_samples = int(self.get_parameter("tracking_confirm_samples").value)
        tracking_track_exit_samples = int(self.get_parameter("tracking_track_exit_samples").value)
        tracking_source_radius = float(self.get_parameter("tracking_source_radius").value)
        tracking_source_hold_steps = int(self.get_parameter("tracking_source_hold_steps").value)

        if tracking_enter_threshold > 0.0:
            launch_cmd.append(f"enter_threshold:={tracking_enter_threshold}")
        if tracking_exit_threshold > 0.0:
            launch_cmd.append(f"exit_threshold:={tracking_exit_threshold}")
        if tracking_source_threshold > 0.0:
            launch_cmd.append(f"source_threshold:={tracking_source_threshold}")
        if tracking_confirm_samples > 0:
            launch_cmd.append(f"confirm_samples:={tracking_confirm_samples}")
        if tracking_track_exit_samples > 0:
            launch_cmd.append(f"track_exit_samples:={tracking_track_exit_samples}")
        if tracking_source_radius > 0.0:
            launch_cmd.append(f"source_radius:={tracking_source_radius}")
        if tracking_source_hold_steps > 0:
            launch_cmd.append(f"source_hold_steps:={tracking_source_hold_steps}")

        env = os.environ.copy()
        if bool(self.get_parameter("tracking_disable_fastdds_shm").value):
            env["FASTDDS_BUILTIN_TRANSPORTS"] = "UDPv4"
        self._tracking_process = subprocess.Popen(launch_cmd, env=env)
        self._tracking_launch_started_sec = self.get_clock().now().nanoseconds / 1e9
        self._tracking_handoff_announced = False
        self._tracking_handoff_failed = False
        self._tracking_handoff_complete_pub.publish(Bool(data=False))
        self._tracking_handoff_failed_pub.publish(Bool(data=False))
        self.get_logger().info(
            "Launching tracking localization with runtime map "
            f"{self._current_map_path} and source target ({actual_source_xy[0]:.3f}, {actual_source_xy[1]:.3f}) "
            f"with tracking model seed ({model_source_xy[0]:.3f}, {model_source_xy[1]:.3f})"
        )

    def _poll_tracking_handoff(self) -> None:
        if self._tracking_process is None or self._tracking_launch_started_sec is None:
            return

        return_code = self._tracking_process.poll()
        if return_code is not None:
            if not self._tracking_handoff_failed:
                self._tracking_handoff_failed = True
                self._tracking_handoff_failed_pub.publish(Bool(data=True))
                self.get_logger().error(
                    "Tracking handoff failed: tracking localization launch exited "
                    f"with code {return_code}"
                )
            return

        if self._tracking_handoff_announced:
            return

        now_sec = self.get_clock().now().nanoseconds / 1e9
        if (now_sec - self._tracking_launch_started_sec) < self._tracking_launch_healthcheck_sec:
            return

        self._tracking_handoff_announced = True
        self._tracking_handoff_complete_pub.publish(Bool(data=True))
        self.get_logger().info("Tracking handoff complete")

    def _poll_save_future(self) -> None:
        self._complete_handoff_after_shutdown()
        self._poll_tracking_handoff()

        if self._freeze_pending and self._save_future is None:
            if not self._save_map_client.wait_for_service(timeout_sec=0.0):
                return
            if not self._freeze_map_ready():
                return

            self._runtime_map_dir.mkdir(parents=True, exist_ok=True)
            scene_name = str(self.get_parameter("scene_name").value)
            request = SaveMap.Request()
            request.map_topic = "/map"
            request.map_url = str(self._runtime_map_dir / f"{scene_name}_freeze_map")
            request.image_format = "pgm"
            request.map_mode = "trinary"
            request.free_thresh = 0.25
            request.occupied_thresh = 0.65

            self._current_map_path = Path(f"{request.map_url}.yaml")
            self._save_future = self._save_map_client.call_async(request)
            self._save_requested = True
            self._freeze_pending = False
            self.get_logger().info(f"Saving frozen map to {request.map_url}")

        if self._save_future is None or not self._save_future.done():
            return

        response = self._save_future.result()
        if response is not None and response.result:
            pose = self._lookup_current_map_pose()
            if pose is None:
                self._save_future = None
                return
            tracking_source = self._resolve_tracking_source()
            if tracking_source is None:
                self._save_future = None
                return
            clamped_source = clamp_tracking_source_seed(
                tracking_source,
                (pose[0], pose[1]),
                self._tracking_source_seed_max_distance,
            )
            if clamped_source != tracking_source:
                self.get_logger().info(
                    "Clamped projected source seed for tracking handoff from "
                    f"({tracking_source[0]:.3f}, {tracking_source[1]:.3f}) to "
                    f"({clamped_source[0]:.3f}, {clamped_source[1]:.3f})"
                )
            tracking_model_source = clamped_source
            snapped_source = snap_tracking_source_to_free_space(
                tracking_model_source,
                self._latest_map,
                self._tracking_source_snap_max_cells,
            )
            if snapped_source != tracking_model_source:
                self.get_logger().info(
                    "Snapped tracking source seed to nearest free map cell from "
                    f"({tracking_model_source[0]:.3f}, {tracking_model_source[1]:.3f}) to "
                    f"({snapped_source[0]:.3f}, {snapped_source[1]:.3f})"
                )
            tracking_model_source = snapped_source
            self._pending_tracking_pose = pose
            self._pending_tracking_source = tracking_source
            self._pending_tracking_model_source = tracking_model_source
            if not self._request_navigation_shutdown():
                self._pending_tracking_pose = None
                self._pending_tracking_source = None
                self._pending_tracking_model_source = None
        else:
            self.get_logger().error("Failed to save frozen map")
        self._save_future = None


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TransitionManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
