"""Tests for persistence module."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from h2track_tracking.persistence import (
    DEFAULT_DB_NAME,
    PersistenceManager,
    SimulationRun,
    _get_default_db_path,
    _now_iso,
)


class TestNowIso:
    """Tests for _now_iso helper."""

    def test_now_iso_returns_iso_format(self):
        result = _now_iso()
        assert isinstance(result, str)
        assert "T" in result

    def test_now_iso_has_timezone(self):
        result = _now_iso()
        assert "+" in result or "Z" in result


class TestGetDefaultDbPath:
    """Tests for _get_default_db_path helper."""

    def test_default_path_without_env(self):
        with patch.dict("os.environ", {}, clear=True):
            path = _get_default_db_path()
            assert path.name == DEFAULT_DB_NAME
            assert "h2track-xian" in str(path)

    def test_default_path_with_env(self):
        with patch.dict("os.environ", {"H2TRACK_WORKSPACE": "/custom/workspace"}):
            path = _get_default_db_path()
            assert path == Path("/custom/workspace") / DEFAULT_DB_NAME


class TestSimulationRun:
    """Tests for SimulationRun dataclass."""

    def test_to_dict_basic(self):
        run = SimulationRun(
            id=1,
            scene="warehouse",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at="2024-01-01T00:10:00+00:00",
            source_found=True,
            metrics='{"duration_sec": 600}',
        )
        result = run.to_dict()
        assert result["id"] == 1
        assert result["scene"] == "warehouse"
        assert result["source_found"] is True
        assert result["metrics"] == {"duration_sec": 600}

    def test_to_dict_without_metrics(self):
        run = SimulationRun(
            id=2,
            scene="baseline",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at=None,
            source_found=None,
            metrics=None,
        )
        result = run.to_dict()
        assert result["metrics"] is None

    def test_to_dict_with_invalid_json_metrics(self):
        run = SimulationRun(
            id=3,
            scene="warehouse",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at="2024-01-01T00:10:00+00:00",
            source_found=False,
            metrics="not valid json",
        )
        result = run.to_dict()
        assert result["metrics"] is None

    def test_frozen_dataclass(self):
        run = SimulationRun(
            id=1,
            scene="warehouse",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at=None,
            source_found=None,
            metrics=None,
        )
        with pytest.raises(AttributeError):
            run.scene = "modified"  # type: ignore


class TestPersistenceManagerInit:
    """Tests for PersistenceManager initialization."""

    def test_init_creates_database_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            assert not db_path.exists()
            PersistenceManager(db_path=db_path)
            assert db_path.exists()

    def test_init_creates_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            PersistenceManager(db_path=db_path)

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='simulation_runs'"
                )
                assert cursor.fetchone() is not None

    def test_init_creates_indexes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            PersistenceManager(db_path=db_path)

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_simulation_runs_scene'"
                )
                assert cursor.fetchone() is not None

    def test_init_idempotent(self):
        """Test that initializing twice doesn't fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            PersistenceManager(db_path=db_path)
            PersistenceManager(db_path=db_path)  # Should not raise


class TestPersistenceManagerStartRun:
    """Tests for start_run method."""

    def test_start_run_returns_integer_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")
            assert isinstance(run_id, int)
            assert run_id > 0

    def test_start_run_creates_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("baseline")

            run = manager.get_run(run_id)
            assert run is not None
            assert run.scene == "baseline"
            assert run.started_at is not None
            assert run.ended_at is None
            assert run.source_found is None
            assert run.metrics is None

    def test_start_run_incrementing_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            id1 = manager.start_run("warehouse")
            id2 = manager.start_run("warehouse")
            id3 = manager.start_run("baseline")
            assert id2 > id1
            assert id3 > id2


class TestPersistenceManagerEndRun:
    """Tests for end_run method."""

    def test_end_run_sets_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")

            manager.end_run(run_id, source_found=True, metrics={"duration_sec": 120})

            run = manager.get_run(run_id)
            assert run is not None
            assert run.ended_at is not None
            assert run.source_found is True
            assert run.metrics is not None
            metrics = json.loads(run.metrics)
            assert metrics["duration_sec"] == 120

    def test_end_run_with_false_source_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")

            manager.end_run(run_id, source_found=False)

            run = manager.get_run(run_id)
            assert run is not None
            assert run.source_found is False

    def test_end_run_without_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")

            manager.end_run(run_id, source_found=True, metrics=None)

            run = manager.get_run(run_id)
            assert run is not None
            assert run.metrics is None


class TestPersistenceManagerGetRun:
    """Tests for get_run method."""

    def test_get_run_returns_none_for_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            result = manager.get_run(99999)
            assert result is None

    def test_get_run_returns_simulation_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")

            result = manager.get_run(run_id)
            assert isinstance(result, SimulationRun)
            assert result.id == run_id


class TestPersistenceManagerListRuns:
    """Tests for list_runs method."""

    def test_list_runs_empty_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            runs = manager.list_runs()
            assert runs == []

    def test_list_returns_most_recent_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            id1 = manager.start_run("warehouse")
            id2 = manager.start_run("warehouse")
            id3 = manager.start_run("baseline")

            runs = manager.list_runs()
            assert len(runs) == 3
            assert runs[0].id == id3
            assert runs[1].id == id2
            assert runs[2].id == id1

    def test_list_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            for _ in range(10):
                manager.start_run("warehouse")

            runs = manager.list_runs(limit=5)
            assert len(runs) == 5

    def test_list_filters_by_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")
            manager.start_run("baseline")
            manager.start_run("warehouse")

            warehouse_runs = manager.list_runs(scene="warehouse")
            assert len(warehouse_runs) == 2
            for run in warehouse_runs:
                assert run.scene == "warehouse"

            baseline_runs = manager.list_runs(scene="baseline")
            assert len(baseline_runs) == 1
            assert baseline_runs[0].scene == "baseline"

    def test_list_scene_filter_nonexistent_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")

            runs = manager.list_runs(scene="nonexistent")
            assert runs == []


class TestPersistenceManagerDeleteRun:
    """Tests for delete_run method."""

    def test_delete_existing_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")

            result = manager.delete_run(run_id)
            assert result is True
            assert manager.get_run(run_id) is None

    def test_delete_nonexistent_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            result = manager.delete_run(99999)
            assert result is False

    def test_delete_does_not_affect_other_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            id1 = manager.start_run("warehouse")
            id2 = manager.start_run("warehouse")

            manager.delete_run(id1)
            assert manager.get_run(id1) is None
            assert manager.get_run(id2) is not None


class TestPersistenceManagerGetStats:
    """Tests for get_stats method."""

    def test_stats_empty_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            stats = manager.get_stats()
            assert stats["total_runs"] == 0
            assert stats["completed_runs"] == 0
            assert stats["successful_runs"] == 0
            assert stats["success_rate"] is None
            assert stats["runs_by_scene"] == {}

    def test_stats_counts_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            id1 = manager.start_run("warehouse")
            id2 = manager.start_run("warehouse")
            id3 = manager.start_run("baseline")

            manager.end_run(id1, source_found=True)
            manager.end_run(id2, source_found=False)
            # id3 is still running

            stats = manager.get_stats()
            assert stats["total_runs"] == 3
            assert stats["completed_runs"] == 2
            assert stats["successful_runs"] == 1
            assert stats["success_rate"] == 0.5

    def test_stats_runs_by_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")
            manager.start_run("warehouse")
            manager.start_run("baseline")
            manager.start_run("warehouse")

            stats = manager.get_stats()
            assert stats["runs_by_scene"]["warehouse"] == 3
            assert stats["runs_by_scene"]["baseline"] == 1

    def test_stats_success_rate_zero_when_no_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            run_id = manager.start_run("warehouse")
            manager.end_run(run_id, source_found=False)

            stats = manager.get_stats()
            assert stats["success_rate"] == 0.0

    def test_stats_success_rate_none_when_no_completed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")

            stats = manager.get_stats()
            assert stats["success_rate"] is None


class TestPersistenceManagerDeleteAllRuns:
    """Tests for delete_all_runs method."""

    def test_delete_all_returns_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")
            manager.start_run("warehouse")
            manager.start_run("baseline")

            count = manager.delete_all_runs()
            assert count == 3

    def test_delete_all_clears_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            manager.start_run("warehouse")
            manager.start_run("baseline")

            manager.delete_all_runs()
            runs = manager.list_runs()
            assert runs == []

    def test_delete_all_empty_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            count = manager.delete_all_runs()
            assert count == 0


class TestPersistenceManagerThreadSafety:
    """Tests for thread safety of PersistenceManager."""

    def test_concurrent_start_run(self):
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            errors = []
            run_ids = []

            def writer(scene: str):
                try:
                    for _ in range(10):
                        run_id = manager.start_run(scene)
                        run_ids.append(run_id)
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=writer, args=(f"scene_{i}",)) for i in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert len(run_ids) == 50
            assert len(set(run_ids)) == 50  # All IDs are unique

    def test_concurrent_read_write(self):
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)
            errors = []
            snapshots = []

            def writer():
                try:
                    for i in range(20):
                        run_id = manager.start_run("warehouse")
                        manager.end_run(run_id, source_found=(i % 2 == 0))
                except Exception as e:
                    errors.append(e)

            def reader():
                try:
                    for _ in range(10):
                        stats = manager.get_stats()
                        snapshots.append(stats)
                        runs = manager.list_runs()
                        snapshots.append(len(runs))
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
            assert len(snapshots) > 0


class TestPersistenceManagerIntegration:
    """Integration tests for PersistenceManager with typical usage patterns."""

    def test_full_run_lifecycle(self):
        """Test a complete run lifecycle from start to stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)

            # Start a run
            run_id = manager.start_run("warehouse")

            # Verify it's running
            run = manager.get_run(run_id)
            assert run is not None
            assert run.scene == "warehouse"
            assert run.ended_at is None
            assert run.source_found is None

            # End the run with metrics
            metrics = {
                "duration_sec": 120.5,
                "nav_goals": 5,
                "mode_transitions": ["PATROL", "SEEK_TRACK", "SOURCE_FOUND"],
            }
            manager.end_run(run_id, source_found=True, metrics=metrics)

            # Verify final state
            run = manager.get_run(run_id)
            assert run is not None
            assert run.ended_at is not None
            assert run.source_found is True

            parsed_metrics = json.loads(run.metrics) if run.metrics else {}
            assert parsed_metrics["duration_sec"] == 120.5
            assert parsed_metrics["nav_goals"] == 5

            # Check stats
            stats = manager.get_stats()
            assert stats["total_runs"] == 1
            assert stats["completed_runs"] == 1
            assert stats["successful_runs"] == 1
            assert stats["success_rate"] == 1.0

    def test_multiple_runs_different_outcomes(self):
        """Test multiple runs with different outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = PersistenceManager(db_path=db_path)

            # Run 1: Success
            id1 = manager.start_run("warehouse")
            manager.end_run(id1, source_found=True, metrics={"time": 100})

            # Run 2: Failure
            id2 = manager.start_run("warehouse")
            manager.end_run(id2, source_found=False, metrics={"time": 200, "error": "timeout"})

            # Run 3: Still running
            id3 = manager.start_run("baseline")

            # Run 4: Success on baseline
            id4 = manager.start_run("baseline")
            manager.end_run(id4, source_found=True)

            # List all runs
            all_runs = manager.list_runs()
            assert len(all_runs) == 4

            # Filter by scene
            warehouse_runs = manager.list_runs(scene="warehouse")
            assert len(warehouse_runs) == 2

            baseline_runs = manager.list_runs(scene="baseline")
            assert len(baseline_runs) == 2

            # Check stats
            stats = manager.get_stats()
            assert stats["total_runs"] == 4
            assert stats["completed_runs"] == 3
            assert stats["successful_runs"] == 2
            assert stats["success_rate"] == pytest.approx(2 / 3, abs=1e-6)
            assert stats["runs_by_scene"]["warehouse"] == 2
            assert stats["runs_by_scene"]["baseline"] == 2

            # Delete a run
            assert manager.delete_run(id2) is True
            assert manager.get_run(id2) is None

            # Verify deletion reflected in stats
            stats = manager.get_stats()
            assert stats["total_runs"] == 3
