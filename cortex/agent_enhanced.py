"""
Backward compatibility module for EnhancedCortex.

This module provides an EnhancedCortex class that now serves as a thin wrapper
around the unified Cortex agent, maintaining the original API.
"""

from typing import Optional, Dict, Any, Callable
from .agent import Cortex
from .models import PermissionMode
from .config import AgentConfig
from .output import OutputFormat

# Re-export key functions/objects for tests that mock them in this module
from .core.streaming import stream_model_response, display_streaming_response
from .ui.console import console


class EnhancedCortex(Cortex):
    """
    Deprecated: Use Cortex(enable_planning=True, enable_layered_memory=True) instead.
    
    Enhanced Cortex agent with planning and layered memory.
    This class maintains the original EnhancedCortex API for backward compatibility.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        project_dir: str = ".",
        permission_mode: str = PermissionMode.NORMAL,
        config: Optional[AgentConfig] = None,
        hook_manager: Optional[Any] = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        on_max_iterations_reached: Optional[Callable[[int, int], Optional[int]]] = None,
        enable_planning: bool = True,
        enable_layered_memory: bool = True,
    ):
        """
        Initialize enhanced Cortex agent.
        Delegates all work to the unified Cortex base class.
        """
        super().__init__(
            model=model,
            project_dir=project_dir,
            permission_mode=permission_mode,
            config=config,
            hook_manager=hook_manager,
            output_format=output_format,
            on_max_iterations_reached=on_max_iterations_reached,
            enable_planning=enable_planning,
            enable_layered_memory=enable_layered_memory,
        )

    # All enhanced methods (process_with_planning, generate_and_execute_plan, etc.)
    # are now available in the base Cortex class.
    
    def process_with_planning(self, user_message: str, use_streaming: bool = False):
        """Backward compatibility for process_with_planning."""
        return self._process_message(user_message, use_streaming=use_streaming)

    async def process_with_planning_async(self, user_message: str, use_streaming: bool = False):
        """Backward compatibility for process_with_planning_async."""
        return await self._process_message_async(user_message, use_streaming=use_streaming)
