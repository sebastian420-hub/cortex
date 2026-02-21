#!/usr/bin/env python3
"""
Test file to demonstrate Cortex agent capabilities.
This file was created by the Cortex AI assistant.
"""

def demonstrate_features():
    """Showcase various Python features."""
    print("Cortex Agent Capabilities Demo")
    print("=" * 40)

    # List comprehension
    squares = [x**2 for x in range(1, 6)]
    print(f"Squares: {squares}")

    # Dictionary
    features = {
        "File Operations": "read/write files",
        "Command Execution": "run shell commands",
        "Git Integration": "status, diff, commit",
        "Search": "find text across files",
        "Testing": "run test suites",
    }

    print("\nAvailable Features:")
    for feature, description in features.items():
        print(f"  • {feature}: {description}")

    return True

if __name__ == "__main__":
    demonstrate_features()
    print("\nDemonstration complete!")
