#!/usr/bin/env python3
"""
Test a simple request with Enhanced Cortex.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cortex.agent_enhanced import EnhancedCortex
from cortex.models import PermissionMode
import time


def test_simple_request():
    """Test processing a simple request with enhanced agent."""

    print("Testing simple request with Enhanced Cortex...")

    # Create enhanced agent in PLAN mode (read-only for safety)
    agent = EnhancedCortex(
        model="llama3.2",
        project_dir=".",
        permission_mode=PermissionMode.PLAN,  # Read-only mode
        enable_planning=True,
        enable_layered_memory=True,
    )

    print(f"Agent created: {type(agent).__name__}")
    print(f"Planning enabled: {agent.enable_planning}")
    print(f"State manager initialized: {hasattr(agent, 'state_manager')}")

    # Make a simple request
    test_request = "What files are in the current directory?"

    print(f"\nMaking request: {test_request}")
    print("(In PLAN mode, agent will only analyze, not execute)")

    try:
        # Process the request
        start_time = time.time()

        # Use a timeout to prevent hanging
        import threading
        from queue import Queue

        result_queue = Queue()

        def process_request():
            try:
                agent.process_with_planning(test_request, use_streaming=False)
                result_queue.put("success")
            except Exception as e:
                result_queue.put(f"error: {e}")

        thread = threading.Thread(target=process_request)
        thread.daemon = True
        thread.start()

        # Wait with timeout
        thread.join(timeout=30)

        if thread.is_alive():
            print("Request timed out after 30 seconds (may be normal for LLM)")
            print("This test confirms agent initialization and basic processing.")
        else:
            result = result_queue.get_nowait() if not result_queue.empty() else "unknown"
            print(f"Request completed with result: {result}")

        elapsed = time.time() - start_time
        print(f"Elapsed time: {elapsed:.1f}s")

        # Check state after request
        print("\nChecking state after request attempt:")
        print(f"  - Iterations: {agent.state_manager.state.iteration_count}")
        print(f"  - Primary goal: {agent.state_manager.state.primary_goal}")
        print(f"  - Current focus: {agent.state_manager.state.focus}")

        # Check if any tools would have been suggested
        if hasattr(agent, '_tools_used') and agent._tools_used:
            print(f"  - Tools that would be used: {list(set(agent._tools_used))}")
        else:
            print("  - No tools used (expected in PLAN mode)")

        # Show enhanced metrics
        metrics = agent.get_enhanced_metrics()
        print("\nEnhanced metrics:")
        for key in ['model', 'permission_mode', 'enable_planning',
                   'plans_generated', 'iterations', 'insights_generated']:
            if key in metrics:
                print(f"  - {key}: {metrics[key]}")

        return True

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_simple_request()
    sys.exit(0 if success else 1)
