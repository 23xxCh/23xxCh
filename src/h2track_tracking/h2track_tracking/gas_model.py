"""Pure gas field helpers used by the ROS node and tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .tracking.types import Pose2D  # canonical Pose2D


@dataclass(frozen=True)
class GasFieldParams:
    source_x: float
    source_y: float
    source_strength: float
    decay_rate: float
    plume_stddev: float
    wind_x: float
    wind_y: float
    noise_stddev: float
    min_concentration: float
    gas_type: str = "H2"  # 气体类型


class GasFieldModel:
    """Simple 2D plume model with downwind bias and bounded noise."""

    def __init__(self, params: GasFieldParams, rng: random.Random | None = None) -> None:
        self.params = params
        self.rng = rng or random.Random(0)

    def concentration_at(self, pose: Pose2D) -> float:
        dx = pose.x - self.params.source_x
        dy = pose.y - self.params.source_y
        distance = math.hypot(dx, dy)

        wind_norm = math.hypot(self.params.wind_x, self.params.wind_y)
        if wind_norm > 1e-6:
            wind_dir = (self.params.wind_x / wind_norm, self.params.wind_y / wind_norm)
            projection = dx * wind_dir[0] + dy * wind_dir[1]
            lateral_sq = max(0.0, distance * distance - projection * projection)
            lateral = math.sqrt(lateral_sq)
            plume_bias = math.exp(-(lateral * lateral) / (2.0 * self.params.plume_stddev**2))
            if projection < 0.0:
                plume_bias *= 0.35
        else:
            plume_bias = 1.0

        baseline = self.params.source_strength * math.exp(-self.params.decay_rate * distance)
        noise = self.rng.gauss(0.0, self.params.noise_stddev) if self.params.noise_stddev > 0.0 else 0.0

        return max(self.params.min_concentration, baseline * plume_bias + noise)

    # next_search_target moved to navigation_executor._gradient_search_target
    # to keep gas_model.py a pure physics module.  Use select_tracking_target()
    # from navigation_executor instead.
