"""HTML templates for the web console.

This module loads the legacy HTML page template from the static_console directory.
For report generation, see reports.py.
"""

from __future__ import annotations

from pathlib import Path

_LEGACY_PAGE_FILENAME = "legacy_page.html"


def _resolve_legacy_page_path() -> Path | None:
    """Resolve the legacy HTML page path.

    Checks both module directory and ROS package share directory.

    Returns:
        Path to legacy_page.html, or None if not found.
    """
    # Check module directory (source tree)
    module_dir = Path(__file__).resolve().parent.parent / "static_console"
    candidate = module_dir / _LEGACY_PAGE_FILENAME
    if candidate.exists():
        return candidate

    # Check ROS package share directory (installed)
    try:
        from ament_index_python.packages import get_package_share_directory

        share_dir = Path(get_package_share_directory("h2track_tracking")) / "static_console"
        candidate = share_dir / _LEGACY_PAGE_FILENAME
        if candidate.exists():
            return candidate
    except Exception:
        pass

    return None


def _load_html_page() -> str:
    """Load the legacy HTML page from the static file.

    Returns:
        The HTML content as a string, or an empty string if file not found.
    """
    path = _resolve_legacy_page_path()
    if path is None:
        return ""
    return path.read_text(encoding="utf-8")


HTML_PAGE = _load_html_page()
