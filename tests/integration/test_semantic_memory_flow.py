"""
Integration tests for the full semantic memory workflow.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.core.memory_layers import EnhancedMemoryBank
from cortex.models import PermissionMode


class TestSemanticMemoryIntegration:
    """Tests the integration of semantic memory into the Agent and MemoryBank."""

    @pytest.fixture
    def semantic_config(self, tmp_path):
        """Config for semantic memory."""
        return {
            "enabled": True,
            "provider": "chroma",
            "persist_directory": str(tmp_path / "semantic_db"),
            "collection_name": "test_collection",
            "clear_on_init": True
        }

    def test_enhanced_memory_bank_indexing(self, semantic_config):
        """Verify that adding a memory item indexes it semantically."""
        bank = EnhancedMemoryBank(max_items=10, semantic_config=semantic_config)
        
        # Add a unique memory using helper method
        bank.add_fact("The secret key is 'CORTEX-123'", source="user")
        
        # Give Chroma a moment to index
        import time
        time.sleep(0.5)
        
        # Search for it semantically
        results = bank.retrieve_semantic_context("The secret key is")
        assert len(results) > 0
        assert "CORTEX-123" in results[0]["document"]

    def test_agent_system_prompt_injection(self, tmp_path, semantic_config):
        """Verify that the agent injects semantic context into the prompt."""
        config = AgentConfig(
            model="llama3.2",
            enable_layered_memory=True,
            semantic_memory=semantic_config
        )
        
        # Setup agent with mocked provider to avoid actual LLM calls
        with patch('cortex.core.providers.factory.ProviderFactory.get_provider'):
            agent = Cortex(config=config, project_dir=tmp_path)
            
            # 1. Add a specific fact to memory
            agent.memory_bank.add_fact("The project lead is Sebastian.", source="user")
            
            import time
            time.sleep(0.5)
            
            # 2. Add a user message to provide context for the next prompt generation
            agent.conversation.add_user_message("Who is the project lead?")
            
            # 3. Generate system prompt
            prompt = agent._get_system_prompt()
            
            # 4. Verify semantic section exists and contains the fact
            assert "Relevant Historical Context" in prompt
            assert "Sebastian" in prompt

    def test_semantic_memory_disabled_by_default(self, tmp_path):
        """Verify that semantic memory is not active if not configured."""
        config = AgentConfig(model="llama3.2", enable_layered_memory=True)
        
        with patch('cortex.core.providers.factory.ProviderFactory.get_provider'):
            agent = Cortex(config=config, project_dir=tmp_path)
            assert agent.memory_bank.semantic_manager is None
            
            # retrieval should return empty list
            assert agent.memory_bank.retrieve_semantic_context("test") == []

    @patch("cortex.cli_commands.commands.memory.console")
    def test_memory_search_command(self, mock_console, tmp_path, semantic_config):
        """Verify the /memory search CLI command."""
        from cortex.cli_commands.commands.memory import MemoryCommand
        from cortex.cli_commands.commands.base import CommandContext
        
        config = AgentConfig(model="llama3.2", enable_layered_memory=True, semantic_memory=semantic_config)
        
        with patch('cortex.core.providers.factory.ProviderFactory.get_provider'):
            agent = Cortex(config=config, project_dir=tmp_path)
            agent.memory_bank.add_fact("The server port is 8080", source="user")
            
            import time
            time.sleep(0.5)
            
            cmd = MemoryCommand()
            ctx = CommandContext(agent=agent, config=config, hook_manager=agent.hook_manager, output_format="text")
            
            # Execute search
            cmd.execute(ctx, args="search port")
            
            # Verify console output (should contain a table with results)
            assert mock_console.print.called
            
            # Check all print calls for the expected content
            all_text = ""
            for call in mock_console.print.call_args_list:
                args, _ = call
                if args:
                    # If it's a Table, convert it to a string or inspect its structure
                    # A safer way is to check if any string in the output contains our data
                    all_text += str(args[0])
            
            # Since Rich Table str() might not show data, let's also check if the 
            # table object itself contains the data in its rows if we can find it
            found_in_table = False
            for call in mock_console.print.call_args_list:
                args, _ = call
                if args and hasattr(args[0], "columns"):
                    table = args[0]
                    # Check if "8080" is in any of the columns' data
                    # This is internal Rich API but works for testing
                    for column in table.columns:
                        if any("8080" in str(item) for item in column._cells):
                            found_in_table = True
                            break
            
            assert found_in_table or "8080" in all_text
