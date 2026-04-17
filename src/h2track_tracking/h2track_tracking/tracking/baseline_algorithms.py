"""Baseline algorithms for gas source localization comparison.

Implements classic algorithms for benchmarking:
1. Gradient-based search (chemotaxis)
2. Random walk
3. Spiral search
"""

from dataclasses import dataclass
import math
import random
from typing import List, Tuple
from .types import Pose2D, TrackingAction, TrackingState


@dataclass
class GradientSearchConfig:
    """Configuration for gradient-based search."""
    step_size: float = 0.5
    gradient_threshold: float = 0.1
    history_size: int = 10


class GradientSearch:
    """Gradient-based chemotaxis algorithm.
    
    Moves in the direction of increasing concentration.
    Classic baseline for gas source localization.
    """
    
    def __init__(self, config: GradientSearchConfig | None = None) -> None:
        self.config = config or GradientSearchConfig()
        self._history: List[Tuple[Pose2D, float]] = []
        self._state = TrackingState.PATROL
    
    def update(
        self,
        concentration: float,
        robot_pose: Pose2D,
        robot_yaw: float,
    ) -> TrackingAction:
        """Update and get next action."""
        self._history.append((robot_pose, concentration))
        if len(self._history) > self.config.history_size:
            self._history.pop(0)
        
        # Compute gradient from history
        if len(self._history) >= 3:
            gradient = self._compute_gradient()
            if gradient is not None:
                heading = math.atan2(gradient[1], gradient[0])
            else:
                heading = robot_yaw + random.uniform(-0.5, 0.5)
        else:
            heading = robot_yaw + random.uniform(-0.5, 0.5)
        
        target = Pose2D(
            robot_pose.x + self.config.step_size * math.cos(heading),
            robot_pose.y + self.config.step_size * math.sin(heading),
        )
        
        return TrackingAction(
            target=target,
            state=self._state,
            heading=heading,
            step_size=self.config.step_size,
            use_particle_filter=False,
        )
    
    def _compute_gradient(self) -> Tuple[float, float] | None:
        """Compute concentration gradient from history."""
        if len(self._history) < 3:
            return None
        
        # Simple finite difference
        positions = [(p.x, p.y) for p, _ in self._history]
        concentrations = [c for _, c in self._history]
        
        # Weighted least squares gradient
        n = len(positions)
        sum_x = sum(p[0] for p in positions)
        sum_y = sum(p[1] for p in positions)
        sum_c = sum(concentrations)
        sum_xc = sum(p[0] * c for p, c in zip(positions, concentrations))
        sum_yc = sum(p[1] * c for p, c in zip(positions, concentrations))
        
        denom = n * sum(x*x for x, _ in positions) - sum_x**2
        if abs(denom) < 1e-6:
            return None
        
        grad_x = (n * sum_xc - sum_x * sum_c) / denom
        grad_y = (n * sum_yc - sum_y * sum_c) / denom
        
        mag = math.hypot(grad_x, grad_y)
        if mag < self.config.gradient_threshold:
            return None
        
        return (grad_x, grad_y)
    
    def reset(self) -> None:
        """Reset algorithm state."""
        self._history.clear()


@dataclass
class RandomWalkConfig:
    """Configuration for random walk."""
    step_size: float = 0.5
    turn_range: float = math.pi  # Max turn angle


class RandomWalk:
    """Random walk baseline algorithm.
    
    Randomly explores the environment.
    Used as lower bound for comparison.
    """
    
    def __init__(self, config: RandomWalkConfig | None = None) -> None:
        self.config = config or RandomWalkConfig()
        self._state = TrackingState.PATROL
    
    def update(
        self,
        concentration: float,
        robot_pose: Pose2D,
        robot_yaw: float,
    ) -> TrackingAction:
        """Update and get next action."""
        # Random turn
        turn = random.uniform(-self.config.turn_range, self.config.turn_range)
        heading = robot_yaw + turn
        
        target = Pose2D(
            robot_pose.x + self.config.step_size * math.cos(heading),
            robot_pose.y + self.config.step_size * math.sin(heading),
        )
        
        return TrackingAction(
            target=target,
            state=self._state,
            heading=heading,
            step_size=self.config.step_size,
            use_particle_filter=False,
        )
    
    def reset(self) -> None:
        """Reset algorithm state."""
        pass


@dataclass
class SpiralSearchConfig:
    """Configuration for spiral search."""
    initial_radius: float = 0.5
    radius_increment: float = 0.3
    angle_increment: float = math.pi / 4


class SpiralSearch:
    """Spiral search algorithm.
    
    Explores in an expanding spiral pattern.
    Systematic coverage baseline.
    """
    
    def __init__(self, config: SpiralSearchConfig | None = None) -> None:
        self.config = config or SpiralSearchConfig()
        self._current_radius = self.config.initial_radius
        self._current_angle = 0.0
        self._center = Pose2D(0.0, 0.0)
        self._state = TrackingState.PATROL
    
    def update(
        self,
        concentration: float,
        robot_pose: Pose2D,
        robot_yaw: float,
    ) -> TrackingAction:
        """Update and get next action."""
        # Compute next position on spiral
        self._current_angle += self.config.angle_increment
        if self._current_angle >= 2 * math.pi:
            self._current_angle = 0.0
            self._current_radius += self.config.radius_increment
        
        target = Pose2D(
            self._center.x + self._current_radius * math.cos(self._current_angle),
            self._center.y + self._current_radius * math.sin(self._current_angle),
        )
        
        heading = math.atan2(
            target.y - robot_pose.y,
            target.x - robot_pose.x,
        )
        
        return TrackingAction(
            target=target,
            state=self._state,
            heading=heading,
            step_size=self.config.initial_radius,
            use_particle_filter=False,
        )
    
    def reset(self) -> None:
        """Reset algorithm state."""
        self._current_radius = self.config.initial_radius
        self._current_angle = 0.0
