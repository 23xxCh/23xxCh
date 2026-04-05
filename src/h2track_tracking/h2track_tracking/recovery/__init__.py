"""Automatic recovery system for H2Track simulation.

This package provides failure detection and automatic recovery:

- RecoveryPolicy: Defines detection criteria and recovery actions
- RecoveryAction: Interface for recovery actions
- RecoveryMonitor: Monitors system health and triggers recovery

Supported failure types:
- Nav2 timeout: No navigation for 60s
- GADEN not publishing: No gas data for 5s
- AMCL lost: No pose updates for 10s
- Simulation crash: Process exit
"""

from .actions import (
    RecoveryAction,
    RestartGadenPlayerAction,
    RestartLifecycleNodesAction,
    RestartSimulationAction,
    ResetAmclPoseAction,
)
from .monitor import RecoveryMonitor
from .policies import RecoveryPolicy, create_default_policies

__all__ = [
    # Actions
    "RecoveryAction",
    "RestartGadenPlayerAction",
    "RestartLifecycleNodesAction",
    "RestartSimulationAction",
    "ResetAmclPoseAction",
    # Monitor
    "RecoveryMonitor",
    # Policies
    "RecoveryPolicy",
    "create_default_policies",
]
