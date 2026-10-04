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

    def _run(self, verifier=None, **agent_attrs):
        for name, value in agent_attrs.items():
            setattr(self.agent, name, value)
        with patch("cortex.core.gym.manager.SandboxProvider") as provider_class:
            provider_class.return_value.create_sandbox.return_value = Path("/tmp/sandbox")
            manager = GymManager(self.agent)
            return manager.run_practice_session("task", "goal", verifier=verifier)

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

    def test_a_finished_turn_without_a_verifier_is_not_called_a_success(self):
        from cortex.core.turn import STATUS_OK, TurnResult

        self.agent._process_message.return_value = TurnResult(STATUS_OK, final_text="I fixed it!")

        outcome = self._run()

        # nothing checked the work: the model saying it is done is not a result
        self.assertIsNone(outcome["success"])
        self.assertFalse(outcome["verified"])
        self.assertTrue(outcome["turn_ok"])

    def test_the_verifier_decides_not_the_model(self):
        from types import SimpleNamespace

        from cortex.core.turn import STATUS_OK, TurnResult

        self.agent._process_message.return_value = TurnResult(STATUS_OK, final_text="All fixed!")

        def failing(path):
            return SimpleNamespace(passed=False, output="1 failed: test_sum")

        def passing(path):
            return SimpleNamespace(passed=True, output="1 passed")

        bad = self._run(verifier=failing)
        good = self._run(verifier=passing)

        self.assertFalse(bad["success"])
        self.assertTrue(bad["verified"])
        self.assertIn("test_sum", bad["error"])
        self.assertTrue(good["success"])

    def test_the_verifier_is_given_the_sessions_directory(self):
        from types import SimpleNamespace

        seen = []
        self._run(
            verifier=lambda path: seen.append(path) or SimpleNamespace(passed=True, output="")
        )

        self.assertEqual(seen, [Path("/tmp/sandbox")])

    def test_a_broken_verifier_is_a_failure_not_a_success(self):
        def broken(path):
            raise RuntimeError("could not run the tests")

        outcome = self._run(verifier=broken)

        self.assertFalse(outcome["success"])
        self.assertIn("could not run the tests", outcome["error"])

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

        self.agent._tools_used = [
            "metacognitive_reflect"
        ]  # from an earlier session: does not count
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
        with (
            patch("cortex.cli_commands.commands.gym.GymManager") as manager_class,
            patch("cortex.cli_commands.commands.gym.console") as console,
        ):
            manager_class.return_value.run_practice_session.return_value = outcome
            console.print.side_effect = lambda *a, **k: printed.append(str(a[0]))
            GymCommand().execute(ctx, '--task "t" --goal "g"')
        return " ".join(printed)

    def test_it_only_claims_learnings_were_saved_when_they_were(self):
        saved = self._run_command({"success": True, "verified": True, "reflected": True})
        not_saved = self._run_command({"success": True, "verified": True, "reflected": False})

        self.assertIn("recorded", saved)
        self.assertNotIn("have been recorded", not_saved)
        self.assertIn("metacognitive_reflect", not_saved)

    def test_a_verified_pass_and_a_verified_failure_are_reported_as_such(self):
        passed = self._run_command({"success": True, "verified": True, "reflected": False})
        failed = self._run_command(
            {"success": False, "verified": True, "error": "1 failed: test_sum", "reflected": True}
        )

        self.assertIn("passed", passed.lower())
        self.assertNotIn("completed successfully", failed)
        self.assertIn("failed", failed.lower())
        self.assertIn("test_sum", failed)

    def test_an_unchecked_session_is_neither_success_nor_failure(self):
        unchecked = self._run_command(
            {"success": None, "verified": False, "turn_ok": True, "reflected": True}
        )

        text = unchecked.lower()
        self.assertNotIn("completed successfully", text)
        self.assertNotIn("passed its verifier", text)
        self.assertNotIn("failed its verifier", text)
        self.assertIn("nothing checked", text)


if __name__ == "__main__":
    unittest.main()
