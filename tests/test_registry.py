"""Tests for Tool Registry"""

import pytest
from pathlib import Path

from cortex.tools.registry import ToolRegistry, get_registry, reset_registry
from cortex.tools.base import Tool


class MockTool(Tool):
    """Mock tool for testing"""

    def execute(self, **kwargs):
        return {"success": True, "data": "mock"}


class TestToolRegistry:
    """Test ToolRegistry functionality"""

    def setup_method(self):
        """Reset registry before each test"""
        reset_registry()

    def test_register_tool(self):
        """Test registering a new tool"""
        registry = ToolRegistry()
        schema = {
            "type": "function",
            "function": {"name": "mock_tool", "description": "A mock tool"}
        }

        registry.register("mock_tool", MockTool, schema)

        assert "mock_tool" in registry.list_tools(include_disabled=True)
        assert registry.get_tool_class("mock_tool") == MockTool
        assert registry.get_schema("mock_tool") == schema

    def test_unregister_tool(self):
        """Test unregistering a tool"""
        registry = ToolRegistry()
        schema = {"type": "function", "function": {"name": "mock_tool"}}

        registry.register("mock_tool", MockTool, schema)
        assert registry.unregister("mock_tool") is True
        assert "mock_tool" not in registry.list_tools(include_disabled=True)

    def test_enable_disable_tool(self):
        """Test enabling and disabling tools"""
        registry = ToolRegistry()
        schema = {"type": "function", "function": {"name": "mock_tool"}}

        registry.register("mock_tool", MockTool, schema, enabled=True)
        assert registry.is_enabled("mock_tool") is True

        registry.disable("mock_tool")
        assert registry.is_enabled("mock_tool") is False
        assert registry.get_tool_class("mock_tool") is None  # Disabled tools return None

        registry.enable("mock_tool")
        assert registry.is_enabled("mock_tool") is True
        assert registry.get_tool_class("mock_tool") == MockTool

    def test_get_all_schemas(self):
        """Test getting all enabled tool schemas"""
        registry = ToolRegistry()
        schema1 = {"type": "function", "function": {"name": "tool1"}}
        schema2 = {"type": "function", "function": {"name": "tool2"}}

        registry.register("tool1", MockTool, schema1, enabled=True)
        registry.register("tool2", MockTool, schema2, enabled=False)

        schemas = registry.get_all_schemas()
        assert len(schemas) == 1
        assert schemas[0] == schema1

    def test_namespace_support(self):
        """Test tool namespaces"""
        registry = ToolRegistry()
        schema = {"type": "function", "function": {"name": "custom_tool"}}

        registry.register("custom_tool", MockTool, schema, namespace="plugin")

        assert "plugin:custom_tool" in registry.list_tools(include_disabled=True)
        assert registry.get_tool_class("plugin:custom_tool") == MockTool

    def test_create_instance(self):
        """Test creating tool instances"""
        registry = ToolRegistry()
        schema = {"type": "function", "function": {"name": "mock_tool"}}

        registry.register("mock_tool", MockTool, schema)

        tool = registry.create_instance(
            "mock_tool",
            project_dir=Path("."),
            permission_mode="normal",
            console=None
        )

        assert isinstance(tool, MockTool)
        result = tool.execute()
        assert result["success"] is True

    def test_create_instance_disabled_tool(self):
        """Test that creating instance of disabled tool raises error"""
        registry = ToolRegistry()
        schema = {"type": "function", "function": {"name": "mock_tool"}}

        registry.register("mock_tool", MockTool, schema, enabled=False)

        with pytest.raises(ValueError, match="Unknown or disabled tool"):
            registry.create_instance(
                "mock_tool",
                project_dir=Path("."),
                permission_mode="normal",
                console=None
            )

    def test_register_builtins(self):
        """Test registering built-in tools"""
        registry = ToolRegistry()
        registry.register_builtins()

        # Check some built-in tools are registered
        assert "read_file" in registry.list_tools()
        assert "write_file" in registry.list_tools()
        assert "execute_command" in registry.list_tools()
        assert "list_files" in registry.list_tools()

    def test_global_registry(self):
        """Test global registry singleton"""
        reset_registry()
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
        assert "read_file" in registry1.list_tools()  # Builtins registered

    def test_apply_config(self):
        """Test applying configuration to registry"""
        registry = ToolRegistry()
        registry.register_builtins()

        config = {
            "tools": {
                "disabled": ["execute_command", "git_commit"],
            }
        }

        registry.apply_config(config)

        assert registry.is_enabled("execute_command") is False
        assert registry.is_enabled("git_commit") is False
        assert registry.is_enabled("read_file") is True

    def test_from_config(self):
        """Test creating registry from config"""
        config = {
            "tools": {
                "disabled": ["write_file"],
            }
        }

        registry = ToolRegistry.from_config(config)

        assert registry.is_enabled("write_file") is False
        assert registry.is_enabled("read_file") is True
