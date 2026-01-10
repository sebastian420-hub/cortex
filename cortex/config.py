"""Configuration management for Cortex"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object


# Default timeout values (in seconds)
DEFAULT_TIMEOUTS = {
    "default": 30,
    "git": 10,
    "test": 120,
    "search": 60,
    "long_running": 300,
}

# Default session retention settings
DEFAULT_SESSION_RETENTION = {
    "max_age_days": 30,
    "max_count": 100,
    "max_total_size_mb": 500,
    "cleanup_on_startup": False,  # Disabled by default for backward compat
    "warn_on_truncation": True,
}

# Default error recovery settings
DEFAULT_ERROR_RECOVERY = {
    "max_repeats": 3,
    "stuck_threshold": 5,
    "recovery_strategy": "suggest",  # "suggest", "escalate", "continue"
    "max_recovery_attempts": 2,
    "buffer_size": 10,
    "enable_smart_recovery": False,  # Disabled by default for backward compat
}


class AgentConfig:
    """
    Configuration for Cortex.

    Supports loading from YAML files, environment variables, or direct initialization.
    Configuration hierarchy: defaults < file config < environment variables.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        permission_mode: str = "normal",
        max_iterations: int = 15,
        max_iterations_continue_default: bool = False,
        max_iterations_continue_amount: int = 10,
        max_tokens: int = 100000,
        keep_recent_messages: int = 20,
        auto_save: bool = False,
        # Output settings
        output_format: str = "text",
        # Hook settings
        hooks: Optional[List[Dict[str, Any]]] = None,
        hooks_enabled: bool = True,
        # Tool settings
        tools_disabled: Optional[List[str]] = None,
        tools_plugins: Optional[List[str]] = None,
        # Subagent settings
        subagent_max_iterations: int = 10,
        subagent_allowed_tools: Optional[List[str]] = None,
        # Provider settings
        provider: Optional[str] = None,
        # Timeout settings (new)
        timeouts: Optional[Dict[str, Any]] = None,
        tool_timeouts: Optional[Dict[str, int]] = None,
        # Session retention settings (new)
        session_retention: Optional[Dict[str, Any]] = None,
        # Error recovery settings (new)
        error_recovery: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # Core settings
        self.model = model
        self.permission_mode = permission_mode
        self.max_iterations = max_iterations
        self.max_iterations_continue_default = max_iterations_continue_default
        self.max_iterations_continue_amount = max_iterations_continue_amount
        self.max_tokens = max_tokens
        self.keep_recent_messages = keep_recent_messages
        self.auto_save = auto_save

        # Output settings
        self.output_format = output_format

        # Hook settings
        self.hooks = hooks or []
        self.hooks_enabled = hooks_enabled

        # Tool settings
        self.tools_disabled = tools_disabled or []
        self.tools_plugins = tools_plugins or []

        # Subagent settings
        self.subagent_max_iterations = subagent_max_iterations
        self.subagent_allowed_tools = subagent_allowed_tools or [
            "read_file", "list_files", "search_files"
        ]

        # Provider settings
        self.provider = provider  # Auto-detected if None

        # Timeout settings (merge with defaults)
        self.timeouts = {**DEFAULT_TIMEOUTS, **(timeouts or {})}
        self.tool_timeouts = tool_timeouts or {}

        # Session retention settings (merge with defaults)
        self.session_retention = {**DEFAULT_SESSION_RETENTION, **(session_retention or {})}

        # Error recovery settings (merge with defaults)
        self.error_recovery = {**DEFAULT_ERROR_RECOVERY, **(error_recovery or {})}

        # Extra settings for extensibility
        self.extra = kwargs

    def get_timeout_config(self) -> "TimeoutConfig":
        """Get TimeoutConfig instance from settings."""
        from .utils.timeouts import TimeoutConfig
        config = TimeoutConfig.from_dict(self.timeouts)
        # Apply per-tool overrides
        for tool_name, timeout in self.tool_timeouts.items():
            config = config.with_override(tool_name, timeout)
        return config

    def get_hooks_config(self) -> Dict[str, Any]:
        """Get configuration for HookManager."""
        return {
            "hooks": self.hooks,
            "enabled": self.hooks_enabled,
        }

    def get_tools_config(self) -> Dict[str, Any]:
        """Get configuration for ToolRegistry."""
        return {
            "tools": {
                "disabled": self.tools_disabled,
                "plugins": self.tools_plugins,
            }
        }
    
    @classmethod
    def from_file(cls, config_path: Path) -> "AgentConfig":
        """Load configuration from YAML file"""
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            return cls(**config_data)
        except Exception as e:
            print(f"Warning: Error loading config file: {e}")
            return cls()
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables"""
        # Build timeouts from env vars
        timeouts = {}
        if os.getenv("CORTEX_TIMEOUT_DEFAULT"):
            timeouts["default"] = int(os.getenv("CORTEX_TIMEOUT_DEFAULT"))
        if os.getenv("CORTEX_TIMEOUT_GIT"):
            timeouts["git"] = int(os.getenv("CORTEX_TIMEOUT_GIT"))
        if os.getenv("CORTEX_TIMEOUT_TEST"):
            timeouts["test"] = int(os.getenv("CORTEX_TIMEOUT_TEST"))
        if os.getenv("CORTEX_TIMEOUT_SEARCH"):
            timeouts["search"] = int(os.getenv("CORTEX_TIMEOUT_SEARCH"))

        # Build session retention from env vars
        session_retention = {}
        if os.getenv("CORTEX_SESSION_MAX_AGE_DAYS"):
            session_retention["max_age_days"] = int(os.getenv("CORTEX_SESSION_MAX_AGE_DAYS"))
        if os.getenv("CORTEX_SESSION_MAX_COUNT"):
            session_retention["max_count"] = int(os.getenv("CORTEX_SESSION_MAX_COUNT"))
        if os.getenv("CORTEX_SESSION_CLEANUP_ON_STARTUP"):
            session_retention["cleanup_on_startup"] = os.getenv("CORTEX_SESSION_CLEANUP_ON_STARTUP").lower() == "true"

        # Build error recovery from env vars
        error_recovery = {}
        if os.getenv("CORTEX_RECOVERY_ENABLED"):
            error_recovery["enable_smart_recovery"] = os.getenv("CORTEX_RECOVERY_ENABLED").lower() == "true"

        return cls(
            model=os.getenv("CORTEX_MODEL", "llama3.2"),
            permission_mode=os.getenv("CORTEX_MODE", "normal"),
            max_iterations=int(os.getenv("CORTEX_MAX_ITERATIONS", "15")),
            max_iterations_continue_default=bool(os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_DEFAULT", "false").lower() == "true"),
            max_iterations_continue_amount=int(os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_AMOUNT", "10")),
            max_tokens=int(os.getenv("CORTEX_MAX_TOKENS", "100000")),
            provider=os.getenv("CORTEX_PROVIDER", None),
            timeouts=timeouts if timeouts else None,
            session_retention=session_retention if session_retention else None,
            error_recovery=error_recovery if error_recovery else None,
        )
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AgentConfig":
        """
        Load configuration from file, environment, or defaults.
        Environment variables override file config.
        """
        # Start with defaults
        config = cls()

        # Load from file if provided
        if config_path and config_path.exists():
            file_config = cls.from_file(config_path)
            # Merge file config - core settings
            config.model = file_config.model
            config.permission_mode = file_config.permission_mode
            config.max_iterations = file_config.max_iterations
            config.max_iterations_continue_default = file_config.max_iterations_continue_default
            config.max_iterations_continue_amount = file_config.max_iterations_continue_amount
            config.max_tokens = file_config.max_tokens
            config.keep_recent_messages = file_config.keep_recent_messages
            config.auto_save = file_config.auto_save
            # New settings
            config.output_format = file_config.output_format
            config.hooks = file_config.hooks
            config.hooks_enabled = file_config.hooks_enabled
            config.tools_disabled = file_config.tools_disabled
            config.tools_plugins = file_config.tools_plugins
            config.subagent_max_iterations = file_config.subagent_max_iterations
            config.subagent_allowed_tools = file_config.subagent_allowed_tools
            config.provider = file_config.provider
            # Robustness settings
            config.timeouts = file_config.timeouts
            config.tool_timeouts = file_config.tool_timeouts
            config.session_retention = file_config.session_retention
            config.error_recovery = file_config.error_recovery

        # Override with environment variables
        env_config = cls.from_env()
        if os.getenv("CORTEX_MODEL"):
            config.model = env_config.model
        if os.getenv("CORTEX_MODE"):
            config.permission_mode = env_config.permission_mode
        if os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_DEFAULT"):
            config.max_iterations_continue_default = env_config.max_iterations_continue_default
        if os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_AMOUNT"):
            config.max_iterations_continue_amount = env_config.max_iterations_continue_amount
        if os.getenv("CORTEX_OUTPUT_FORMAT"):
            config.output_format = os.getenv("CORTEX_OUTPUT_FORMAT")
        if os.getenv("CORTEX_HOOKS_ENABLED"):
            config.hooks_enabled = os.getenv("CORTEX_HOOKS_ENABLED").lower() == "true"
        if os.getenv("CORTEX_PROVIDER"):
            config.provider = os.getenv("CORTEX_PROVIDER")

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "model": self.model,
            "permission_mode": self.permission_mode,
            "max_iterations": self.max_iterations,
            "max_iterations_continue_default": self.max_iterations_continue_default,
            "max_iterations_continue_amount": self.max_iterations_continue_amount,
            "max_tokens": self.max_tokens,
            "keep_recent_messages": self.keep_recent_messages,
            "auto_save": self.auto_save,
            "output_format": self.output_format,
            "hooks": self.hooks,
            "hooks_enabled": self.hooks_enabled,
            "tools_disabled": self.tools_disabled,
            "tools_plugins": self.tools_plugins,
            "subagent_max_iterations": self.subagent_max_iterations,
            "subagent_allowed_tools": self.subagent_allowed_tools,
            "provider": self.provider,
            # Robustness settings
            "timeouts": self.timeouts,
            "tool_timeouts": self.tool_timeouts,
            "session_retention": self.session_retention,
            "error_recovery": self.error_recovery,
        }

