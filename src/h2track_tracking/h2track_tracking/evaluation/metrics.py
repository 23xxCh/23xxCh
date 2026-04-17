"""Evaluation metrics for gas source localization."""

from dataclasses import dataclass, field
from typing import List, Tuple
import math
import time


@dataclass
class TrackingMetrics:
    """Metrics for a single tracking run.
    
    Attributes:
        source_position: Ground truth source position (x, y)
        estimated_position: Final estimated source position (x, y)
        distance_error: Distance between estimated and true source (meters)
        time_to_source: Time from start to source found (seconds)
        path_length: Total distance traveled (meters)
        num_detections: Number of times gas was detected
        avg_concentration: Average gas concentration during tracking
        success: Whether source was found
    """
    source_position: Tuple[float, float]
    estimated_position: Tuple[float, float] | None = None
    distance_error: float = float('inf')
    time_to_source: float = float('inf')
    path_length: float = 0.0
    num_detections: int = 0
    avg_concentration: float = 0.0
    success: bool = False
    timestamp: float = field(default_factory=time.time)
    
    def compute_error(self) -> float:
        """Compute distance error between estimated and true source."""
        if self.estimated_position is None:
            return float('inf')
        dx = self.estimated_position[0] - self.source_position[0]
        dy = self.estimated_position[1] - self.source_position[1]
        self.distance_error = math.hypot(dx, dy)
        return self.distance_error


@dataclass
class BenchmarkResult:
    """Results from multiple tracking runs.
    
    Attributes:
        algorithm_name: Name of the algorithm being evaluated
        metrics_list: List of individual run metrics
        success_rate: Percentage of successful runs
        avg_distance_error: Mean distance error across runs
        avg_time_to_source: Mean time to find source
        avg_path_length: Mean path length
        std_distance_error: Standard deviation of distance error
    """
    algorithm_name: str
    metrics_list: List[TrackingMetrics] = field(default_factory=list)
    
    def compute_statistics(self) -> None:
        """Compute summary statistics from all runs."""
        if not self.metrics_list:
            return
        
        successful = [m for m in self.metrics_list if m.success]
        self.success_rate = len(successful) / len(self.metrics_list) * 100
        
        if successful:
            self.avg_distance_error = sum(m.distance_error for m in successful) / len(successful)
            self.avg_time_to_source = sum(m.time_to_source for m in successful) / len(successful)
            self.avg_path_length = sum(m.path_length for m in successful) / len(successful)
            
            # Compute standard deviation
            if len(successful) > 1:
                variance = sum((m.distance_error - self.avg_distance_error) ** 2 for m in successful) / len(successful)
                self.std_distance_error = math.sqrt(variance)
            else:
                self.std_distance_error = 0.0
        else:
            self.avg_distance_error = float('inf')
            self.avg_time_to_source = float('inf')
            self.avg_path_length = float('inf')
            self.std_distance_error = float('inf')
    
    def to_markdown_table(self) -> str:
        """Generate markdown table for results."""
        self.compute_statistics()
        return f"""
| Metric | Value |
|--------|-------|
| Algorithm | {self.algorithm_name} |
| Success Rate | {self.success_rate:.1f}% |
| Avg Distance Error | {self.avg_distance_error:.3f} m |
| Std Distance Error | {self.std_distance_error:.3f} m |
| Avg Time to Source | {self.avg_time_to_source:.1f} s |
| Avg Path Length | {self.avg_path_length:.1f} m |
| Total Runs | {len(self.metrics_list)} |
"""
