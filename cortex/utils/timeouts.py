"""Timeout management utilities for Cortex tools"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class TimeoutConfig:
    """
    Configuration for operation timeouts across tools.

    All timeout values are in seconds.
    """

    default: int = 30  # General command timeout
    git: int = 10  # Git operations timeout
    test: int = 120  # Test execution timeout
    search: int = 60  # File search timeout
    long_running: int = 300  # Long-running operations (5 min)

    # Per-tool overrides (tool_name -> timeout)
    tool_overrides: Dict[str, int] = field(default_factory=dict)

    # Tool name to category mapping
    _tool_categories: Dict[str, str] = field(
        default_factory=lambda: {
            "execute_command": "default",
            "git_status": "git",
            "git_diff": "git",
            "git_commit": "git",
            "git_log": "git",
            "run_tests": "test",
            "search_files": "search",
            "list_files": "default",
            "read_file": "default",
            "write_file": "default",
        },
        repr=False,
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeoutConfig":
        """
        Create TimeoutConfig from dictionary.

        Missing values use defaults. Unknown keys are ignored.

        Args:
            data: Dictionary with timeout values

        Returns:
            TimeoutConfig instance
        """
        return cls(
            default=data.get("default", 30),
            git=data.get("git", 10),
            test=data.get("test", 120),
            search=data.get("search", 60),
            long_running=data.get("long_running", 300),
            tool_overrides=data.get("tool_overrides", {}),
        )

    def get_timeout(self, tool_name: str, operation: Optional[str] = None) -> int:
        """
        Get timeout for a specific tool.

        Priority:
        1. Per-tool override if configured
        2. Category-based timeout (git, test, search, etc.)
        3. Default timeout

        Args:
            tool_name: Name of the tool (e.g., "execute_command", "git_status")
            operation: Optional operation hint for fine-grained control

        Returns:
            Timeout value in seconds
        """
        # Check per-tool override first
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]

        # Check category-based timeout
        category = self._tool_categories.get(tool_name, "default")
        category_timeouts = {
            "default": self.default,
            "git": self.git,
            "test": self.test,
            "search": self.search,
            "long_running": self.long_running,
        }

        return category_timeouts.get(category, self.default)

    def with_override(self, tool_name: str, timeout: int) -> "TimeoutConfig":
        """
        Create new config with a specific tool override.

        Args:
            tool_name: Tool to override
            timeout: Timeout value in seconds

        Returns:
            New TimeoutConfig with the override applied
        """
        new_overrides = dict(self.tool_overrides)
        new_overrides[tool_name] = timeout
        return TimeoutConfig(
            default=self.default,
            git=self.git,
            test=self.test,
            search=self.search,
            long_running=self.long_running,
            tool_overrides=new_overrides,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {
            "default": self.default,
            "git": self.git,
            "test": self.test,
            "search": self.search,
            "long_running": self.long_running,
        }
        if self.tool_overrides:
            result["tool_overrides"] = self.tool_overrides
        return result


# Default timeout configuration instance
DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()
