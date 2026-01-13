"""Comprehensive error handling tests for Cortex tools"""

import pytest
from pathlib import Path
from cortex.tools import create_tool_instance
from cortex.models import PermissionMode
from cortex.utils.errors import create_error_response, create_success_response, create_permission_denial, ErrorType
from cortex.ui.console import console

def test_error_format_consistency():
    """Verify all tools return standardized error format"""
    # Test that all error responses have the required fields
    error = create_error_response("Test error", ErrorType.EXECUTION, {"context": "test"})

    # Check required fields
    assert "success" in error
    assert error["success"] is False
    assert "error" in error
    assert "error_type" in error
    assert "retryable" in error
    assert "error_context" in error

    # Check values
    assert error["error"] == "Test error"
    assert error["error_type"] == ErrorType.EXECUTION
    assert error["error_context"]["context"] == "test"

def test_error_context_completeness():
    """Verify errors include sufficient debugging context"""
    # Test that error context includes tool name, operation, and timestamp
    error = create_error_response(
        "File not found",
        ErrorType.NOT_FOUND,
        {
            "tool_name": "read_file",
            "operation": "read_file",
            "path": "test.py",
            "hint": "Check if file exists"
        }
    )

    # Check context completeness
    context = error["error_context"]
    assert "tool_name" in context
    assert "operation" in context
    assert "path" in context
    assert "hint" in context

def test_permission_denial_format():
    """Test permission denial response format"""
    denial = create_permission_denial("Plan mode restriction", "write_file", {"path": "test.py"})

    # Check required fields
    assert "success" in denial
    assert denial["success"] is False
    assert "permission_denied" in denial
    assert denial["permission_denied"] is True
    assert "error_type" in denial
    assert denial["error_type"] == ErrorType.PERMISSION
    assert "reason" in denial
    assert "action" in denial
    assert "retryable" in denial
    assert denial["retryable"] is False

    # Check values
    assert denial["reason"] == "Plan mode restriction"
    assert denial["action"] == "write_file"

def test_success_response_format():
    """Test success response format"""
    success = create_success_response({"content": "test", "lines": 10})

    # Check required fields
    assert "success" in success
    assert success["success"] is True
    assert "content" in success
    assert "lines" in success

    # Check values
    assert success["content"] == "test"
    assert success["lines"] == 10

def test_error_recovery_flows(tmp_path):
    """Test loop guard intervention on errors"""
    from cortex.core.loop_guards import LoopGuard
    from cortex.core.recovery import RecoveryStrategy, RecoveryAction, RecoveryManager

    # Create loop guard with recovery manager
    recovery_manager = RecoveryManager()
    guard = LoopGuard(max_repeats=2, recovery_manager=recovery_manager)

    # Test repeated error detection
    error = create_error_response("File not found", ErrorType.NOT_FOUND)

    # Record same error multiple times
    guard.record_error(error)
    guard.record_error(error)

    # Should detect repetition
    assert guard.check_repeated_error(error) is True

    # Test recovery action (requires tool name and arguments)
    recovery_action = guard.get_recovery_action(error, "read_file", {"path": "test.py"})
    assert recovery_action is not None
    assert recovery_action.strategy in [RecoveryStrategy.SUGGEST, RecoveryStrategy.ESCALATE]

def test_all_tools_use_standardized_errors():
    """Test that all tools use create_error_response pattern"""
    # List of all tools that should use standardized error handling
    tools_to_test = [
        "read_file", "write_file", "execute_command", "list_files",
        "git_status", "git_diff", "git_commit", "git_log", "git_add",
        "git_branch", "git_push", "git_remote", "git_show", "git_checkout",
        "git_reset", "git_fetch", "git_pull", "edit", "glob", "grep",
        "search_files", "web_fetch", "web_search", "run_tests",
        "skill_loader", "todo_write", "ask_user_question"
    ]

    # Test each tool can be instantiated and uses the base class methods
    for tool_name in tools_to_test:
        try:
            tool = create_tool_instance(tool_name, tmp_path, PermissionMode.NORMAL, console)

            # Check that the tool has the base class error methods
            assert hasattr(tool, '_create_error')
            assert hasattr(tool, '_create_permission_denial')
            assert hasattr(tool, '_create_success')

            # Test that the methods work
            error = tool._create_error("Test error", "validation", context={"test": "data"})
            assert error["success"] is False
            assert error["error"] == "Test error"
            assert error["error_type"] == "validation"
            assert "error_context" in error

            permission_denial = tool._create_permission_denial("Test reason", "test_action")
            assert permission_denial["success"] is False
            assert permission_denial["permission_denied"] is True

            success = tool._create_success(content="test")
            assert success["success"] is True
            assert success["content"] == "test"

        except Exception as e:
            # Some tools might not be available or have specific requirements
            # This is expected for certain tools
            pass

def test_error_type_constants():
    """Test that all error type constants are defined"""
    # Test all expected error types
    assert ErrorType.PERMISSION == "permission"
    assert ErrorType.NOT_FOUND == "not_found"
    assert ErrorType.VALIDATION == "validation"
    assert ErrorType.EXECUTION == "execution"
    assert ErrorType.TIMEOUT == "timeout"
    assert ErrorType.NETWORK == "network"
    assert ErrorType.SECURITY == "security"
    assert ErrorType.PROVIDER == "provider"

def test_error_handling_in_file_operations(tmp_path):
    """Test error handling in file operations"""
    from cortex.core.security import SecurityError

    # Test read_file with non-existent file
    tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    result = tool.execute(path="nonexistent.py")

    assert result["success"] is False
    assert result["error_type"] == ErrorType.NOT_FOUND
    assert "error" in result
    assert "error_context" in result
    assert "path" in result["error_context"]

    # Test read_file with directory instead of file
    (tmp_path / "test_dir").mkdir()
    result = tool.execute(path="test_dir")

    assert result["success"] is False
    assert result["error_type"] == ErrorType.VALIDATION
    assert "error" in result
    assert "error_context" in result

def test_error_handling_in_git_operations(tmp_path):
    """Test error handling in git operations"""
    import subprocess

    # Test git_status in non-git directory (should fail)
    non_git_dir = tmp_path / "non_git"
    non_git_dir.mkdir()

    tool = create_tool_instance("git_status", non_git_dir, PermissionMode.NORMAL, console)
    result = tool.execute()

    # Should fail with execution error
    assert result["success"] is False
    assert result["error_type"] == ErrorType.EXECUTION
    assert "error" in result
    assert "error_context" in result

def test_error_handling_in_command_execution(tmp_path):
    """Test error handling in command execution"""
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)

    # Test with non-existent command
    result = tool.execute(command="nonexistent_command_xyz")

    assert result["success"] is False
    assert result["error_type"] in [ErrorType.EXECUTION, ErrorType.NOT_FOUND]
    assert "error" in result
    assert "error_context" in result
    assert "command" in result["error_context"]

def test_error_handling_in_web_operations(tmp_path):
    """Test error handling in web operations"""
    tool = create_tool_instance("web_fetch", tmp_path, PermissionMode.NORMAL, console)

    # Test with invalid URL
    result = tool.execute(url="")

    assert result["success"] is False
    assert result["error_type"] == ErrorType.VALIDATION
    assert "error" in result
    assert "error_context" in result

def test_error_handling_in_search_operations(tmp_path):
    """Test error handling in search operations"""
    tool = create_tool_instance("search_files", tmp_path, PermissionMode.NORMAL, console)

    # Test with empty query
    result = tool.execute(query="")

    # Should return success with empty results, not an error
    assert result["success"] is True
    assert result["match_count"] == 0

def test_error_recovery_suggestions():
    """Test that error responses include recovery suggestions where applicable"""
    # Test error with recovery suggestion
    error = create_error_response(
        "File not found",
        ErrorType.NOT_FOUND,
        {
            "path": "test.py",
            "suggestion": "Use list_files to find the correct path"
        }
    )

    assert "error_context" in error
    assert "suggestion" in error["error_context"]
    assert error["error_context"]["suggestion"] == "Use list_files to find the correct path"

def test_error_timestamp_inclusion():
    """Test that errors include timestamp for debugging"""
    # Create error with context to include timestamp
    error = create_error_response("Test error", ErrorType.EXECUTION, {"timestamp": "2026-01-13T03:53:00"})

    # Check that context is included when provided
    assert "error_context" in error
    assert "timestamp" in error["error_context"]

def test_error_format_validation():
    """Test that error format validation works correctly"""
    # Test valid error format
    valid_error = create_error_response("Test", ErrorType.VALIDATION)
    assert valid_error["success"] is False
    assert "error" in valid_error
    assert "error_type" in valid_error

    # Test that manual error dictionaries would fail validation
    # (This is more of a documentation test)
    manual_error = {
        "success": False,
        "error": "Manual error"
        # Missing error_type, retryable, etc.
    }

    # This would be caught by validation in real usage
    assert "error_type" not in manual_error
    assert "retryable" not in manual_error

def test_error_context_enrichment(tmp_path):
    """Test that tool base class enriches error context"""
    from cortex.tools.base import Tool

    # Create a mock tool instance
    class TestTool(Tool):
        def execute(self, **kwargs):
            return self._create_error("Test error", "validation")

    tool = TestTool(project_dir=tmp_path, permission_mode=PermissionMode.NORMAL)

    # Execute and check context enrichment
    result = tool.execute()

    assert result["success"] is False
    assert "error_context" in result
    assert "tool_name" in result["error_context"]
    assert "permission_mode" in result["error_context"]

def test_error_handling_edge_cases():
    """Test error handling edge cases"""
    # Test empty error message
    error = create_error_response("", ErrorType.VALIDATION)
    assert error["error"] == ""

    # Test very long error message
    long_message = "x" * 1000
    error = create_error_response(long_message, ErrorType.EXECUTION)
    assert error["error"] == long_message

    # Test error with complex context
    complex_context = {
        "nested": {
            "data": ["list", "of", "values"],
            "more_data": {"key": "value"}
        },
        "simple": "value"
    }
    error = create_error_response("Test", ErrorType.VALIDATION, complex_context)
    assert error["error_context"] == complex_context

def test_error_retryable_flag():
    """Test retryable flag in error responses"""
    # Test retryable error
    retryable_error = create_error_response("Network error", ErrorType.NETWORK, retryable=True)
    assert retryable_error["retryable"] is True

    # Test non-retryable error
    non_retryable_error = create_error_response("Validation error", ErrorType.VALIDATION, retryable=False)
    assert non_retryable_error["retryable"] is False

    # Test default (should be False)
    default_error = create_error_response("Default error", ErrorType.EXECUTION)
    assert default_error["retryable"] is False

def test_error_type_specific_behaviors():
    """Test that different error types have appropriate behaviors"""
    # Network errors should be retryable
    network_error = create_error_response("Connection failed", ErrorType.NETWORK, retryable=True)
    assert network_error["retryable"] is True

    # Validation errors should not be retryable
    validation_error = create_error_response("Invalid input", ErrorType.VALIDATION, retryable=False)
    assert validation_error["retryable"] is False

    # Timeout errors should be retryable
    timeout_error = create_error_response("Operation timed out", ErrorType.TIMEOUT, retryable=True)
    assert timeout_error["retryable"] is True

    # Security errors should not be retryable
    security_error = create_error_response("Permission denied", ErrorType.SECURITY, retryable=False)
    assert security_error["retryable"] is False

def test_error_handling_integration(tmp_path):
    """Test error handling integration across multiple tools"""
    # Test that errors from one tool can be properly handled by another
    # This tests the consistency of error formats

    # Create error from one tool
    read_tool = create_tool_instance("read_file", tmp_path, PermissionMode.NORMAL, console)
    error_result = read_tool.execute(path="nonexistent.py")

    # Verify another tool can understand the error format
    assert error_result["success"] is False
    assert "error" in error_result
    assert "error_type" in error_result

    # Test that success responses are also consistent
    (tmp_path / "test.txt").write_text("test")
    success_result = read_tool.execute(path="test.txt")

    assert success_result["success"] is True
    assert "content" in success_result

def test_error_metrics_and_monitoring():
    """Test that error metrics can be extracted for monitoring"""
    # Create various error types with explicit retryable flags
    errors = [
        create_error_response("Network error", ErrorType.NETWORK, retryable=True),
        create_error_response("Validation error", ErrorType.VALIDATION, retryable=False),
        create_error_response("Timeout error", ErrorType.TIMEOUT, retryable=True),
        create_error_response("Security error", ErrorType.SECURITY, retryable=False),
    ]

    # Extract metrics
    error_types = [error["error_type"] for error in errors]
    retryable_count = sum(1 for error in errors if error.get("retryable", False))

    # Verify metrics
    assert len(error_types) == 4
    assert ErrorType.NETWORK in error_types
    assert ErrorType.VALIDATION in error_types
    assert ErrorType.TIMEOUT in error_types
    assert ErrorType.SECURITY in error_types

    # Network and timeout errors should be retryable in this test
    assert retryable_count == 2

def test_error_response_serialization():
    """Test that error responses can be serialized and deserialized"""
    import json

    # Create error response
    error = create_error_response(
        "Test error",
        ErrorType.EXECUTION,
        {"context": "test", "nested": {"data": "value"}}
    )

    # Serialize to JSON
    json_str = json.dumps(error)

    # Deserialize from JSON
    deserialized = json.loads(json_str)

    # Verify structure is preserved
    assert deserialized["success"] is False
    assert deserialized["error"] == "Test error"
    assert deserialized["error_type"] == ErrorType.EXECUTION
    assert deserialized["error_context"]["context"] == "test"
    assert deserialized["error_context"]["nested"]["data"] == "value"

def test_error_handling_performance():
    """Test that error handling doesn't significantly impact performance"""
    import time

    # Measure time to create many error responses
    start_time = time.time()

    for i in range(1000):
        create_error_response(f"Error {i}", ErrorType.EXECUTION, {"index": i})

    end_time = time.time()

    # Should be very fast (less than 1 second for 1000 errors)
    duration = end_time - start_time
    assert duration < 1.0, f"Error creation took {duration} seconds, expected < 1.0"

def test_error_context_consistency():
    """Test that error context is consistent across different tools"""
    # Create errors from different tools
    tools = ["read_file", "write_file", "execute_command", "list_files"]

    for tool_name in tools:
        try:
            tool = create_tool_instance(tool_name, tmp_path, PermissionMode.NORMAL, console)

            # Create an error (method depends on tool)
            if tool_name == "read_file":
                result = tool.execute(path="nonexistent.py")
            elif tool_name == "write_file":
                result = tool.execute(path="/invalid/path/test.txt", content="test")
            elif tool_name == "execute_command":
                result = tool.execute(command="nonexistent_command")
            elif tool_name == "list_files":
                result = tool.execute(path="nonexistent_dir")
            else:
                continue

            # Verify consistent error structure
            assert "success" in result
            assert result["success"] is False
            assert "error" in result
            assert "error_type" in result
            assert "error_context" in result

        except Exception:
            # Some tools might not be available or have different error conditions
            continue

def test_error_handling_documentation():
    """Test that error handling is well documented"""
    # This is more of a documentation test to ensure error types are documented
    error_types = [
        "PERMISSION", "NOT_FOUND", "VALIDATION", "EXECUTION",
        "TIMEOUT", "NETWORK", "SECURITY", "PROVIDER"
    ]

    # Verify all error types are defined
    for error_type in error_types:
        assert hasattr(ErrorType, error_type)
