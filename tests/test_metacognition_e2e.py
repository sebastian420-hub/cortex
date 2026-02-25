import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

from cortex.agent import Cortex
from cortex.config import AgentConfig
from cortex.core.memory_layers.state import AgentFocus
from cortex.core.providers import ProviderFactory

class TestMetacognitionE2E(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path("test_project_metacognition")
        self.project_dir.mkdir(exist_ok=True)
        (self.project_dir / "README.md").write_text("# Test Project")
        
        self.config = AgentConfig(
            model="test-model",
            provider="mock",
            max_iterations=5
        )
        
        # Mock provider
        self.mock_provider = MagicMock()
        self.mock_provider.validate_api_key.return_value = True
        self.mock_provider.normalize_model_name.return_value = "test-model"
        self.mock_provider.supports_streaming.return_value = False
        
        # Patch ProviderFactory to return our mock
        self.patcher = patch('cortex.core.providers.ProviderFactory.get_provider', return_value=self.mock_provider)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir)

    def test_metacognitive_lifecycle_e2e(self):
        """Test the full lifecycle of metacognitive state during an agent session."""
        agent = Cortex(
            model="test-model",
            project_dir=str(self.project_dir),
            config=self.config
        )
        
        # Initial State Check
        self.assertEqual(agent.state_manager.state.metacognition.confidence_score, 0.8)
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "analytical")
        
        # 1. Simulate SUCCESS
        # Model calls read_file
        self.mock_provider.chat.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "I will read the README.",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "README.md"})}
                    }]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "I have read the README. It looks good.",
                    "tool_calls": None
                }
            }
        ]
        
        agent._process_message("What is in the README?")
        
        # Verify confidence increased and tone changed
        self.assertGreater(agent.state_manager.state.metacognition.confidence_score, 0.8)
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "confident")
        self.assertIn("momentum", agent.state_manager.state.metacognition.internal_monologue)
        
        # 2. Simulate FAILURE
        # Reset provider for next turn
        agent.state_manager.state.metacognition.confidence_score = 0.8 # Reset for controlled test
        
        self.mock_provider.chat.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "I will read a non-existent file.",
                    "tool_calls": [{
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "non_existent.txt"})}
                    }]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Oh, it failed.",
                    "tool_calls": None
                }
            }
        ]
        
        agent._process_message("Read non_existent.txt")
        
        # Verify confidence decreased and tone became cautious
        self.assertLess(agent.state_manager.state.metacognition.confidence_score, 0.8)
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "cautious")
        self.assertIn("double-check", agent.state_manager.state.metacognition.internal_monologue)

        # 3. Simulate REPEATED FAILURE (Frustration)
        agent.state_manager.state.failed_tools = 2 # Already had 1 failure from above
        
        self.mock_provider.chat.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "I will try again and fail.",
                    "tool_calls": [{
                        "id": "call_3",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "non_existent_2.txt"})}
                    }]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "I am stuck.",
                    "tool_calls": None
                }
            }
        ]
        
        agent._process_message("Try again")
        
        # Verify tone became frustrated
        self.assertEqual(agent.state_manager.state.metacognition.emotional_tone, "frustrated")
        self.assertGreater(agent.state_manager.state.metacognition.urgency_score, 0.1)
        self.assertIn("repeated obstacles", agent.state_manager.state.metacognition.internal_monologue)

    def test_prompt_injection_e2e(self):
        """Verify that metacognitive context is actually injected into the system prompt."""
        agent = Cortex(
            model="test-model",
            project_dir=str(self.project_dir),
            config=self.config
        )
        
        # Set a specific metacognitive state
        agent.state_manager.state.metacognition.emotional_tone = "frustrated"
        agent.state_manager.state.metacognition.internal_monologue = "TEST_MONOLOGUE_X"
        
        # Mock provider to capture the system prompt
        captured_messages = []
        def mock_chat(model, messages, tools):
            captured_messages.append(messages)
            return {"message": {"role": "assistant", "content": "OK", "tool_calls": None}}
            
        self.mock_provider.chat.side_effect = mock_chat
        
        agent._process_message("Test prompt injection")
        
        # Check the captured system prompt (usually the first message)
        system_prompt = captured_messages[0][0]["content"]
        
        self.assertIn("Internal Metacognition", system_prompt)
        self.assertIn("frustrated", system_prompt)
        self.assertIn("TEST_MONOLOGUE_X", system_prompt)

    def test_insight_confidence_boost(self):
        """Test that recording an insight boosts confidence."""
        agent = Cortex(
            model="test-model",
            project_dir=str(self.project_dir),
            config=self.config
        )
        
        initial_conf = agent.state_manager.state.metacognition.confidence_score
        
        # Record an insight
        agent.state_manager.record_insight("The project uses a custom build system.")
        
        new_conf = agent.state_manager.state.metacognition.confidence_score
        self.assertGreater(new_conf, initial_conf)

    def test_gym_practice_and_reflection(self):
        """Test the Cognitive Gym manager and metacognitive reflection tool."""
        from cortex.core.gym.manager import GymManager
        
        agent = Cortex(
            model="test-model",
            project_dir=str(self.project_dir),
            config=self.config
        )
        
        gym = GymManager(agent)
        
        # Mock the agent's response to the gym prompt
        # The agent should call metacognitive_reflect
        self.mock_provider.chat.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "I will practice refactoring and then reflect.",
                    "tool_calls": [{
                        "id": "call_gym_reflect",
                        "type": "function",
                        "function": {
                            "name": "metacognitive_reflect", 
                            "arguments": json.dumps({
                                "task_description": "Practice Refactoring",
                                "success": True,
                                "key_insight": "Always check for side effects.",
                                "successful_patterns": ["Pattern A", "Pattern B"],
                                "failed_attempts": [{"approach": "Approach X", "error": "Error Y"}]
                            })
                        }
                    }]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Practice complete.",
                    "tool_calls": None
                }
            }
        ]
        
        # Run practice session
        result = gym.run_practice_session("Refactoring", "Practice refactoring code safely.")
        
        self.assertTrue(result["success"])
        
        # Verify focus was set to TRAINING during execution (GymManager restores it to EXPLORING after)
        # We can't easily check it during execution without more mocking, but we can check if 
        # learnings were recorded in memory bank.
        
        # Verify learnings in EnhancedMemoryBank
        memory_bank = agent.memory_bank
        
        # 1. Check for synthetic experience memory item
        synthetic_items = [i for i in memory_bank.items if i.metadata and i.metadata.get("synthetic")]
        self.assertEqual(len(synthetic_items), 1)
        self.assertIn("Always check for side effects", synthetic_items[0].content)
        
        # 2. Check for successful patterns
        patterns = [p.pattern for p in memory_bank.successful_patterns]
        self.assertIn("Pattern A", patterns)
        self.assertIn("Pattern B", patterns)
        
        # 3. Check for failed approaches
        failures = [f.approach for f in memory_bank.failed_approaches]
        self.assertIn("Approach X", failures)

if __name__ == "__main__":
    unittest.main()
