"""Tests for the paths configuration module."""

import os
from pathlib import Path
from unittest import mock

import pytest


class TestPathEnvironmentOverrides:
    """Test that environment variables correctly override default paths."""

    def test_workspace_root_from_env(self):
        """H2TRACK_WORKSPACE should override default workspace detection."""
        from h2track_tracking import paths

        with mock.patch.dict(os.environ, {"H2TRACK_WORKSPACE": "/custom/workspace"}):
            # Re-import to get fresh values
            import importlib

            importlib.reload(paths)
            assert paths.WORKSPACE_ROOT == Path("/custom/workspace")

        # Reload again to restore defaults
        importlib.reload(paths)

    def test_gaden_workspace_from_env(self):
        """GADEN_WS should override default GADEN workspace path."""
        from h2track_tracking import paths

        with mock.patch.dict(os.environ, {"GADEN_WS": "/custom/gaden"}):
            import importlib

            importlib.reload(paths)
            assert paths.GADEN_WS == Path("/custom/gaden")

        importlib.reload(paths)

    def test_h2track_sim_share_from_env(self):
        """H2TRACK_SIM_SHARE should override ament index resolution."""
        from h2track_tracking import paths

        with mock.patch.dict(os.environ, {"H2TRACK_SIM_SHARE": "/custom/share"}):
            import importlib

            importlib.reload(paths)
            result = paths.get_h2track_sim_share_path()
            assert result == Path("/custom/share")

        importlib.reload(paths)


class TestPathDefaults:
    """Test default path values when no overrides are set."""

    def test_shm_dir_is_dev_shm(self):
        """SHM_DIR should always be /dev/shm."""
        from h2track_tracking.paths import SHM_DIR

        assert SHM_DIR == Path("/dev/shm")

    def test_validate_paths_returns_list(self):
        """validate_paths should return a list of warnings."""
        from h2track_tracking.paths import validate_paths

        warnings = validate_paths()
        assert isinstance(warnings, list)


class TestPathResolution:
    """Test path resolution functions."""

    def test_get_h2track_sim_share_path_returns_path_or_none(self):
        """get_h2track_sim_share_path should return Path or None."""
        from h2track_tracking.paths import get_h2track_sim_share_path

        result = get_h2track_sim_share_path()
        assert result is None or isinstance(result, Path)

    def test_get_gaden_workspace_returns_path(self):
        """get_gaden_workspace should always return a Path."""
        from h2track_tracking.paths import get_gaden_workspace

        result = get_gaden_workspace()
        assert isinstance(result, Path)

    def test_get_workspace_root_returns_path(self):
        """get_workspace_root should always return a Path."""
        from h2track_tracking.paths import get_workspace_root

        result = get_workspace_root()
        assert isinstance(result, Path)
