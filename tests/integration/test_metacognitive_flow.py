
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from cortex.agent import Cortex
from cortex.core.memory_layers.state import AgentFocus

class TestMetacognitiveFlow(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.max_tokens = 4000
        self.config.keep_recent_messages = 10
        self.config.rate_limit = {"enabled": False}
        self.config.error_recovery = {"enable_smart_recovery": False}
        self.config.file_cache = {"enabled": False}
        self.config.redis_cache = {"enabled": False}
        self.config.cache_warming = {"enabled": False}
        self.config.session_retention = {"warn_on_truncation": True}
        self.config.get_parallel_execution_config.return_value = {"enabled": False}
        self.config.get_timeout_config.return_value = {}
        self.config.get_routing_config.return_value = {"enabled": False}
        self.config.max_iterations = 5
        self.config.max_iterations_continue_default = False
        
    @patch("cortex.agent.ProviderFactory.get_provider")
    def test_metacognitive_prompt_injection(self, mock_get_provider):
        # Setup mock provider
        mock_provider = MagicMock()
        mock_provider.validate_api_key.return_value = True
        mock_provider.normalize_model_name.return_value = "test-model"
        mock_provider.chat.return_value = {
            "message": {"role": "assistant", "content": "I am thinking."},
            "usage": {"total_tokens": 10}
        }
        mock_get_provider.return_value = mock_provider
        
        # Initialize agent
        agent = Cortex(model="test-model", config=self.config)
        
        # 1. Initial state check
        self.assertEqual(agent.state_manager.state.metacognition.confidence_score, 0.8)
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "analytical")
        
        # 2. Check prompt injection
        system_prompt = agent._get_system_prompt()
        self.assertIn("# Internal Metacognition", system_prompt)
        self.assertIn("Tone: analytical", system_prompt)
        
        # 3. Simulate a failure via tool execution
        # We'll call execute_tool directly to see if it updates state
        # Mock create_tool_instance to return a failing tool
        with patch("cortex.agent.create_tool_instance") as mock_create_tool:
            failing_tool = MagicMock()
            failing_tool.execute.return_value = {"success": False, "error": "Simulated failure"}
            mock_create_tool.return_value = failing_tool
            
            agent.execute_tool("read_file", {"path": "nonexistent.txt"})
            
        # 4. Verify state update
        self.assertLess(agent.state_manager.state.metacognition.confidence_score, 0.8)
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "cautious")
        
        # 5. Check prompt injection after failure
        system_prompt_after = agent._get_system_prompt()
        self.assertIn("Tone: cautious", system_prompt_after)
        self.assertIn("Confidence:", system_prompt_after)

    @patch("cortex.agent.ProviderFactory.get_provider")
    def test_frustration_flow_integration(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.validate_api_key.return_value = True
        mock_get_provider.return_value = mock_provider
        
        agent = Cortex(model="test-model", config=self.config)
        
        # Manually spike failures to trigger frustration
        agent.state_manager.state.failed_tools = 3
        agent.state_manager.update_metacognition("test_tool", {"success": False})
        
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "frustrated")
        
        system_prompt = agent._get_system_prompt()
        self.assertIn("Tone: frustrated", system_prompt)
        self.assertIn("I're hitting repeated obstacles", system_prompt.replace("I'm", "I're")) # Handle potential contraction variations

if __name__ == "__main__":
    unittest.main()
