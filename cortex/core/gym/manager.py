"""Gym manager for coordinating practice sessions."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from .sandbox import SandboxProvider
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
        
        try:
            # 2. Update agent to use sandbox
            self.agent.project_dir = self.current_sandbox
            
            # 3. Set agent focus to TRAINING
            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.TRAINING)
            
            # 4. Inject practice goal
            training_prompt = (
                f"PRACTICE SESSION: {task_name}\n"
                f"GOAL: {practice_goal}\n\n"
                f"You are in a SAFE SANDBOX. Explore freely, take risks, and learn from mistakes.\n"
                f"At the end of this session, you MUST call 'metacognitive_reflect' to save your learnings."
            )
            
            # 5. Execute practice run
            # Use process_message directly
            result = self.agent._process_message(training_prompt)
            
            return {
                "success": True,
                "task": task_name,
                "sandbox": str(self.current_sandbox),
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Practice session failed: {e}")
            return {"success": False, "error": str(e)}
            
        finally:
            # 6. Restore original project dir
            self.agent.project_dir = original_project_dir
            
            # 7. Cleanup sandbox
            if self.current_sandbox:
                self.sandbox_provider.cleanup_sandbox(self.current_sandbox)
                self.current_sandbox = None
            
            # 8. Restore focus
            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.set_focus(AgentFocus.EXPLORING)
