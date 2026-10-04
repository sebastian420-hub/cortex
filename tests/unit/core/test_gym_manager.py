
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

    def _run(self, **agent_attrs):
        for name, value in agent_attrs.items():
            setattr(self.agent, name, value)
        with patch("cortex.core.gym.manager.SandboxProvider") as provider_class:
            provider_class.return_value.create_sandbox.return_value = Path("/tmp/sandbox")
            manager = GymManager(self.agent)
            return manager.run_practice_session("task", "goal")

    def test_prompt_does_not_call_a_project_copy_safe(self):
        self._run()

        prompt = self.agent._process_message.call_args[0][0]
        self.assertNotIn("SAFE SANDBOX", prompt)
        self.assertIn("COPY", prompt)
        # commands are not confined by default, and the model is told so
        self.assertIn("not isolated", prompt.lower())

    def test_prompt_reports_real_confinement_when_it_is_on(self):
        from cortex.core.command_sandbox import SandboxConfig

        self._run(command_sandbox=SandboxConfig.from_dict({"mode": "bubblewrap"}))

        prompt = self.agent._process_message.call_args[0][0]
        self.assertIn("bubblewrap", prompt.lower())
        self.assertNotIn("not isolated", prompt.lower())

    def test_a_failed_turn_is_reported_as_a_failed_session(self):
        from cortex.core.turn import STATUS_ERROR, TurnResult

        self.agent._process_message.return_value = TurnResult(STATUS_ERROR, error="model crashed")

        outcome = self._run()

        self.assertFalse(outcome["success"])
        self.assertIn("model crashed", outcome["error"])

    def test_a_finished_turn_is_reported_as_success(self):
        from cortex.core.turn import STATUS_OK, TurnResult

        self.agent._process_message.return_value = TurnResult(STATUS_OK, final_text="done")

        self.assertTrue(self._run()["success"])

    def test_the_real_projects_checkpoints_are_off_during_a_session_and_back_after(self):
        real_store = object()
        seen = {}

        def capture(prompt):
            seen["during"] = self.agent.checkpoints
            from cortex.core.turn import STATUS_OK, TurnResult

            return TurnResult(STATUS_OK)

        self.agent._process_message.side_effect = capture
        self._run(checkpoints=real_store)

        self.assertIsNone(seen["during"])
        self.assertIs(self.agent.checkpoints, real_store)

    def test_the_outcome_says_whether_the_model_saved_its_learnings(self):
        from cortex.core.turn import STATUS_OK, TurnResult

        self.agent._tools_used = ["read_file"]

        def reflect(prompt):
            self.agent._tools_used.append("metacognitive_reflect")
            return TurnResult(STATUS_OK)

        self.agent._process_message.side_effect = reflect
        self.assertTrue(self._run()["reflected"])

        self.agent._tools_used = ["metacognitive_reflect"]  # from an earlier session: does not count
        self.agent._process_message.side_effect = lambda prompt: TurnResult(STATUS_OK)
        self.assertFalse(self._run()["reflected"])


class TestGymCommandMessages(unittest.TestCase):
    def _run_command(self, outcome):
        from cortex.cli_commands.commands.base import CommandContext
        from cortex.cli_commands.commands.gym import GymCommand

        printed = []
        ctx = CommandContext(
            agent=MagicMock(), config=MagicMock(), hook_manager=MagicMock(), output_format="text"
        )
        with patch("cortex.cli_commands.commands.gym.GymManager") as manager_class, patch(
            "cortex.cli_commands.commands.gym.console"
        ) as console:
            manager_class.return_value.run_practice_session.return_value = outcome
            console.print.side_effect = lambda *a, **k: printed.append(str(a[0]))
            GymCommand().execute(ctx, '--task "t" --goal "g"')
        return " ".join(printed)

    def test_it_only_claims_learnings_were_saved_when_they_were(self):
        saved = self._run_command({"success": True, "reflected": True})
        not_saved = self._run_command({"success": True, "reflected": False})

        self.assertIn("recorded", saved)
        self.assertNotIn("have been recorded", not_saved)
        self.assertIn("metacognitive_reflect", not_saved)


if __name__ == "__main__":
    unittest.main()
