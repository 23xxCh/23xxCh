"""ROS adapter that republishes GADEN gas sensor readings as /gas_concentration."""

from __future__ import annotations

import time

from olfaction_msgs.msg import GasSensor
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

from .gaden_adapter import (
    GasSensorAdapterConfig,
    GasSensorSample,
    GasSensorUnits,
    HydrogenSensorModel,
    convert_gas_sensor_sample,
)


def should_emit_periodic_log(
    *,
    last_emit_sec: float | None,
    now_sec: float,
    interval_sec: float,
) -> bool:
    if interval_sec <= 0.0:
        return True
    if last_emit_sec is None:
        return True
    return (now_sec - last_emit_sec) >= interval_sec


class GadenAdapterNode(Node):
    def __init__(self) -> None:
        super().__init__("gaden_adapter_node")
        self.declare_parameter("gas_sensor_topic", "/gaden/sensor_reading")
        self.declare_parameter("gas_concentration_topic", "/gas_concentration")
        self.declare_parameter("sensor_model", -1)
        self.declare_parameter("fallback_ohm_scale", 0.0)
        self.declare_parameter("voltage_scale", 1.0)
        self.declare_parameter("minimum_concentration_ppm", 0.0)
        self.declare_parameter("maximum_concentration_ppm", 0.0)
        self.declare_parameter("log_interval_sec", 1.0)

        self._config = GasSensorAdapterConfig(
            sensor_model=self._resolve_default_sensor_model(),
            fallback_ohm_scale=float(self.get_parameter("fallback_ohm_scale").value),
            voltage_scale=float(self.get_parameter("voltage_scale").value),
            minimum_concentration_ppm=float(self.get_parameter("minimum_concentration_ppm").value),
            maximum_concentration_ppm=self._resolve_maximum_concentration(),
        )
        sensor_topic = str(self.get_parameter("gas_sensor_topic").value)
        concentration_topic = str(self.get_parameter("gas_concentration_topic").value)
        self._log_interval_sec = max(0.0, float(self.get_parameter("log_interval_sec").value))
        self._last_log_emit_sec: float | None = None
        self._publisher = self.create_publisher(Float32, concentration_topic, 10)
        self.create_subscription(GasSensor, sensor_topic, self._sensor_callback, 10)

        self.get_logger().info(
            f"gaden_adapter listening on {sensor_topic} and republishing {concentration_topic}"
        )

    def _resolve_default_sensor_model(self) -> HydrogenSensorModel:
        sensor_model_value = int(self.get_parameter("sensor_model").value)
        if sensor_model_value >= 0:
            try:
                return HydrogenSensorModel(sensor_model_value)
            except ValueError as e:
                self.get_logger().warning(f"Invalid sensor value: {e}")
                pass
        return HydrogenSensorModel.TGS2600

    def _resolve_maximum_concentration(self) -> float | None:
        value = float(self.get_parameter("maximum_concentration_ppm").value)
        return None if value <= 0.0 else value

    def _sensor_callback(self, msg: GasSensor) -> None:
        sample = GasSensorSample(
            raw=float(msg.raw),
            raw_units=self._coerce_units(int(msg.raw_units)),
            raw_air=float(msg.raw_air),
            calib_a=float(msg.calib_a),
            calib_b=float(msg.calib_b),
            technology=int(msg.technology),
            manufacturer=int(msg.manufacturer),
            mpn=int(msg.mpn),
        )
        if self.get_parameter("sensor_model").value < 0:
            inferred = HydrogenSensorModel.from_mpn(sample.mpn)
            if inferred is not None:
                self._config = GasSensorAdapterConfig(
                    sensor_model=inferred,
                    fallback_ohm_scale=self._config.fallback_ohm_scale,
                    voltage_scale=self._config.voltage_scale,
                    minimum_concentration_ppm=self._config.minimum_concentration_ppm,
                    maximum_concentration_ppm=self._config.maximum_concentration_ppm,
                )

        concentration = convert_gas_sensor_sample(sample, self._config)
        self._publisher.publish(Float32(data=float(concentration)))
        now_sec = time.monotonic()
        if should_emit_periodic_log(
            last_emit_sec=self._last_log_emit_sec,
            now_sec=now_sec,
            interval_sec=self._log_interval_sec,
        ):
            self._last_log_emit_sec = now_sec
            self.get_logger().info(f"concentration={float(concentration):.3f}")

    def _coerce_units(self, value: int) -> GasSensorUnits:
        try:
            return GasSensorUnits(value)
        except ValueError:
            return GasSensorUnits.NOT_VALID


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GadenAdapterNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
