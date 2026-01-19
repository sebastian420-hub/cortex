"""Tests for TaskTool and Subagent System"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from cortex.subagent import TaskTool, SubagentContext, TASK_TOOL_SCHEMA
from cortex.hooks import HookManager, PermissionHook, HookAction
from cortex.utils.errors import ErrorType


class TestTaskToolSchema:
    """Test TaskTool schema definition"""

    def test_schema_structure(self):
        """Test schema has correct structure"""
        assert TASK_TOOL_SCHEMA["type"] == "function"
        assert TASK_TOOL_SCHEMA["function"]["name"] == "task"
        assert "description" in TASK_TOOL_SCHEMA["function"]

    def test_schema_parameters(self):
        """Test schema parameters"""
        params = TASK_TOOL_SCHEMA["function"]["parameters"]
        assert params["type"] == "object"

        properties = params["properties"]
        assert "description" in properties
        assert "allowed_tools" in properties
        assert "max_iterations" in properties
        assert "context" in properties

    def test_required_parameters(self):
        """Test required parameters"""
        params = TASK_TOOL_SCHEMA["function"]["parameters"]
        assert "description" in params["required"]


class TestSubagentContext:
    """Test SubagentContext dataclass"""

    def test_context_creation(self):
        """Test creating a context"""
        context = SubagentContext(
            task_id="test123",
            task_description="Test task",
            parent_context={"key": "value"},
            allowed_tools=["read_file"],
            max_iterations=5,
        )

        assert context.task_id == "test123"
        assert context.task_description == "Test task"
        assert context.allowed_tools == ["read_file"]
        assert context.max_iterations == 5
        assert context.completed is False

    def test_context_lifecycle(self):
        """Test context start/complete lifecycle"""
        context = SubagentContext(
            task_id="test123",
            task_description="Test task",
            parent_context={},
            allowed_tools=["read_file"],
        )

        # Start
        context.start()
        assert context.started_at is not None
        assert context.completed is False

        # Complete
        result = {"data": "test"}
        context.complete(result)
        assert context.completed is True
        assert context.result == result
        assert context.completed_at is not None

    def test_context_failure(self):
        """Test context failure"""
        context = SubagentContext(
            task_id="test123",
            task_description="Test task",
            parent_context={},
            allowed_tools=["read_file"],
        )

        context.start()
        context.fail("Something went wrong")

        assert context.completed is True
        assert context.error == "Something went wrong"

    def test_context_to_dict(self):
        """Test context serialization"""
        context = SubagentContext(
            task_id="test123",
            task_description="Test task",
            parent_context={"key": "value"},
            allowed_tools=["read_file", "list_files"],
            max_iterations=10,
        )

        data = context.to_dict()

        assert data["task_id"] == "test123"
        assert data["task_description"] == "Test task"
        assert data["allowed_tools"] == ["read_file", "list_files"]
        assert data["completed"] is False


class TestTaskToolInit:
    """Test TaskTool initialization"""

    def test_basic_init(self, tmp_path):
        """Test basic initialization"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        assert tool.project_dir == tmp_path
        assert tool.permission_mode == "normal"
        assert tool.parent_agent is None
        assert len(tool.active_tasks) == 0

    def test_init_with_parent_agent(self, tmp_path):
        """Test initialization with parent agent"""
        console = Mock()
        parent_agent = Mock()

        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="auto",
            console=console,
            parent_agent=parent_agent,
        )

        assert tool.parent_agent is parent_agent


class TestTaskToolExecution:
    """Test TaskTool execute method"""

    def test_execute_with_default_tools(self, tmp_path):
        """Test execution with default allowed tools"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        # Mock _run_subagent to avoid actual agent creation
        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {"final_response": "Task completed"}

            result = tool.execute(description="Find all Python files")

            assert result["success"] is True
            assert "task_id" in result["data"]  # Result fields are now under "data"

            # Check context was created with default tools (now includes grep/glob)
            context = mock_run.call_args[0][0]
            assert context.allowed_tools == ["read_file", "list_files", "grep", "glob"]

    def test_execute_with_custom_tools(self, tmp_path):
        """Test execution with custom allowed tools"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {"final_response": "Done"}

            result = tool.execute(
                description="Write a test",
                allowed_tools=["read_file", "write_file"],
            )

            assert result["success"] is True
            context = mock_run.call_args[0][0]
            assert context.allowed_tools == ["read_file", "write_file"]

    def test_execute_with_max_iterations(self, tmp_path):
        """Test execution with custom max iterations"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {"final_response": "Done"}

            result = tool.execute(
                description="Complex task",
                max_iterations=20,
            )

            context = mock_run.call_args[0][0]
            assert context.max_iterations == 20

    def test_execute_with_context(self, tmp_path):
        """Test execution with additional context"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {"final_response": "Done"}

            result = tool.execute(
                description="Analyze code",
                context="Focus on error handling",
            )

            context = mock_run.call_args[0][0]
            assert context.parent_context["additional_context"] == "Focus on error handling"

    def test_execute_handles_failure(self, tmp_path):
        """Test execution handles subagent failure"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.side_effect = Exception("Subagent crashed")

            result = tool.execute(description="Failing task")

            assert result["success"] is False
            assert result["error_type"] == ErrorType.EXECUTION
            assert "crashed" in result["error"].lower()


class TestTaskToolHelpers:
    """Test TaskTool helper methods"""

    def test_get_task_status_not_found(self, tmp_path):
        """Test getting status of non-existent task"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        status = tool.get_task_status("nonexistent")
        assert status is None

    def test_list_active_tasks_empty(self, tmp_path):
        """Test listing active tasks when none exist"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        tasks = tool.list_active_tasks()
        assert tasks == []

    def test_subagent_prompt_generation(self, tmp_path):
        """Test subagent prompt generation"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        context = SubagentContext(
            task_id="test123",
            task_description="Find security vulnerabilities",
            parent_context={"additional_context": "Focus on SQL injection"},
            allowed_tools=["read_file", "search_files"],
            working_directory=tmp_path,
        )

        prompt = tool._get_subagent_prompt(context)

        assert "Find security vulnerabilities" in prompt
        assert "Focus on SQL injection" in prompt
        assert "read_file" in prompt
        assert "search_files" in prompt
        assert str(tmp_path) in prompt


class TestAllowedToolsEnforcement:
    """Test that allowed_tools is enforced via hooks"""

    def test_permission_hook_blocks_disallowed_tools(self):
        """Test that PermissionHook blocks tools not in allowed list"""
        from cortex.hooks import PreToolUseEvent

        # Create hook with whitelist
        hook = PermissionHook(allowed=["read_file", "list_files"])

        # Allowed tool should continue
        event1 = PreToolUseEvent(
            tool_name="read_file", arguments={"path": "test.txt"}, permission_mode="normal"
        )
        result1 = hook.execute(event1)
        assert result1.action == HookAction.CONTINUE

        # Disallowed tool should abort
        event2 = PreToolUseEvent(
            tool_name="write_file",
            arguments={"path": "test.txt", "content": "data"},
            permission_mode="normal",
        )
        result2 = hook.execute(event2)
        assert result2.action == HookAction.ABORT

    def test_subagent_uses_permission_hook(self, tmp_path):
        """Test that PermissionHook is correctly configured for subagents"""
        # This test verifies the integration by checking that
        # when allowed_tools is set, a PermissionHook would block disallowed tools

        # Create a hook manager like _run_subagent does
        from cortex.hooks import HookManager, PermissionHook, PreToolUseEvent, HookAction

        allowed_tools = ["read_file", "list_files"]
        subagent_hooks = HookManager()
        permission_hook = PermissionHook(allowed=allowed_tools)
        subagent_hooks.register(permission_hook)

        # Test that allowed tool passes
        event1 = PreToolUseEvent(
            tool_name="read_file", arguments={"path": "test.txt"}, permission_mode="normal"
        )
        result1 = subagent_hooks.dispatch(event1)
        assert result1.action == HookAction.CONTINUE

        # Test that disallowed tool is blocked
        event2 = PreToolUseEvent(
            tool_name="write_file",
            arguments={"path": "test.txt", "content": "data"},
            permission_mode="normal",
        )
        result2 = subagent_hooks.dispatch(event2)
        assert result2.action == HookAction.ABORT


class TestTaskToolIntegration:
    """Integration tests for TaskTool (requires mocking Ollama)"""

    def test_task_result_structure(self, tmp_path):
        """Test that task results have expected structure"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {
                "final_response": "Found 5 Python files",
                "messages_count": 3,
            }

            result = tool.execute(description="Count Python files")

            # Result fields are now under "data"
            assert result["success"] is True
            assert "task_id" in result["data"]
            assert "result" in result["data"]
            assert result["data"]["result"] == "Found 5 Python files"
            assert "iterations_used" in result["data"]
            assert "tools_called" in result["data"]
            assert "duration_seconds" in result["data"]

    def test_cleanup_after_task(self, tmp_path):
        """Test that tasks are cleaned up after completion"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.return_value = {"final_response": "Done"}

            result = tool.execute(description="Quick task")
            task_id = result["data"]["task_id"]  # task_id at top level

            # Task should be cleaned up
            assert task_id not in tool.active_tasks

    def test_cleanup_after_failure(self, tmp_path):
        """Test that tasks are cleaned up after failure"""
        console = Mock()
        tool = TaskTool(
            project_dir=tmp_path,
            permission_mode="normal",
            console=console,
        )

        with patch.object(tool, "_run_subagent") as mock_run:
            mock_run.side_effect = Exception("Failed")

            result = tool.execute(description="Failing task")

            # All tasks should be cleaned up
            assert len(tool.active_tasks) == 0
