"""MCP tool integration for Cortex."""

from typing import Dict, Any, Optional
from pathlib import Path

from ..tools.base import Tool
from ..core.security import validate_path, SecurityError
from ..utils.errors import create_error_response, create_success_response, ErrorType

from .client import MCPClient, MCPServerConfig, TransportType


class MCPToolWrapper(Tool):
    """
    Tool wrapper for calling MCP tools.

    This is a dynamic tool that can call any MCP tool.
    It's created per MCP tool discovered.
    """

    timeout_category = "search"
    default_timeout = 30

    def __init__(
        self,
        mcp_client: MCPClient,
        server_name: str,
        tool_name: str,
        tool_description: str,
        input_schema: Dict[str, Any],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.mcp_client = mcp_client
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.input_schema = input_schema

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the MCP tool with given arguments."""
        if self.console:
            self.console.print(
                f"[cyan]Calling MCP tool:[/cyan] {self.server_name}.{self.tool_name}"
            )

        try:
            # Call the MCP tool
            result = self.mcp_client.call_tool(
                server_name=self.server_name, tool_name=self.tool_name, arguments=kwargs
            )

            # Format the result
            content = result.get("content", [{}])[0] if result.get("content") else result

            # Extract text from content if it's a complex object
            if isinstance(content, dict):
                text = content.get("text", str(content))
            else:
                text = str(content)

            return create_success_response(
                {"result": result, "text": text[:5000]}  # Limit output size
            )

        except Exception as e:
            return create_error_response(
                f"Failed to execute MCP tool {self.server_name}.{self.tool_name}: {e}",
                ErrorType.EXECUTION,
                {"server": self.server_name, "tool": self.tool_name, "error": str(e)},
            )


class MCPManager:
    """
    Manager for MCP integration.

    Handles MCP client lifecycle and tool registration.
    """

    def __init__(self, project_dir: Path, console=None):
        self.project_dir = project_dir
        self.console = console
        self.mcp_client: Optional[MCPClient] = None
        self.mcp_tools: Dict[str, MCPToolWrapper] = {}

    def start(self, server_configs: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """Start MCP client and connect to servers."""
        if self.mcp_client is not None:
            return  # Already started

        self.mcp_client = MCPClient()

        # Add configured servers
        if server_configs:
            for server_name, config in server_configs.items():
                server = MCPServerConfig(
                    name=server_name,
                    command=config.get("command", ""),
                    transport=TransportType.STDIO,
                    env=config.get("env"),
                    args=config.get("args", []),
                )
                self.mcp_client.add_server(server)

        # Start the client
        try:
            self.mcp_client.start()

            if self.console:
                self.console.print(f"[green]MCP client started[/green]")
                tool_count = len(self.mcp_client.get_tools())
                self.console.print(f"[dim]Discovered {tool_count} MCP tools[/dim]")

        except Exception as e:
            if self.console:
                self.console.print(f"[red]Failed to start MCP client: {e}[/red]")
            self.mcp_client = None
            raise

    def create_tool_wrappers(self) -> Dict[str, MCPToolWrapper]:
        """Create tool wrappers for all discovered MCP tools."""
        if self.mcp_client is None:
            return {}

        wrappers = {}
        for tool in self.mcp_client.get_tools():
            # Create unique tool name
            tool_wrapper_name = f"mcp_{tool.server_name}_{tool.name}"

            # Create wrapper tool
            wrapper = MCPToolWrapper(
                mcp_client=self.mcp_client,
                server_name=tool.server_name,
                tool_name=tool.name,
                tool_description=tool.description,
                input_schema=tool.input_schema,
                project_dir=self.project_dir,
                permission_mode="normal",  # Will be overridden by agent
                console=self.console,
            )

            wrappers[tool_wrapper_name] = wrapper

        return wrappers

    def stop(self) -> None:
        """Stop MCP client and cleanup."""
        if self.mcp_client:
            self.mcp_client.stop()
            self.mcp_client = None
            self.mcp_tools.clear()
