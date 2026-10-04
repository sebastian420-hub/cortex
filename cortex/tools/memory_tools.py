"""The remember tool: lets the model (or the user, through the model) keep something for later."""

from typing import Any, Dict

from .base import Tool
from ..utils.errors import ErrorType, create_error_response, create_success_response

REMEMBER_KINDS = ("convention", "decision", "fact", "solution")
MAX_REMEMBER_CHARS = 500

REMEMBER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": (
            "Keep something for future sessions: a project convention, a decision and the reason "
            "for it, a fact that is costly to rediscover, or how a hard problem was solved. Use it "
            "when the user asks you to remember something, or when you learn something a later "
            "session would otherwise have to work out again. Write one self-contained sentence. "
            "Do NOT store the user's request, a file you just read, an error message, or "
            "anything about the task in progress."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "One self-contained sentence, e.g. 'Run the tests with pytest -x'.",
                },
                "kind": {
                    "type": "string",
                    "enum": list(REMEMBER_KINDS),
                    "description": "convention (default), decision, fact, or solution",
                },
                "user_requested": {
                    "type": "boolean",
                    "description": "True if the user explicitly asked you to remember this.",
                },
            },
            "required": ["content"],
        },
    },
}


class RememberTool(Tool):
    """Stores one memory and says plainly whether it will outlive the session."""

    def __init__(
        self,
        project_dir,
        permission_mode="normal",
        console=None,
        timeout_config=None,
        transaction_manager=None,
        parent_agent=None,
        **kwargs,
    ):
        super().__init__(
            project_dir,
            permission_mode,
            console,
            timeout_config,
            transaction_manager,
            **kwargs,
        )
        self.parent_agent = parent_agent

    def execute(
        self, content: str = "", kind: str = "convention", user_requested: bool = False, **kwargs
    ) -> Dict[str, Any]:
        text = (content or "").strip()
        if not text:
            return create_error_response(
                "Nothing to remember: content is empty.", ErrorType.VALIDATION
            )
        if len(text) > MAX_REMEMBER_CHARS:
            return create_error_response(
                f"Too long to remember ({len(text)} characters, the limit is "
                f"{MAX_REMEMBER_CHARS}). Say it in one sentence.",
                ErrorType.VALIDATION,
            )
        if kind not in REMEMBER_KINDS:
            return create_error_response(
                f"Unknown kind '{kind}'. Use one of: {', '.join(REMEMBER_KINDS)}.",
                ErrorType.VALIDATION,
            )

        bank = getattr(self.parent_agent, "memory_bank", None)
        if bank is None or not hasattr(bank, "remember"):
            return create_error_response(
                "Memory is not available in this session.", ErrorType.EXECUTION
            )

        return create_success_response(bank.remember(text, kind, bool(user_requested)))
