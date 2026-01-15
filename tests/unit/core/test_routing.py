"""
Unit tests for the intelligent model routing system.
"""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestTaskAnalysis:
    """Tests for task analysis engine."""

    def test_task_analysis_import(self):
        """Test that task analysis module can be imported."""
        from cortex.core.routing.task_analysis import (
            TaskAnalysisEngine,
            TaskType,
            TaskAnalysis,
            TaskComplexity,
        )
        assert TaskAnalysisEngine is not None
        assert TaskType is not None

    def test_task_types_enum(self):
        """Test task type enumeration values."""
        from cortex.core.routing.task_analysis import TaskType

        assert TaskType.CODING.value == "coding"
        assert TaskType.DEBUGGING.value == "debugging"
        assert TaskType.REFACTORING.value == "refactoring"
        assert TaskType.PLANNING.value == "planning"
        assert TaskType.SECURITY.value == "security"
        assert TaskType.DOCUMENTATION.value == "documentation"
        assert TaskType.TESTING.value == "testing"

    def test_analyze_coding_task(self):
        """Test analysis of a coding task."""
        from cortex.core.routing.task_analysis import TaskAnalysisEngine, TaskType

        engine = TaskAnalysisEngine()
        result = engine.analyze("Write a function to calculate fibonacci numbers")

        assert result is not None
        assert result.task_type == TaskType.CODING
        assert result.confidence > 0

    def test_analyze_debugging_task(self):
        """Test analysis of a debugging task."""
        from cortex.core.routing.task_analysis import TaskAnalysisEngine, TaskType

        engine = TaskAnalysisEngine()
        result = engine.analyze("Fix the bug in the authentication module")

        assert result is not None
        assert result.task_type == TaskType.DEBUGGING
        assert result.confidence > 0

    def test_analyze_security_task(self):
        """Test analysis of a security task."""
        from cortex.core.routing.task_analysis import TaskAnalysisEngine, TaskType

        engine = TaskAnalysisEngine()
        result = engine.analyze("Analyze the authentication system for security vulnerabilities and potential exploits")

        assert result is not None
        assert result.task_type == TaskType.SECURITY
        assert result.confidence > 0

    def test_analyze_planning_task(self):
        """Test analysis of a planning task."""
        from cortex.core.routing.task_analysis import TaskAnalysisEngine, TaskType

        engine = TaskAnalysisEngine()
        result = engine.analyze("Plan the architecture for the new microservice")

        assert result is not None
        assert result.task_type == TaskType.PLANNING
        assert result.confidence > 0

    def test_complexity_scoring(self):
        """Test that complexity is scored appropriately."""
        from cortex.core.routing.task_analysis import TaskAnalysisEngine

        engine = TaskAnalysisEngine()

        # Simple task
        simple = engine.analyze("Print hello world")
        # Complex task
        complex_task = engine.analyze(
            "Refactor the entire authentication system to use OAuth2 with "
            "JWT tokens, implement refresh token rotation, add rate limiting, "
            "and ensure backwards compatibility with existing sessions"
        )

        # Complex task should have higher complexity score
        assert complex_task.complexity.score >= simple.complexity.score


class TestCostTracking:
    """Tests for cost tracking system."""

    def test_cost_tracking_import(self):
        """Test that cost tracking module can be imported."""
        from cortex.core.routing.cost_tracking import (
            CostTracker,
            CostEstimate,
            ModelPricing,
            get_cost_tracker,
        )
        assert CostTracker is not None
        assert CostEstimate is not None
        assert ModelPricing is not None

    def test_model_pricing_calculation(self):
        """Test pricing calculation for a model."""
        from cortex.core.routing.cost_tracking import ModelPricing

        pricing = ModelPricing(
            model_name="test-model",
            provider="test",
            input_cost_per_1k_tokens=0.001,
            output_cost_per_1k_tokens=0.002,
            context_window=128000,
        )

        # 1000 input, 500 output tokens
        cost = pricing.estimate_cost(1000, 500, include_context_overhead=False)

        expected = (1000 / 1000 * 0.001) + (500 / 1000 * 0.002)
        assert abs(cost - expected) < 0.0001

    def test_cost_estimate_function(self):
        """Test the convenience cost estimation function."""
        from cortex.core.routing.cost_tracking import estimate_model_cost

        # This should return an estimate for known models
        estimate = estimate_model_cost("deepseek-chat", "deepseek", 1000, 500)

        # May be None if model not in registry, but shouldn't error
        if estimate:
            assert estimate.estimated_cost_usd >= 0
            assert estimate.model_name == "deepseek-chat"


class TestProviderFactory:
    """Tests for enhanced provider factory."""

    def test_factory_import(self):
        """Test that factory module can be imported."""
        from cortex.core.routing.factory import (
            EnhancedProviderFactory,
            ProviderType,
            ProviderConfig,
        )
        assert EnhancedProviderFactory is not None
        assert ProviderType is not None

    def test_provider_types(self):
        """Test provider type enumeration."""
        from cortex.core.routing.factory import ProviderType

        assert ProviderType.OLLAMA.value == "ollama"
        assert ProviderType.DEEPSEEK.value == "deepseek"
        assert ProviderType.ANTHROPIC.value == "anthropic"
        assert ProviderType.OPENROUTER.value == "openrouter"

    def test_factory_initialization(self):
        """Test factory initialization with default config."""
        from cortex.core.routing.factory import EnhancedProviderFactory

        factory = EnhancedProviderFactory()

        assert factory is not None
        assert len(factory.provider_configs) > 0
        assert len(factory.routing_rules) > 0


class TestTransparency:
    """Tests for transparency layer."""

    def test_transparency_import(self):
        """Test that transparency module can be imported."""
        from cortex.core.routing.transparency import (
            TransparencyLayer,
            RoutingDecision,
            RoutingReasoning,
            DecisionSource,
            DisplayFormat,
        )
        assert TransparencyLayer is not None
        assert RoutingDecision is not None
        assert DecisionSource is not None

    def test_decision_source_enum(self):
        """Test decision source enumeration."""
        from cortex.core.routing.transparency import DecisionSource

        assert DecisionSource.RULE_BASED.value == "rule_based"
        assert DecisionSource.USER_OVERRIDE.value == "user_override"
        assert DecisionSource.FALLBACK.value == "fallback"

    def test_display_format_enum(self):
        """Test display format enumeration."""
        from cortex.core.routing.transparency import DisplayFormat

        assert DisplayFormat.TEXT.value == "text"
        assert DisplayFormat.JSON.value == "json"
        assert DisplayFormat.MINIMAL.value == "minimal"


class TestRoutingOrchestrator:
    """Tests for the main routing orchestrator."""

    def test_orchestrator_import(self):
        """Test that orchestrator module can be imported."""
        from cortex.core.routing.orchestrator import (
            RoutingOrchestrator,
            RoutingConfig,
            RoutingContext,
        )
        assert RoutingOrchestrator is not None
        assert RoutingConfig is not None
        assert RoutingContext is not None

    def test_routing_config_defaults(self):
        """Test routing config has sensible defaults."""
        from cortex.core.routing.orchestrator import RoutingConfig

        config = RoutingConfig()

        assert config.enabled == True
        assert config.mode == "rule_based"
        assert config.prefer_local_models == True
        assert config.task_analysis_enabled == True
        assert config.cost_optimization_enabled == True

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        from cortex.core.routing.orchestrator import RoutingOrchestrator, RoutingConfig

        config = RoutingConfig(enabled=True)
        orchestrator = RoutingOrchestrator(config)

        assert orchestrator is not None
        assert orchestrator.config.enabled == True

    def test_get_statistics(self):
        """Test getting orchestrator statistics."""
        from cortex.core.routing.orchestrator import RoutingOrchestrator, RoutingConfig

        config = RoutingConfig(enabled=True)
        orchestrator = RoutingOrchestrator(config)

        stats = orchestrator.get_statistics()

        assert "total_requests" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "errors" in stats


class TestRoutingIntegration:
    """Integration tests for the routing system."""

    def test_full_routing_import(self):
        """Test that all routing components can be imported from __init__."""
        from cortex.core.routing import (
            TaskAnalysisEngine,
            TaskType,
            EnhancedProviderFactory,
            ProviderType,
            TransparencyLayer,
            RoutingDecision,
            CostTracker,
            RoutingOrchestrator,
            RoutingConfig,
            get_orchestrator,
        )

        # All should be importable
        assert TaskAnalysisEngine is not None
        assert TaskType is not None
        assert EnhancedProviderFactory is not None
        assert ProviderType is not None
        assert TransparencyLayer is not None
        assert RoutingDecision is not None
        assert CostTracker is not None
        assert RoutingOrchestrator is not None
        assert RoutingConfig is not None
        assert get_orchestrator is not None

    def test_agent_routing_attribute(self):
        """Test that Cortex agent has routing attribute."""
        # This tests the integration without actually creating a full agent
        from cortex.agent import ROUTING_AVAILABLE

        # Should be True since we have the routing module
        assert ROUTING_AVAILABLE == True
