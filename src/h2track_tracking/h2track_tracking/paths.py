"""Configurable paths for the h2track_tracking package.

This module provides path resolution that supports:
- Environment variable overrides for deployment flexibility
- ROS 2 ament index for runtime package discovery
- Consistent path access across the codebase

Environment Variables:
    H2TRACK_WORKSPACE: Override workspace root detection
    GADEN_WS: GADEN workspace path (defaults to /home/user/gaden_ws)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_workspace_root() -> Path:
    """Get workspace root from environment variable.

    Resolution order:
    1. H2TRACK_WORKSPACE environment variable (required for non-default setups)

    Returns:
        Path to workspace root directory

    Note:
        For ROS 2 packages, prefer using get_h2track_sim_share_path() which
        uses the ament index for proper runtime resolution.
    """
    env_path = os.environ.get("H2TRACK_WORKSPACE")
    if env_path:
        return Path(env_path).resolve()

    # Default assumption for the standard development environment
    return Path("/home/user/h2track-xian")


def get_h2track_sim_share_path() -> Optional[Path]:
    """Get h2track_sim share directory path using ament index.

    Resolution order:
    1. H2TRACK_SIM_SHARE environment variable
    2. ament_index_python if package is installed
    3. Computed from workspace root

    Returns:
        Path to install/h2track_sim/share/h2track_sim, or None if not found
    """
    # 1. Check environment variable override
    env_path = os.environ.get("H2TRACK_SIM_SHARE")
    if env_path:
        return Path(env_path).resolve()

    # 2. Try ament index
    try:
        from ament_index_python.packages import get_package_share_directory

        return Path(get_package_share_directory("h2track_sim"))
    except ImportError:
        pass
    except Exception:
        # PackageNotFoundError or other issues
        pass

    # 3. Fallback to computed path from workspace root
    share_path = get_workspace_root() / "install" / "h2track_sim" / "share" / "h2track_sim"
    if share_path.exists():
        return share_path

    return None


def get_gaden_workspace() -> Path:
    """Get GADEN workspace path.

    Resolution order:
    1. GADEN_WS environment variable
    2. Default to /home/user/gaden_ws

    Returns:
        Path to GADEN workspace root
    """
    env_path = os.environ.get("GADEN_WS")
    if env_path:
        return Path(env_path).resolve()

    return Path("/home/user/gaden_ws")


# Computed constants for common paths
WORKSPACE_ROOT = get_workspace_root()
GADEN_WS = get_gaden_workspace()

# Default world paths for scene fallbacks - computed lazily
_h2track_sim_share = get_h2track_sim_share_path()
BASELINE_WORLD_PATH = (
    _h2track_sim_share / "worlds" / "h2track_lab.world"
    if _h2track_sim_share
    else WORKSPACE_ROOT / "install" / "h2track_sim" / "share" / "h2track_sim" / "worlds" / "h2track_lab.world"
)
WAREHOUSE_WORLD_PATH = (
    _h2track_sim_share / "scenes" / "warehouse" / "warehouse.world"
    if _h2track_sim_share
    else WORKSPACE_ROOT / "install" / "h2track_sim" / "share" / "h2track_sim" / "scenes" / "warehouse" / "warehouse.world"
)

# Shared memory directory for FastDDS lock files
SHM_DIR = Path("/dev/shm")


def validate_paths() -> list[str]:
    """Validate that required paths exist.

    Returns:
        List of warning messages for missing paths
    """
    warnings: list[str] = []

    if not WORKSPACE_ROOT.exists():
        warnings.append(f"Workspace root not found: {WORKSPACE_ROOT}")

    h2track_sim_share = get_h2track_sim_share_path()
    if h2track_sim_share is None or not h2track_sim_share.exists():
        warnings.append(f"h2track_sim share directory not found")

    return warnings
