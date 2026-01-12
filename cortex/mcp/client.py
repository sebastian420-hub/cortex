"""MCP client implementation."""

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from .protocol import (
    MCPRequest,
    MCPResponse,
    MCPError,
    InitializeRequest,
    Tool,
    ListToolsResult,
    CallToolRequest,
)
from .transport import SimpleStdioTransport


class TransportType(Enum):
    """MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str  # Command to start server
    transport: TransportType = TransportType.STDIO
    env: Optional[Dict[str, str]] = None
    args: List[str] = field(default_factory=list)


@dataclass
class MCPTool:
    """A tool exposed by an MCP server."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str

    def to_tool_schema(self) -> Dict[str, Any]:
        """Convert to Cortex tool schema."""
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_name}_{self.name}",
                "description": f"[MCP:{self.server_name}] {self.description}",
                "parameters": self.input_schema,
            },
        }


class MCPClient:
    """
    Simple MCP client for connecting to MCP servers.

    This is a synchronous implementation for simplicity.
    """

    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.transports: Dict[str, SimpleStdioTransport] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.initialized: bool = False

    def add_server(self, server: MCPServerConfig) -> None:
        """Add an MCP server configuration."""
        self.servers[server.name] = server

    def start(self) -> None:
        """Start all configured MCP servers."""
        for server_name, server_config in self.servers.items():
            if server_config.transport == TransportType.STDIO:
                transport = SimpleStdioTransport(server_config.command)
                transport.start()
                self.transports[server_name] = transport

                # Initialize the connection
                self._initialize_server(server_name)

                # List tools
                self._list_tools(server_name)
            else:
                print(
                    f"Warning: Unsupported transport type {server_config.transport} for server {server_name}"
                )

        self.initialized = True

    def _initialize_server(self, server_name: str) -> None:
        """Initialize connection to an MCP server."""
        transport = self.transports[server_name]

        # Create initialize request
        init_request = InitializeRequest(
            protocolVersion="2024-11-05",
            capabilities={"tools": {}},  # We support tools
            clientInfo={"name": "Cortex", "version": "1.0.0"},
        )

        request = MCPRequest(id=1, method="initialize", params=init_request.to_params())

        # Send request
        response = transport.send_request(request)

        if response.error:
            raise RuntimeError(
                f"Failed to initialize MCP server {server_name}: {response.error.message}"
            )

        # Send initialized notification (no response expected)
        initialized_request = MCPRequest(id=None, method="initialized", params={})  # Notification

        # Use send_notification - doesn't wait for response
        try:
            transport.send_notification(initialized_request)
        except Exception:
            # Some servers might not handle notifications properly
            pass

    def _list_tools(self, server_name: str) -> List[MCPTool]:
        """List tools from an MCP server."""
        transport = self.transports[server_name]

        request = MCPRequest(id=2, method="tools/list", params={})

        response = transport.send_request(request)

        if response.error:
            print(
                f"Warning: Failed to list tools from MCP server {server_name}: {response.error.message}"
            )
            return []

        # Parse tools
        tools = []
        result = response.result or {}
        tools_data = result.get("tools", [])

        for tool_data in tools_data:
            tool = MCPTool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
                server_name=server_name,
            )

            # Store with unique key
            tool_key = f"{server_name}:{tool.name}"
            self.tools[tool_key] = tool
            tools.append(tool)

        print(f"Discovered {len(tools)} tools from MCP server {server_name}")
        return tools

    def call_tool(
        self, server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server."""
        transport = self.transports.get(server_name)
        if not transport:
            raise ValueError(f"No active connection to MCP server {server_name}")

        # Create tool call request
        call_request = CallToolRequest(name=tool_name, arguments=arguments or {})

        request = MCPRequest(
            id=int(time.time() * 1000),  # Simple unique ID
            method="tools/call",
            params=call_request.to_params(),
        )

        response = transport.send_request(request)

        if response.error:
            raise RuntimeError(f"MCP tool call failed: {response.error.message}")

        return response.result or {}

    def get_tools(self) -> List[MCPTool]:
        """Get all discovered MCP tools."""
        return list(self.tools.values())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all MCP tools as Cortex tool schemas."""
        return [tool.to_tool_schema() for tool in self.tools.values()]

    def stop(self) -> None:
        """Stop all MCP servers."""
        for server_name, transport in self.transports.items():
            try:
                transport.stop()
            except Exception as e:
                print(f"Error stopping MCP server {server_name}: {e}")

        self.transports.clear()
        self.tools.clear()
        self.initialized = False
