from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class CognitiveConfig:
    """
    A dataclass for configuring the cognitive architecture.
    """
    personality: dict[str, Any] = field(default_factory=dict)
    initial_goals: list[str] = field(default_factory=list)
    initial_beliefs: list[str] = field(default_factory=list)
