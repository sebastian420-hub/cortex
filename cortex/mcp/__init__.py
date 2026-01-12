"""Model Context Protocol (MCP) integration for Cortex.

This module provides MCP client functionality to connect Cortex
to external tool servers via the Model Context Protocol.
"""

from .client import MCPClient, MCPServerConfig, MCPTool
from .protocol import MCPRequest, MCPResponse, MCPError
from .transport import StdioTransport

__all__ = [
    "MCPClient",
    "MCPServerConfig",
    "MCPTool",
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "StdioTransport",
]
