"""
Intelligent Model Routing System for Cortex.

This module provides advanced model routing capabilities including:
- Provider detection with configurable rules
- Task analysis for intelligent routing
- Cost tracking and optimization
- Fallback and load balancing
- Transparency and decision logging
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
from ..providers import (
    ModelProvider,
    OllamaProvider,
    DeepSeekProvider,
    AnthropicProvider,
    OpenRouterProvider,
    ProviderError,
    ProviderFactory as LegacyProviderFactory,
)

# Export task analysis components
from .task_analysis import (
    TaskAnalysisEngine,
    TaskAnalysis,
    TaskType,
    TaskComplexity,
    analyze_task,
    get_task_analyzer,
)

# Export factory components
from .factory import (
    EnhancedProviderFactory,
    ProviderType,
    ProviderConfig,
    RoutingRule,
    get_provider_factory,
)

# Export transparency components
from .transparency import (
    TransparencyLayer,
    RoutingDecision,
    RoutingReasoning,
    DecisionSource,
    DecisionLogger,
    DisplayFormat,
    show_decision,
    get_transparency_layer,
)

# Export cost tracking components
from .cost_tracking import (
    CostTracker,
    CostEstimate,
    CostRecord,
    ModelPricing,
    CostGranularity,
    estimate_model_cost,
    get_cost_tracker,
    get_pricing_registry,
)

# Export orchestrator (main entry point)
from .orchestrator import (
    RoutingOrchestrator,
    RoutingConfig,
    RoutingContext,
    get_orchestrator,
    route_request,
)

__all__ = [
    # Legacy compatibility
    "ModelProvider",
    "OllamaProvider",
    "DeepSeekProvider",
    "AnthropicProvider",
    "OpenRouterProvider",
    "ProviderError",
    "LegacyProviderFactory",
    # Task analysis
    "TaskAnalysisEngine",
    "TaskAnalysis",
    "TaskType",
    "TaskComplexity",
    "analyze_task",
    "get_task_analyzer",
    # Factory
    "EnhancedProviderFactory",
    "ProviderType",
    "ProviderConfig",
    "RoutingRule",
    "get_provider_factory",
    # Transparency
    "TransparencyLayer",
    "RoutingDecision",
    "RoutingReasoning",
    "DecisionSource",
    "DecisionLogger",
    "DisplayFormat",
    "show_decision",
    "get_transparency_layer",
    # Cost tracking
    "CostTracker",
    "CostEstimate",
    "CostRecord",
    "ModelPricing",
    "CostGranularity",
    "estimate_model_cost",
    "get_cost_tracker",
    "get_pricing_registry",
    # Orchestrator
    "RoutingOrchestrator",
    "RoutingConfig",
    "RoutingContext",
    "get_orchestrator",
    "route_request",
]
