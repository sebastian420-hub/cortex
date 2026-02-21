import pytest
from unittest.mock import MagicMock, patch
from cortex.agent import Cortex
from cortex.cli import handle_command
from cortex.core.providers import ProviderError
from cortex.ui.console import console
from cortex.models import PermissionMode # Import PermissionMode

@pytest.fixture
def mock_agent():
    """Fixture to provide a mock Cortex agent instance."""
    agent = MagicMock(spec=Cortex)
    agent.model = "llama3.2" # Default model for the mock agent
    agent.permission_mode = PermissionMode.NORMAL # Mock permission_mode

    # Mock nested attributes explicitly
    agent.config = MagicMock()
    agent.config.provider = None # Default provider for the mock config

    agent.conversation = MagicMock()
    agent.conversation.history = [{"role": "system", "content": "You are Cortex."}] # A simple history  # noqa: E501
    agent.conversation.update_model = MagicMock() # Mock the method

    agent._get_system_prompt.return_value = "You are Cortex updated system prompt." # Mock system prompt update  # noqa: E501

    # Ensure switch_model is a mock method that can be configured
    agent.switch_model = MagicMock()

    # Add attributes needed for CommandContext
    agent.hook_manager = MagicMock()
    agent.output_format = MagicMock()
    agent.output_format.value = "text"

    return agent

@pytest.fixture
def mock_repl():
    """Fixture to provide a mock REPL instance."""
    return MagicMock()

def test_handle_model_switch_success(mock_agent, mock_repl):
    """Test successful model switch using /model command."""
    new_model_name = "deepseek-coder"
    # Configure the mock switch_model to simulate success
    mock_agent.switch_model.side_effect = lambda new_m, provider_o: setattr(mock_agent, 'model', new_m)  # noqa: E501

    with patch.object(console, 'print') as mock_console_print:
        handle_command(f"/model {new_model_name}", mock_agent, MagicMock(), mock_repl)

        mock_agent.switch_model.assert_called_once_with(new_model_name, mock_agent.config.provider)
        mock_console_print.assert_any_call(f"[green]✓[/green] Model switched to: {new_model_name}")

        # Verify system prompt was updated
        mock_agent._get_system_prompt.assert_called_once()
        assert mock_agent.conversation.history[0]["content"] == mock_agent._get_system_prompt.return_value  # noqa: E501
        assert mock_agent.model == new_model_name # Check if agent's model attribute was updated


def test_handle_model_switch_no_model_name(mock_agent, mock_repl):
    """Test /model command without providing a model name."""
    # Ensure the mock_agent.model is accessed correctly before the patch
    initial_model = mock_agent.model
    with patch.object(console, 'print') as mock_console_print:
        handle_command("/model", mock_agent, MagicMock(), mock_repl)

        mock_agent.switch_model.assert_not_called()
        mock_console_print.assert_any_call(f"Current model: {initial_model}")
        mock_console_print.assert_any_call("[dim]Usage: /model <model_name>[/dim]")
        # System prompt should not be updated
        mock_agent._get_system_prompt.assert_not_called()


def test_handle_model_switch_provider_error(mock_agent, mock_repl):
    """Test model switch failure due to ProviderError."""
    new_model_name = "nonexistent-model"
    mock_agent.switch_model.side_effect = ProviderError("API key not set for provider.")

    with patch.object(console, 'print') as mock_console_print:
        handle_command(f"/model {new_model_name}", mock_agent, MagicMock(), mock_repl)

        mock_agent.switch_model.assert_called_once_with(new_model_name, mock_agent.config.provider)
        mock_console_print.assert_any_call(f"[red]Error switching model:[/red] API key not set for provider.")  # noqa: E501
        # System prompt should not be updated on error
        mock_agent._get_system_prompt.assert_not_called()
        # Agent's model should not change on error
        assert mock_agent.model == "llama3.2"


def test_handle_model_switch_unexpected_error(mock_agent, mock_repl):
    """Test model switch failure due to unexpected Exception."""
    new_model_name = "deepseek-coder"
    mock_agent.switch_model.side_effect = ValueError("Some unexpected issue.")

    with patch.object(console, 'print') as mock_console_print:
        handle_command(f"/model {new_model_name}", mock_agent, MagicMock(), mock_repl)

        mock_agent.switch_model.assert_called_once_with(new_model_name, mock_agent.config.provider)
        mock_console_print.assert_any_call(f"[red]An unexpected error occurred:[/red] Some unexpected issue.")  # noqa: E501
        # System prompt should not be updated on error
        mock_agent._get_system_prompt.assert_not_called()
        # Agent's model should not change on error
        assert mock_agent.model == "llama3.2"
