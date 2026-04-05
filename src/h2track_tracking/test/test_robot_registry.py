"""Tests for robot_registry module."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import pytest

from h2track_tracking.robot_registry import (
    Pose2D,
    RobotRegistry,
    RobotState,
    _now_utc,
)


class TestPose2D:
    """Tests for Pose2D dataclass."""

    def test_default_values(self):
        pose = Pose2D()
        assert pose.x == pytest.approx(0.0, abs=1e-9)
        assert pose.y == pytest.approx(0.0, abs=1e-9)
        assert pose.yaw == pytest.approx(0.0, abs=1e-9)

    def test_custom_values(self):
        pose = Pose2D(x=1.5, y=2.5, yaw=0.785)
        assert pose.x == pytest.approx(1.5, abs=1e-9)
        assert pose.y == pytest.approx(2.5, abs=1e-9)
        assert pose.yaw == pytest.approx(0.785, abs=1e-9)

    def test_frozen(self):
        pose = Pose2D(x=1.0, y=2.0, yaw=0.5)
        with pytest.raises(AttributeError):
            pose.x = 5.0  # type: ignore[misc]

    def test_to_dict(self):
        pose = Pose2D(x=1.5, y=2.5, yaw=0.785)
        result = pose.to_dict()
        assert result == {"x": 1.5, "y": 2.5, "yaw": 0.785}

    def test_from_dict(self):
        data = {"x": 1.5, "y": 2.5, "yaw": 0.785}
        pose = Pose2D.from_dict(data)
        assert pose.x == pytest.approx(1.5, abs=1e-9)
        assert pose.y == pytest.approx(2.5, abs=1e-9)
        assert pose.yaw == pytest.approx(0.785, abs=1e-9)

    def test_from_dict_missing_keys(self):
        data: dict[str, float] = {}
        pose = Pose2D.from_dict(data)
        assert pose.x == pytest.approx(0.0, abs=1e-9)
        assert pose.y == pytest.approx(0.0, abs=1e-9)
        assert pose.yaw == pytest.approx(0.0, abs=1e-9)

    def test_from_dict_partial(self):
        data = {"x": 1.5}
        pose = Pose2D.from_dict(data)
        assert pose.x == pytest.approx(1.5, abs=1e-9)
        assert pose.y == pytest.approx(0.0, abs=1e-9)
        assert pose.yaw == pytest.approx(0.0, abs=1e-9)

    def test_roundtrip(self):
        original = Pose2D(x=3.14, y=2.71, yaw=1.57)
        result = Pose2D.from_dict(original.to_dict())
        assert result.x == pytest.approx(original.x, abs=1e-9)
        assert result.y == pytest.approx(original.y, abs=1e-9)
        assert result.yaw == pytest.approx(original.yaw, abs=1e-9)


class TestRobotState:
    """Tests for RobotState dataclass."""

    def test_creation(self):
        pose = Pose2D(x=1.0, y=2.0, yaw=0.5)
        now = _now_utc()
        state = RobotState(
            robot_id="robot_1",
            namespace="/robot_1",
            mode="PATROL",
            pose=pose,
            gas_reading=0.42,
            last_updated=now,
        )
        assert state.robot_id == "robot_1"
        assert state.namespace == "/robot_1"
        assert state.mode == "PATROL"
        assert state.pose.x == pytest.approx(1.0, abs=1e-9)
        assert state.gas_reading == pytest.approx(0.42, abs=1e-9)
        assert state.last_updated == now

    def test_frozen(self):
        pose = Pose2D()
        state = RobotState(
            robot_id="robot_1",
            namespace="/robot_1",
            mode="PATROL",
            pose=pose,
            gas_reading=0.42,
            last_updated=_now_utc(),
        )
        with pytest.raises(AttributeError):
            state.mode = "SEEK_TRACK"  # type: ignore[misc]

    def test_to_dict(self):
        pose = Pose2D(x=1.0, y=2.0, yaw=0.5)
        now = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        state = RobotState(
            robot_id="robot_1",
            namespace="/robot_1",
            mode="PATROL",
            pose=pose,
            gas_reading=0.42,
            last_updated=now,
        )
        result = state.to_dict()
        assert result["robot_id"] == "robot_1"
        assert result["namespace"] == "/robot_1"
        assert result["mode"] == "PATROL"
        assert result["pose"] == {"x": 1.0, "y": 2.0, "yaw": 0.5}
        assert result["gas_reading"] == pytest.approx(0.42, abs=1e-9)
        assert result["last_updated"] == "2026-04-05T12:00:00+00:00"


class TestNowUtc:
    """Tests for _now_utc helper."""

    def test_returns_datetime(self):
        result = _now_utc()
        assert isinstance(result, datetime)

    def test_has_timezone(self):
        result = _now_utc()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_is_recent(self):
        before = datetime.now(tz=timezone.utc)
        result = _now_utc()
        after = datetime.now(tz=timezone.utc)
        assert before <= result <= after


class TestRobotRegistryInit:
    """Tests for RobotRegistry initialization."""

    def test_init_empty(self):
        registry = RobotRegistry()
        assert registry.count() == 0

    def test_init_empty_robots_dict(self):
        registry = RobotRegistry()
        assert len(registry._robots) == 0

    def test_init_empty_namespaces_dict(self):
        registry = RobotRegistry()
        assert len(registry._namespaces) == 0


class TestRobotRegistryRegister:
    """Tests for register method."""

    def test_register_creates_entry(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        assert registry.is_registered("robot_1")

    def test_register_stores_namespace(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        assert registry.get_namespace("robot_1") == "/robot_1"

    def test_register_creates_initial_state(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        state = registry.get_state("robot_1")
        assert state is not None
        assert state.robot_id == "robot_1"
        assert state.namespace == "/robot_1"
        assert state.mode == "INIT"
        assert state.gas_reading == pytest.approx(0.0, abs=1e-9)

    def test_register_increments_count(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        assert registry.count() == 1
        registry.register("robot_2", "/robot_2")
        assert registry.count() == 2

    def test_register_idempotent(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_1", "/robot_1")
        assert registry.count() == 1

    def test_register_strips_whitespace(self):
        registry = RobotRegistry()
        registry.register("  robot_1  ", "  /robot_1  ")
        state = registry.get_state("robot_1")
        assert state is not None
        assert state.namespace == "/robot_1"

    def test_register_empty_robot_id_raises(self):
        registry = RobotRegistry()
        with pytest.raises(ValueError, match="robot_id cannot be empty"):
            registry.register("", "/robot_1")

    def test_register_whitespace_robot_id_raises(self):
        registry = RobotRegistry()
        with pytest.raises(ValueError, match="robot_id cannot be empty"):
            registry.register("   ", "/robot_1")

    def test_register_empty_namespace_raises(self):
        registry = RobotRegistry()
        with pytest.raises(ValueError, match="namespace cannot be empty"):
            registry.register("robot_1", "")

    def test_register_whitespace_namespace_raises(self):
        registry = RobotRegistry()
        with pytest.raises(ValueError, match="namespace cannot be empty"):
            registry.register("robot_1", "   ")


class TestRobotRegistryUnregister:
    """Tests for unregister method."""

    def test_unregister_removes_entry(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        result = registry.unregister("robot_1")
        assert result is True
        assert not registry.is_registered("robot_1")

    def test_unregister_decrements_count(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_2", "/robot_2")
        registry.unregister("robot_1")
        assert registry.count() == 1

    def test_unregister_nonexistent_returns_false(self):
        registry = RobotRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_unregister_removes_namespace(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.unregister("robot_1")
        assert registry.get_namespace("robot_1") is None


class TestRobotRegistryUpdateState:
    """Tests for update_state method."""

    def test_update_state(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")

        new_state = RobotState(
            robot_id="robot_1",
            namespace="/robot_1",
            mode="SEEK_TRACK",
            pose=Pose2D(x=5.0, y=3.0, yaw=1.0),
            gas_reading=0.75,
            last_updated=_now_utc(),
        )
        registry.update_state("robot_1", new_state)

        result = registry.get_state("robot_1")
        assert result is not None
        assert result.mode == "SEEK_TRACK"
        assert result.pose.x == pytest.approx(5.0, abs=1e-9)
        assert result.gas_reading == pytest.approx(0.75, abs=1e-9)

    def test_update_state_nonexistent_raises(self):
        registry = RobotRegistry()
        state = RobotState(
            robot_id="nonexistent",
            namespace="/nonexistent",
            mode="PATROL",
            pose=Pose2D(),
            gas_reading=0.0,
            last_updated=_now_utc(),
        )
        with pytest.raises(KeyError, match="not registered"):
            registry.update_state("nonexistent", state)

    def test_update_state_mismatched_id_raises(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")

        state = RobotState(
            robot_id="robot_2",
            namespace="/robot_2",
            mode="PATROL",
            pose=Pose2D(),
            gas_reading=0.0,
            last_updated=_now_utc(),
        )
        with pytest.raises(ValueError, match="doesn't match"):
            registry.update_state("robot_1", state)


class TestRobotRegistryUpdateConvenience:
    """Tests for convenience update methods."""

    def test_update_pose(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")

        new_pose = Pose2D(x=10.0, y=20.0, yaw=1.57)
        registry.update_pose("robot_1", new_pose)

        state = registry.get_state("robot_1")
        assert state is not None
        assert state.pose.x == pytest.approx(10.0, abs=1e-9)
        assert state.pose.y == pytest.approx(20.0, abs=1e-9)
        assert state.mode == "INIT"  # Unchanged

    def test_update_mode(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")

        registry.update_mode("robot_1", "SEEK_CONFIRM")

        state = registry.get_state("robot_1")
        assert state is not None
        assert state.mode == "SEEK_CONFIRM"

    def test_update_gas_reading(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")

        registry.update_gas_reading("robot_1", 0.85)

        state = registry.get_state("robot_1")
        assert state is not None
        assert state.gas_reading == pytest.approx(0.85, abs=1e-9)

    def test_update_pose_nonexistent_raises(self):
        registry = RobotRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.update_pose("nonexistent", Pose2D())

    def test_update_mode_nonexistent_raises(self):
        registry = RobotRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.update_mode("nonexistent", "PATROL")

    def test_update_gas_reading_nonexistent_raises(self):
        registry = RobotRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.update_gas_reading("nonexistent", 0.5)


class TestRobotRegistryQueries:
    """Tests for query methods."""

    def test_get_state_returns_none_for_nonexistent(self):
        registry = RobotRegistry()
        result = registry.get_state("nonexistent")
        assert result is None

    def test_list_robots_empty(self):
        registry = RobotRegistry()
        result = registry.list_robots()
        assert result == []

    def test_list_robots_returns_all(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_2", "/robot_2")

        result = registry.list_robots()
        ids = {r.robot_id for r in result}
        assert ids == {"robot_1", "robot_2"}

    def test_list_robot_ids_empty(self):
        registry = RobotRegistry()
        result = registry.list_robot_ids()
        assert result == []

    def test_list_robot_ids_returns_all(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_2", "/robot_2")

        result = registry.list_robot_ids()
        assert set(result) == {"robot_1", "robot_2"}

    def test_count_empty(self):
        registry = RobotRegistry()
        assert registry.count() == 0

    def test_count_after_operations(self):
        registry = RobotRegistry()
        assert registry.count() == 0
        registry.register("robot_1", "/robot_1")
        assert registry.count() == 1
        registry.register("robot_2", "/robot_2")
        assert registry.count() == 2
        registry.unregister("robot_1")
        assert registry.count() == 1

    def test_is_registered(self):
        registry = RobotRegistry()
        assert not registry.is_registered("robot_1")
        registry.register("robot_1", "/robot_1")
        assert registry.is_registered("robot_1")
        assert not registry.is_registered("robot_2")


class TestRobotRegistryClear:
    """Tests for clear method."""

    def test_clear_removes_all(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_2", "/robot_2")
        registry.clear()
        assert registry.count() == 0

    def test_clear_empty_registry(self):
        registry = RobotRegistry()
        registry.clear()
        assert registry.count() == 0


class TestRobotRegistryUpdatedAt:
    """Tests for updated_at property."""

    def test_updated_at_initial(self):
        registry = RobotRegistry()
        assert isinstance(registry.updated_at, datetime)

    def test_updated_after_register(self):
        registry = RobotRegistry()
        before = registry.updated_at
        time.sleep(0.01)
        registry.register("robot_1", "/robot_1")
        after = registry.updated_at
        assert after > before

    def test_updated_after_unregister(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        before = registry.updated_at
        time.sleep(0.01)
        registry.unregister("robot_1")
        after = registry.updated_at
        assert after > before

    def test_updated_after_update(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        before = registry.updated_at
        time.sleep(0.01)
        registry.update_mode("robot_1", "PATROL")
        after = registry.updated_at
        assert after > before


class TestRobotRegistrySnapshot:
    """Tests for snapshot method."""

    def test_snapshot_empty(self):
        registry = RobotRegistry()
        snap = registry.snapshot()
        assert snap["count"] == 0
        assert snap["robots"] == {}
        assert snap["robot_ids"] == []

    def test_snapshot_single_robot(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.update_mode("robot_1", "SEEK_TRACK")

        snap = registry.snapshot()
        assert snap["count"] == 1
        assert "robot_1" in snap["robots"]
        assert snap["robots"]["robot_1"]["mode"] == "SEEK_TRACK"

    def test_snapshot_multiple_robots(self):
        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.register("robot_2", "/robot_2")

        snap = registry.snapshot()
        assert snap["count"] == 2
        assert set(snap["robot_ids"]) == {"robot_1", "robot_2"}

    def test_snapshot_includes_updated_at(self):
        registry = RobotRegistry()
        snap = registry.snapshot()
        assert "updated_at" in snap
        assert isinstance(snap["updated_at"], str)

    def test_snapshot_serializable(self):
        """Test that snapshot can be JSON serialized."""
        import json

        registry = RobotRegistry()
        registry.register("robot_1", "/robot_1")
        registry.update_pose("robot_1", Pose2D(x=1.0, y=2.0, yaw=0.5))

        snap = registry.snapshot()
        # Should not raise
        json_string = json.dumps(snap)
        assert json_string is not None


class TestRobotRegistryThreadSafety:
    """Tests for thread safety of RobotRegistry."""

    def test_concurrent_register(self):
        registry = RobotRegistry()
        errors: list[Exception] = []

        def register_robot(i: int):
            try:
                registry.register(f"robot_{i}", f"/robot_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_robot, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert registry.count() == 50

    def test_concurrent_update(self):
        registry = RobotRegistry()
        for i in range(10):
            registry.register(f"robot_{i}", f"/robot_{i}")

        errors: list[Exception] = []

        def update_robot(i: int):
            try:
                for _ in range(100):
                    registry.update_mode(f"robot_{i}", "SEEK_TRACK")
                    registry.update_gas_reading(f"robot_{i}", 0.5)
                    registry.update_pose(f"robot_{i}", Pose2D(x=float(i), y=float(i)))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_robot, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self):
        registry = RobotRegistry()
        for i in range(5):
            registry.register(f"robot_{i}", f"/robot_{i}")

        errors: list[Exception] = []
        snapshots: list[dict] = []

        def writer():
            try:
                for i in range(100):
                    registry.update_gas_reading("robot_0", float(i) / 100.0)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    snap = registry.snapshot()
                    snapshots.append(snap)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer)] + [
            threading.Thread(target=reader) for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(snapshots) == 150

    def test_concurrent_register_unregister(self):
        registry = RobotRegistry()
        errors: list[Exception] = []

        def register_unregister(i: int):
            try:
                for _ in range(10):
                    registry.register(f"robot_{i}", f"/robot_{i}")
                    registry.unregister(f"robot_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_unregister, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestRobotRegistryIntegration:
    """Integration tests for typical multi-robot workflows."""

    def test_full_robot_lifecycle(self):
        """Test complete robot lifecycle from registration to source found."""
        registry = RobotRegistry()

        # Register robot
        registry.register("robot_1", "/robot_1")
        state = registry.get_state("robot_1")
        assert state is not None
        assert state.mode == "INIT"

        # Start patrol
        registry.update_mode("robot_1", "PATROL")
        assert registry.get_state("robot_1").mode == "PATROL"

        # Update pose during patrol
        registry.update_pose("robot_1", Pose2D(x=5.0, y=3.0, yaw=0.5))
        assert registry.get_state("robot_1").pose.x == pytest.approx(5.0, abs=1e-9)

        # Gas detection triggers mode change
        registry.update_gas_reading("robot_1", 0.7)
        registry.update_mode("robot_1", "SEEK_CONFIRM")
        assert registry.get_state("robot_1").mode == "SEEK_CONFIRM"

        # Confirm and start tracking
        registry.update_gas_reading("robot_1", 0.85)
        registry.update_mode("robot_1", "SEEK_TRACK")

        # Approaching source
        registry.update_gas_reading("robot_1", 3.5)
        registry.update_pose("robot_1", Pose2D(x=10.0, y=10.0, yaw=1.57))
        registry.update_mode("robot_1", "SOURCE_FOUND")

        # Verify final state
        final_state = registry.get_state("robot_1")
        assert final_state is not None
        assert final_state.mode == "SOURCE_FOUND"
        assert final_state.gas_reading == pytest.approx(3.5, abs=1e-9)
        assert final_state.pose.x == pytest.approx(10.0, abs=1e-9)

    def test_multi_robot_fleet_tracking(self):
        """Test tracking multiple robots simultaneously."""
        registry = RobotRegistry()

        # Register fleet of 3 robots
        for i in range(3):
            registry.register(f"robot_{i}", f"/robot_{i}")

        # Each robot in different state
        registry.update_mode("robot_0", "PATROL")
        registry.update_mode("robot_1", "SEEK_TRACK")
        registry.update_mode("robot_2", "SOURCE_FOUND")

        # Update positions
        positions = [
            (0.0, 0.0),  # robot_0 at origin
            (5.0, 3.0),  # robot_1 mid-field
            (10.0, 10.0),  # robot_2 at source
        ]
        for i, (x, y) in enumerate(positions):
            registry.update_pose(f"robot_{i}", Pose2D(x=x, y=y))

        # Query fleet status
        fleet = registry.list_robots()
        modes = {r.robot_id: r.mode for r in fleet}
        assert modes["robot_0"] == "PATROL"
        assert modes["robot_1"] == "SEEK_TRACK"
        assert modes["robot_2"] == "SOURCE_FOUND"

        # Check positions
        positions_by_id = {r.robot_id: r.pose for r in fleet}
        assert positions_by_id["robot_0"].x == pytest.approx(0.0, abs=1e-9)
        assert positions_by_id["robot_1"].x == pytest.approx(5.0, abs=1e-9)
        assert positions_by_id["robot_2"].x == pytest.approx(10.0, abs=1e-9)

        # Snapshot for web console
        snap = registry.snapshot()
        assert snap["count"] == 3

    def test_robot_re_registration_after_unregister(self):
        """Test that a robot can be re-registered after removal."""
        registry = RobotRegistry()

        # Register and set state
        registry.register("robot_1", "/robot_1")
        registry.update_mode("robot_1", "SOURCE_FOUND")

        # Unregister
        registry.unregister("robot_1")

        # Re-register (should start fresh)
        registry.register("robot_1", "/robot_1")
        state = registry.get_state("robot_1")
        assert state is not None
        assert state.mode == "INIT"  # Reset to initial state
