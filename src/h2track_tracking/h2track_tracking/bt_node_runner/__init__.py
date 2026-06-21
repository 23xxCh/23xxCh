#!/usr/bin/env python3
"""BT Node Runner subpackage.

Re-exports BTNodeRunner and main for backward compatibility:
    from h2track_tracking.bt_node_runner import BTNodeRunner, main
"""

from h2track_tracking.bt_node_runner.runner import BTNodeRunner, main

__all__ = ["BTNodeRunner", "main"]
