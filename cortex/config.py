"""Configuration management for Cortex"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import yaml

if TYPE_CHECKING:
    from .utils.timeouts import TimeoutConfig

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

# Default file cache settings
DEFAULT_FILE_CACHE = {
    "enabled": True,
    "max_entries": 100,
    "max_size_mb": 50.0,
}

# Default transaction settings
DEFAULT_TRANSACTIONS = {
    "enabled": True,
    "max_backups": 10,
    "backup_dir": None,  # Uses .cortex/backups by default
}

# Default parallel execution settings
DEFAULT_PARALLEL_EXECUTION = {
    "enabled": True,
    "max_workers": 4,
    "batch_size": 10,
}

# Default rate limiting settings
DEFAULT_RATE_LIMIT = {
    "enabled": False,  # Disabled by default for backward compatibility
    "requests_per_minute": 60,
    "tokens_per_minute": 100000,
    "burst_multiplier": 1.5,
}

# Default cache warming settings
DEFAULT_CACHE_WARMING = {
    "enabled": False,  # Disabled by default for backward compatibility
    "source": "git_history",  # "git_history", "git_tracked", "directory"
    "patterns": ["*.py", "*.md", "*.yaml", "*.yml"],  # File patterns to cache
    "max_files": 50,  # Maximum files to pre-cache
    "directory": None,  # Directory to search (None = current directory)
}

# Default Redis cache settings
DEFAULT_REDIS_CACHE = {
    "enabled": False,  # Disabled by default (requires Redis installation)
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,
    "ttl": 3600,  # 1 hour
    "max_entries": 100,
    "max_size_mb": 50.0,
    "fallback_to_local": True,  # Fall back to local cache on Redis failure
}

# Default routing settings
DEFAULT_ROUTING = {
    "enabled": False,  # Disabled by default for backward compatibility
    "mode": "rule_based",  # "rule_based", "manual", "auto"
    "prefer_local_models": True,
    "allow_cloud_fallback": True,
    "task_analysis_enabled": True,
    "cost_optimization_enabled": True,
    "transparency_enabled": True,
    "cache_decisions": True,
    "log_decisions": False,
    "log_file": None,
}

# Default context compression/summarization settings
DEFAULT_CONTEXT_COMPRESSION = {
    "summarization_threshold": 0.75,  # Trigger at 75% (was 0.8)
    "compression_ratio": 0.2,  # Target 20% of original
    "preserve_tool_results": True,
    "preserve_errors": True,
    "large_file_threshold": 5000,  # Tokens threshold for large file warnings
}


class AgentConfig:
    """
    Configuration for Cortex.

    Supports loading from YAML files, environment variables, or direct initialization.
    Configuration hierarchy: defaults < file config < environment variables.
    """

    def __init__(
        self,
        model: str = "moonshotai/kimi-k2.5",
        permission_mode: str = "normal",
        max_iterations: int = 15,
        max_iterations_continue_default: bool = False,
        max_iterations_continue_amount: int = 10,
        max_tokens: Optional[int] = None,  # None = auto-detect from model
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
        # MCP settings (new)
        mcp_servers: Optional[Dict[str, Dict[str, Any]]] = None,
        mcp_enabled: bool = False,
        # Timeout settings (new)
        timeouts: Optional[Dict[str, Any]] = None,
        tool_timeouts: Optional[Dict[str, int]] = None,
        # Session retention settings (new)
        session_retention: Optional[Dict[str, Any]] = None,
        # Error recovery settings (new)
        error_recovery: Optional[Dict[str, Any]] = None,
        # File cache settings (new)
        file_cache: Optional[Dict[str, Any]] = None,
        # Cache warming settings (new)
        cache_warming: Optional[Dict[str, Any]] = None,
        # Redis cache settings (new)
        redis_cache: Optional[Dict[str, Any]] = None,
        # Transaction settings (new)
        transactions: Optional[Dict[str, Any]] = None,
        # Parallel execution settings (new)
        parallel_execution: Optional[Dict[str, Any]] = None,
        # Rate limiting settings (new)
        rate_limit: Optional[Dict[str, Any]] = None,
        # Routing settings (new)
        routing: Optional[Dict[str, Any]] = None,
        **kwargs,
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
            "read_file",
            "list_files",
            "search_files",
        ]

        # Provider settings
        self.provider = provider  # Auto-detected if None

        # MCP settings
        self.mcp_servers = mcp_servers or {}
        self.mcp_enabled = mcp_enabled

        # Timeout settings (merge with defaults)
        self.timeouts = {**DEFAULT_TIMEOUTS, **(timeouts or {})}
        self.tool_timeouts = tool_timeouts or {}

        # Session retention settings (merge with defaults)
        self.session_retention = {**DEFAULT_SESSION_RETENTION, **(session_retention or {})}

        # Error recovery settings (merge with defaults)
        self.error_recovery = {**DEFAULT_ERROR_RECOVERY, **(error_recovery or {})}

        # File cache settings (merge with defaults)
        self.file_cache = {**DEFAULT_FILE_CACHE, **(file_cache or {})}

        # Cache warming settings (merge with defaults)
        self.cache_warming = {**DEFAULT_CACHE_WARMING, **(cache_warming or {})}

        # Redis cache settings (merge with defaults)
        self.redis_cache = {**DEFAULT_REDIS_CACHE, **(redis_cache or {})}

        # Transaction settings (merge with defaults)
        self.transactions = {**DEFAULT_TRANSACTIONS, **(transactions or {})}

        # Parallel execution settings (merge with defaults)
        self.parallel_execution = {**DEFAULT_PARALLEL_EXECUTION, **(parallel_execution or {})}

        # Rate limiting settings (merge with defaults)
        self.rate_limit = {**DEFAULT_RATE_LIMIT, **(rate_limit or {})}

        # Routing settings (merge with defaults)
        self.routing = {**DEFAULT_ROUTING, **(routing or {})}

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

    def get_file_cache_config(self) -> Dict[str, Any]:
        """Get configuration for FileCache."""
        return self.file_cache

    def get_transactions_config(self) -> Dict[str, Any]:
        """Get configuration for TransactionManager."""
        return self.transactions

    def get_parallel_execution_config(self) -> Dict[str, Any]:
        """Get configuration for ParallelToolExecutor."""
        return self.parallel_execution

    def get_routing_config(self) -> Dict[str, Any]:
        """Get configuration for RoutingOrchestrator."""
        return self.routing

    @staticmethod
    def _parse_max_tokens(value: Any) -> Optional[int]:
        """
        Parse max_tokens from config value.

        Handles:
        - 'auto' or None -> None (auto-detect from model)
        - Integer string -> int
        - Integer -> int

        Args:
            value: Config value for max_tokens

        Returns:
            Parsed integer or None for auto-detect
        """
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ("auto", "none", ""):
                return None
            try:
                return int(value)
            except ValueError:
                # Invalid value, default to auto
                return None

        return None

    @classmethod
    def from_file(cls, config_path: Path) -> "AgentConfig":
        """Load configuration from YAML file"""
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

            # Parse max_tokens if present (handle 'auto' string)
            if "max_tokens" in config_data:
                config_data["max_tokens"] = cls._parse_max_tokens(config_data["max_tokens"])

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
            session_retention["cleanup_on_startup"] = (
                os.getenv("CORTEX_SESSION_CLEANUP_ON_STARTUP").lower() == "true"
            )

        # Build error recovery from env vars
        error_recovery = {}
        if os.getenv("CORTEX_RECOVERY_ENABLED"):
            error_recovery["enable_smart_recovery"] = (
                os.getenv("CORTEX_RECOVERY_ENABLED").lower() == "true"
            )

        return cls(
            model=os.getenv("CORTEX_MODEL", "moonshotai/kimi-k2.5"),
            permission_mode=os.getenv("CORTEX_MODE", "normal"),
            max_iterations=int(os.getenv("CORTEX_MAX_ITERATIONS", "15")),
            max_iterations_continue_default=bool(
                os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_DEFAULT", "false").lower() == "true"
            ),
            max_iterations_continue_amount=int(
                os.getenv("CORTEX_MAX_ITERATIONS_CONTINUE_AMOUNT", "10")
            ),
            max_tokens=cls._parse_max_tokens(os.getenv("CORTEX_MAX_TOKENS", "auto")),
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
            "file_cache": self.file_cache,
            "transactions": self.transactions,
            "routing": self.routing,
        }
