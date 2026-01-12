"""MCP protocol message types (JSON-RPC 2.0)."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class MCPErrorCode(int, Enum):
    """MCP error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000


@dataclass
class MCPError:
    """MCP error object."""

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC error object."""
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class MCPRequest:
    """MCP request message (JSON-RPC 2.0)."""

    id: Union[int, str, None]
    method: str
    params: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC request dict."""
        result = {"jsonrpc": self.jsonrpc, "method": self.method, "id": self.id}
        if self.params is not None:
            result["params"] = self.params
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "MCPRequest":
        """Parse from JSON string."""
        data = json.loads(json_str)
        return cls(
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class MCPResponse:
    """MCP response message (JSON-RPC 2.0)."""

    id: Union[int, str, None]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC response dict."""
        result = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            result["error"] = self.error.to_dict()
        else:
            result["result"] = self.result or {}
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "MCPResponse":
        """Parse from JSON string."""
        data = json.loads(json_str)

        # Parse error if present
        error = None
        if "error" in data:
            error_data = data["error"]
            error = MCPError(
                code=error_data.get("code", MCPErrorCode.INTERNAL_ERROR.value),
                message=error_data.get("message", "Unknown error"),
                data=error_data.get("data"),
            )

        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=error,
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


# Specific MCP request/response types


@dataclass
class InitializeRequest:
    """Initialize request parameters."""

    protocolVersion: str = "2024-11-05"
    capabilities: Dict[str, Any] = field(default_factory=dict)
    clientInfo: Optional[Dict[str, str]] = None

    def to_params(self) -> Dict[str, Any]:
        """Convert to params dict for MCPRequest."""
        params = {"protocolVersion": self.protocolVersion, "capabilities": self.capabilities}
        if self.clientInfo is not None:
            params["clientInfo"] = self.clientInfo
        return params


@dataclass
class Tool:
    """MCP tool definition."""

    name: str
    description: str
    inputSchema: Dict[str, Any]


@dataclass
class ListToolsResult:
    """Result of tools/list request."""

    tools: List[Tool]


@dataclass
class CallToolRequest:
    """Call tool request parameters."""

    name: str
    arguments: Optional[Dict[str, Any]] = None

    def to_params(self) -> Dict[str, Any]:
        """Convert to params dict for MCPRequest."""
        params = {"name": self.name}
        if self.arguments is not None:
            params["arguments"] = self.arguments
        return params
