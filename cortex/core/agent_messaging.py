"""Message processing module - handles conversation loop and LLM calls"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent import Cortex

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    Handles message processing and conversation flow.

    Responsibilities:
    - Process user messages
    - Manage conversation loop
    - Call LLM provider
    - Handle iteration limits

    Note: Core processing logic remains in Cortex._process_message()
    for backward compatibility. This class provides organization.
    """

    def __init__(self, agent: 'Cortex'):
        """Initialize with reference to parent agent"""
        self.agent = agent
        self.iteration_count = 0

    def process(self, user_message: str, use_streaming: bool = False) -> None:
        """
        Process a user message.

        Delegates to agent._process_message() for actual processing.

        Args:
            user_message: Message from user
            use_streaming: Whether to use streaming responses
        """
        return self.agent._process_message(user_message, use_streaming)

    def reset_iteration_count(self):
        """Reset iteration counter"""
        self.iteration_count = 0
