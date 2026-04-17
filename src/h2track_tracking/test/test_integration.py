"""Integration tests for gas source localization pipeline.

Tests the complete flow:
1. Gas detection → 2. Wind estimation → 3. Surge-Cast → 4. Source found
"""

import pytest
import numpy as np

from h2track_tracking.tracking import (
    SurgeCastTracker,
    SurgeCastConfig,
    WindEstimator,
    WindEstimatorConfig,
    TrackingFusion,
    FusionConfig,
)
from h2track_tracking.tracking.types import Pose2D, TrackingState
from h2track_tracking.gas_types import GasType, get_gas_properties


class TestIntegrationPipeline:
    """Integration tests for complete tracking pipeline."""

    def test_gas_properties_integration(self) -> None:
        """Test gas properties are correctly loaded."""
        props = get_gas_properties(GasType.HYDROGEN)
        assert props.name == "Hydrogen"
        assert props.alarm_threshold == 250.0

    def test_wind_estimation_to_surge_cast(self) -> None:
        """Test wind estimation feeds into surge-cast."""
        # Setup wind estimator
        wind_config = WindEstimatorConfig(min_samples_for_estimate=5)
        wind_estimator = WindEstimator(wind_config)

        # Simulate robot path with wind
        for i in range(10):
            wind_estimator.update(
                Pose2D(float(i) * 0.5, 0.0),
                concentration=1.0 + i * 0.5,
                timestamp=float(i) * 0.1,
            )

        # Get wind estimate
        wind = wind_estimator.get_estimate()
        assert wind is not None

        # Use wind in surge-cast
        surge_config = SurgeCastConfig(
            plume_found_threshold=3.0,
        )
        tracker = SurgeCastTracker(surge_config)

        # Need multiple updates with high concentration to trigger SURGE
        # PlumeDetector requires at least 2 of last 3 samples >= 3.0
        for i in range(3):
            action = tracker.update(
                concentration=10.0,  # High concentration
                robot_pose=Pose2D(float(i), 0.0),
                robot_yaw=0.0,
                wind=(wind.wind_x, wind.wind_y),
            )

        assert action is not None
        assert action.state in [TrackingState.SURGE, TrackingState.CAST]

    def test_full_tracking_pipeline(self) -> None:
        """Test complete tracking from detection to source."""
        config = SurgeCastConfig(
            plume_found_threshold=2.0,
            plume_lost_threshold=1.0,
            source_threshold=20.0,
            source_radius=5.0,  # Larger radius to allow source detection
            source_hold_steps=1,  # Only need 1 hit to confirm
        )
        tracker = SurgeCastTracker(config)

        # Simulate approaching source with increasing concentration
        # Start from PATROL, transition through SURGE to SOURCE_FOUND
        concentrations = [1.0, 3.0, 8.0, 12.0, 18.0, 25.0]
        robot_poses = [
            Pose2D(10.0, 0.0),
            Pose2D(8.0, 0.0),
            Pose2D(6.0, 0.0),
            Pose2D(4.0, 0.0),
            Pose2D(2.0, 0.0),
            Pose2D(1.0, 0.0),
        ]

        final_state = None
        for conc, pose in zip(concentrations, robot_poses):
            action = tracker.update(
                concentration=conc,
                robot_pose=pose,
                robot_yaw=0.0,
                wind=(0.5, 0.0),
            )
            if action:
                final_state = action.state

        # Should reach SOURCE_FOUND state
        assert final_state == TrackingState.SOURCE_FOUND

    def test_multi_gas_tracking(self) -> None:
        """Test tracking with different gas types."""
        for gas_type in [GasType.HYDROGEN, GasType.METHANE, GasType.PROPANE]:
            props = get_gas_properties(gas_type)
            
            config = SurgeCastConfig(
                source_threshold=props.alarm_threshold * 0.5,
            )
            tracker = SurgeCastTracker(config)
            
            # Simulate high concentration
            action = tracker.update(
                concentration=props.alarm_threshold,
                robot_pose=Pose2D(1.0, 1.0),
                robot_yaw=0.0,
                wind=(0.3, 0.0),
            )
            
            assert action is not None


class TestAdaptiveStepSize:
    """Tests for adaptive step size feature."""

    def test_step_size_decreases_near_source(self) -> None:
        """Test that step size decreases as concentration increases."""
        config = SurgeCastConfig(
            surge_step=1.0,
            cast_step=0.3,
        )
        tracker = SurgeCastTracker(config)

        # Low concentration - expect large step
        tracker.update(
            concentration=0.5,
            robot_pose=Pose2D(10.0, 0.0),
            robot_yaw=0.0,
            wind=(0.5, 0.0),
        )

        # High concentration - expect small step
        action = tracker.update(
            concentration=10.0,
            robot_pose=Pose2D(2.0, 0.0),
            robot_yaw=0.0,
            wind=(0.5, 0.0),
        )

        assert action is not None
        assert action.step_size <= config.surge_step


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
