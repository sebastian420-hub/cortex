"""Ask User Questions tool for structured user input during tasks."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import ErrorType, create_error_response, create_success_response

logger = logging.getLogger(__name__)


@dataclass
class QuestionOption:
    """An option for a question."""

    label: str
    description: str
    value: Optional[str] = None

    def __post_init__(self):
        if self.value is None:
            self.value = self.label


@dataclass
class QuestionAnswer:
    """User's answer to a question."""

    question_header: str
    selected_options: List[str]
    custom_input: Optional[str] = None


class AskUserQuestionTool(Tool):
    """
    Tool for asking structured questions to the user.

    This tool pauses execution and presents the user with options,
    allowing for precise input without ambiguity.

    Features:
    - Single or multi-select questions
    - Custom "Other" option always available
    - Clear descriptions for each option
    - Support for 1-4 questions at once
    """

    default_timeout = 300  # 5 minutes for user input

    def __init__(
        self,
        project_dir: Path,
        permission_mode: str = PermissionMode.NORMAL,
        console=None,
        timeout_config=None,
    ):
        super().__init__(project_dir, permission_mode, console, timeout_config)

    def execute(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute the question tool.

        Args:
            questions: List of question objects, each with:
                - question: The full question text
                - header: Short label (max 12 chars)
                - options: List of {label, description} objects (2-4 options)
                - multiSelect: bool, allow multiple selections (default: False)

        Returns:
            Dict with success and answers list
        """
        if not questions:
            return create_error_response("No questions provided", ErrorType.VALIDATION)

        if len(questions) > 4:
            return create_error_response(
                "Maximum 4 questions allowed at once",
                ErrorType.VALIDATION,
                context={"max_allowed": 4, "provided": len(questions)},
            )

        answers = []

        for q_data in questions:
            # Validate question structure
            validation_error = self._validate_question(q_data)
            if validation_error:
                return validation_error

            # Build options
            options = [
                QuestionOption(label=opt["label"], description=opt.get("description", ""))
                for opt in q_data["options"]
            ]

            # Ask the question
            answer = self._ask_question(
                question=q_data["question"],
                header=q_data["header"],
                options=options,
                multi_select=q_data.get("multiSelect", False),
            )

            answers.append(
                {
                    "header": answer.question_header,
                    "selected": answer.selected_options,
                    "custom_input": answer.custom_input,
                }
            )

        return create_success_response({"answers": answers})

    def _validate_question(self, q_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate question structure, return error dict if invalid."""
        if "question" not in q_data:
            return create_error_response(
                "Question must have 'question' field",
                ErrorType.VALIDATION,
                context={"missing_field": "question"},
            )

        if "header" not in q_data:
            return create_error_response(
                "Question must have 'header' field",
                ErrorType.VALIDATION,
                context={"missing_field": "header"},
            )

        if len(q_data.get("header", "")) > 12:
            return create_error_response(
                f"Header too long: '{q_data['header']}' (max 12 chars)",
                ErrorType.VALIDATION,
                context={"header_length": len(q_data.get("header", "")), "max_length": 12},
            )

        options = q_data.get("options", [])
        if len(options) < 2:
            return create_error_response(
                "Question must have at least 2 options",
                ErrorType.VALIDATION,
                context={"options_count": len(options), "min_required": 2},
            )

        if len(options) > 4:
            return create_error_response(
                "Question can have maximum 4 options",
                ErrorType.VALIDATION,
                context={"options_count": len(options), "max_allowed": 4},
            )

        for i, opt in enumerate(options):
            if "label" not in opt:
                return create_error_response(
                    f"Option {i+1} missing 'label' field",
                    ErrorType.VALIDATION,
                    context={"option_index": i, "missing_field": "label"},
                )

        return None

    def _ask_question(
        self, question: str, header: str, options: List[QuestionOption], multi_select: bool
    ) -> QuestionAnswer:
        """Display question and get user input."""
        from rich.panel import Panel
        from rich.prompt import Prompt

        # Display question header
        self.console.print(f"\n[bold cyan]{header}[/bold cyan]")
        self.console.print(f"[white]{question}[/white]\n")

        # Display options
        for i, opt in enumerate(options, 1):
            self.console.print(f"  [yellow]{i}[/yellow]. {opt.label}")
            if opt.description:
                self.console.print(f"     [dim]{opt.description}[/dim]")

        # Always show "Other" option
        other_num = len(options) + 1
        self.console.print(f"  [yellow]{other_num}[/yellow]. Other (custom input)")
        self.console.print()

        # Get selection
        if multi_select:
            prompt_text = "Select options (comma-separated numbers, e.g., 1,3)"
        else:
            prompt_text = "Select an option (number)"

        while True:
            selection = Prompt.ask(prompt_text)

            if not selection.strip():
                self.console.print("[yellow]Please enter a selection[/yellow]")
                continue

            # Parse selection
            result = self._parse_selection(selection, options, other_num, multi_select)
            if result:
                return QuestionAnswer(
                    question_header=header,
                    selected_options=result["selected"],
                    custom_input=result.get("custom_input"),
                )

            self.console.print(f"[yellow]Invalid selection. Enter numbers 1-{other_num}[/yellow]")

    def _parse_selection(
        self, selection: str, options: List[QuestionOption], other_num: int, multi_select: bool
    ) -> Optional[Dict[str, Any]]:
        """Parse user selection string."""
        selected_options = []
        custom_input = None

        try:
            # Split by comma for potential multi-select
            parts = [p.strip() for p in selection.split(",")]

            if not multi_select and len(parts) > 1:
                # Single select but multiple values provided
                return None

            for part in parts:
                if not part:
                    continue

                idx = int(part)

                if idx == other_num:
                    # User selected "Other"
                    from rich.prompt import Prompt

                    custom_input = Prompt.ask("Enter your custom input")
                    selected_options.append("other")
                elif 1 <= idx <= len(options):
                    selected_options.append(options[idx - 1].value)
                else:
                    return None  # Invalid number

            if not selected_options:
                return None

            return {"selected": selected_options, "custom_input": custom_input}

        except ValueError:
            # Not a valid number, treat as custom input if single value
            if not multi_select and len(parts) == 1:
                return {"selected": ["other"], "custom_input": selection.strip()}
            return None


# Tool schema for function calling
ASK_USER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_user_question",
        "description": "Ask the user structured questions with multiple choice options. Use this when you need to clarify requirements, get user preferences, or make decisions about implementation approach. Users can always select 'Other' to provide custom input.",
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "description": "List of questions to ask (1-4 questions)",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The complete question to ask the user",
                            },
                            "header": {
                                "type": "string",
                                "description": "Short label for the question (max 12 chars)",
                                "maxLength": 12,
                            },
                            "options": {
                                "type": "array",
                                "description": "Available choices (2-4 options)",
                                "minItems": 2,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {
                                            "type": "string",
                                            "description": "Display text for this option",
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "Explanation of what this option means",
                                        },
                                    },
                                    "required": ["label", "description"],
                                },
                            },
                            "multiSelect": {
                                "type": "boolean",
                                "default": False,
                                "description": "Allow multiple selections",
                            },
                        },
                        "required": ["question", "header", "options"],
                    },
                }
            },
            "required": ["questions"],
        },
    },
}
