"""SQLite-based persistence for simulation run history.

This module provides the PersistenceManager class for tracking:
- Simulation run lifecycle (start/end times)
- Run outcomes (source found status)
- Run metrics (JSON serialized)

All methods are thread-safe via an internal lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Default database path relative to workspace
DEFAULT_DB_NAME = "h2track_runs.db"


def _now_iso() -> str:
    """Return current time as ISO format string with timezone."""
    return datetime.now(tz=timezone.utc).isoformat()


def _get_default_db_path() -> Path:
    """Get the default database path.

    Resolution order:
    1. H2TRACK_WORKSPACE environment variable
    2. Default to /home/user/h2track-xian

    Returns:
        Path to the database file in the workspace root
    """
    import os

    workspace = os.environ.get("H2TRACK_WORKSPACE", "/home/user/h2track-xian")
    return Path(workspace) / DEFAULT_DB_NAME


@dataclass(frozen=True)
class SimulationRun:
    """Immutable representation of a simulation run record.

    Attributes:
        id: Unique run identifier (auto-incremented)
        scene: Scene name for this run
        started_at: ISO timestamp when run started
        ended_at: ISO timestamp when run ended (None if running)
        source_found: Whether the source was found (None if running)
        metrics: JSON-serialized metrics dictionary
    """

    id: int
    scene: str
    started_at: str
    ended_at: str | None
    source_found: bool | None
    metrics: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with parsed metrics.

        Returns:
            Dictionary representation with metrics as dict
        """
        result: dict[str, Any] = {
            "id": self.id,
            "scene": self.scene,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "source_found": self.source_found,
        }
        if self.metrics:
            try:
                result["metrics"] = json.loads(self.metrics)
            except json.JSONDecodeError:
                result["metrics"] = None
        else:
            result["metrics"] = None
        return result


class PersistenceManager:
    """Thread-safe SQLite-based persistence for simulation runs.

    This class provides:
    - CRUD operations for simulation runs
    - Thread-safe database access
    - Automatic schema initialization

    All methods are thread-safe via an internal lock.

    Example:
        >>> manager = PersistenceManager()
        >>> run_id = manager.start_run("warehouse")
        >>> # ... run simulation ...
        >>> manager.end_run(run_id, source_found=True, metrics={"duration_sec": 120})
        >>> run = manager.get_run(run_id)
        >>> print(run.source_found)  # True
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS simulation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        ended_at TIMESTAMP,
        source_found BOOLEAN,
        metrics JSON
    );

    CREATE INDEX IF NOT EXISTS idx_simulation_runs_scene
        ON simulation_runs(scene);

    CREATE INDEX IF NOT EXISTS idx_simulation_runs_started_at
        ON simulation_runs(started_at);

    CREATE INDEX IF NOT EXISTS idx_simulation_runs_source_found
        ON simulation_runs(source_found);
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the persistence manager.

        Args:
            db_path: Path to SQLite database file. If None, uses default path.
        """
        self._lock = threading.Lock()
        self._db_path = Path(db_path) if db_path else _get_default_db_path()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript(self.SCHEMA_SQL)
            conn.commit()

    def start_run(self, scene: str) -> int:
        """Start a new simulation run.

        Args:
            scene: Name of the scene being simulated

        Returns:
            The run_id of the newly created run
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO simulation_runs (scene, started_at)
                    VALUES (?, ?)
                    """,
                    (scene, _now_iso()),
                )
                conn.commit()
                run_id = cursor.lastrowid
                if run_id is None:
                    raise RuntimeError("Failed to get lastrowid after INSERT")
                return run_id

    def end_run(
        self, run_id: int, source_found: bool, metrics: dict[str, Any] | None = None
    ) -> None:
        """End a simulation run with results.

        Args:
            run_id: The run identifier returned by start_run
            source_found: Whether the source was successfully found
            metrics: Optional metrics dictionary (will be JSON serialized)
        """
        metrics_json = json.dumps(metrics) if metrics else None

        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """
                    UPDATE simulation_runs
                    SET ended_at = ?, source_found = ?, metrics = ?
                    WHERE id = ?
                    """,
                    (_now_iso(), source_found, metrics_json, run_id),
                )
                conn.commit()

    def get_run(self, run_id: int) -> SimulationRun | None:
        """Get a specific run by ID.

        Args:
            run_id: The run identifier

        Returns:
            SimulationRun if found, None otherwise
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT id, scene, started_at, ended_at, source_found, metrics
                    FROM simulation_runs
                    WHERE id = ?
                    """,
                    (run_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None

                return SimulationRun(
                    id=row["id"],
                    scene=row["scene"],
                    started_at=row["started_at"],
                    ended_at=row["ended_at"],
                    source_found=bool(row["source_found"]) if row["source_found"] is not None else None,
                    metrics=row["metrics"],
                )

    def list_runs(self, limit: int = 100, scene: str | None = None) -> list[SimulationRun]:
        """List recent simulation runs.

        Args:
            limit: Maximum number of runs to return
            scene: Optional scene filter

        Returns:
            List of SimulationRun objects, most recent first
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if scene:
                    cursor = conn.execute(
                        """
                        SELECT id, scene, started_at, ended_at, source_found, metrics
                        FROM simulation_runs
                        WHERE scene = ?
                        ORDER BY started_at DESC
                        LIMIT ?
                        """,
                        (scene, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT id, scene, started_at, ended_at, source_found, metrics
                        FROM simulation_runs
                        ORDER BY started_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    )

                runs = []
                for row in cursor.fetchall():
                    runs.append(
                        SimulationRun(
                            id=row["id"],
                            scene=row["scene"],
                            started_at=row["started_at"],
                            ended_at=row["ended_at"],
                            source_found=bool(row["source_found"]) if row["source_found"] is not None else None,
                            metrics=row["metrics"],
                        )
                    )
                return runs

    def delete_run(self, run_id: int) -> bool:
        """Delete a specific run by ID.

        Args:
            run_id: The run identifier

        Returns:
            True if a run was deleted, False if no such run existed
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM simulation_runs
                    WHERE id = ?
                    """,
                    (run_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics across all runs.

        Returns:
            Dictionary with total_runs, successful_runs, success_rate, etc.
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                # Total runs
                total_cursor = conn.execute("SELECT COUNT(*) FROM simulation_runs")
                total_runs = total_cursor.fetchone()[0]

                # Completed runs (ended_at is not null)
                completed_cursor = conn.execute(
                    "SELECT COUNT(*) FROM simulation_runs WHERE ended_at IS NOT NULL"
                )
                completed_runs = completed_cursor.fetchone()[0]

                # Successful runs (source_found is true)
                success_cursor = conn.execute(
                    "SELECT COUNT(*) FROM simulation_runs WHERE source_found = 1"
                )
                successful_runs = success_cursor.fetchone()[0]

                # Runs by scene
                scene_cursor = conn.execute(
                    """
                    SELECT scene, COUNT(*) as count
                    FROM simulation_runs
                    GROUP BY scene
                    ORDER BY count DESC
                    """
                )
                runs_by_scene = {row[0]: row[1] for row in scene_cursor.fetchall()}

                # Success rate
                success_rate = None
                if completed_runs > 0:
                    success_rate = successful_runs / completed_runs

                return {
                    "total_runs": total_runs,
                    "completed_runs": completed_runs,
                    "successful_runs": successful_runs,
                    "success_rate": success_rate,
                    "runs_by_scene": runs_by_scene,
                }

    def delete_all_runs(self) -> int:
        """Delete all runs from the database.

        Returns:
            Number of runs deleted
        """
        with self._lock:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM simulation_runs")
                count = cursor.fetchone()[0]
                conn.execute("DELETE FROM simulation_runs")
                conn.commit()
                return count
