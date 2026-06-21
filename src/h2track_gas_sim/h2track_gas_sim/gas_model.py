"""Pure gas field helpers used by the ROS node and tests."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .gas_types import GasType, get_gas_properties


@dataclass(frozen=True)
class Pose2D:
    """2D pose for gas simulation domain."""
    x: float = 0.0
    y: float = 0.0


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
    """Simple 2D plume model with downwind bias and bounded noise.

    Gas-type physics:
    - Diffusion coefficient scales lateral plume spread (wider for H2, narrower for C3H8)
    - Density ratio biases upwind/downwind asymmetry (light gases spread more upwind)
    """

    # Reference diffusion coefficient (H2) for scaling
    _REF_DIFFUSION = 0.61

    def __init__(self, params: GasFieldParams, rng: random.Random | None = None) -> None:
        self.params = params
        self.rng = rng or random.Random(0)

        # Look up gas properties for physics modifiers
        try:
            gas_enum = GasType(params.gas_type)
        except ValueError:
            gas_enum = GasType.HYDROGEN
        props = get_gas_properties(gas_enum)
        # Diffusion scale: wider plume for high-diffusion gases
        self._diffusion_scale = props.diffusion_coefficient / self._REF_DIFFUSION
        # Buoyancy factor: light gases (< 1.0) spread more upwind,
        # heavy gases (> 1.0) are more confined downwind
        self._buoyancy_factor = props.density_ratio

    def concentration_at(self, pose: Pose2D) -> float:
        dx = pose.x - self.params.source_x
        dy = pose.y - self.params.source_y
        distance = math.hypot(dx, dy)

        # Effective plume width scaled by gas diffusion coefficient
        effective_stddev = self.params.plume_stddev * self._diffusion_scale

        wind_norm = math.hypot(self.params.wind_x, self.params.wind_y)
        if wind_norm > 1e-6:
            wind_dir = (self.params.wind_x / wind_norm, self.params.wind_y / wind_norm)
            projection = dx * wind_dir[0] + dy * wind_dir[1]
            lateral_sq = max(0.0, distance * distance - projection * projection)
            lateral = math.sqrt(lateral_sq)
            plume_bias = math.exp(-(lateral * lateral) / (2.0 * effective_stddev**2))
            if projection < 0.0:
                # Upwind penalty modulated by buoyancy:
                # light gases (density < 1) → less penalty (spread more upwind)
                # heavy gases (density > 1) → more penalty (confined downwind)
                # Inverse: divide by density_ratio so light gases get higher factor
                upwind_factor = 0.35 / max(self._buoyancy_factor, 0.1)
                plume_bias *= min(upwind_factor, 0.8)
        else:
            plume_bias = 1.0

        baseline = self.params.source_strength * math.exp(-self.params.decay_rate * distance)
        noise = self.rng.gauss(0.0, self.params.noise_stddev) if self.params.noise_stddev > 0.0 else 0.0

        return max(self.params.min_concentration, baseline * plume_bias + noise)

    # next_search_target moved to navigation_executor._gradient_search_target
    # to keep gas_model.py a pure physics module.  Use select_tracking_target()
    # from navigation_executor instead.
