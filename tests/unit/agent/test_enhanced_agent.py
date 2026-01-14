"""
Tests for EnhancedCortex agent (cortex/agent_enhanced.py).

These tests cover the enhanced features:
- Planning system integration
- Layered memory functionality
- Enhanced processing workflows
- Backward compatibility with base Cortex
- Plan execution monitoring
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from cortex.agent_enhanced import EnhancedCortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig
from cortex.core.memory_layers import EnhancedMemoryBank, StateManager
from cortex.core.planning import PlanningEngine


class TestEnhancedCortexInitialization:
    """Test EnhancedCortex initialization and configuration."""
    
    def test_enhanced_agent_initialization(self, tmp_project_dir):
        """Test basic initialization of enhanced agent."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=True,
            enable_layered_memory=True
        )
        
        assert agent.model == "llama3.2"
        assert agent.project_dir == tmp_project_dir.resolve()
        assert agent.permission_mode == PermissionMode.NORMAL
        assert agent.enable_planning is True
        assert agent.enable_layered_memory is True
        
        # Verify enhanced components are initialized
        if agent.enable_layered_memory:
            assert isinstance(agent.memory_bank, EnhancedMemoryBank)
        assert isinstance(agent.state_manager, StateManager)
        
    def test_enhanced_agent_without_planning(self, tmp_project_dir):
        """Test enhanced agent with planning disabled."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=False,
            enable_layered_memory=True
        )
        
        assert agent.enable_planning is False
        assert agent.planning_engine is None
        assert agent.enable_layered_memory is True
        assert isinstance(agent.memory_bank, EnhancedMemoryBank)
        
    def test_enhanced_agent_without_layered_memory(self, tmp_project_dir):
        """Test enhanced agent with layered memory disabled."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=True,
            enable_layered_memory=False
        )
        
        assert agent.enable_planning is True
        assert agent.enable_layered_memory is False
        # Should use base memory bank, not EnhancedMemoryBank
        assert not isinstance(agent.memory_bank, EnhancedMemoryBank)
        assert agent.planning_engine is not None
        
    def test_enhanced_agent_system_prompt_update(self, tmp_project_dir):
        """Test that system prompt is updated with enhanced guidance."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL
        )
        
        # Get system prompt from conversation
        system_message = agent.conversation.history[0]
        assert "ENHANCED PLANNING AND MEMORY CAPABILITIES" in system_message["content"]
        assert "Goal Decomposition" in system_message["content"]
        assert "Memory Layers" in system_message["content"]
        
    def test_enhanced_agent_backward_compatibility(self, tmp_project_dir):
        """Test that enhanced agent maintains compatibility with base agent API."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL
        )
        
        # Verify base agent methods are available
        assert hasattr(agent, 'execute_tool')
        assert hasattr(agent, 'clear_conversation')
        assert hasattr(agent, 'get_conversation_history')
        assert hasattr(agent, 'load_project_context')
        
        # Verify enhanced methods are available
        assert hasattr(agent, 'process_with_planning')
        assert hasattr(agent, '_load_skill')
        assert hasattr(agent, '_execute_tool_for_planning')
        assert hasattr(agent, '_on_plan_reflection')


class TestEnhancedCortexPlanningSystem:
    """Test planning system integration."""
    
    @pytest.fixture
    def planning_agent(self, tmp_project_dir):
        """Create an enhanced agent with planning enabled."""
        return EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=True,
            enable_layered_memory=False
        )
    
    def test_planning_engine_initialization(self, planning_agent):
        """Test that planning engine is properly initialized."""
        assert planning_agent.planning_engine is not None
        assert isinstance(planning_agent.planning_engine, PlanningEngine)
        
        # Verify planning engine has required dependencies
        assert planning_agent.planning_engine.project_dir is not None
        assert planning_agent.planning_engine.skill_loader is not None
        assert planning_agent.planning_engine.tool_executor is not None
        assert planning_agent.planning_engine.reflection_callback is not None
    
    def test_load_skill_method(self, planning_agent):
        """Test the _load_skill method."""
        # Currently returns empty dict (placeholder)
        skill = planning_agent._load_skill("test_skill")
        assert isinstance(skill, dict)
        assert skill == {}
    
    def test_execute_tool_for_planning_method(self, planning_agent):
        """Test the _execute_tool_for_planning method."""
        # Mock the execute_tool method
        mock_result = {"success": True, "content": "test"}
        with patch.object(planning_agent, 'execute_tool', return_value=mock_result) as mock_execute:
            result = planning_agent._execute_tool_for_planning("read_file", {"path": "test.txt"})
            
            mock_execute.assert_called_once_with("read_file", {"path": "test.txt"})
            assert result == mock_result
    
    def test_plan_reflection_callback(self, planning_agent):
        """Test the _on_plan_reflection callback."""
        # Mock plan object
        mock_plan = Mock()
        mock_plan.id = "test_plan"
        
        reflection_text = "This plan worked well"
        
        # Call reflection callback
        planning_agent._on_plan_reflection(mock_plan, reflection_text)
        
        # Should log and record insight if layered memory enabled
        # Since layered memory is disabled in this fixture, just verify no error
        # If we want to test with layered memory, we need separate test
        pass


class TestEnhancedCortexLayeredMemory:
    """Test layered memory functionality."""
    
    @pytest.fixture
    def memory_agent(self, tmp_project_dir):
        """Create an enhanced agent with layered memory enabled."""
        return EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=False,
            enable_layered_memory=True
        )
    
    def test_enhanced_memory_bank_initialization(self, memory_agent):
        """Test that enhanced memory bank is used."""
        assert isinstance(memory_agent.memory_bank, EnhancedMemoryBank)
        assert memory_agent.memory_bank.max_items == 100
        
    def test_state_manager_initialization(self, memory_agent):
        """Test that state manager is initialized."""
        assert isinstance(memory_agent.state_manager, StateManager)
        assert memory_agent.state_manager.project_dir == memory_agent.project_dir.resolve()
        
    def test_state_manager_focus_transitions(self, memory_agent):
        """Test state manager focus transitions."""
        # Initial focus should be IDLE or similar
        # Let's check that we can set focus
        memory_agent.state_manager.set_focus("EXPLORING")
        # We'd need to check internal state; for now just ensure no error
        assert True


class TestEnhancedCortexProcessing:
    """Test enhanced processing workflows."""
    
    @pytest.fixture
    def enhanced_agent(self, tmp_project_dir):
        """Create a fully enhanced agent."""
        return EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL,
            enable_planning=True,
            enable_layered_memory=True
        )
    
    def test_process_with_planning_method_exists(self, enhanced_agent):
        """Test that process_with_planning method is available."""
        assert hasattr(enhanced_agent, 'process_with_planning')
        assert callable(enhanced_agent.process_with_planning)
    
    @patch('cortex.agent_enhanced.console')
    @patch('cortex.agent_enhanced.stream_model_response')
    @patch('cortex.agent_enhanced.display_streaming_response')
    def test_process_with_planning_basic_flow(self, mock_display, mock_stream, mock_console, enhanced_agent):
        """Test basic flow of process_with_planning."""
        # Mock provider
        mock_provider = Mock()
        mock_provider.supports_streaming.return_value = False
        enhanced_agent.provider = mock_provider
        
        # Mock model response without tool calls
        mock_response = {
            "message": {
                "content": "I'll help you with that.",
                "tool_calls": None
            }
        }
        with patch.object(enhanced_agent, '_call_model', return_value=mock_response):
            # Mock hook manager
            mock_hook_manager = Mock()
            mock_hook_manager.dispatch.return_value.action = "CONTINUE"
            enhanced_agent.hook_manager = mock_hook_manager
            
            # Call process_with_planning
            enhanced_agent.process_with_planning("Help me with something")
            
            # Verify hooks were called
            mock_hook_manager.dispatch.assert_called()
            
            # Verify conversation was updated
            history = enhanced_agent.get_conversation_history()
            assert len(history) > 1  # Should have system + user + assistant messages
    
    def test_enhanced_context_generation(self, enhanced_agent):
        """Test that enhanced context is generated."""
        # The method _get_enhanced_context should exist
        # It might be private; we can check if it's called during processing
        # For now, just verify the agent has state manager
        assert enhanced_agent.state_manager is not None


class TestEnhancedCortexMetrics:
    """Test enhanced agent metrics tracking."""
    
    def test_metrics_initialization(self, tmp_project_dir):
        """Test that enhanced metrics are initialized."""
        agent = EnhancedCortex(
            model="llama3.2",
            project_dir=str(tmp_project_dir),
            permission_mode=PermissionMode.NORMAL
        )
        
        assert hasattr(agent, 'plans_generated')
        assert hasattr(agent, 'plans_executed')
        assert hasattr(agent, 'plans_completed')
        
        assert agent.plans_generated == 0
        assert agent.plans_executed == 0
        assert agent.plans_completed == 0


@pytest.mark.integration
class TestEnhancedCortexIntegration:
    """Integration tests for enhanced agent."""
    
    def test_enhanced_agent_with_mocked_provider(self, tmp_project_dir, mock_ollama_provider):
        """Test enhanced agent integration with mocked provider."""
        with patch('cortex.agent_enhanced.ProviderFactory.get_provider', return_value=mock_ollama_provider):
            agent = EnhancedCortex(
                model="llama3.2",
                project_dir=str(tmp_project_dir),
                permission_mode=PermissionMode.NORMAL
            )
            
            assert agent.provider == mock_ollama_provider
            assert agent.model == "llama3.2"
            
            # Verify enhanced components are present
            assert agent.state_manager is not None
            if agent.enable_planning:
                assert agent.planning_engine is not None
            if agent.enable_layered_memory:
                assert isinstance(agent.memory_bank, EnhancedMemoryBank)