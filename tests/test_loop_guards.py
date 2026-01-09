"""Tests for loop guard system"""

import pytest
from cortex.core.loop_guards import LoopGuard


def test_loop_guard_initialization():
    """Test loop guard initialization"""
    guard = LoopGuard(max_repeats=3)
    
    assert guard.max_repeats == 3
    assert len(guard.tool_call_history) == 0
    assert len(guard.error_history) == 0
    assert len(guard.unique_operations) == 0
    assert len(guard.files_read) == 0
    assert len(guard.files_written) == 0
    assert guard.iteration_count == 0


def test_record_tool_call():
    """Test recording tool calls"""
    guard = LoopGuard()
    
    guard.record_tool_call("read_file", {"path": "test.txt"})
    assert len(guard.tool_call_history) == 1
    assert guard.tool_call_history[0] == ("read_file", {"path": "test.txt"})


def test_check_repeated_tool_call():
    """Test detection of repeated tool calls"""
    guard = LoopGuard(max_repeats=2)
    
    # Record same call twice
    guard.record_tool_call("read_file", {"path": "test.txt"})
    guard.record_tool_call("read_file", {"path": "test.txt"})
    
    assert guard.check_repeated_tool_call("read_file", {"path": "test.txt"}) is True


def test_check_repeated_error():
    """Test detection of repeated errors"""
    guard = LoopGuard(max_repeats=2)
    
    error = {
        "success": False,
        "error": "File not found",
        "error_type": "not_found"
    }
    
    guard.record_error(error)
    guard.record_error(error)
    
    assert guard.check_repeated_error(error) is True


def test_record_operation():
    """Test recording unique operations"""
    guard = LoopGuard()
    
    guard.record_operation("read_file", {"path": "test.txt"})
    guard.record_operation("read_file", {"path": "test2.txt"})
    
    assert len(guard.unique_operations) == 2
    assert len(guard.files_read) == 2
    assert "test.txt" in guard.files_read
    assert "test2.txt" in guard.files_read


def test_record_write_operation():
    """Test recording write operations"""
    guard = LoopGuard()
    
    guard.record_operation("write_file", {"path": "output.txt", "content": "test"})
    
    assert len(guard.files_written) == 1
    assert "output.txt" in guard.files_written


def test_increment_iteration():
    """Test iteration counter"""
    guard = LoopGuard()
    
    assert guard.iteration_count == 0
    guard.increment_iteration()
    assert guard.iteration_count == 1
    guard.increment_iteration()
    assert guard.iteration_count == 2


def test_check_stuck_state():
    """Test stuck state detection"""
    guard = LoopGuard()
    
    # Not stuck initially
    assert guard.check_stuck_state() is False
    
    # Increment iterations without operations
    for _ in range(6):
        guard.increment_iteration()
    
    # Should be stuck (many iterations, no unique operations)
    assert guard.check_stuck_state() is True
    
    # Add an operation - should not be stuck
    guard.record_operation("read_file", {"path": "test.txt"})
    assert guard.check_stuck_state() is False


def test_check_progress():
    """Test progress checking"""
    guard = LoopGuard()
    
    # No progress initially
    assert guard.check_progress() is False
    
    # Add operations
    guard.record_operation("read_file", {"path": "test.txt"})
    assert guard.check_progress() is True


def test_reset():
    """Test resetting guard state"""
    guard = LoopGuard()
    
    guard.record_tool_call("read_file", {"path": "test.txt"})
    guard.record_error({"error": "test"})
    guard.record_operation("read_file", {"path": "test.txt"})
    guard.increment_iteration()
    
    guard.reset()
    
    assert len(guard.tool_call_history) == 0
    assert len(guard.error_history) == 0
    assert len(guard.unique_operations) == 0
    assert len(guard.files_read) == 0
    assert len(guard.files_written) == 0
    assert guard.iteration_count == 0
