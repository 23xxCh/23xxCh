"""Particle filter integrator for gas tracking."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .types import Pose2D


@dataclass
class SourceEstimate:
    """Source estimate from particle filter."""
    position: tuple[float, float]
    confidence: float
    covariance: tuple[float, float, float, float]  # (var_x, var_y, cov_xy, cov_yx)


@dataclass
class ParticleFilterIntegratorConfig:
    """Configuration for particle filter integrator."""
    min_confidence: float = 0.3
    max_covariance: float = 10.0  # Max acceptable variance
    position_weight: float = 0.5  # How much to weight PF vs current tracking


class ParticleFilterIntegrator:
    """Integrates particle filter estimates into tracking decisions.

    The particle filter provides source location estimates that can
    guide the robot when local gradient information is insufficient.
    """

    def __init__(self, config: ParticleFilterIntegratorConfig | None = None) -> None:
        self.config = config or ParticleFilterIntegratorConfig()
        self._estimate: SourceEstimate | None = None
        self._confidence_history: list[float] = []

    def update(
        self,
        position: tuple[float, float],
        confidence: float,
        covariance: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Update with new particle filter estimate.

        Args:
            position: Estimated source position (x, y).
            confidence: Confidence of estimate [0, 1].
            covariance: Optional covariance matrix values.
        """
        self._estimate = SourceEstimate(
            position=position,
            confidence=confidence,
            covariance=covariance or (1.0, 1.0, 0.0, 0.0),
        )

        # Track confidence history
        self._confidence_history.append(confidence)
        if len(self._confidence_history) > 20:
            self._confidence_history = self._confidence_history[-20:]

    def get_navigational_hint(self, robot_pose: Pose2D) -> Pose2D | None:
        """Get navigation hint if estimate is reliable.

        Args:
            robot_pose: Current robot position.

        Returns:
            Target position to navigate to, or None if estimate unreliable.
        """
        if not self._is_reliable():
            return None

        return Pose2D(self._estimate.position[0], self._estimate.position[1])

    def get_weighted_target(
        self,
        robot_pose: Pose2D,
        current_target: Pose2D,
    ) -> Pose2D | None:
        """Get weighted target combining PF estimate and current target.

        Args:
            robot_pose: Current robot position.
            current_target: Current tracking target.

        Returns:
            Weighted target position, or None if PF unreliable.
        """
        if not self._is_reliable():
            return None

        pf_target = self.get_navigational_hint(robot_pose)
        if not pf_target:
            return None

        weight = self.config.position_weight * self._estimate.confidence

        # Weighted average of positions
        weighted_x = (1 - weight) * current_target.x + weight * pf_target.x
        weighted_y = (1 - weight) * current_target.y + weight * pf_target.y

        return Pose2D(weighted_x, weighted_y)

    def _is_reliable(self) -> bool:
        """Check if particle filter estimate is reliable."""
        if self._estimate is None:
            return False

        if self._estimate.confidence < self.config.min_confidence:
            return False

        # Check covariance (high variance = unreliable)
        var_x = self._estimate.covariance[0]
        var_y = self._estimate.covariance[1]
        if var_x > self.config.max_covariance or var_y > self.config.max_covariance:
            return False

        return True

    @property
    def confidence(self) -> float:
        """Current estimate confidence."""
        return self._estimate.confidence if self._estimate else 0.0

    @property
    def position(self) -> tuple[float, float] | None:
        """Current estimated position."""
        return self._estimate.position if self._estimate else None

    @property
    def average_confidence(self) -> float:
        """Average confidence over recent history."""
        if not self._confidence_history:
            return 0.0
        return sum(self._confidence_history) / len(self._confidence_history)

    def reset(self) -> None:
        """Reset integrator state."""
        self._estimate = None
        self._confidence_history.clear()
