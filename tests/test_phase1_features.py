"""Tests for Phase 1 features: Todo tool, Ask User tool, and Context Summarization."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Todo tool tests
from cortex.tools.todo_tool import (
    TodoManager,
    TodoItem,
    TodoStatus,
    TodoWriteTool,
    TODO_TOOL_SCHEMA,
)

# Ask user tool tests
from cortex.tools.ask_user_tool import (
    AskUserQuestionTool,
    QuestionOption,
    QuestionAnswer,
    ASK_USER_TOOL_SCHEMA,
)

# Summarization tests
from cortex.core.summarization import (
    SimpleSummarizer,
    HybridSummarizer,
    SummaryChunk,
    SummarizationStrategy,
    create_summarizer,
)

# Types tests
from cortex.types import (
    ToolResult,
    TodoItem as TodoItemType,
    Question,
    QuestionAnswer as QuestionAnswerType,
)


# ============ Todo Manager Tests ============


class TestTodoManager:
    """Tests for TodoManager class."""

    def test_create_empty_manager(self):
        """Test creating an empty todo manager."""
        manager = TodoManager()
        assert len(manager.todos) == 0
        assert manager.get_progress() == {
            "total": 0,
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
        }

    def test_add_todos(self):
        """Test adding todos to the manager."""
        manager = TodoManager()
        result = manager.update(
            [
                {"content": "Task 1", "status": "pending", "activeForm": "Working on Task 1"},
                {"content": "Task 2", "status": "in_progress", "activeForm": "Working on Task 2"},
            ]
        )

        assert result["success"] is True
        assert len(manager.todos) == 2
        assert manager.get_progress()["pending"] == 1
        assert manager.get_progress()["in_progress"] == 1

    def test_only_one_in_progress(self):
        """Test that only one task can be in_progress."""
        manager = TodoManager()
        result = manager.update(
            [
                {"content": "Task 1", "status": "in_progress", "activeForm": "Task 1"},
                {"content": "Task 2", "status": "in_progress", "activeForm": "Task 2"},
            ]
        )

        assert result["success"] is False
        assert "Only one task" in result.get("error", "")

    def test_complete_task(self):
        """Test completing a task."""
        manager = TodoManager()
        manager.update(
            [
                {"content": "Task 1", "status": "pending", "activeForm": "Task 1"},
            ]
        )

        # Complete the task
        manager.update(
            [
                {"content": "Task 1", "status": "completed", "activeForm": "Task 1"},
            ]
        )

        assert manager.todos[0].status == TodoStatus.COMPLETED
        assert manager.todos[0].completed_at is not None

    def test_get_current_task(self):
        """Test getting the current in_progress task."""
        manager = TodoManager()
        manager.update(
            [
                {"content": "Task 1", "status": "pending", "activeForm": "Task 1"},
                {"content": "Task 2", "status": "in_progress", "activeForm": "Working on Task 2"},
                {"content": "Task 3", "status": "completed", "activeForm": "Task 3"},
            ]
        )

        current = manager.get_current_task()
        assert current is not None
        assert current.content == "Task 2"
        assert current.active_form == "Working on Task 2"

    def test_invalid_status(self):
        """Test handling invalid status."""
        manager = TodoManager()
        result = manager.update(
            [
                {"content": "Task 1", "status": "invalid_status", "activeForm": "Task 1"},
            ]
        )

        assert result["success"] is False
        assert "Invalid status" in result.get("error", "")

    def test_display_callback(self):
        """Test that display callback is called on update."""
        callback_called = []

        def mock_callback(todos):
            callback_called.append(len(todos))

        manager = TodoManager(display_callback=mock_callback)
        manager.update(
            [
                {"content": "Task 1", "status": "pending", "activeForm": "Task 1"},
            ]
        )

        assert len(callback_called) == 1
        assert callback_called[0] == 1


class TestTodoWriteTool:
    """Tests for TodoWriteTool."""

    def test_tool_schema_valid(self):
        """Test that tool schema is valid."""
        assert TODO_TOOL_SCHEMA["type"] == "function"
        assert TODO_TOOL_SCHEMA["function"]["name"] == "todo_write"
        assert "parameters" in TODO_TOOL_SCHEMA["function"]

    def test_execute_creates_todos(self):
        """Test executing the tool creates todos."""
        mock_console = Mock()
        tool = TodoWriteTool(project_dir=Path("."), permission_mode="normal", console=mock_console)

        result = tool.execute(
            todos=[
                {"content": "Test task", "status": "pending", "activeForm": "Testing"},
            ]
        )

        assert result["success"] is True
        assert "progress" in result["data"]
        assert result["data"]["progress"]["total"] == 1


# ============ Ask User Tool Tests ============


class TestAskUserQuestionTool:
    """Tests for AskUserQuestionTool."""

    def test_tool_schema_valid(self):
        """Test that tool schema is valid."""
        assert ASK_USER_TOOL_SCHEMA["type"] == "function"
        assert ASK_USER_TOOL_SCHEMA["function"]["name"] == "ask_user_question"

    def test_validate_question_missing_question(self):
        """Test validation catches missing question field."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        result = tool._validate_question({"header": "Test"})
        assert result is not None
        assert result["success"] is False

    def test_validate_question_header_too_long(self):
        """Test validation catches header that's too long."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        result = tool._validate_question(
            {
                "question": "Test question?",
                "header": "This is way too long for a header",
                "options": [
                    {"label": "A", "description": "Option A"},
                    {"label": "B", "description": "Option B"},
                ],
            }
        )
        assert result is not None
        assert "too long" in result.get("error", "")

    def test_validate_question_too_few_options(self):
        """Test validation catches too few options."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        result = tool._validate_question(
            {
                "question": "Test question?",
                "header": "Test",
                "options": [{"label": "Only one", "description": "Single option"}],
            }
        )
        assert result is not None
        assert "at least 2" in result.get("error", "")

    def test_validate_question_valid(self):
        """Test validation passes for valid question."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        result = tool._validate_question(
            {
                "question": "What option?",
                "header": "Choice",
                "options": [
                    {"label": "A", "description": "Option A"},
                    {"label": "B", "description": "Option B"},
                ],
            }
        )
        assert result is None  # No error

    def test_empty_questions_list(self):
        """Test handling of empty questions list."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        result = tool.execute(questions=[])
        assert result["success"] is False
        assert "No questions" in result.get("error", "")

    def test_too_many_questions(self):
        """Test handling of too many questions."""
        mock_console = Mock()
        tool = AskUserQuestionTool(project_dir=Path("."), console=mock_console)

        questions = [
            {
                "question": f"Q{i}?",
                "header": f"H{i}",
                "options": [
                    {"label": "A", "description": "A"},
                    {"label": "B", "description": "B"},
                ],
            }
            for i in range(5)  # 5 questions, max is 4
        ]

        result = tool.execute(questions=questions)
        assert result["success"] is False
        assert "Maximum 4" in result.get("error", "")


# ============ Summarization Tests ============


class TestSimpleSummarizer:
    """Tests for SimpleSummarizer."""

    def test_summarize_empty(self):
        """Test summarizing empty messages."""
        summarizer = SimpleSummarizer()
        summary = summarizer.summarize([])

        assert summary.original_message_count == 0
        assert isinstance(summary.summary_content, str)

    def test_summarize_user_messages(self):
        """Test summarizing user messages."""
        summarizer = SimpleSummarizer()
        messages = [
            {"role": "user", "content": "Read the README file"},
            {"role": "assistant", "content": "I'll read the README."},
            {"role": "user", "content": "Now fix the bug"},
        ]

        summary = summarizer.summarize(messages)

        assert summary.original_message_count == 3
        assert "User asked" in summary.summary_content

    def test_extract_tool_calls(self):
        """Test extracting information from tool calls."""
        summarizer = SimpleSummarizer()
        messages = [
            {"role": "user", "content": "Read test.py"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "test.py"}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "1",
                "content": json.dumps({"success": True, "content": "..."}),
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"path": "output.py", "content": "..."}),
                        }
                    }
                ],
            },
        ]

        summary = summarizer.summarize(messages)

        assert "test.py" in summary.files_read
        assert "output.py" in summary.files_modified

    def test_extract_errors(self):
        """Test extracting errors from tool results."""
        summarizer = SimpleSummarizer()
        messages = [
            {
                "role": "tool",
                "tool_call_id": "1",
                "content": json.dumps({"success": False, "error": "File not found"}),
            }
        ]

        summary = summarizer.summarize(messages)

        assert len(summary.errors_encountered) > 0
        assert "File not found" in summary.errors_encountered[0]

    def test_should_summarize(self):
        """Test the should_summarize check."""
        summarizer = SimpleSummarizer()

        # Under threshold - should not summarize
        assert not summarizer.should_summarize([], 500, 1000, 0.8)

        # Over threshold - should summarize
        assert summarizer.should_summarize([], 900, 1000, 0.8)


class TestHybridSummarizer:
    """Tests for HybridSummarizer."""

    def test_without_llm(self):
        """Test hybrid summarizer without LLM falls back to simple."""
        summarizer = HybridSummarizer(provider=None, model="")
        messages = [
            {"role": "user", "content": "Test message"},
        ]

        summary = summarizer.summarize(messages)

        assert summary.original_message_count == 1


class TestCreateSummarizer:
    """Tests for create_summarizer factory."""

    def test_create_simple(self):
        """Test creating simple summarizer."""
        summarizer = create_summarizer(SummarizationStrategy.SIMPLE)
        assert isinstance(summarizer, SimpleSummarizer)

    def test_create_hybrid_without_provider(self):
        """Test creating hybrid summarizer without provider."""
        summarizer = create_summarizer(SummarizationStrategy.HYBRID)
        assert isinstance(summarizer, HybridSummarizer)

    def test_create_llm_without_provider_fallback(self):
        """Test creating LLM summarizer without provider falls back to simple."""
        summarizer = create_summarizer(SummarizationStrategy.LLM_BASED)
        assert isinstance(summarizer, SimpleSummarizer)


# ============ Types Tests ============


class TestTypes:
    """Tests for TypedDict types."""

    def test_tool_result_type(self):
        """Test ToolResult type can be used correctly."""
        result: ToolResult = {"success": True, "data": {"content": "test"}}
        assert result["success"] is True

    def test_todo_item_type(self):
        """Test TodoItem type can be used correctly."""
        item: TodoItemType = {"content": "Test task", "status": "pending", "activeForm": "Testing"}
        assert item["content"] == "Test task"

    def test_question_type(self):
        """Test Question type can be used correctly."""
        question: Question = {
            "question": "What option?",
            "header": "Choice",
            "options": [
                {"label": "A", "description": "Option A"},
                {"label": "B", "description": "Option B"},
            ],
        }
        assert question["header"] == "Choice"


# ============ Integration Tests ============


class TestConversationManagerWithSummarization:
    """Integration tests for ConversationManager with summarization."""

    def test_manager_with_summarizer(self):
        """Test ConversationManager can use a summarizer."""
        from cortex.core.conversation import ConversationManager

        summarizer = SimpleSummarizer()
        manager = ConversationManager(
            system_prompt="Test prompt",
            max_tokens=1000,
            summarizer=summarizer,
            enable_summarization=True,
        )

        assert manager.summarizer is summarizer
        assert manager.enable_summarization is True

    def test_manager_stats_include_summarization(self):
        """Test truncation stats include summarization info."""
        from cortex.core.conversation import ConversationManager

        manager = ConversationManager(system_prompt="Test prompt", enable_summarization=True)

        stats = manager.get_truncation_stats()

        assert "summarization_count" in stats
        assert "summarization_enabled" in stats
        assert stats["summarization_enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
