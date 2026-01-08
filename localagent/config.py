"""Configuration management for LocalAgent"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object


class AgentConfig:
    """Configuration for LocalAgent"""
    
    def __init__(
        self,
        model: str = "llama3.2",
        permission_mode: str = "normal",
        max_iterations: int = 15,
        max_tokens: int = 100000,
        keep_recent_messages: int = 20,
        auto_save: bool = False,
        **kwargs
    ):
        self.model = model
        self.permission_mode = permission_mode
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.keep_recent_messages = keep_recent_messages
        self.auto_save = auto_save
        self.extra = kwargs
    
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
            # Merge file config
            config.model = file_config.model
            config.permission_mode = file_config.permission_mode
            config.max_iterations = file_config.max_iterations
            config.max_tokens = file_config.max_tokens
            config.keep_recent_messages = file_config.keep_recent_messages
            config.auto_save = file_config.auto_save
        
        # Override with environment variables
        env_config = cls.from_env()
        if os.getenv("LOCALAGENT_MODEL"):
            config.model = env_config.model
        if os.getenv("LOCALAGENT_MODE"):
            config.permission_mode = env_config.permission_mode
        
        return config

