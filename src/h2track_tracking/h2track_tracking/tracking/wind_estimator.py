"""Wind estimation from gas concentration gradients.

Estimates wind direction and speed from spatial concentration patterns.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import time

import numpy as np

from .types import Pose2D


@dataclass(frozen=True)
class WindEstimatorConfig:
    """Configuration for wind estimation.

    Attributes:
        history_size: Number of observations to keep for gradient analysis
        min_samples_for_estimate: Minimum samples needed before estimating
        gradient_threshold: Minimum gradient magnitude to consider significant
        smoothing_factor: Exponential smoothing factor (0-1)
        max_wind_speed: Maximum expected wind speed (m/s)
    """
    history_size: int = 100
    min_samples_for_estimate: int = 10
    gradient_threshold: float = 0.1
    smoothing_factor: float = 0.3
    max_wind_speed: float = 2.0


@dataclass
class WindEstimate:
    """Estimated wind vector with confidence.

    Attributes:
        wind_x: Wind X component (m/s), positive = blowing in +X direction
        wind_y: Wind Y component (m/s)
        confidence: Estimation confidence (0.0 to 1.0)
        timestamp: Time of estimation
    """
    wind_x: float
    wind_y: float
    confidence: float
    timestamp: float

    @property
    def speed(self) -> float:
        """Wind speed magnitude (m/s)."""
        return math.hypot(self.wind_x, self.wind_y)

    @property
    def direction(self) -> float:
        """Wind direction in radians (where wind is blowing TO)."""
        return math.atan2(self.wind_y, self.wind_x)

    @property
    def upwind_direction(self) -> float:
        """Direction to move upwind (opposite to wind)."""
        return math.atan2(-self.wind_y, -self.wind_x)


class WindEstimator:
    """Estimate wind from gas concentration gradients.

    Uses spatial concentration patterns to infer wind direction:
    - Higher concentrations are typically found downwind of the source
    - Plume elongation indicates wind direction
    - Concentration gradients point toward source, opposite to wind

    Example:
        >>> estimator = WindEstimator(WindEstimatorConfig())
        >>> estimator.update(pose, concentration, timestamp)
        >>> estimate = estimator.get_estimate()
        >>> if estimate and estimate.confidence > 0.5:
        ...     print(f"Wind: {estimate.speed:.2f} m/s at {estimate.direction:.1f} rad")
    """

    def __init__(self, config: WindEstimatorConfig | None = None) -> None:
        """Initialize the wind estimator.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or WindEstimatorConfig()
        # History: (pose, concentration, timestamp)
        self._history: deque[tuple[Pose2D, float, float]] = deque(
            maxlen=self.config.history_size
        )
        self._current_estimate: WindEstimate | None = None

    def update(
        self,
        pose: Pose2D,
        concentration: float,
        timestamp: float | None = None,
    ) -> WindEstimate | None:
        """Update estimate with new observation.

        Args:
            pose: Current robot position
            concentration: Observed gas concentration
            timestamp: Observation time (defaults to current time)

        Returns:
            Current wind estimate if available, None otherwise.
        """
        if timestamp is None:
            timestamp = time.time()

        self._history.append((pose, concentration, timestamp))

        # Update estimate if we have enough samples
        if len(self._history) >= self.config.min_samples_for_estimate:
            self._update_estimate()

        return self._current_estimate

    def _update_estimate(self) -> None:
        """Recalculate wind estimate from history."""
        if len(self._history) < self.config.min_samples_for_estimate:
            return

        # Method 1: Gradient-based estimation
        gradient_estimate = self._estimate_from_gradient()

        # Method 2: Plume shape analysis
        plume_estimate = self._estimate_from_plume_shape()

        # Combine estimates if both available
        if gradient_estimate is not None and plume_estimate is not None:
            # Weight based on confidence
            g_conf = gradient_estimate[2]
            p_conf = plume_estimate[2]
            total_conf = g_conf + p_conf

            if total_conf > 0:
                wind_x = (gradient_estimate[0] * g_conf + plume_estimate[0] * p_conf) / total_conf
                wind_y = (gradient_estimate[1] * g_conf + plume_estimate[1] * p_conf) / total_conf
                confidence = min(1.0, total_conf / 2)
            else:
                wind_x, wind_y = gradient_estimate[0], gradient_estimate[1]
                confidence = 0.0

        elif gradient_estimate is not None:
            wind_x, wind_y, confidence = gradient_estimate
        elif plume_estimate is not None:
            wind_x, wind_y, confidence = plume_estimate
        else:
            return

        # Clamp wind speed
        speed = math.hypot(wind_x, wind_y)
        if speed > self.config.max_wind_speed:
            scale = self.config.max_wind_speed / speed
            wind_x *= scale
            wind_y *= scale

        # Apply smoothing with previous estimate
        if self._current_estimate is not None:
            alpha = self.config.smoothing_factor
            wind_x = alpha * wind_x + (1 - alpha) * self._current_estimate.wind_x
            wind_y = alpha * wind_y + (1 - alpha) * self._current_estimate.wind_y
            confidence = alpha * confidence + (1 - alpha) * self._current_estimate.confidence

        self._current_estimate = WindEstimate(
            wind_x=wind_x,
            wind_y=wind_y,
            confidence=confidence,
            timestamp=time.time(),
        )

    def _estimate_from_gradient(self) -> tuple[float, float, float] | None:
        """Estimate wind from concentration gradients.

        The gradient points toward higher concentration (toward source).
        Wind typically blows FROM the source, so wind is opposite to gradient.

        Returns:
            (wind_x, wind_y, confidence) or None if estimation fails.
        """
        if len(self._history) < self.config.min_samples_for_estimate:
            return None

        # Convert history to arrays
        positions = np.array([(p.x, p.y) for p, _, _ in self._history])
        concentrations = np.array([c for _, c, _ in self._history])

        # Compute gradients using finite differences
        # We need at least 3 points to compute a meaningful gradient
        if len(positions) < 3:
            return None

        # Fit a linear regression: concentration = a*x + b*y + c
        # Gradient = (a, b)
        try:
            # Add bias term
            X = np.column_stack([positions, np.ones(len(positions))])
            # Weighted by concentration (higher concentration = more reliable)
            weights = concentrations / (concentrations.max() + 1e-6)

            # Simple least squares with weights
            W = np.diag(weights)
            XtWX = X.T @ W @ X
            XtWy = X.T @ W @ concentrations

            coeffs = np.linalg.solve(XtWX, XtWy)
            grad_x, grad_y = coeffs[0], coeffs[1]

            grad_mag = math.hypot(grad_x, grad_y)

            if grad_mag < self.config.gradient_threshold:
                return None

            # Wind direction is opposite to gradient (blowing from source)
            # Scale by gradient magnitude (stronger gradient = stronger wind signal)
            wind_x = -grad_x
            wind_y = -grad_y

            # Confidence based on gradient strength and sample count
            confidence = min(1.0, grad_mag / self.config.gradient_threshold * 0.5)
            confidence *= min(1.0, len(self._history) / self.config.history_size)

            return (wind_x, wind_y, confidence)

        except np.linalg.LinAlgError:
            return None

    def _estimate_from_plume_shape(self) -> tuple[float, float, float] | None:
        """Estimate wind from plume elongation direction.

        Plumes are elongated in the wind direction.
        We fit an ellipse to high-concentration observations.

        Returns:
            (wind_x, wind_y, confidence) or None if estimation fails.
        """
        if len(self._history) < self.config.min_samples_for_estimate:
            return None

        # Filter for significant concentrations
        concentrations = np.array([c for _, c, _ in self._history])
        threshold = np.percentile(concentrations, 50)  # Top 50%

        high_conc_mask = concentrations > threshold
        if high_conc_mask.sum() < 5:
            return None

        positions = np.array([(p.x, p.y) for p, _, _ in self._history])
        high_conc_positions = positions[high_conc_mask]

        # Compute covariance of high-concentration positions
        if len(high_conc_positions) < 3:
            return None

        try:
            cov = np.cov(high_conc_positions.T)
            eigenvalues, eigenvectors = np.linalg.eigh(cov)

            # Eigenvector with largest eigenvalue is the major axis
            major_idx = np.argmax(eigenvalues)
            major_axis = eigenvectors[:, major_idx]

            # Plume elongation indicates wind direction
            wind_x = major_axis[0]
            wind_y = major_axis[1]

            # Confidence based on elongation ratio
            elongation = eigenvalues.max() / (eigenvalues.min() + 1e-6)
            confidence = min(1.0, elongation / 3.0)  # Elongation > 3 = high confidence

            return (wind_x, wind_y, confidence)

        except (np.linalg.LinAlgError, ValueError):
            return None

    def get_estimate(self) -> WindEstimate | None:
        """Get current wind estimate.

        Returns:
            WindEstimate if available, None otherwise.
        """
        return self._current_estimate

    def reset(self) -> None:
        """Clear history and reset estimate."""
        self._history.clear()
        self._current_estimate = None

    @property
    def sample_count(self) -> int:
        """Number of samples in history."""
        return len(self._history)

    @property
    def has_estimate(self) -> bool:
        """Whether a wind estimate is available."""
        return self._current_estimate is not None
