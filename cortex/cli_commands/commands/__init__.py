"""CLI command system - modular command pattern implementation"""

from .base import Command, CommandContext, CommandRegistry

# Import all command classes
from .clear import ClearCommand, ResetContextCommand
from .mode import PermissionModeCommand, UIModeCommand, PlanCommand
from .model import ModelCommand, ProfileCommand
from .memory import MemoryCommand, FocusCommand, ThinkingCommand, SummaryCommand
from .session import (
    SaveSessionCommand,
    LoadSessionCommand,
    ListSessionsCommand,
    SessionRecoveryCommand,
)
from .stats import ProjectCommand, StatsCommand, RoutingCommand, StorageCommand, CleanupCommand
from .cache import CacheCommand
from .transaction import RollbackCommand, TransactionsCommand
from .help import HelpCommand, ExitCommand

__all__ = [
    # Base classes
    "Command",
    "CommandContext",
    "CommandRegistry",
    # Commands
    "ClearCommand",
    "ResetContextCommand",
    "PermissionModeCommand",
    "UIModeCommand",
    "PlanCommand",
    "ModelCommand",
    "ProfileCommand",
    "MemoryCommand",
    "FocusCommand",
    "ThinkingCommand",
    "SummaryCommand",
    "SaveSessionCommand",
    "LoadSessionCommand",
    "ListSessionsCommand",
    "SessionRecoveryCommand",
    "ProjectCommand",
    "StatsCommand",
    "RoutingCommand",
    "StorageCommand",
    "CleanupCommand",
    "CacheCommand",
    "RollbackCommand",
    "TransactionsCommand",
    "HelpCommand",
    "ExitCommand",
]
