"""Plume detection for gas tracking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from .types import PlumeState, SurgeCastConfig


@dataclass
class PlumeDetectorConfig:
    """Configuration for plume detector."""

    history_size: int = 20
    min_samples: int = 3
    plume_threshold: float = 3.0
    trend_window: int = 5

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.history_size < 1:
            raise ValueError(f"history_size must be >= 1, got {self.history_size}")
        if self.min_samples < 1:
            raise ValueError(f"min_samples must be >= 1, got {self.min_samples}")
        if self.min_samples > self.history_size:
            raise ValueError(
                f"min_samples ({self.min_samples}) cannot exceed "
                f"history_size ({self.history_size})"
            )
        if self.plume_threshold < 0:
            raise ValueError(
                f"plume_threshold must be >= 0, got {self.plume_threshold}"
            )
        if self.trend_window < 2:
            raise ValueError(f"trend_window must be >= 2, got {self.trend_window}")


class PlumeDetector:
    """Detects whether the robot is within a gas plume."""

    def __init__(self, config: PlumeDetectorConfig | None = None) -> None:
        self.config = config or PlumeDetectorConfig()
        self._history: deque[float] = deque(maxlen=self.config.history_size)
        self._position_history: deque[tuple[float, float]] = deque(
            maxlen=self.config.history_size
        )
        self._state = PlumeState()

    def update(
        self,
        concentration: float,
        position: tuple[float, float] | None = None,
    ) -> PlumeState:
        """Update detector with new concentration reading.

        Args:
            concentration: Current gas concentration.
            position: Optional robot position for tracking.

        Returns:
            Updated plume state.
        """
        self._history.append(concentration)
        if position:
            self._position_history.append(position)

        self._update_state()
        return self._state

    def _update_state(self) -> None:
        """Update internal state based on history."""
        if len(self._history) < self.config.min_samples:
            self._state = PlumeState(
                in_plume=False,
                confidence=0.0,
                average_concentration=0.0,
                trend="stable",
            )
            return

        # Calculate average concentration
        avg_conc = sum(self._history) / len(self._history)

        # Determine if in plume
        recent = list(self._history)[-self.config.min_samples:]
        in_plume_count = sum(1 for c in recent if c >= self.config.plume_threshold)
        in_plume = in_plume_count >= self.config.min_samples // 2 + 1

        # Calculate confidence
        confidence = in_plume_count / len(recent)

        # Determine trend
        if len(self._history) >= self.config.trend_window:
            trend = self._calculate_trend()
        else:
            trend = "stable"

        self._state = PlumeState(
            in_plume=in_plume,
            confidence=confidence,
            average_concentration=avg_conc,
            trend=trend,
        )

    def _calculate_trend(self) -> str:
        """Calculate concentration trend from recent history."""
        recent = list(self._history)[-self.config.trend_window:]
        if len(recent) < 2:
            return "stable"

        # Simple linear regression for trend
        n = len(recent)
        x_mean = (n - 1) / 2.0
        y_mean = sum(recent) / n

        numerator = sum(
            (i - x_mean) * (y - y_mean)
            for i, y in enumerate(recent)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if abs(denominator) < 1e-6:
            return "stable"

        slope = numerator / denominator

        # Classify trend
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    @property
    def state(self) -> PlumeState:
        """Current plume state."""
        return self._state

    @property
    def in_plume(self) -> bool:
        """Whether currently in plume."""
        return self._state.in_plume

    @property
    def confidence(self) -> float:
        """Confidence of plume detection."""
        return self._state.confidence

    @property
    def current_concentration(self) -> float:
        """Most recent concentration reading."""
        return self._history[-1] if self._history else 0.0

    @property
    def average_concentration(self) -> float:
        """Average concentration in history."""
        return self._state.average_concentration

    def get_best_position(self) -> tuple[float, float] | None:
        """Get position with highest concentration in history."""
        if not self._position_history or not self._history:
            return None

        best_idx = max(range(len(self._history)), key=lambda i: self._history[i])
        if best_idx < len(self._position_history):
            return self._position_history[best_idx]
        return None

    def reset(self) -> None:
        """Reset detector state."""
        self._history.clear()
        self._position_history.clear()
        self._state = PlumeState()
