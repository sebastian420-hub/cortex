#!/usr/bin/env python3
"""
Demo script for Enhanced Cortex with planning and layered memory.

This script demonstrates the enhanced capabilities of Cortex:
1. Planning and goal decomposition
2. Layered memory architecture
3. State management
4. Enhanced context awareness
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cortex.agent_enhanced import EnhancedCortex
from cortex.models import PermissionMode
from cortex.config import AgentConfig


def demonstrate_enhanced_cortex():
    """Demonstrate enhanced Cortex capabilities."""
    
    print("=" * 80)
    print("DEMONSTRATING ENHANCED CORTEX WITH PLANNING AND LAYERED MEMORY")
    print("=" * 80)
    
    # Create enhanced agent
    print("\n1. Creating EnhancedCortex agent...")
    agent = EnhancedCortex(
        model="llama3.2",  # Using a simple local model
        project_dir=".",
        permission_mode=PermissionMode.NORMAL,
        enable_planning=True,
        enable_layered_memory=True,
    )
    
    print(f"   - Model: {agent.model}")
    print(f"   - Planning enabled: {agent.enable_planning}")
    print(f"   - Layered memory enabled: {agent.enable_layered_memory}")
    
    # Show enhanced system prompt
    print("\n2. Enhanced system prompt includes planning and memory guidance")
    system_prompt = agent.conversation.history[0]["content"]
    enhanced_section = "# ENHANCED PLANNING AND MEMORY CAPABILITIES"
    if enhanced_section in system_prompt:
        print("   [OK] Enhanced guidance found in system prompt")
        # Extract a snippet
        start_idx = system_prompt.find(enhanced_section)
        snippet = system_prompt[start_idx:start_idx + 500]
        print(f"   Snippet: {snippet[:200]}...")
    
    # Demonstrate state manager
    print("\n3. State Manager Initialized")
    print(f"   - Session ID: {agent.state_manager.state.session_id}")
    print(f"   - Initial focus: {agent.state_manager.state.focus}")
    
    # Set a goal
    print("\n4. Setting a primary goal...")
    test_goal = "Explore the current directory structure"
    agent.state_manager.set_primary_goal(test_goal)
    print(f"   - Primary goal: {agent.state_manager.state.primary_goal}")
    print(f"   - Working memory task: {agent.state_manager.state.working_memory.current_task}")
    
    # Record a tool execution (simulated)
    print("\n5. Simulating tool execution and memory recording...")
    agent.state_manager.record_tool_execution(
        tool_name="list_files",
        arguments={"path": "."},
        result={"success": True, "data": {"files": ["demo.py", "README.md"]}},
    )
    
    print(f"   - Tool chain length: {len(agent.state_manager.state.tool_chain)}")
    print(f"   - Successful tools: {agent.state_manager.state.successful_tools}")
    
    # Record insights and patterns
    print("\n6. Recording insights and patterns...")
    agent.state_manager.record_insight("Python files are organized in modules")
    agent.state_manager.record_pattern(
        pattern="Use list_files for initial exploration",
        context="Directory structure discovery",
        effectiveness=0.9,
    )
    
    print(f"   - Insights generated: {agent.state_manager.state.insights_generated}")
    print(f"   - Patterns recognized: {agent.state_manager.state.patterns_recognized}")
    
    # Get state summary
    print("\n7. State summary for LLM context:")
    state_summary = agent.state_manager.get_state_summary()
    print(f"   Summary length: {len(state_summary)} characters")
    print(f"   Preview: {state_summary[:150]}...")
    
    # Get enhanced metrics
    print("\n8. Enhanced metrics:")
    metrics = agent.get_enhanced_metrics()
    for key, value in metrics.items():
        if isinstance(value, (str, int, float, bool)):
            print(f"   - {key}: {value}")
    
    # Demonstrate working memory
    print("\n9. Working memory operations...")
    file_id = agent.state_manager.state.working_memory.add_file_context(
        file_path="demo.py",
        summary="Demonstration script for enhanced Cortex",
        relevance_score=0.8,
    )
    print(f"   - Added file context with ID: {file_id}")
    print(f"   - Files in working memory: {len(agent.state_manager.state.working_memory.get_files())}")
    
    # Demonstrate session memory
    print("\n10. Session memory operations...")
    agent.state_manager.state.session_memory.record_failed_approach(
        approach="Tried to read non-existent file",
        error="File not found",
        root_cause="Incorrect file path",
        alternative_suggested="Check file existence first",
    )
    
    failed_approaches = agent.state_manager.state.session_memory.failed_approaches
    print(f"   - Failed approaches recorded: {len(failed_approaches)}")
    if failed_approaches:
        print(f"   - Most recent: {failed_approaches[-1].approach}")
    
    # Clear state for next task
    print("\n11. Clearing enhanced state (keeping base conversation)...")
    agent.clear_enhanced_state()
    print(f"   - Plans generated after clear: {agent.plans_generated}")
    print(f"   - Working memory items: {len(agent.state_manager.state.working_memory.items)}")
    
    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    
    print("\nKey enhancements demonstrated:")
    print("1. State management with goal tracking")
    print("2. Layered memory (working, session)")
    print("3. Tool execution tracking and learning")
    print("4. Insight and pattern extraction")
    print("5. Enhanced context for LLM")
    print("\nThese enhancements enable more structured, self-aware,")
    print("and adaptive agent behavior following the mental model.")
    
    return agent


if __name__ == "__main__":
    try:
        demonstrate_enhanced_cortex()
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()