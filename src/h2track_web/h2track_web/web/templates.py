"""HTML templates for the web console.

This module loads the HTML page template from the static_console directory.
For report generation, see reports.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PAGE_FILENAME = "index.html"
_DASHBOARD_FILENAME = "dashboard.html"

# Fallback HTML when the page file is not found
_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>H2Track 控制台 - 加载错误</title>
    <style>
        body { font-family: sans-serif; padding: 2rem; text-align: center; }
        .error { color: #c00; }
    </style>
</head>
<body>
    <h1 class="error">控制台不可用</h1>
    <p>无法加载Web控制台页面。请检查安装是否正确。</p>
</body>
</html>
"""


def _resolve_page_path() -> Path | None:
    """Resolve the HTML page path.

    Checks both module directory and ROS package share directory.

    Returns:
        Path to index.html, or None if not found.
    """
    # Check module directory (source tree)
    module_dir = Path(__file__).resolve().parent.parent / "static_console"
    candidate = module_dir / _PAGE_FILENAME
    if candidate.exists():
        return candidate

    # Check ROS package share directory (installed)
    try:
        from ament_index_python.packages import get_package_share_directory

        share_dir = Path(get_package_share_directory("h2track_tracking")) / "static_console"
        candidate = share_dir / _PAGE_FILENAME
        if candidate.exists():
            return candidate
    except ImportError:
        pass  # Expected when ament_index_python not available
    except Exception as exc:
        logger.debug(f"Error resolving ROS package path: {exc}")

    return None


def _load_html_page() -> str:
    """Load the HTML page from the static file.

    Returns:
        The HTML content as a string, or a fallback HTML if file not found.
    """
    path = _resolve_page_path()
    if path is None:
        logger.warning("HTML page not found, using fallback template")
        return _FALLBACK_HTML
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to read HTML page: {exc}")
        return _FALLBACK_HTML


HTML_PAGE = _load_html_page()
