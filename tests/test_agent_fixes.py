"""Tests for agent fixes: loop guards, error formats, and edge cases"""

import pytest
from pathlib import Path
from cortex.agent import Cortex
from cortex.core.loop_guards import LoopGuard
from cortex.utils.errors import create_error_response, create_success_response, ErrorType
from cortex.models import PermissionMode


def test_loop_guard_repeated_tool_call():
    """Test loop guard detects repeated tool calls"""
    guard = LoopGuard(max_repeats=3)
    
    # Call same tool 3 times
    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_tool_call("read_file", {"path": "test.py"})
    
    # Should detect repetition
    assert guard.check_repeated_tool_call("read_file", {"path": "test.py"}) is True
    
    # Different arguments should not trigger
    assert guard.check_repeated_tool_call("read_file", {"path": "other.py"}) is False


def test_loop_guard_repeated_error():
    """Test loop guard detects repeated errors"""
    guard = LoopGuard(max_repeats=3)
    
    error = create_error_response("File not found", ErrorType.NOT_FOUND)
    
    # Record same error 3 times
    guard.record_error(error)
    guard.record_error(error)
    guard.record_error(error)
    
    # Should detect repetition
    assert guard.check_repeated_error(error) is True


def test_error_response_format():
    """Test standardized error response format"""
    error = create_error_response(
        "File not found",
        ErrorType.NOT_FOUND,
        {"path": "test.py"}
    )
    
    assert error["success"] is False
    assert error["error"] == "File not found"
    assert error["error_type"] == ErrorType.NOT_FOUND
    assert "error_context" in error
    assert error["error_context"]["path"] == "test.py"


def test_success_response_format():
    """Test standardized success response format"""
    success = create_success_response({
        "content": "test",
        "lines": 10
    })
    
    assert success["success"] is True
    assert success["content"] == "test"
    assert success["lines"] == 10


def test_error_type_constants():
    """Test error type constants are defined"""
    from cortex.utils.errors import ErrorType
    
    assert ErrorType.PERMISSION == "permission"
    assert ErrorType.NOT_FOUND == "not_found"
    assert ErrorType.VALIDATION == "validation"
    assert ErrorType.EXECUTION == "execution"
    assert ErrorType.TIMEOUT == "timeout"
    assert ErrorType.NETWORK == "network"
    assert ErrorType.SECURITY == "security"


def test_loop_guard_reset():
    """Test loop guard reset functionality"""
    guard = LoopGuard()
    
    guard.record_tool_call("read_file", {"path": "test.py"})
    guard.record_error(create_error_response("Error", ErrorType.EXECUTION))
    
    assert len(guard.tool_call_history) == 1
    assert len(guard.error_history) == 1
    
    guard.reset()
    
    assert len(guard.tool_call_history) == 0
    assert len(guard.error_history) == 0


def test_loop_guard_history_limit():
    """Test loop guard limits history size"""
    guard = LoopGuard()
    
    # Add more than 10 calls
    for i in range(15):
        guard.record_tool_call("read_file", {"path": f"test{i}.py"})
    
    # Should only keep last 10
    assert len(guard.tool_call_history) == 10
    # First 5 should be removed
    assert ("read_file", {"path": "test0.py"}) not in guard.tool_call_history
    # Last 10 should be present
    assert ("read_file", {"path": "test14.py"}) in guard.tool_call_history

