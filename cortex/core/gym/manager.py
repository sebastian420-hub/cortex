"""Gym manager for coordinating practice sessions."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from .sandbox import SandboxProvider
from ..command_sandbox import SandboxConfig, describe
from ..memory_layers.state import AgentFocus

logger = logging.getLogger(__name__)

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

    def run_practice_session(self, task_name: str, practice_goal: str) -> Dict[str, Any]:
        """
        Run a single autonomous practice session.
        """
        logger.info(f"Starting practice session: {task_name}")
        
        # 1. Create sandbox
        self.current_sandbox = self.sandbox_provider.create_sandbox(name_prefix=f"gym_{task_name}_")
        
        # Save original project dir to restore later
        original_project_dir = self.agent.project_dir
        # The agent's git checkpoints belong to the real project; this session edits a throwaway
        # copy, so they must not snapshot (or later /undo) the real one
        original_checkpoints = getattr(self.agent, "checkpoints", None)
        self.agent.checkpoints = None

        try:
            # 2. Update agent to use sandbox
            self.agent.project_dir = self.current_sandbox
            
            # 3. Set agent focus to TRAINING
            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.TRAINING)
            
            # 4. Inject practice goal
            # A copy of the project is not a sandbox: it protects the original files, nothing more.
            # Say what is actually true about the commands, so the model does not take risks that
            # reach outside the copy.
            sandbox_config = getattr(self.agent, "command_sandbox", None)
            if not isinstance(sandbox_config, SandboxConfig):
                sandbox_config = None
            training_prompt = (
                f"PRACTICE SESSION: {task_name}\n"
                f"GOAL: {practice_goal}\n\n"
                f"You are working in a scratch COPY of the project; edits here do not change the "
                f"original. {describe(sandbox_config)} Explore and learn from mistakes, but keep "
                f"everything inside this directory.\n"
                f"At the end of this session, you MUST call 'metacognitive_reflect' to save your learnings."
            )
            
            # 5. Execute practice run
            # Use process_message directly
            tools_before = len(list(getattr(self.agent, "_tools_used", [])))
            result = self.agent._process_message(training_prompt)
            tools_used = list(getattr(self.agent, "_tools_used", []))[tools_before:]

            # Report how the turn really ended instead of assuming it went well
            succeeded = bool(getattr(result, "ok", True))
            outcome = {
                "success": succeeded,
                "task": task_name,
                "sandbox": str(self.current_sandbox),
                "result": result,
                # The prompt asks for a reflection; whether the model made it is a fact to check
                "reflected": "metacognitive_reflect" in tools_used,
            }
            if not succeeded:
                outcome["error"] = getattr(result, "error", None) or getattr(
                    result, "status", "practice session did not finish"
                )
            return outcome
            
        except Exception as e:
            logger.error(f"Practice session failed: {e}")
            return {"success": False, "error": str(e)}
            
        finally:
            # 6. Restore original project dir (and its checkpoints)
            self.agent.project_dir = original_project_dir
            self.agent.checkpoints = original_checkpoints
            
            # 7. Cleanup sandbox
            if self.current_sandbox:
                self.sandbox_provider.cleanup_sandbox(self.current_sandbox)
                self.current_sandbox = None
            
            # 8. Restore focus
            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.EXPLORING)
