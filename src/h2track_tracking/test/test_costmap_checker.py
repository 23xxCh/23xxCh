"""Tests for CostmapChecker."""

from __future__ import annotations

import pytest
import numpy as np

from h2track_tracking.tracking.costmap_checker import CostmapChecker, CostmapConfig
from h2track_tracking.tracking.types import Pose2D, TrackingAction, TrackingState


class TestCostmapConfig:
    """Tests for CostmapConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CostmapConfig()
        assert config.lethal_cost_threshold == 254
        assert config.free_threshold == 1
        assert config.unknown_cost_value == -1

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = CostmapConfig(
            lethal_cost_threshold=200,
            free_threshold=10,
        )
        assert config.lethal_cost_threshold == 200
        assert config.lethal_cost_threshold == 200
        assert config.free_threshold == 10

    def test_frozen(self) -> None:
        """Test that config is immutable."""
        config = CostmapConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.lethal_cost_threshold = 200


class TestCostmapChecker:
    """Tests for CostmapChecker."""

    @pytest.fixture
    def checker(self) -> CostmapChecker:
        """Create a CostmapChecker with default config."""
        return CostmapChecker(CostmapConfig())

    @pytest.fixture
    def checker_no_costmap(self) -> CostmapChecker:
        """Create a CostmapChecker without costmap data."""
        return CostmapChecker()

    @pytest.fixture
    def mock_costmap(self) -> "Costmap":
        """Create a mock nav2_msgs/Costmap with a simple obstacle.

        Layout:
        - Origin at (-5.0, -5.0)
        - 100x100 cells at 0.1m resolution = 10m x 10m area
        - Obstacle in center (rows 40-60, cols 40-60) = 2m x 2m obstacle at origin
        """
        from nav2_msgs.msg import Costmap, CostmapMetaData
        from geometry_msgs.msg import Pose
        from std_msgs.msg import Header

        msg = Costmap()
        msg.header = Header()
        msg.header.frame_id = "map"

        msg.metadata = CostmapMetaData()
        msg.metadata.resolution = 0.1
        msg.metadata.size_x = 100
        msg.metadata.size_y = 100
        msg.metadata.origin = Pose()
        msg.metadata.origin.position.x = -5.0
        msg.metadata.origin.position.y = -5.0

        # Create costmap with free space (0) and obstacle (254)
        data = np.zeros((100, 100), dtype=np.uint8)
        # Add obstacle in center (rows 40-60, cols 40-60)
        # This corresponds to world coords: x in [-1, 1], y in [-1, 1]
        data[40:60, 40:60] = 254
        msg.data = data.flatten().tolist()
        return msg

    def test_init_default_config(self, checker_no_costmap: CostmapChecker) -> None:
        """Test initialization with default config."""
        assert checker_no_costmap.config.lethal_cost_threshold == 254
        assert checker_no_costmap.has_costmap is False

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = CostmapConfig(lethal_cost_threshold=200)
        checker = CostmapChecker(config)
        assert checker.config.lethal_cost_threshold == 200

    def test_update_costmap(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test costmap update from ROS message."""
        checker.update_costmap(mock_costmap)
        assert checker.has_costmap is True
        assert checker._resolution == 0.1
        assert checker._width == 100
        assert checker._height == 100
        assert checker.frame_id == "map"

    def test_is_valid_target_no_costmap(self, checker_no_costmap: CostmapChecker) -> None:
        """Test validation without costmap data (should allow by default)."""
        target = Pose2D(0.0, 0.0)
        assert checker_no_costmap.is_valid_target(target) is True

    def test_is_valid_target_free_space(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test validation of target in free space."""
        checker.update_costmap(mock_costmap)
        # Position at (3.0, 3.0) should be free (outside obstacle)
        target = Pose2D(3.0, 3.0)
        assert checker.is_valid_target(target) is True

    def test_is_valid_target_obstacle(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test validation of target in obstacle."""
        checker.update_costmap(mock_costmap)
        # Position at (0.0, 0.0) is inside the obstacle
        target = Pose2D(0.0, 0.0)
        assert checker.is_valid_target(target) is False

    def test_is_valid_target_outside_bounds(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test validation of target outside costmap bounds."""
        checker.update_costmap(mock_costmap)
        # Position at (100.0, 100.0) is outside the 10m x 10m costmap
        target = Pose2D(100.0, 100.0)
        assert checker.is_valid_target(target) is False

    def test_get_cost_at_free(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test getting cost at free space position."""
        checker.update_costmap(mock_costmap)
        target = Pose2D(3.0, 3.0)
        assert checker.get_cost_at(target) == 0

    def test_get_cost_at_obstacle(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test getting cost at obstacle position."""
        checker.update_costmap(mock_costmap)
        target = Pose2D(0.0, 0.0)
        assert checker.get_cost_at(target) == 254

    def test_get_cost_at_outside_bounds(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test getting cost outside costmap bounds returns lethal."""
        checker.update_costmap(mock_costmap)
        target = Pose2D(100.0, 100.0)
        assert checker.get_cost_at(target) == 254

    def test_project_to_free_space_already_valid(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test projection of already valid target returns same target."""
        checker.update_costmap(mock_costmap)
        source = Pose2D(-2.0, 0.0)
        target = Pose2D(3.0, 3.0)  # Free space

        projected = checker.project_to_free_space(target, source)
        assert projected is not None
        assert projected.x == pytest.approx(target.x)
        assert projected.y == pytest.approx(target.y)

    def test_project_to_free_space_backward(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test projection backward along source->target line."""
        checker.update_costmap(mock_costmap)
        # Source is left of obstacle, target is inside obstacle
        source = Pose2D(-3.0, 0.0)  # Left of obstacle
        target = Pose2D(0.0, 0.0)   # Inside obstacle

        projected = checker.project_to_free_space(target, source)
        assert projected is not None
        assert checker.is_valid_target(projected)
        # Projected point should be closer to source than target
        assert abs(projected.x - source.x) < abs(target.x - source.x)

    def test_project_to_free_space_no_costmap(
        self,
        checker_no_costmap: CostmapChecker,
    ) -> None:
        """Test projection without costmap returns original target."""
        source = Pose2D(-3.0, 0.0)
        target = Pose2D(0.0, 0.0)

        projected = checker_no_costmap.project_to_free_space(target, source)
        assert projected is not None
        assert projected.x == target.x
        assert projected.y == target.y

    def test_project_to_free_space_same_position(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test projection when source and target are same point."""
        checker.update_costmap(mock_costmap)
        # Both inside obstacle
        point = Pose2D(0.0, 0.0)

        projected = checker.project_to_free_space(point, point)
        # Should find nearby free space
        assert projected is not None
        assert checker.is_valid_target(projected)

    def test_safe_tracking_action_valid_target(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test safe_tracking_action with valid target."""
        checker.update_costmap(mock_costmap)
        action = TrackingAction(
            target=Pose2D(3.0, 3.0),  # Free space
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )
        robot = Pose2D(-3.0, -3.0)

        safe = checker.safe_tracking_action(action, robot)
        assert safe.target.x == action.target.x
        assert safe.target.y == action.target.y
        assert safe.state == action.state

    def test_safe_tracking_action_invalid_target(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test safe_tracking_action with invalid target."""
        checker.update_costmap(mock_costmap)
        action = TrackingAction(
            target=Pose2D(0.0, 0.0),  # In obstacle
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )
        robot = Pose2D(-3.0, 0.0)

        safe = checker.safe_tracking_action(action, robot)
        assert checker.is_valid_target(safe.target)
        # Target should be different from original
        assert not (safe.target.x == 0.0 and safe.target.y == 0.0)

    def test_safe_tracking_action_no_valid_projection(
        self,
        checker: CostmapChecker,
    ) -> None:
        """Test safe_tracking_action when no valid projection exists.

        This creates a costmap where the robot is surrounded by obstacles
        and the target is also in obstacle, with no free space reachable.
        """
        from nav2_msgs.msg import Costmap, CostmapMetaData
        from geometry_msgs.msg import Pose
        from std_msgs.msg import Header

        msg = Costmap()
        msg.header = Header()
        msg.header.frame_id = "map"
        msg.metadata = CostmapMetaData()
        msg.metadata.resolution = 0.1
        msg.metadata.size_x = 20
        msg.metadata.size_y = 20
        msg.metadata.origin = Pose()
        msg.metadata.origin.position.x = -1.0
        msg.metadata.origin.position.y = -1.0

        # Create a costmap that's entirely lethal (no free space)
        data = np.full((20, 20), 254, dtype=np.uint8)
        msg.data = data.flatten().tolist()

        checker.update_costmap(msg)

        action = TrackingAction(
            target=Pose2D(0.0, 0.0),  # In obstacle
            state=TrackingState.SURGE,
            heading=0.0,
            step_size=0.5,
            use_particle_filter=False,
        )
        robot = Pose2D(0.0, 0.0)

        safe = checker.safe_tracking_action(action, robot)
        # Should return robot pose since no free space found
        assert safe.target.x == robot.x
        assert safe.target.y == robot.y
        assert safe.step_size == 0.0

    def test_world_to_grid_conversion(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test world to grid coordinate conversion."""
        checker.update_costmap(mock_costmap)

        # Origin is at (-5, -5), so world (0, 0) should map to grid (50, 50)
        indices = checker._world_to_grid(0.0, 0.0)
        assert indices == (50, 50)

        # World (-5, -5) should map to grid (0, 0)
        indices = checker._world_to_grid(-5.0, -5.0)
        assert indices == (0, 0)

        # World outside bounds should return None
        indices = checker._world_to_grid(100.0, 100.0)
        assert indices is None

    def test_grid_to_world_conversion(
        self,
        checker: CostmapChecker,
        mock_costmap: "Costmap",
    ) -> None:
        """Test grid to world coordinate conversion."""
        checker.update_costmap(mock_costmap)

        # Grid (0, 0) should map to center of first cell
        # Origin at (-5, -5), resolution 0.1, cell center at (-4.95, -4.95)
        x, y = checker._grid_to_world(0, 0)
        assert x == pytest.approx(-4.95)
        assert y == pytest.approx(-4.95)

        # Grid (50, 50) should map to approximately (0.05, 0.05)
        x, y = checker._grid_to_world(50, 50)
        assert x == pytest.approx(0.05)
        assert y == pytest.approx(0.05)


class TestUpdateCostmapWithOccupancyGrid:
    """Test update_costmap with nav_msgs/OccupancyGrid messages."""

    @pytest.fixture
    def checker(self) -> CostmapChecker:
        return CostmapChecker(CostmapConfig())

    @pytest.fixture
    def mock_occupancy_grid(self):
        """Create a mock nav_msgs/OccupancyGrid with an obstacle."""
        from nav_msgs.msg import OccupancyGrid
        from geometry_msgs.msg import Pose
        from std_msgs.msg import Header

        msg = OccupancyGrid()
        msg.header = Header()
        msg.header.frame_id = "map"

        msg.info.resolution = 0.1
        msg.info.width = 100
        msg.info.height = 100
        msg.info.origin = Pose()
        msg.info.origin.position.x = -5.0
        msg.info.origin.position.y = -5.0

        # Create occupancy grid: 0 = free, 100 = occupied, -1 = unknown
        data = np.zeros((100, 100), dtype=np.int8)
        # Obstacle in center (rows 40-60, cols 40-60) = 2m x 2m at world (0,0)
        data[40:60, 40:60] = 100
        msg.data = data.flatten().tolist()
        return msg

    def test_update_from_occupancy_grid(self, checker, mock_occupancy_grid):
        """Test that OccupancyGrid is parsed correctly."""
        checker.update_costmap(mock_occupancy_grid)
        assert checker.has_costmap is True
        assert checker._resolution == 0.1
        assert checker._width == 100
        assert checker._height == 100
        assert checker.frame_id == "map"

    def test_occupancy_grid_obstacle_detected(self, checker, mock_occupancy_grid):
        """Test obstacle detection from OccupancyGrid."""
        checker.update_costmap(mock_occupancy_grid)
        # (0, 0) is inside the obstacle
        target = Pose2D(0.0, 0.0)
        assert checker.is_valid_target(target) is False

    def test_occupancy_grid_free_space(self, checker, mock_occupancy_grid):
        """Test free space detection from OccupancyGrid."""
        checker.update_costmap(mock_occupancy_grid)
        # (3, 3) is free
        target = Pose2D(3.0, 3.0)
        assert checker.is_valid_target(target) is True

    def test_occupancy_grid_unknown_cells_are_valid(self, checker):
        """Test that unknown cells (-1) in OccupancyGrid are treated as valid."""
        from nav_msgs.msg import OccupancyGrid
        from geometry_msgs.msg import Pose
        from std_msgs.msg import Header

        msg = OccupancyGrid()
        msg.header = Header()
        msg.header.frame_id = "map"
        msg.info.resolution = 0.1
        msg.info.width = 20
        msg.info.height = 20
        msg.info.origin = Pose()
        msg.info.origin.position.x = -1.0
        msg.info.origin.position.y = -1.0

        # All cells are unknown (-1)
        data = np.full((20, 20), -1, dtype=np.int8)
        msg.data = data.flatten().tolist()

        checker.update_costmap(msg)
        target = Pose2D(0.0, 0.0)
        assert checker.is_valid_target(target) is True

    def test_occupancy_grid_cost_at_obstacle(self, checker, mock_occupancy_grid):
        """Test cost value at obstacle position from OccupancyGrid."""
        checker.update_costmap(mock_occupancy_grid)
        target = Pose2D(0.0, 0.0)
        # OccupancyGrid uses 0-100 scale, not 0-255
        cost = checker.get_cost_at(target)
        assert cost == 100