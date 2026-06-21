"""Path resolution for h2track_web package.

Provides access to h2track_bringup share directory for scene loading.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_workspace_root() -> Path:
    """Get workspace root from environment variable."""
    env_path = os.environ.get("H2TRACK_WORKSPACE")
    if env_path:
        return Path(env_path).resolve()
    return Path("/home/user/h2track-xian")


def get_h2track_bringup_share_path() -> Optional[Path]:
    """Get h2track_bringup share directory path using ament index."""
    env_path = os.environ.get("H2TRACK_BRINGUP_SHARE")
    if env_path:
        return Path(env_path).resolve()

    try:
        from ament_index_python.packages import get_package_share_directory
        return Path(get_package_share_directory("h2track_bringup"))
    except Exception:
        pass

    share_path = get_workspace_root() / "install" / "h2track_bringup" / "share" / "h2track_bringup"
    if share_path.exists():
        return share_path

    return None


# Backward-compatible alias
def get_h2track_sim_share_path() -> Optional[Path]:
    """Alias for get_h2track_bringup_share_path()."""
    return get_h2track_bringup_share_path()
