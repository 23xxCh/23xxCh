"""Algorithm fusion for gas source localization.

Fuses Surge-Cast and Particle Filter estimates for improved tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
import math

if TYPE_CHECKING:
    from .surge_cast import SurgeCastTracker
    from .types import Pose2D, TrackingAction
    from ..particle_filter.filter import ParticleFilter

from .types import Pose2D as Pose, TrackingAction, TrackingState


@dataclass(frozen=True)
class FusionConfig:
    """Configuration for algorithm fusion.

    Attributes:
        pf_weight_base: Base weight for particle filter estimate (0-1)
        pf_confidence_threshold: Minimum PF confidence to use estimate
        surge_weight: Base weight for surge-cast (0-1)
        blending_mode: How to combine estimates
            - "weighted": Weighted average based on confidence
            - "switching": Use one algorithm at a time based on conditions
            - "cascade": PF provides region, Surge-Cast navigates
        min_plume_strength: Minimum concentration for surge-cast dominance
    """
    pf_weight_base: float = 0.3
    pf_confidence_threshold: float = 0.5
    surge_weight: float = 0.7
    blending_mode: Literal["weighted", "switching", "cascade"] = "weighted"
    min_plume_strength: float = 2.0


@dataclass
class FusionState:
    """Current state of the fusion algorithm.

    Attributes:
        current_mode: Which algorithm is dominant
        pf_contribution: How much PF contributed to last decision (0-1)
        surge_contribution: How much Surge-Cast contributed (0-1)
        last_fused_target: Last computed fused target
    """
    current_mode: str = "surge_cast"
    pf_contribution: float = 0.0
    surge_contribution: float = 1.0
    last_fused_target: Pose | None = None


class TrackingFusion:
    """Fuses Surge-Cast and Particle Filter estimates.

    Provides three fusion modes:

    1. **Weighted**: Combines targets based on confidence
       - PF weight scales with its confidence
       - Surge-Cast weight scales with plume strength

    2. **Switching**: Selects one algorithm based on conditions
       - Use Surge-Cast when in plume (high concentration)
       - Use PF when plume lost (low concentration)

    3. **Cascade**: Hierarchical approach
       - PF provides coarse target region
       - Surge-Cast navigates within that region

    Example:
        >>> fusion = TrackingFusion(config, surge_tracker, particle_filter)
        >>> action = fusion.compute_fused_action(
        ...     surge_action, pf_estimate, concentration
        ... )
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        """Initialize the fusion algorithm.

        Args:
            config: Optional fusion configuration.
        """
        self.config = config or FusionConfig()
        self._state = FusionState()

    def compute_fused_action(
        self,
        surge_action: TrackingAction,
        pf_position: Pose | None,
        pf_confidence: float,
        concentration: float,
        robot_pose: Pose,
    ) -> TrackingAction:
        """Compute a fused tracking action.

        Args:
            surge_action: Action from Surge-Cast tracker
            pf_position: Estimated source position from Particle Filter
            pf_confidence: Confidence of PF estimate (0-1)
            concentration: Current gas concentration
            robot_pose: Current robot position

        Returns:
            Fused TrackingAction with combined target.
        """
        if self.config.blending_mode == "weighted":
            return self._weighted_fusion(
                surge_action, pf_position, pf_confidence, robot_pose
            )
        elif self.config.blending_mode == "switching":
            return self._switching_fusion(
                surge_action, pf_position, pf_confidence, concentration, robot_pose
            )
        else:  # cascade
            return self._cascade_fusion(
                surge_action, pf_position, pf_confidence, robot_pose
            )

    def _weighted_fusion(
        self,
        surge_action: TrackingAction,
        pf_position: Pose | None,
        pf_confidence: float,
        robot_pose: Pose,
    ) -> TrackingAction:
        """Weighted average fusion of targets.

        PF contribution increases with confidence.
        Surge-Cast contribution is fixed or varies with plume strength.
        """
        # If no PF estimate, use surge action directly
        if pf_position is None or pf_confidence < self.config.pf_confidence_threshold:
            self._state.pf_contribution = 0.0
            self._state.surge_contribution = 1.0
            self._state.current_mode = "surge_cast"
            return surge_action

        # Compute weights
        pf_weight = self.config.pf_weight_base * pf_confidence
        surge_weight = self.config.surge_weight

        # Normalize weights
        total = pf_weight + surge_weight
        pf_weight /= total
        surge_weight /= total

        # Weighted average of positions
        surge_target = surge_action.target
        fused_x = pf_weight * pf_position.x + surge_weight * surge_target.x
        fused_y = pf_weight * pf_position.y + surge_weight * surge_target.y
        fused_target = Pose(fused_x, fused_y)

        # Update state
        self._state.pf_contribution = pf_weight
        self._state.surge_contribution = surge_weight
        self._state.current_mode = "weighted"
        self._state.last_fused_target = fused_target

        return TrackingAction(
            target=fused_target,
            state=surge_action.state,
            heading=self._compute_heading(robot_pose, fused_target),
            step_size=surge_action.step_size,
            use_particle_filter=True,
        )

    def _switching_fusion(
        self,
        surge_action: TrackingAction,
        pf_position: Pose | None,
        pf_confidence: float,
        concentration: float,
        robot_pose: Pose,
    ) -> TrackingAction:
        """Switch between algorithms based on conditions.

        Use Surge-Cast when concentration is high (in plume).
        Use PF when concentration is low (lost plume).
        """
        # In plume: use surge-cast
        if concentration >= self.config.min_plume_strength:
            self._state.pf_contribution = 0.0
            self._state.surge_contribution = 1.0
            self._state.current_mode = "surge_cast"
            return surge_action

        # Lost plume and have PF estimate: use PF
        if pf_position is not None and pf_confidence >= self.config.pf_confidence_threshold:
            self._state.pf_contribution = 1.0
            self._state.surge_contribution = 0.0
            self._state.current_mode = "particle_filter"
            self._state.last_fused_target = pf_position

            # Compute heading from robot to PF target
            dx = pf_position.x - robot_pose.x
            dy = pf_position.y - robot_pose.y
            pf_heading = math.atan2(dy, dx) if (dx or dy) else 0.0

            return TrackingAction(
                target=pf_position,
                state=surge_action.state,  # Keep state from surge
                heading=pf_heading,
                step_size=surge_action.step_size,
                use_particle_filter=True,
            )

        # Default to surge-cast
        self._state.pf_contribution = 0.0
        self._state.surge_contribution = 1.0
        self._state.current_mode = "surge_cast"
        return surge_action

    def _cascade_fusion(
        self,
        surge_action: TrackingAction,
        pf_position: Pose | None,
        pf_confidence: float,
        robot_pose: Pose,
    ) -> TrackingAction:
        """Cascade: PF provides region, Surge-Cast navigates.

        If PF has high confidence, bias surge-cast target toward PF estimate.
        """
        # No PF estimate: use surge action
        if pf_position is None or pf_confidence < self.config.pf_confidence_threshold:
            self._state.pf_contribution = 0.0
            self._state.surge_contribution = 1.0
            self._state.current_mode = "surge_cast"
            return surge_action

        # Bias surge-cast target toward PF region
        surge_target = surge_action.target

        # Compute direction to PF estimate
        dx = pf_position.x - surge_target.x
        dy = pf_position.y - surge_target.y
        dist = math.hypot(dx, dy)

        # If surge target is far from PF region, blend toward PF
        if dist > 1.0:  # More than 1 meter away
            blend_factor = min(0.5, pf_confidence * 0.5)
            fused_x = surge_target.x + blend_factor * dx
            fused_y = surge_target.y + blend_factor * dy
            fused_target = Pose(fused_x, fused_y)
        else:
            fused_target = surge_target

        # Update state
        self._state.pf_contribution = pf_confidence * 0.3  # PF guides but doesn't dominate
        self._state.surge_contribution = 1.0 - self._state.pf_contribution
        self._state.current_mode = "cascade"
        self._state.last_fused_target = fused_target

        return TrackingAction(
            target=fused_target,
            state=surge_action.state,
            heading=self._compute_heading(robot_pose, fused_target),
            step_size=surge_action.step_size,
            use_particle_filter=True,
        )

    def _compute_heading(self, robot_pose: Pose, target: Pose) -> float:
        """Compute heading from robot to target."""
        dx = target.x - robot_pose.x
        dy = target.y - robot_pose.y
        return math.atan2(dy, dx)

    @property
    def state(self) -> FusionState:
        """Get current fusion state."""
        return self._state

    def reset(self) -> None:
        """Reset fusion state."""
        self._state = FusionState()
