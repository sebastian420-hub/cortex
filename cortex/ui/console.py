"""Console utilities for Cortex"""

from rich.console import Console

# Global console instance with color support forced
console = Console(force_terminal=True, color_system="auto")

__all__ = ["console"]
