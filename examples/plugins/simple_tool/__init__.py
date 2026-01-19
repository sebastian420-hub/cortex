"""
Simple Plugin Example for Cortex

This is a minimal example demonstrating how to create a Cortex plugin.
It includes two simple tools: a UUID generator and a text statistics tool.

Usage:
    from cortex.tools.registry import get_registry
    registry = get_registry()
    registry.load_plugin("examples.plugins.simple_tool")
"""

from .tools import PLUGIN_TOOLS, UUIDTool, TextStatsTool

__all__ = ["PLUGIN_TOOLS", "UUIDTool", "TextStatsTool"]
