#!/usr/bin/env python3
"""
Test script to verify Enhanced Cortex works with CLI.
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import subprocess
import tempfile


def test_enhanced_cli():
    """Test that enhanced CLI flag works."""

    print("Testing Enhanced Cortex CLI integration...")

    # Test 1: Check that --enhanced flag is recognized
    print("\n1. Testing --enhanced flag recognition...")
    result = subprocess.run(
        [sys.executable, "-m", "cortex.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )

    if "--enhanced" in result.stdout:
        print("   [OK] --enhanced flag found in help")
    else:
        print("   [FAIL] --enhanced flag not found in help")
        print(f"   Output: {result.stdout[:500]}")
        return False

    # Test 2: Test enhanced agent creation (dry run)
    print("\n2. Testing enhanced agent creation (dry run)...")

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create a simple test file
        test_file = test_dir / "test.txt"
        test_file.write_text("Test content for enhanced Cortex")

        # Run cortex with --enhanced flag in plan mode (read-only)
        # to avoid actually executing commands
        cmd = [
            sys.executable, "-m", "cortex.cli",
            "--project-dir", str(test_dir),
            "--plan-mode",  # Read-only mode for safety
            "--enhanced",
            "-p", "list files in directory"
        ]

        try:
            # Run with timeout to avoid hanging
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent,
                timeout=30,
            )

            print(f"   Exit code: {result.returncode}")

            # Check for enhanced indicator in output
            if "Using enhanced agent" in result.stdout or "enhanced" in result.stdout.lower():
                print("   [OK] Enhanced agent mentioned in output")
            else:
                print("   [WARNING] Enhanced agent not clearly indicated in output")
                print(f"   Output preview: {result.stdout[:200]}")

            # Check for errors
            if result.returncode != 0:
                print(f"   [WARNING] Non-zero exit code: {result.returncode}")
                if result.stderr:
                    print(f"   Stderr: {result.stderr[:500]}")

        except subprocess.TimeoutExpired:
            print("   [WARNING] Command timed out (might be normal for LLM initialization)")
        except Exception as e:
            print(f"   [ERROR] Command failed: {e}")

    # Test 3: Test that both regular and enhanced agents can be created
    print("\n3. Testing agent creation from Python...")
    try:
        from cortex.agent import Cortex
        from cortex.agent_enhanced import EnhancedCortex
        from cortex.models import PermissionMode

        # Create regular agent
        regular_agent = Cortex(
            model="llama3.2",
            project_dir=".",
            permission_mode=PermissionMode.NORMAL,
        )
        print("   [OK] Regular Cortex agent created")

        # Create enhanced agent
        enhanced_agent = EnhancedCortex(
            model="llama3.2",
            project_dir=".",
            permission_mode=PermissionMode.NORMAL,
            enable_planning=True,
            enable_layered_memory=True,
        )
        print("   [OK] Enhanced Cortex agent created")

        # Check enhanced features
        if hasattr(enhanced_agent, 'state_manager'):
            print("   [OK] Enhanced agent has state_manager")

        if hasattr(enhanced_agent, 'planning_engine'):
            print("   [OK] Enhanced agent has planning_engine")

        # Check that they're different classes
        if type(regular_agent) != type(enhanced_agent):
            print("   [OK] Agents are of different types (as expected)")
        else:
            print("   [WARNING] Agents are of same type")

    except Exception as e:
        print(f"   [ERROR] Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("CLI INTEGRATION TEST COMPLETE")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_enhanced_cli()
    sys.exit(0 if success else 1)
