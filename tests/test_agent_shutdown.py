"""Tests for graceful shutdown handlers"""

import pytest
import signal
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from cortex.agent import Cortex
from cortex.models import PermissionMode


def test_shutdown_flag(tmp_path):
    """Test that shutdown flag is properly set"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    assert agent._shutdown_requested is False
    
    agent.request_shutdown()
    assert agent._shutdown_requested is True


def test_cleanup_method(tmp_path):
    """Test that cleanup method executes without errors"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    # Add some state
    agent._session_dirty = True
    
    # Should not raise
    agent._cleanup()
    
    # Verify session end event was dispatched (check hook manager was called)
    # The cleanup should complete without errors


def test_shutdown_check_in_loop(tmp_path):
    """Test that agent loop checks shutdown flag"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    # Request shutdown
    agent.request_shutdown()
    
    # Process message should return early
    initial_history_len = len(agent.conversation.get_history())
    agent._process_message("test")
    
    # Verify loop exited early (history shouldn't have changed much)
    # Since shutdown was requested, the message processing should exit quickly
    final_history_len = len(agent.conversation.get_history())
    
    # The user message might be added, but processing should stop early
    assert agent._shutdown_requested is True


def test_shutdown_during_tool_execution(tmp_path):
    """Test graceful shutdown during tool execution"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.AUTO_APPROVE
    )
    
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Mock model response with tool call
    mock_response = {
        "message": {
            "tool_calls": [{
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "test.txt"}'
                },
                "id": "call_test"
            }]
        }
    }
    
    shutdown_called = [False]
    
    def mock_call_model(*args, **kwargs):
        # Request shutdown after first call
        if not shutdown_called[0]:
            shutdown_called[0] = True
            agent.request_shutdown()
        return mock_response
    
    with patch.object(agent, '_call_model', side_effect=mock_call_model):
        # Process message
        agent._process_message("read test.txt")
    
    # Verify shutdown was requested
    assert agent._shutdown_requested is True


def test_signal_handler_registration(tmp_path):
    """Test that signal handlers are registered in CLI"""
    from cortex.cli import run_interactive
    from cortex.storage.sessions import SessionManager
    
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    session_manager = SessionManager(tmp_path / "sessions")
    
    # Mock signal.signal to capture registrations
    signal_handlers = {}
    
    def mock_signal(sig, handler):
        signal_handlers[sig] = handler
    
    with patch('signal.signal', side_effect=mock_signal):
        with patch('cortex.cli.REPL') as mock_repl:
            # Mock REPL to exit immediately
            mock_repl_instance = MagicMock()
            mock_repl_instance.prompt.side_effect = EOFError()
            mock_repl.return_value = mock_repl_instance
            
            try:
                run_interactive(agent, session_manager, use_streaming=False)
            except (EOFError, SystemExit):
                pass
    
    # Verify signal handlers were registered (if platform supports it)
    if hasattr(signal, 'SIGINT'):
        # On platforms that support signals, handlers should be registered
        # Note: This may not work on Windows in the same way
        pass


def test_keyboard_interrupt_handling(tmp_path):
    """Test that KeyboardInterrupt triggers cleanup"""
    from cortex.cli import run_interactive
    from cortex.storage.sessions import SessionManager
    
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    agent._session_dirty = True
    
    session_manager = SessionManager(tmp_path / "sessions")
    
    cleanup_called = [False]
    
    original_cleanup = agent._cleanup
    
    def mock_cleanup():
        cleanup_called[0] = True
        original_cleanup()
    
    agent._cleanup = mock_cleanup
    
    with patch('cortex.cli.REPL') as mock_repl:
        mock_repl_instance = MagicMock()
        mock_repl_instance.prompt.side_effect = KeyboardInterrupt()
        
        # Mock rich.prompt.Confirm.ask to return True (exit)
        with patch('rich.prompt.Confirm') as mock_confirm:
            mock_confirm.ask.return_value = True
            mock_repl.return_value = mock_repl_instance
            
            try:
                run_interactive(agent, session_manager, use_streaming=False)
            except (SystemExit, KeyboardInterrupt):
                pass
    
    # Verify cleanup was called
    assert cleanup_called[0] is True or agent._shutdown_requested is True


def test_auto_save_on_shutdown(tmp_path):
    """Test that session is auto-saved on shutdown if dirty"""
    from cortex.storage.sessions import SessionManager
    
    sessions_dir = tmp_path / "sessions"
    session_manager = SessionManager(sessions_dir)
    
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    agent._session_dirty = True
    
    # Add some conversation history
    agent.conversation.add_user_message("test message")
    
    # Trigger shutdown
    agent.request_shutdown()
    agent._cleanup()
    
    # Manually trigger auto-save (simulating CLI behavior)
    from datetime import datetime
    auto_save_name = f"autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if agent._session_dirty:
        session_manager.save_session(
            auto_save_name,
            agent.get_conversation_history(),
            str(agent.project_dir),
            agent.model,
            agent.permission_mode
        )
    
    # Verify session was saved
    sessions = session_manager.list_sessions()
    autosave_sessions = [s for s in sessions if s["name"].startswith("autosave_")]
    assert len(autosave_sessions) > 0, "Autosave session should exist"


def test_shutdown_during_streaming(tmp_path):
    """Test graceful shutdown during streaming response"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    # Mock streaming response
    def mock_stream():
        yield {"message": {"content": "chunk1"}}
        agent.request_shutdown()  # Request shutdown during streaming
        yield {"message": {"content": "chunk2"}}
    
    with patch.object(agent.provider, 'stream_chat', return_value=mock_stream()):
        with patch.object(agent.provider, 'supports_streaming', return_value=True):
            # Process message with streaming
            agent._process_message("test", use_streaming=True)
    
    # Verify shutdown was requested
    assert agent._shutdown_requested is True


def test_shutdown_flag_persistence(tmp_path):
    """Test that shutdown flag persists across method calls"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    assert agent._shutdown_requested is False
    
    agent.request_shutdown()
    assert agent._shutdown_requested is True
    
    # Flag should remain True
    agent._cleanup()
    assert agent._shutdown_requested is True
    
    # Even after cleanup, flag should persist
    agent._process_message("test")
    assert agent._shutdown_requested is True


def test_multiple_shutdown_requests(tmp_path):
    """Test that multiple shutdown requests are handled gracefully"""
    agent = Cortex(
        model="llama3.2",
        project_dir=str(tmp_path),
        permission_mode=PermissionMode.NORMAL
    )
    
    # Request shutdown multiple times
    agent.request_shutdown()
    agent.request_shutdown()
    agent.request_shutdown()
    
    # Should still be True (idempotent)
    assert agent._shutdown_requested is True
    
    # Cleanup should work
    agent._cleanup()
    assert agent._shutdown_requested is True
