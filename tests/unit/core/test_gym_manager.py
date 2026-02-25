
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from cortex.core.gym.manager import GymManager
from cortex.agent import Cortex

class TestGymLogic(unittest.TestCase):
    def setUp(self):
        self.agent = MagicMock()
        self.agent.project_dir = Path(".").resolve()
        self.agent.state_manager = MagicMock()
        
    @patch("cortex.core.gym.manager.SandboxProvider")
    def test_gym_session_flow(self, mock_sandbox_provider_class):
        # Setup mocks
        mock_provider = MagicMock()
        mock_sandbox_path = Path("/tmp/sandbox")
        mock_provider.create_sandbox.return_value = mock_sandbox_path
        mock_sandbox_provider_class.return_value = mock_provider
        
        manager = GymManager(self.agent)
        
        # Run practice session
        manager.run_practice_session("test_task", "test_goal")
        
        # Verify sandbox was created and cleaned up
        mock_provider.create_sandbox.assert_called_once()
        mock_provider.cleanup_sandbox.assert_called_with(mock_sandbox_path)
        
        # Verify agent focus was set to TRAINING
        from cortex.core.memory_layers.state import AgentFocus
        self.agent.state_manager.set_focus.assert_any_call(AgentFocus.TRAINING)
        
        # Verify agent process_message was called with practice prompt
        self.agent._process_message.assert_called_once()
        args, _ = self.agent._process_message.call_args
        self.assertIn("PRACTICE SESSION: test_task", args[0])

if __name__ == "__main__":
    unittest.main()
