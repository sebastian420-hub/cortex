"""
Shared pytest fixtures and configuration for Cortex tests.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Generator
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.models import PermissionMode
from cortex.core.providers import ProviderFactory


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with basic structure."""
    # Create some example files
    (tmp_path / "README.md").write_text("# Test Project\n\nExample project for testing.")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text('print("Hello, World!")')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text('def test_main(): pass')
    
    return tmp_path


@pytest.fixture
def agent_config() -> AgentConfig:
    """Create a default agent configuration for testing."""
    return AgentConfig(
        model="llama3.2",
        provider="ollama",
        permission_mode=PermissionMode.NORMAL,
        auto_approve=False,
        max_iterations=10,
        project_context="Test project context"
    )


@pytest.fixture
def basic_agent(tmp_project_dir: Path, agent_config: AgentConfig) -> Cortex:
    """Create a basic Cortex agent with test configuration."""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_project_dir),
        permission_mode=PermissionMode.NORMAL,
        config=agent_config
    )
    return agent


@pytest.fixture
def auto_approve_agent(tmp_project_dir: Path) -> Cortex:
    """Create an agent with auto-approve permission mode."""
    config = AgentConfig(
        model="llama3.2",
        permission_mode=PermissionMode.AUTO_APPROVE,
        auto_approve=True
    )
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_project_dir),
        permission_mode=PermissionMode.AUTO_APPROVE,
        config=config
    )
    return agent


@pytest.fixture
def plan_mode_agent(tmp_project_dir: Path) -> Cortex:
    """Create an agent with plan permission mode."""
    config = AgentConfig(
        model="llama3.2",
        permission_mode=PermissionMode.PLAN,
        auto_approve=False
    )
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_project_dir),
        permission_mode=PermissionMode.PLAN,
        config=config
    )
    return agent


@pytest.fixture
def mock_ollama_provider():
    """Mock Ollama provider for testing."""
    provider = Mock()
    provider.name = "ollama"
    provider.supports_streaming = True
    provider.validate_api_key.return_value = True
    provider.normalize_model_name.return_value = "llama3.2"
    
    # Default chat response
    provider.chat.return_value = {
        "message": {"role": "assistant", "content": "Test response from Ollama"}
    }
    
    # Default streaming response
    provider.stream_chat.return_value = iter([
        {"message": {"content": "Streamed"}},
        {"message": {"content": " response"}}
    ])
    
    return provider


@pytest.fixture
def mock_deepseek_provider():
    """Mock DeepSeek provider for testing."""
    provider = Mock()
    provider.name = "deepseek"
    provider.supports_streaming = True
    provider.validate_api_key.return_value = True
    provider.normalize_model_name.return_value = "deepseek-chat"
    
    provider.chat.return_value = {
        "message": {"role": "assistant", "content": "Test response from DeepSeek"}
    }
    
    provider.stream_chat.return_value = iter([
        {"message": {"content": "Streamed"}},
        {"message": {"content": " response"}}
    ])
    
    return provider


@pytest.fixture
def mock_anthropic_provider():
    """Mock Anthropic provider for testing."""
    provider = Mock()
    provider.name = "anthropic"
    provider.supports_streaming = True
    provider.validate_api_key.return_value = True
    provider.normalize_model_name.return_value = "claude-3-haiku-20240307"
    
    provider.chat.return_value = {
        "message": {"role": "assistant", "content": "Test response from Claude"}
    }
    
    provider.stream_chat.return_value = iter([
        {"message": {"content": "Streamed"}},
        {"message": {"content": " response"}}
    ])
    
    return provider


@pytest.fixture
def mock_provider_factory(
    mock_ollama_provider, 
    mock_deepseek_provider, 
    mock_anthropic_provider
):
    """Mock the ProviderFactory to return mocked providers."""
    def get_provider(provider_name: str, **kwargs):
        if provider_name == "ollama":
            return mock_ollama_provider
        elif provider_name == "deepseek":
            return mock_deepseek_provider
        elif provider_name == "anthropic":
            return mock_anthropic_provider
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    with patch.object(ProviderFactory, 'get_provider', side_effect=get_provider) as mock_factory:
        yield mock_factory


@pytest.fixture
def sample_conversation_history() -> list:
    """Return sample conversation history for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, can you help me?"},
        {"role": "assistant", "content": "Sure, what do you need help with?"},
        {"role": "user", "content": "I need to write a function."}
    ]


@pytest.fixture
def sample_tool_call() -> dict:
    """Return a sample tool call for testing."""
    return {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "read_file",
            "arguments": json.dumps({"path": "README.md"})
        }
    }


@pytest.fixture
def sample_tool_response() -> dict:
    """Return a sample tool response for testing."""
    return {
        "tool_call_id": "call_123",
        "role": "tool",
        "name": "read_file",
        "content": json.dumps({
            "success": True,
            "content": "# Test Project\n\nExample content.",
            "total_lines": 3
        })
    }


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    server = Mock()
    server.tools = []
    server.connect.return_value = None
    server.disconnect.return_value = None
    server.get_tools.return_value = []
    return server


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary configuration file."""
    config = {
        "model": "llama3.2",
        "provider": "ollama",
        "permission_mode": "normal",
        "auto_approve": False,
        "max_iterations": 10
    }
    
    config_file = tmp_path / "config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    return config_file


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "web: marks tests that require network/web access"
    )
    config.addinivalue_line(
        "markers", "cloud: marks tests that require cloud provider access"
    )
    config.addinivalue_line(
        "markers", "mcp: marks tests that require MCP server access"
    )
    config.addinivalue_line(
        "markers", "enhanced: marks tests for enhanced agent features"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "functional: marks tests as functional tests"
    )


# Auto-use fixtures for certain test categories
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Automatically setup test environment for all tests."""
    # Ensure we don't accidentally call real APIs
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    
    # Disable any external network calls
    monkeypatch.setattr("requests.get", Mock(side_effect=RuntimeError("Network calls disabled in tests")))
    monkeypatch.setattr("requests.post", Mock(side_effect=RuntimeError("Network calls disabled in tests")))