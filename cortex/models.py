"""Data models for Cortex"""

from typing import Literal

PermissionModeType = Literal["normal", "auto", "plan"]


class PermissionMode:
    """Permission modes for agent actions"""
    NORMAL = "normal"      # Ask for everything
    AUTO_APPROVE = "auto"  # Auto-approve all
    PLAN = "plan"          # Read-only, no writes

