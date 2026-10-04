"""Gym manager for coordinating practice sessions.

A practice session lets the agent work in a scratch copy of a project. Whether it *succeeded* is
decided by a verifier (the task's tests), never by the model saying it is done. Without a
verifier the outcome says so: the result is neither a success nor a failure, it is unchecked.
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .sandbox import SandboxProvider
from ..command_sandbox import SandboxConfig, describe
from ..memory_layers.state import AgentFocus

logger = logging.getLogger(__name__)

# A verifier takes the session's project directory and returns something with `.passed` (bool)
# and `.output` (text), such as bench.task.VerifyResult.
Verifier = Callable[[Path], Any]


class GymManager:
    """
    Coordinates engineering practice sessions for the agent.
    """

    def __init__(self, agent: Any):
        """
        Initialize gym manager.

        Args:
            agent: The Cortex agent instance to train.
        """
        self.agent = agent
        self.sandbox_provider = SandboxProvider(base_project_dir=agent.project_dir)
        self.current_sandbox: Optional[Path] = None

    # ---- the two ways to start a session -----------------------------------------------

    def run_practice_session(
        self, task_name: str, practice_goal: str, verifier: Optional[Verifier] = None
    ) -> Dict[str, Any]:
        """Practise on a copy of the current project.

        Without a ``verifier`` the outcome is unchecked (``success`` is None).
        """
        logger.info(f"Starting practice session: {task_name}")
        sandbox = self.sandbox_provider.create_sandbox(name_prefix=f"gym_{task_name}_")
        return self._run(
            sandbox,
            task_name,
            practice_goal,
            verifier,
            cleanup=lambda: self.sandbox_provider.cleanup_sandbox(sandbox),
        )

    def run_benchmark_task(self, task_id: str) -> Dict[str, Any]:
        """Practise on one task of the benchmark (see bench/); its tests decide the outcome."""
        try:
            from bench.suite import TASKS, get
            from bench.task import materialize, verify
        except ImportError:
            return {
                "success": False,
                "verified": False,
                "error": "The benchmark tasks are not installed (they live in bench/ in a source "
                "checkout of Cortex).",
            }
        try:
            task = get(task_id)
        except KeyError:
            return {
                "success": False,
                "verified": False,
                "error": f"No benchmark task '{task_id}'. Available: "
                + ", ".join(t.id for t in TASKS),
            }

        directory = Path(tempfile.mkdtemp(prefix=f"gym_bench_{task.id}_"))
        materialize(task, directory)
        return self._run(
            directory,
            task.id,
            task.prompt,
            lambda project: verify(task, project),
            cleanup=lambda: shutil.rmtree(directory, ignore_errors=True),
        )

    # ---- one session -------------------------------------------------------------------

    def _run(
        self,
        sandbox: Path,
        task_name: str,
        practice_goal: str,
        verifier: Optional[Verifier],
        cleanup: Callable[[], None],
    ) -> Dict[str, Any]:
        self.current_sandbox = sandbox

        # Save original project dir to restore later
        original_project_dir = self.agent.project_dir
        # The agent's git checkpoints belong to the real project; this session edits a throwaway
        # copy, so they must not snapshot (or later /undo) the real one
        original_checkpoints = getattr(self.agent, "checkpoints", None)
        self.agent.checkpoints = None

        try:
            self.agent.project_dir = sandbox

            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.TRAINING)

            # A copy of the project is not a sandbox: it protects the original files, nothing more.
            # Say what is actually true about the commands, so the model does not take risks that
            # reach outside the copy.
            sandbox_config = getattr(self.agent, "command_sandbox", None)
            if not isinstance(sandbox_config, SandboxConfig):
                sandbox_config = None
            checked = (
                "When you finish, the project's tests will be run to check your work. "
                if verifier
                else ""
            )
            training_prompt = (
                f"PRACTICE SESSION: {task_name}\n"
                f"GOAL: {practice_goal}\n\n"
                f"You are working in a scratch COPY of the project; edits here do not change the "
                f"original. {describe(sandbox_config)} Explore and learn from mistakes, but keep "
                f"everything inside this directory. {checked}\n"
                f"At the end of this session, you MUST call 'metacognitive_reflect' to save your learnings."
            )

            tools_before = len(list(getattr(self.agent, "_tools_used", [])))
            result = self.agent._process_message(training_prompt)
            tools_used = list(getattr(self.agent, "_tools_used", []))[tools_before:]

            turn_ok = bool(getattr(result, "ok", True))
            outcome: Dict[str, Any] = {
                "task": task_name,
                "sandbox": str(sandbox),
                "result": result,
                "turn_ok": turn_ok,
                # The prompt asks for a reflection; whether the model made it is a fact to check
                "reflected": "metacognitive_reflect" in tools_used,
            }

            if verifier is not None:
                try:
                    verdict = verifier(sandbox)
                    outcome["verified"] = True
                    outcome["success"] = bool(verdict.passed)
                    if not verdict.passed:
                        outcome["error"] = (verdict.output or "the tests failed")[-600:]
                except Exception as e:  # a verifier that cannot run is not a pass
                    outcome["verified"] = False
                    outcome["success"] = False
                    outcome["error"] = f"The result could not be verified: {e}"
            else:
                outcome["verified"] = False
                # Nothing checked the work. A turn that ended badly is still a failure; one that
                # ended well is unchecked, not a success.
                outcome["success"] = None if turn_ok else False
                if not turn_ok:
                    outcome["error"] = getattr(result, "error", None) or getattr(
                        result, "status", "practice session did not finish"
                    )
            return outcome

        except Exception as e:
            logger.error(f"Practice session failed: {e}")
            return {"success": False, "verified": False, "error": str(e)}

        finally:
            # Restore original project dir (and its checkpoints)
            self.agent.project_dir = original_project_dir
            self.agent.checkpoints = original_checkpoints

            cleanup()
            self.current_sandbox = None

            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.EXPLORING)
