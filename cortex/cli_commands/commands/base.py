"""Base classes for CLI command system"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """
    Context object passed to commands containing dependencies and state.

    This provides a clean way to inject dependencies into commands without
    coupling them to the CLI class internals.
    """

    agent: Any  # Cortex agent instance
    config: Any  # AgentConfig instance
    hook_manager: Any  # HookManager instance
    output_format: str  # Current output format

    # State flags
    verbose: bool = False

    def __post_init__(self):
        """Validate context after initialization"""
        if self.agent is None:
            raise ValueError("agent cannot be None")
        if self.config is None:
            raise ValueError("config cannot be None")


class Command(ABC):
    """
    Abstract base class for all CLI commands.

    Commands follow the Command Pattern:
    - Each command is a separate class with execute()
    - Commands receive CommandContext for dependencies
    - Commands are self-contained and testable

    Subclasses must implement:
    - name: Command name (e.g., "mode", "context", "undo")
    - description: Brief description for help text
    - execute(): Command logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (e.g., 'mode', 'context', 'undo')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description for help text"""
        pass

    @property
    def aliases(self) -> List[str]:
        """Optional command aliases (default: empty list)"""
        return []

    @property
    def requires_agent(self) -> bool:
        """Whether command requires an initialized agent (default: True)"""
        return True

    @abstractmethod
    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """
        Execute the command.

        Args:
            ctx: Command context with dependencies
            args: Optional command arguments (raw string)

        Raises:
            ValueError: For invalid arguments
            RuntimeError: For execution errors
        """
        pass

    def validate_args(self, args: Optional[str]) -> None:
        """
        Validate command arguments (optional override).

        Args:
            args: Command arguments to validate

        Raises:
            ValueError: If arguments are invalid
        """
        pass


class CommandRegistry:
    """
    Registry for CLI commands.

    Provides:
    - Command registration by name and aliases
    - Command lookup
    - List all commands
    - Help text generation

    Usage:
        registry = CommandRegistry()
        registry.register(ModeCommand())
        registry.register(ContextCommand())

        cmd = registry.get("mode")
        cmd.execute(ctx, "plan")
    """

    def __init__(self):
        """Initialize empty registry"""
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command_name mapping

    def register(self, command: Command) -> None:
        """
        Register a command.

        Args:
            command: Command instance to register

        Raises:
            ValueError: If command name or alias already registered
        """
        # Check for duplicate names
        if command.name in self._commands:
            raise ValueError(f"Command '{command.name}' already registered")

        # Check for duplicate aliases
        for alias in command.aliases:
            if alias in self._aliases:
                existing = self._aliases[alias]
                raise ValueError(f"Alias '{alias}' already registered for command '{existing}'")
            if alias in self._commands:
                raise ValueError(f"Alias '{alias}' conflicts with command name")

        # Register command
        self._commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")

        # Register aliases
        for alias in command.aliases:
            self._aliases[alias] = command.name
            logger.debug(f"Registered alias: {alias} -> {command.name}")

    def get(self, name: str) -> Optional[Command]:
        """
        Get command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command instance or None if not found
        """
        # Try direct lookup
        if name in self._commands:
            return self._commands[name]

        # Try alias lookup
        if name in self._aliases:
            command_name = self._aliases[name]
            return self._commands[command_name]

        return None

    def has(self, name: str) -> bool:
        """
        Check if command exists.

        Args:
            name: Command name or alias

        Returns:
            True if command exists, False otherwise
        """
        return name in self._commands or name in self._aliases

    def list_commands(self) -> List[Command]:
        """
        Get list of all registered commands.

        Returns:
            List of Command instances
        """
        return list(self._commands.values())

    def get_help_text(self) -> str:
        """
        Generate help text for all commands.

        Returns:
            Formatted help text string
        """
        lines = ["Available commands:"]

        for cmd in sorted(self._commands.values(), key=lambda c: c.name):
            # Command name and description
            line = f"  /{cmd.name:<15} - {cmd.description}"

            # Add aliases if present
            if cmd.aliases:
                aliases_str = ", ".join(f"/{a}" for a in cmd.aliases)
                line += f" (aliases: {aliases_str})"

            lines.append(line)

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all registered commands (useful for testing)"""
        self._commands.clear()
        self._aliases.clear()
        logger.debug("Cleared command registry")
