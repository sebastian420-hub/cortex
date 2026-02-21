"""Centralized theme system for Cortex UI

Provides consistent colors, icons, and styling across all UI components.
Eliminates hardcoded values and ensures visual consistency.

Usage:
    from cortex.ui.theme import UITheme, get_theme

    theme = get_theme()
    console.print(f"[{theme.colors.PRIMARY}]Hello[/]")
    console.print(f"{theme.icons.FILE} Reading file...")
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class ColorScheme(Enum):
    """Available color schemes"""

    DEFAULT = "default"
    HIGH_CONTRAST = "high_contrast"
    NO_COLOR = "no_color"


@dataclass(frozen=True)
class Colors:
    """Color palette - 5 core colors for consistency"""

    # Primary colors
    PRIMARY: str = "bright_cyan"
    SUCCESS: str = "bright_green"
    WARNING: str = "bright_yellow"
    ERROR: str = "bright_red"

    # Neutral colors
    MUTED: str = "dim"
    WHITE: str = "white"
    BLACK: str = "black"

    # Semantic aliases
    INFO: str = "bright_cyan"  # Same as PRIMARY
    DEBUG: str = "dim"

    # Border colors
    BORDER_PRIMARY: str = "cyan"
    BORDER_SUCCESS: str = "green"
    BORDER_WARNING: str = "yellow"
    BORDER_ERROR: str = "red"
    BORDER_MUTED: str = "dim"


@dataclass(frozen=True)
class Icons:
    """Text-based icons for Windows compatibility (no emojis)"""

    # File operations
    FILE: str = "[FILE]"
    FOLDER: str = "[DIR]"
    DIFF: str = "[DIFF]"
    EDIT: str = "[EDIT]"
    WRITE: str = "[WRITE]"
    READ: str = "[READ]"

    # Thinking/Processing
    THINK: str = "[THINK]"
    REASONING: str = "[REASON]"
    PROCESSING: str = "[...]"

    # Status
    OK: str = "[OK]"
    ERROR: str = "[X]"
    WARNING: str = "[!]"
    INFO: str = "[i]"

    # Search
    SEARCH: str = "[FIND]"
    MATCH: str = "[MATCH]"

    # Plan/Steps
    PLAN: str = "[PLAN]"
    STEP: str = "[STEP]"
    SUMMARY: str = "[SUM]"

    # Security
    LOCK: str = "[LOCK]"
    SHIELD: str = "[SECURE]"

    # Navigation
    ARROW_RIGHT: str = "->"
    ARROW_LEFT: str = "<-"
    BULLET: str = "•"
    ELLIPSIS: str = "..."


@dataclass(frozen=True)
class StatusIndicators:
    """Status indicator characters"""

    PENDING: str = "○"
    IN_PROGRESS: str = "◐"
    COMPLETED: str = "●"
    FAILED: str = "✗"
    SKIPPED: str = "⊘"

    # Alternative ASCII-only for strict compatibility
    PENDING_ASCII: str = "[ ]"
    IN_PROGRESS_ASCII: str = "[~]"
    COMPLETED_ASCII: str = "[x]"
    FAILED_ASCII: str = "[!]"
    SKIPPED_ASCII: str = "[-]"


@dataclass
class PanelStyle:
    """Panel styling configuration"""

    border_style: str = "cyan"
    title_align: str = "left"
    padding: tuple = (0, 1)
    highlight: bool = False


@dataclass
class UITheme:
    """Complete UI theme configuration"""

    colors: Colors = field(default_factory=Colors)
    icons: Icons = field(default_factory=Icons)
    status: StatusIndicators = field(default_factory=StatusIndicators)
    panel: PanelStyle = field(default_factory=PanelStyle)

    # Configuration
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    use_ascii_only: bool = False  # For strict Windows compatibility
    animations_enabled: bool = True

    def get_status_icon(self, status: str) -> str:
        """Get status icon, respecting ASCII-only setting"""
        if self.use_ascii_only:
            mapping = {
                "pending": self.status.PENDING_ASCII,
                "in_progress": self.status.IN_PROGRESS_ASCII,
                "completed": self.status.COMPLETED_ASCII,
                "failed": self.status.FAILED_ASCII,
                "skipped": self.status.SKIPPED_ASCII,
            }
        else:
            mapping = {
                "pending": self.status.PENDING,
                "in_progress": self.status.IN_PROGRESS,
                "completed": self.status.COMPLETED,
                "failed": self.status.FAILED,
                "skipped": self.status.SKIPPED,
            }
        return mapping.get(status, "?")


# Global theme instance
_theme_instance: Optional[UITheme] = None


def get_theme() -> UITheme:
    """Get the global theme instance"""
    global _theme_instance
    if _theme_instance is None:
        _theme_instance = UITheme()
    return _theme_instance


def set_theme(theme: UITheme) -> None:
    """Set the global theme instance"""
    global _theme_instance
    _theme_instance = theme


def configure_theme(
    color_scheme: Optional[str] = None,
    use_ascii_only: Optional[bool] = None,
    animations_enabled: Optional[bool] = None,
) -> UITheme:
    """Configure theme with settings"""
    theme = get_theme()

    if color_scheme:
        theme.color_scheme = ColorScheme(color_scheme)

    if use_ascii_only is not None:
        theme.use_ascii_only = use_ascii_only

    if animations_enabled is not None:
        theme.animations_enabled = animations_enabled

    return theme


# Convenience exports
__all__ = [
    "UITheme",
    "Colors",
    "Icons",
    "StatusIndicators",
    "PanelStyle",
    "ColorScheme",
    "get_theme",
    "set_theme",
    "configure_theme",
]
