"""Configuration management for LocalAgent"""

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


class AgentConfig:
    """
    Configuration for LocalAgent.

    Supports loading from YAML files, environment variables, or direct initialization.
    Configuration hierarchy: defaults < file config < environment variables.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        permission_mode: str = "normal",
        max_iterations: int = 15,
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
        **kwargs
    ):
        # Core settings
        self.model = model
        self.permission_mode = permission_mode
        self.max_iterations = max_iterations
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

        # Extra settings for extensibility
        self.extra = kwargs

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
        return cls(
            model=os.getenv("LOCALAGENT_MODEL", "llama3.2"),
            permission_mode=os.getenv("LOCALAGENT_MODE", "normal"),
            max_iterations=int(os.getenv("LOCALAGENT_MAX_ITERATIONS", "15")),
            max_tokens=int(os.getenv("LOCALAGENT_MAX_TOKENS", "100000")),
            provider=os.getenv("LOCALAGENT_PROVIDER", None),
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

        # Override with environment variables
        env_config = cls.from_env()
        if os.getenv("LOCALAGENT_MODEL"):
            config.model = env_config.model
        if os.getenv("LOCALAGENT_MODE"):
            config.permission_mode = env_config.permission_mode
        if os.getenv("LOCALAGENT_OUTPUT_FORMAT"):
            config.output_format = os.getenv("LOCALAGENT_OUTPUT_FORMAT")
        if os.getenv("LOCALAGENT_HOOKS_ENABLED"):
            config.hooks_enabled = os.getenv("LOCALAGENT_HOOKS_ENABLED").lower() == "true"
        if os.getenv("LOCALAGENT_PROVIDER"):
            config.provider = os.getenv("LOCALAGENT_PROVIDER")

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "model": self.model,
            "permission_mode": self.permission_mode,
            "max_iterations": self.max_iterations,
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
        }

