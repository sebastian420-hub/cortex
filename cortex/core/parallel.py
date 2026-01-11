"""Parallel tool execution with intelligent batching."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# Tools that are safe to run in parallel (read-only operations)
PARALLELIZABLE_TOOLS = frozenset(
    [
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
    ]
)

# Tools that modify state and must run sequentially
SERIALIZED_TOOLS = frozenset(
    [
        "write_file",
        "edit",
        "execute_command",
        "git_commit",
        "run_tests",
    ]
)


class ExecutionMode(Enum):
    """Execution mode for a tool."""

    PARALLEL = "parallel"
    SERIAL = "serial"


@dataclass
class ToolCall:
    """Represents a single tool call to be executed."""

    id: str
    name: str
    arguments: Dict[str, Any]
    index: int  # Original order in batch


@dataclass
class ToolResult:
    """Result of a tool execution."""

    id: str
    name: str
    result: Dict[str, Any]
    index: int  # Original order
    success: bool
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class BatchResult:
    """Result of executing a batch of tools."""

    results: List[ToolResult]
    parallel_count: int
    serial_count: int
    total_time_ms: float
    parallel_time_ms: float = 0.0


class ParallelToolExecutor:
    """
    Executes tools with intelligent parallelization.

    Features:
    - Separates parallelizable (read-only) from serial (state-modifying) tools
    - Executes parallel tools concurrently using ThreadPoolExecutor
    - Maintains result ordering for conversation consistency
    - Configurable max workers
    - Thread-safe operation

    Usage:
        executor = ParallelToolExecutor(execute_fn, max_workers=4)

        # Execute a batch of tool calls
        results = executor.execute_batch([
            ToolCall(id="1", name="read_file", arguments={"path": "a.py"}, index=0),
            ToolCall(id="2", name="read_file", arguments={"path": "b.py"}, index=1),
            ToolCall(id="3", name="write_file", arguments={...}, index=2),
        ])

        # Results are returned in original order
    """

    def __init__(
        self,
        execute_fn: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        max_workers: int = 4,
        enabled: bool = True,
    ):
        """
        Initialize ParallelToolExecutor.

        Args:
            execute_fn: Function to execute a single tool (name, args) -> result
            max_workers: Maximum number of concurrent workers
            enabled: Whether parallel execution is enabled
        """
        self.execute_fn = execute_fn
        self.max_workers = max_workers
        self.enabled = enabled

        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()

        # Statistics
        self._total_batches = 0
        self._total_parallel = 0
        self._total_serial = 0

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def get_execution_mode(self, tool_name: str) -> ExecutionMode:
        """
        Determine if a tool can be parallelized.

        Args:
            tool_name: Name of the tool

        Returns:
            ExecutionMode.PARALLEL if safe to parallelize, SERIAL otherwise
        """
        if tool_name in PARALLELIZABLE_TOOLS:
            return ExecutionMode.PARALLEL
        return ExecutionMode.SERIAL

    def execute_batch(
        self,
        tool_calls: List[ToolCall],
        pre_hook: Optional[Callable[[ToolCall], bool]] = None,
        post_hook: Optional[Callable[[ToolCall, ToolResult], None]] = None,
    ) -> BatchResult:
        """
        Execute a batch of tool calls with intelligent parallelization.

        Args:
            tool_calls: List of tool calls to execute
            pre_hook: Optional hook called before each tool (return False to skip)
            post_hook: Optional hook called after each tool with result

        Returns:
            BatchResult with all results in original order
        """
        if not tool_calls:
            return BatchResult(results=[], parallel_count=0, serial_count=0, total_time_ms=0.0)

        start_time = datetime.now()

        # If disabled, execute all sequentially
        if not self.enabled:
            results = self._execute_sequential(tool_calls, pre_hook, post_hook)
            total_time = (datetime.now() - start_time).total_seconds() * 1000
            return BatchResult(
                results=results,
                parallel_count=0,
                serial_count=len(tool_calls),
                total_time_ms=total_time,
            )

        # Separate into parallel and serial groups
        parallel_calls = []
        serial_calls = []

        for call in tool_calls:
            mode = self.get_execution_mode(call.name)
            if mode == ExecutionMode.PARALLEL:
                parallel_calls.append(call)
            else:
                serial_calls.append(call)

        results: List[ToolResult] = []
        parallel_time_ms = 0.0

        # Execute parallel tools concurrently
        if parallel_calls:
            parallel_start = datetime.now()
            parallel_results = self._execute_parallel(parallel_calls, pre_hook, post_hook)
            results.extend(parallel_results)
            parallel_time_ms = (datetime.now() - parallel_start).total_seconds() * 1000

        # Execute serial tools sequentially
        if serial_calls:
            serial_results = self._execute_sequential(serial_calls, pre_hook, post_hook)
            results.extend(serial_results)

        # Sort results back to original order
        results.sort(key=lambda r: r.index)

        total_time = (datetime.now() - start_time).total_seconds() * 1000

        # Update statistics
        with self._lock:
            self._total_batches += 1
            self._total_parallel += len(parallel_calls)
            self._total_serial += len(serial_calls)

        logger.debug(
            f"Batch executed: {len(parallel_calls)} parallel, {len(serial_calls)} serial, "
            f"{total_time:.1f}ms total, {parallel_time_ms:.1f}ms parallel"
        )

        return BatchResult(
            results=results,
            parallel_count=len(parallel_calls),
            serial_count=len(serial_calls),
            total_time_ms=total_time,
            parallel_time_ms=parallel_time_ms,
        )

    def _execute_parallel(
        self,
        tool_calls: List[ToolCall],
        pre_hook: Optional[Callable[[ToolCall], bool]],
        post_hook: Optional[Callable[[ToolCall, ToolResult], None]],
    ) -> List[ToolResult]:
        """Execute tools in parallel."""
        executor = self._get_executor()
        futures: Dict[Future, ToolCall] = {}

        for call in tool_calls:
            # Check pre-hook
            if pre_hook and not pre_hook(call):
                # Skip this tool
                continue

            future = executor.submit(self._execute_single, call)
            futures[future] = call

        results = []
        for future in as_completed(futures):
            call = futures[future]
            try:
                result = future.result()
                results.append(result)

                # Call post-hook
                if post_hook:
                    post_hook(call, result)

            except Exception as e:
                logger.error(f"Error executing {call.name}: {e}")
                error_result = ToolResult(
                    id=call.id,
                    name=call.name,
                    result={"error": str(e)},
                    index=call.index,
                    success=False,
                    error=str(e),
                )
                results.append(error_result)

                if post_hook:
                    post_hook(call, error_result)

        return results

    def _execute_sequential(
        self,
        tool_calls: List[ToolCall],
        pre_hook: Optional[Callable[[ToolCall], bool]],
        post_hook: Optional[Callable[[ToolCall, ToolResult], None]],
    ) -> List[ToolResult]:
        """Execute tools sequentially."""
        results = []

        for call in tool_calls:
            # Check pre-hook
            if pre_hook and not pre_hook(call):
                # Skip this tool
                continue

            try:
                result = self._execute_single(call)
                results.append(result)

                # Call post-hook
                if post_hook:
                    post_hook(call, result)

            except Exception as e:
                logger.error(f"Error executing {call.name}: {e}")
                error_result = ToolResult(
                    id=call.id,
                    name=call.name,
                    result={"error": str(e)},
                    index=call.index,
                    success=False,
                    error=str(e),
                )
                results.append(error_result)

                if post_hook:
                    post_hook(call, error_result)

        return results

    def _execute_single(self, call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        start = datetime.now()

        try:
            result = self.execute_fn(call.name, call.arguments)
            execution_time = (datetime.now() - start).total_seconds() * 1000

            success = result.get("success", True) if isinstance(result, dict) else True

            return ToolResult(
                id=call.id,
                name=call.name,
                result=result,
                index=call.index,
                success=success,
                execution_time_ms=execution_time,
            )
        except Exception as e:
            execution_time = (datetime.now() - start).total_seconds() * 1000
            return ToolResult(
                id=call.id,
                name=call.name,
                result={"error": str(e)},
                index=call.index,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "max_workers": self.max_workers,
                "total_batches": self._total_batches,
                "total_parallel_calls": self._total_parallel,
                "total_serial_calls": self._total_serial,
                "parallelizable_tools": list(PARALLELIZABLE_TOOLS),
                "serialized_tools": list(SERIALIZED_TOOLS),
            }

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor."""
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


def is_parallelizable(tool_name: str) -> bool:
    """Check if a tool is safe to parallelize."""
    return tool_name in PARALLELIZABLE_TOOLS


def is_serialized(tool_name: str) -> bool:
    """Check if a tool must be serialized."""
    return tool_name in SERIALIZED_TOOLS
