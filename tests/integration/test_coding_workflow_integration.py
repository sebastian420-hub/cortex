"""
Integration test for a comprehensive coding assistant workflow.
This test simulates a user request for code refactoring and verifies the agent's
ability to plan, execute tools, and provide a solution.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from cortex.agent import Cortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig
from tests.fixtures.mock_ollama import create_mock_response, create_tool_call


@pytest.fixture
def mock_llm_provider():
    """Mock model provider for LLM interactions."""
    provider = MagicMock()
    provider.supports_streaming.return_value = False
    provider.normalize_model_name.return_value = "mock-model"
    provider.validate_api_key.return_value = True
    return provider


@pytest.fixture
def mock_tools():
    """Mock built-in tools like read_file, write_file, edit."""
    tools = MagicMock()

    mock_read_file_instance = MagicMock()
    mock_read_file_instance.execute.return_value = {
        "success": True,
        "content": "def foo():\n    pass\n",
    }  # noqa: E501
    tools.read_file_tool_instance = mock_read_file_instance

    mock_edit_tool_instance = MagicMock()
    mock_edit_tool_instance.execute.return_value = {
        "success": True,
        "message": "File edited.",
        "diff": "mock diff",
    }  # noqa: E501
    tools.edit_tool_instance = mock_edit_tool_instance

    mock_glob_tool_instance = MagicMock()
    mock_glob_tool_instance.execute.return_value = {"success": True, "paths": []}
    tools.glob_tool_instance = mock_glob_tool_instance

    mock_grep_tool_instance = MagicMock()
    mock_grep_tool_instance.execute.return_value = {"success": True, "matches": []}
    tools.grep_tool_instance = mock_grep_tool_instance

    return tools


def test_refactor_workflow_integration(tmp_path, mock_llm_provider, mock_tools):
    """
    Simulates a full refactoring workflow:
    1. User requests refactoring.
    2. Agent plans to read the file.
    3. Agent 'reads' the file (mocked).
    4. Agent plans to edit the file.
    5. Agent 'edits' the file (mocked).
    6. Agent provides a summary.
    """
    # Setup dummy project file
    target_file = tmp_path / "bar.py"
    target_file.write_text("def foo():\n    pass\n")

    # Mock LLM responses for the conversation flow
    # First turn: Agent plans to read the file
    mock_llm_provider.chat.side_effect = [
        create_mock_response(
            tool_calls=[create_tool_call("read_file", {"path": str(target_file)})],
            content="Okay, I will start by reading `bar.py` to understand its content.",
        ),
        # Second turn: After reading, agent plans to edit the file
        create_mock_response(
            tool_calls=[
                create_tool_call(
                    "edit",
                    {
                        "file_path": str(target_file),
                        "old_string": "def foo():\n    pass\n",
                        "new_string": "def foo_refactored():\n    # Refactored content\n    pass\n",
                        "instruction": "Refactor function foo to foo_refactored and add a comment.",
                    },
                )
            ],
            content="I have analyzed the file and will now refactor the `foo` function.",
        ),
        # Third turn: After editing, agent provides a summary
        create_mock_response(
            content="The `foo` function in `bar.py` has been refactored to `foo_refactored`."
        ),
    ]

    with patch("cortex.agent.ProviderFactory.get_provider", return_value=mock_llm_provider):
        # Patch create_tool_instance directly
        with patch("cortex.agent.create_tool_instance") as mock_create_tool_instance:
            mock_create_tool_instance.side_effect = lambda tool_name, *args, **kwargs: {
                "read_file": mock_tools.read_file_tool_instance,
                "edit": mock_tools.edit_tool_instance,
                "glob": mock_tools.glob_tool_instance,
                "grep": mock_tools.grep_tool_instance,
                "write_file": mock_tools.write_file_tool_instance,
            }.get(tool_name) or MagicMock(
                execute=MagicMock(
                    return_value={"success": False, "error": f"Mocked tool {tool_name} not found"}
                )
            )  # noqa: E501

            agent = Cortex(
                model="mock-model",
                project_dir=str(tmp_path),
                permission_mode=PermissionMode.AUTO_APPROVE,
                config=AgentConfig(max_iterations=5),
            )

            user_message = "Refactor function foo in bar.py to improve readability."
            agent._process_message(user_message)

            # Assertions
            history = agent.get_conversation_history()
            assert (
                len(history) >= 5
            )  # System + User + Agent (read) + Tool (read) + Agent (edit) + Tool (edit) + Agent (summary)  # noqa: E501

            # Verify read_file.execute was called
            mock_tools.read_file_tool_instance.execute.assert_called_once_with(
                path=str(target_file)
            )  # noqa: E501

            # Verify edit.execute was called
            mock_tools.edit_tool_instance.execute.assert_called_once_with(
                file_path=str(target_file),
                old_string="def foo():\n    pass\n",
                new_string="def foo_refactored():\n    # Refactored content\n    pass\n",
                instruction="Refactor function foo to foo_refactored and add a comment.",
            )

            # Verify the final agent message
            final_agent_message = history[-1]["content"]
            assert (
                "The `foo` function in `bar.py` has been refactored to `foo_refactored`."
                in final_agent_message
            )  # noqa: E501
