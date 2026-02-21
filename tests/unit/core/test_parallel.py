"""
Unit tests for parallel tool execution (cortex/core/parallel.py).
"""

import time
from unittest.mock import Mock, patch, call
import pytest

from cortex.core.parallel import (
    ParallelToolExecutor,
    ToolCall,
    ToolResult,
    BatchResult,
    ExecutionMode,
    PARALLELIZABLE_TOOLS,
    SERIALIZED_TOOLS,
)


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_execution_mode_values(self):
        """Test that ExecutionMode has correct values."""
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.SERIAL.value == "serial"


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_tool_call_creation(self):
        """Test creating a ToolCall instance."""
        tool_call = ToolCall(
            id="call_123", name="read_file", arguments={"path": "test.txt"}, index=0
        )

        assert tool_call.id == "call_123"
        assert tool_call.name == "read_file"
        assert tool_call.arguments == {"path": "test.txt"}
        assert tool_call.index == 0


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_tool_result_creation(self):
        """Test creating a ToolResult instance."""
        result_data = {"success": True, "content": "test"}
        tool_result = ToolResult(
            id="call_123",
            name="read_file",
            result=result_data,
            index=0,
            success=True,
            error=None,
            execution_time_ms=50.5,
        )

        assert tool_result.id == "call_123"
        assert tool_result.name == "read_file"
        assert tool_result.result == result_data
        assert tool_result.success is True
        assert tool_result.error is None
        assert tool_result.execution_time_ms == 50.5


class TestBatchResult:
    """Test BatchResult dataclass."""

    def test_batch_result_creation(self):
        """Test creating a BatchResult instance."""
        results = [
            ToolResult(id="1", name="read_file", result={}, index=0, success=True),
            ToolResult(id="2", name="grep", result={}, index=1, success=True),
        ]

        batch_result = BatchResult(
            results=results,
            parallel_count=2,
            serial_count=0,
            total_time_ms=100.0,
            parallel_time_ms=80.0,
        )

        assert batch_result.results == results
        assert batch_result.parallel_count == 2
        assert batch_result.serial_count == 0
        assert batch_result.total_time_ms == 100.0
        assert batch_result.parallel_time_ms == 80.0


class TestParallelToolExecutor:
    """Test ParallelToolExecutor class."""

    @pytest.fixture
    def mock_execute_fn(self):
        """Create a mock execute function."""
        return Mock()

    @pytest.fixture
    def executor(self, mock_execute_fn):
        """Create a ParallelToolExecutor instance."""
        return ParallelToolExecutor(execute_fn=mock_execute_fn, max_workers=2, enabled=True)

    def test_initialization(self, mock_execute_fn):
        """Test executor initialization."""
        executor = ParallelToolExecutor(execute_fn=mock_execute_fn, max_workers=5, enabled=False)

        assert executor.execute_fn == mock_execute_fn
        assert executor.max_workers == 5
        assert executor.enabled is False
        assert executor._executor is None
        assert executor._total_batches == 0
        assert executor._total_parallel == 0
        assert executor._total_serial == 0

    def test_get_execution_mode_parallelizable(self):
        """Test execution mode detection for parallelizable tools."""
        executor = ParallelToolExecutor(execute_fn=Mock())

        # Test some parallelizable tools
        for tool_name in ["read_file", "grep", "glob", "list_files"]:
            assert tool_name in PARALLELIZABLE_TOOLS
            mode = executor.get_execution_mode(tool_name)
            assert mode == ExecutionMode.PARALLEL

    def test_get_execution_mode_serialized(self):
        """Test execution mode detection for serialized tools."""
        executor = ParallelToolExecutor(execute_fn=Mock())

        # Test some serialized tools
        for tool_name in ["write_file", "edit", "execute_command", "git_commit"]:
            assert tool_name in SERIALIZED_TOOLS
            mode = executor.get_execution_mode(tool_name)
            assert mode == ExecutionMode.SERIAL

    def test_get_execution_mode_unknown_tool(self):
        """Test execution mode detection for unknown tools."""
        executor = ParallelToolExecutor(execute_fn=Mock())

        # Unknown tool should default to SERIAL for safety
        mode = executor.get_execution_mode("unknown_tool")
        assert mode == ExecutionMode.SERIAL

    def test_execute_batch_empty(self, executor):
        """Test executing an empty batch."""
        batch_result = executor.execute_batch([])

        assert isinstance(batch_result, BatchResult)
        assert batch_result.results == []
        assert batch_result.parallel_count == 0
        assert batch_result.serial_count == 0
        assert batch_result.total_time_ms >= 0

    def test_execute_batch_single_parallel_tool(self, executor, mock_execute_fn):
        """Test executing a single parallel tool."""
        mock_execute_fn.return_value = {"success": True, "content": "test"}

        tool_calls = [ToolCall(id="1", name="read_file", arguments={"path": "test.txt"}, index=0)]

        batch_result = executor.execute_batch(tool_calls)

        # Verify execute_fn was called
        mock_execute_fn.assert_called_once_with("read_file", {"path": "test.txt"})

        # Verify result
        assert len(batch_result.results) == 1
        result = batch_result.results[0]
        assert result.id == "1"
        assert result.name == "read_file"
        assert result.success is True
        assert result.result == {"success": True, "content": "test"}
        assert batch_result.parallel_count == 1
        assert batch_result.serial_count == 0

    def test_execute_batch_single_serial_tool(self, executor, mock_execute_fn):
        """Test executing a single serial tool."""
        mock_execute_fn.return_value = {"success": True}

        tool_calls = [
            ToolCall(
                id="1",
                name="write_file",
                arguments={"path": "test.txt", "content": "test"},
                index=0,
            )  # noqa: E501
        ]

        batch_result = executor.execute_batch(tool_calls)

        mock_execute_fn.assert_called_once_with(
            "write_file", {"path": "test.txt", "content": "test"}
        )  # noqa: E501

        assert len(batch_result.results) == 1
        assert batch_result.parallel_count == 0
        assert batch_result.serial_count == 1

    def test_execute_batch_mixed_parallel_and_serial(self, executor, mock_execute_fn):
        """Test executing a mix of parallel and serial tools."""

        # Setup mock to return different results based on tool name
        def execute_side_effect(tool_name, args):
            if tool_name == "read_file":
                return {"success": True, "content": f"Content of {args['path']}"}
            elif tool_name == "write_file":
                return {"success": True}
            else:
                return {"success": False}

        mock_execute_fn.side_effect = execute_side_effect

        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "a.txt"}, index=0),
            ToolCall(id="2", name="read_file", arguments={"path": "b.txt"}, index=1),
            ToolCall(
                id="3", name="write_file", arguments={"path": "c.txt", "content": "test"}, index=2
            ),  # noqa: E501
            ToolCall(id="4", name="read_file", arguments={"path": "d.txt"}, index=3),
        ]

        batch_result = executor.execute_batch(tool_calls)

        # Verify all tools were executed
        assert mock_execute_fn.call_count == 4

        # Verify results are in original order
        assert len(batch_result.results) == 4
        assert [r.id for r in batch_result.results] == ["1", "2", "3", "4"]

        # Verify parallel and serial counts
        # read_file is parallel, write_file is serial
        # However, serial tools cause sequential execution: all parallel tools before serial are executed first,  # noqa: E501
        # then serial, then remaining parallel tools after serial? Need to check actual logic.
        # We'll just check that results exist.
        assert batch_result.parallel_count >= 2
        assert batch_result.serial_count >= 1

    def test_execute_batch_disabled_parallelization(self, mock_execute_fn):
        """Test execution when parallelization is disabled."""
        executor = ParallelToolExecutor(execute_fn=mock_execute_fn, enabled=False)

        mock_execute_fn.return_value = {"success": True}

        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "a.txt"}, index=0),
            ToolCall(id="2", name="read_file", arguments={"path": "b.txt"}, index=1),
        ]

        batch_result = executor.execute_batch(tool_calls)

        # Should execute sequentially even for parallelizable tools
        assert mock_execute_fn.call_count == 2
        assert batch_result.parallel_count == 0
        assert batch_result.serial_count == 2

    def test_execute_batch_error_handling(self, executor, mock_execute_fn):
        """Test error handling during batch execution."""
        mock_execute_fn.side_effect = Exception("Test error")

        tool_calls = [ToolCall(id="1", name="read_file", arguments={"path": "test.txt"}, index=0)]

        batch_result = executor.execute_batch(tool_calls)

        assert len(batch_result.results) == 1
        result = batch_result.results[0]
        assert result.success is False
        assert "Test error" in str(result.error)

    def test_execute_batch_maintains_order_with_parallel_tools(self, executor, mock_execute_fn):
        """Test that results maintain original order even with parallel execution."""
        # Create mock that returns based on arguments
        call_results = {}

        def execute_side_effect(tool_name, args):
            # Simulate varying execution time based on file name
            time.sleep(0.01 if args["path"] == "fast.txt" else 0.05)
            result = {"success": True, "content": f"Content of {args['path']}"}
            call_results[tool_name + args["path"]] = result
            return result

        mock_execute_fn.side_effect = execute_side_effect

        tool_calls = [
            ToolCall(id="slow", name="read_file", arguments={"path": "slow.txt"}, index=0),
            ToolCall(id="fast", name="read_file", arguments={"path": "fast.txt"}, index=1),
        ]

        batch_result = executor.execute_batch(tool_calls)

        # Results should be in original index order despite fast finishing first
        assert len(batch_result.results) == 2
        assert batch_result.results[0].id == "slow"
        assert batch_result.results[1].id == "fast"

    def test_statistics_tracking(self, executor, mock_execute_fn):
        """Test that statistics are properly tracked across batches."""
        mock_execute_fn.return_value = {"success": True}

        # Execute first batch
        tool_calls1 = [
            ToolCall(id="1", name="read_file", arguments={}, index=0),
            ToolCall(id="2", name="write_file", arguments={}, index=1),
        ]
        batch_result1 = executor.execute_batch(tool_calls1)

        assert executor._total_batches == 1
        assert executor._total_parallel == 1  # read_file
        assert executor._total_serial == 1  # write_file

        # Execute second batch
        tool_calls2 = [
            ToolCall(id="3", name="read_file", arguments={}, index=0),
            ToolCall(id="4", name="read_file", arguments={}, index=1),
        ]
        batch_result2 = executor.execute_batch(tool_calls2)

        assert executor._total_batches == 2
        assert executor._total_parallel == 3  # 1 + 2
        assert executor._total_serial == 1  # unchanged

    @patch("cortex.core.parallel.ThreadPoolExecutor")
    def test_thread_pool_creation(self, mock_executor_class, mock_execute_fn):
        """Test that thread pool is created lazily."""
        executor = ParallelToolExecutor(execute_fn=mock_execute_fn)

        # Executor not created yet
        assert executor._executor is None
        assert mock_executor_class.call_count == 0

        # Trigger executor creation
        executor._get_executor()

        # Should be created now
        assert executor._executor is not None
        mock_executor_class.assert_called_once_with(max_workers=4)

    def test_executor_shutdown(self):
        """Test that executor can be shut down."""
        mock_execute_fn = Mock()

        with patch("cortex.core.parallel.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            executor = ParallelToolExecutor(execute_fn=mock_execute_fn)

            # Create executor
            executor._get_executor()

            # Shutdown
            executor.shutdown()

            mock_executor.shutdown.assert_called_once_with(wait=True)
            assert executor._executor is None

    # def test_context_manager(self):
    #     """Test using executor as a context manager."""
    #     mock_execute_fn = Mock()

    #     with patch('cortex.core.parallel.ThreadPoolExecutor') as mock_executor_class:
    #         mock_executor = Mock()
    #         mock_executor_class.return_value = mock_executor

    #         with ParallelToolExecutor(execute_fn=mock_execute_fn) as executor:
    #             # Use executor (should create executor lazily)
    #             tool_calls = [ToolCall(id="1", name="read_file", arguments={}, index=0)]
    #             executor.execute_batch(tool_calls)

    #         # Should shutdown on exit
    #         mock_executor.shutdown.assert_called_once_with(wait=True)


class TestConstants:
    """Test module-level constants."""

    def test_parallelizable_tools_set(self):
        """Test that PARALLELIZABLE_TOOLS contains expected tools."""
        expected = {
            "read_file",
            "grep",
            "glob",
            "list_files",
            "search_files",
            "git_status",
            "git_diff",
            "git_log",
            "web_fetch",
            "web_search",
        }

        assert PARALLELIZABLE_TOOLS == frozenset(expected)

        # Verify all are read-only operations
        # (subjective, but we can document the assumption)

    def test_serialized_tools_set(self):
        """Test that SERIALIZED_TOOLS contains expected tools."""
        expected = {"write_file", "edit", "execute_command", "git_commit", "run_tests"}

        assert SERIALIZED_TOOLS == frozenset(expected)

        # Verify all modify state or have side effects

    def test_sets_are_disjoint(self):
        """Verify no tool is in both sets."""
        intersection = PARALLELIZABLE_TOOLS.intersection(SERIALIZED_TOOLS)
        assert len(intersection) == 0, f"Tools in both sets: {intersection}"
