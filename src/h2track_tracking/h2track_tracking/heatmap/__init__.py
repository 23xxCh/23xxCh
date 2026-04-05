"""Heatmap module for gas concentration visualization."""

from .grid import ConcentrationGrid, HeatmapConfig
from .history_store import Snapshot, TimeSeriesStore

__all__ = ["ConcentrationGrid", "HeatmapConfig", "Snapshot", "TimeSeriesStore"]
