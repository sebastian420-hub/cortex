"""UI mode management for Cortex

Provides toggleable UI modes: minimal (Claude Code style), normal (current Cortex),
and debug (development details).
"""

from enum import Enum
from typing import Optional
from rich.console import Console

console = Console()


class UIMode(Enum):
    """UI display modes"""
    MINIMAL = "minimal"   # Like Claude Code - clean, minimal borders, focused
    NORMAL = "normal"     # Current Cortex - rich panels, detailed displays
    DEBUG = "debug"       # Development - all details, timing, internals


class UIManager:
    """Global UI manager singleton"""
    _instance: Optional['UIManager'] = None
    _mode: UIMode = UIMode.NORMAL  # Start with normal for backward compatibility
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_mode(cls) -> UIMode:
        return cls._mode
    
    @classmethod
    def set_mode(cls, mode: UIMode):
        cls._mode = mode
    
    @classmethod
    def toggle_mode(cls):
        """Cycle through UI modes: MINIMAL -> NORMAL -> DEBUG -> MINIMAL"""
        modes = list(UIMode)
        current_idx = modes.index(cls._mode)
        next_idx = (current_idx + 1) % len(modes)
        cls._mode = modes[next_idx]
        return cls._mode
    
    @classmethod
    def is_minimal(cls) -> bool:
        return cls._mode == UIMode.MINIMAL
    
    @classmethod
    def is_normal(cls) -> bool:
        return cls._mode == UIMode.NORMAL
    
    @classmethod
    def is_debug(cls) -> bool:
        return cls._mode == UIMode.DEBUG


# Global instance
ui_manager = UIManager()


def get_ui_mode() -> UIMode:
    """Get current UI mode"""
    return ui_manager.get_mode()


def set_ui_mode(mode: UIMode):
    """Set UI mode globally"""
    ui_manager.set_mode(mode)


def toggle_ui_mode():
    """Toggle to next UI mode"""
    new_mode = ui_manager.toggle_mode()
    console.print(f"[dim]UI mode: {new_mode.value}[/dim]")
    return new_mode


def should_show_panels() -> bool:
    """Check if panels should be shown (False in minimal mode)"""
    return not ui_manager.is_minimal()


def is_minimal_mode() -> bool:
    """Check if in minimal mode"""
    return ui_manager.is_minimal()


def is_debug_mode() -> bool:
    """Check if in debug mode"""
    return ui_manager.is_debug()


__all__ = [
    'UIMode',
    'UIManager',
    'ui_manager',
    'get_ui_mode',
    'set_ui_mode',
    'toggle_ui_mode',
    'should_show_panels',
    'is_minimal_mode',
    'is_debug_mode',
]