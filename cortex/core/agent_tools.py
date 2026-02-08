"""Tool execution module - handles tool orchestration and execution"""

import logging
from typing import List, Dict, Any, TYPE_CHECKING

from ..core.parallel import ToolCall

if TYPE_CHECKING:
    from ..agent import Cortex

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Handles tool execution orchestration.

    Responsibilities:
    - Execute tool calls (single or batch)
    - Delegate to parallel executor when appropriate
    - Coordinate with permission manager
    - Handle tool call formatting and results

    Note: The actual tool execution logic remains in the Cortex class
    for backward compatibility. This class provides a cleaner interface.
    """

    def __init__(self, agent: 'Cortex'):
        """
        Initialize with reference to parent agent.

        Args:
            agent: Parent Cortex agent instance
        """
        self.agent = agent

    def execute_batch(self, tool_calls: List[ToolCall]) -> List[Dict[str, Any]]:
        """
        Execute a batch of tool calls.

        Delegates to the parallel executor which handles:
        - Parallel vs sequential execution
        - Permission checks (via execute_tool)
        - Error handling
        - Result formatting

        Args:
            tool_calls: List of ToolCall objects to execute

        Returns:
            List of result dictionaries
        """
        return self.agent.parallel_executor.execute_batch(tool_calls)

    def execute_single(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool call.

        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments

        Returns:
            Result dictionary
        """
        return self.agent.execute_tool(tool_name, arguments)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tool definitions.

        Returns:
            List of tool definition dictionaries
        """
        return self.agent.tool_registry.get_tool_definitions()

    def is_tool_available(self, tool_name: str) -> bool:
        """
        Check if a tool is available.

        Args:
            tool_name: Tool name to check

        Returns:
            True if available, False otherwise
        """
        try:
            self.agent.tool_registry.get_tool(tool_name)
            return True
        except (ValueError, KeyError):
            return False
