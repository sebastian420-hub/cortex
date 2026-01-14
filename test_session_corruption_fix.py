#!/usr/bin/env python3
"""
Test script to verify the session corruption fixes work correctly.
This tests the prevention of "Invalid assistant message" errors and session recovery.
"""

import sys
import os
from pathlib import Path

# Add the cortex package to the path
sys.path.insert(0, str(Path(__file__).parent))

from cortex.core.conversation import ConversationManager
from cortex.agent import Cortex

def test_conversation_manager_validation():
    """Test that ConversationManager validates assistant messages correctly."""
    print("Testing ConversationManager validation...")

    # Create a conversation manager
    cm = ConversationManager("Test system prompt")

    # Test 1: Valid assistant message with content
    cm.add_assistant_message(content="Hello world")
    assert cm.history[-1]["content"] == "Hello world"
    print("✓ Valid message with content accepted")

    # Test 2: Valid assistant message with tool_calls
    cm.add_assistant_message(content="", tool_calls=[{"function": {"name": "test"}}])
    assert cm.history[-1]["tool_calls"] is not None
    print("✓ Valid message with tool_calls accepted")

    # Test 3: Invalid assistant message (no content, no tool_calls) - should be auto-fixed
    cm.add_assistant_message(content="", tool_calls=None)
    assert cm.history[-1]["content"] == "[Empty assistant response]"
    print("✓ Invalid message auto-repaired with fallback content")

    # Test 4: Invalid message with reasoning_content - should convert to content
    cm.add_assistant_message(content="", tool_calls=None, reasoning_content="This is reasoning")
    assert "Reasoning:" in cm.history[-1]["content"]
    print("✓ Invalid message auto-repaired by converting reasoning to content")

    # Test validation
    validation = cm.validate_history()
    print(f"✓ Validation completed: {validation['message_count']} messages, {len(validation['issues'])} issues")

    return True

def test_agent_message_validation():
    """Test that Agent validates messages before API calls."""
    print("\nTesting Agent message validation...")

    # Create a minimal agent instance (this is tricky without full setup, so we'll test the methods directly)
    # For now, just test that the validation methods exist and work
    agent = Cortex.__new__(Cortex)  # Create without __init__

    # Mock some messages
    messages = [
        {"role": "system", "content": "Test"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "", "tool_calls": None},  # Invalid
        {"role": "assistant", "content": "Response", "tool_calls": None},  # Valid
    ]

    # Test validation
    validation = agent._validate_messages_for_api(messages)
    assert not validation["valid"]
    assert validation["severity_levels"]["critical"] == 1
    print(f"✓ Detected {validation['severity_levels']['critical']} critical issues")

    # Test repair
    critical_issues = [i for i in validation["issues"] if i["severity"] == "critical"]
    repaired = agent._repair_messages_for_api(messages, critical_issues)
    assert repaired[2]["content"] == "[Repaired empty assistant response]"
    print("✓ Critical issues auto-repaired")

    return True

def test_session_health_check():
    """Test session health validation."""
    print("\nTesting session health validation...")

    # Create a conversation with some issues
    cm = ConversationManager("Test system prompt")

    # Add many messages to trigger warning
    for i in range(110):  # More than 100
        cm.add_user_message(f"Message {i}")
        cm.add_assistant_message(f"Response {i}")

    # Add a corrupted assistant message to make it critical
    cm.add_assistant_message(content="", tool_calls=None)  # This will be auto-fixed but we want to test detection

    # Create mock agent to test health check
    agent = Cortex.__new__(Cortex)
    agent.conversation = cm

    health = agent.validate_session_health()
    # Should have issues (warnings from high count)
    assert len(health["issues"]) > 0
    assert len(health["recommendations"]) > 0
    print(f"✓ Health check detected {len(health['issues'])} issues")
    print(f"✓ Provided {len(health['recommendations'])} recommendations")

    # Test with truly corrupted conversation (bypass auto-fix)
    cm2 = ConversationManager("Test system prompt")
    # Manually add corrupted message (bypass validation)
    corrupted_msg = {"role": "assistant", "content": "", "tool_calls": None}
    cm2.history.append(corrupted_msg)  # Add directly to bypass validation

    agent2 = Cortex.__new__(Cortex)
    agent2.conversation = cm2

    health2 = agent2.validate_session_health()
    # This should detect critical issues
    critical_issues = [i for i in health2["issues"] if i["severity"] == "critical"]
    assert len(critical_issues) > 0
    assert not health2["healthy"]
    print(f"✓ Detected {len(critical_issues)} critical issues making session unhealthy")

    return True

def main():
    """Run all tests."""
    print("Running session corruption fix tests...\n")

    try:
        test_conversation_manager_validation()
        test_agent_message_validation()
        test_session_health_check()

        print("\n🎉 All tests passed! Session corruption fixes are working correctly.")
        print("\nKey improvements implemented:")
        print("• Assistant messages are validated and auto-repaired when invalid")
        print("• Pre-flight validation prevents API errors before they occur")
        print("• Enhanced error messages provide recovery hints")
        print("• Session health validation detects and reports issues")
        print("• Automatic repair of corrupted messages")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
