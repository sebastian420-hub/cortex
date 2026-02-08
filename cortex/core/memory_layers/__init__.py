"""Layered memory system for Cortex agent.

This module provides a comprehensive memory architecture with three layers:

1. **Working Memory**: Short-term context for current task execution
   - Files currently being examined
   - Tool execution context
   - Immediate insights and observations
   - Open questions and hypotheses

2. **Session Memory**: Mid-term memory for the current session
   - Extended MemoryBank with failed approaches tracking
   - Successful patterns and strategies
   - Session insights and progress markers
   - Context assembly summaries

3. **State Management**: Integration layer
   - Complete agent state tracking
   - Coordination between memory layers
   - Progress tracking against goals
   - State transitions and checkpoints

Usage:
    ```python
    from cortex.core.memory_layers import (
        WorkingMemory,
        EnhancedMemoryBank,
        StateManager,
        AgentState,
        AgentFocus,
    )

    # Create state manager
    state_manager = StateManager(project_dir=Path("."))

    # Set primary goal
    state_manager.set_primary_goal("Fix the bug in api.py")

    # Record tool execution
    state_manager.record_tool_execution(
        tool_name="read_file",
        arguments={"path": "api.py"},
        result={"success": True, "content": "..."},
    )

    # Get context for LLM
    context = state_manager.get_llm_context()
    ```
"""

from .working import (
    WorkingMemory,
    WorkingMemoryItem,
    WorkingMemoryItemType,
    FileContext,
    ToolContext,
)

from .session import (
    EnhancedMemoryBank,
    FailedApproach,
    SuccessfulPattern,
    SessionMemoryType,
)

from .state import (
    StateManager,
    AgentState,
    AgentFocus,
)

__all__ = [
    # Working memory
    "WorkingMemory",
    "WorkingMemoryItem",
    "WorkingMemoryItemType",
    "FileContext",
    "ToolContext",
    # Session memory
    "EnhancedMemoryBank",
    "FailedApproach",
    "SuccessfulPattern",
    "SessionMemoryType",
    # State management
    "StateManager",
    "AgentState",
    "AgentFocus",
]
