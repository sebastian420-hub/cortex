"""
Phase 1 Routing Orchestrator.

This is the main entry point for the intelligent routing system in Phase 1.
It combines task analysis, provider selection, cost estimation, and transparency
to make routing decisions based on simple rules and heuristics.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import logging
import uuid

from .task_analysis import TaskAnalysisEngine, TaskAnalysis, TaskType, analyze_task
from .factory import EnhancedProviderFactory, ProviderType, get_provider_factory
from .transparency import (
    TransparencyLayer, RoutingDecision, RoutingReasoning, DecisionSource,
    DisplayFormat, show_decision, get_transparency_layer
)
from .cost_tracking import (
    CostTracker, estimate_model_cost, get_cost_tracker,
    CostEstimate, CostRecord
)
from ..providers import ModelProvider, ProviderError

logger = logging.getLogger(__name__)


@dataclass
class RoutingConfig:
    """Configuration for the routing orchestrator."""
    
    # General settings
    enabled: bool = True
    mode: str = "rule_based"  # "rule_based", "manual", "auto"
    
    # Task analysis settings
    task_analysis_enabled: bool = True
    min_confidence_threshold: float = 0.3
    
    # Provider selection settings
    prefer_local_models: bool = True
    allow_cloud_fallback: bool = True
    cloud_fallback_threshold: float = 0.7  # Confidence threshold for cloud fallback
    
    # Cost optimization settings
    cost_optimization_enabled: bool = True
    max_cost_per_task: float = 5.0  # Maximum allowed cost per task in USD
    warn_on_high_cost: bool = True
    high_cost_threshold: float = 1.0  # Threshold for high cost warning
    
    # Transparency settings
    transparency_enabled: bool = True
    display_format: DisplayFormat = DisplayFormat.TEXT
    log_decisions: bool = True
    log_file: Optional[str] = None
    
    # Performance settings
    cache_decisions: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes
    max_cache_size: int = 100
    
    # Advanced settings (for future phases)
    enable_ai_routing: bool = False  # Phase 2 feature
    enable_multi_model: bool = False  # Phase 4 feature
    enable_learning: bool = False  # Phase 2 feature
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingContext:
    """Context for routing decisions."""
    
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    previous_decisions: List[RoutingDecision] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    system_capabilities: Dict[str, Any] = field(default_factory=dict)
    
    # For Phase 1, we keep it simple
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "history_length": len(self.conversation_history),
            "previous_decisions_count": len(self.previous_decisions),
            "has_user_preferences": bool(self.user_preferences)
        }


class RoutingOrchestrator:
    """
    Main routing orchestrator for Phase 1.
    
    This implements the core routing logic combining:
    1. Task analysis (keyword-based)
    2. Provider selection (rule-based with fallback)
    3. Cost estimation and optimization
    4. Transparency and logging
    """
    
    def __init__(self, config: Optional[RoutingConfig] = None):
        """
        Initialize the routing orchestrator.
        
        Args:
            config: Routing configuration
        """
        self.config = config or RoutingConfig()
        
        # Initialize components
        self.task_analyzer = TaskAnalysisEngine()
        self.provider_factory = EnhancedProviderFactory()
        self.transparency_layer = get_transparency_layer(
            log_file=self.config.log_file if self.config.log_decisions else None,
            display_format=self.config.display_format,
            enabled=self.config.transparency_enabled
        )
        self.cost_tracker = get_cost_tracker()
        
        # Decision cache (simple in-memory cache for Phase 1)
        self.decision_cache: Dict[str, Tuple[RoutingDecision, float]] = {}
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "task_analysis_time_ms": 0.0,
            "routing_time_ms": 0.0,
            "errors": 0
        }
        
        logger.info(f"Routing orchestrator initialized with mode: {self.config.mode}")
    
    def route_request(
        self,
        user_request: str,
        context: Optional[RoutingContext] = None,
        force_provider: Optional[str] = None,
        force_model: Optional[str] = None
    ) -> RoutingDecision:
        """
        Main routing entry point.
        
        Args:
            user_request: User's natural language request
            context: Optional routing context
            force_provider: Force specific provider (overrides routing)
            force_model: Force specific model (overrides routing)
            
        Returns:
            RoutingDecision object with full details
            
        Raises:
            ProviderError: If routing fails or provider cannot be created
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # Generate request ID for tracking
        request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Check cache if enabled
            cache_key = None
            if self.config.cache_decisions:
                cache_key = self._generate_cache_key(user_request, context)
                cached = self._check_cache(cache_key)
                if cached:
                    logger.debug(f"Cache hit for request: {user_request[:50]}...")
                    self.stats["cache_hits"] += 1
                    
                    # Update context in cached decision
                    cached.session_id = context.session_id if context else None
                    cached.user_id = context.user_id if context else None
                    cached.project_id = context.project_id if context else None
                    
                    # Show decision if transparency enabled
                    if self.config.transparency_enabled:
                        self.transparency_layer.show_decision(cached)
                    
                    return cached
                else:
                    self.stats["cache_misses"] += 1
            
            # Step 1: Analyze task (if enabled)
            task_analysis = None
            task_analysis_time = 0.0
            
            if self.config.task_analysis_enabled:
                task_start = time.time()
                task_analysis = self.task_analyzer.analyze(user_request)
                task_analysis_time = (time.time() - task_start) * 1000
                self.stats["task_analysis_time_ms"] += task_analysis_time
                
                logger.debug(
                    f"Task analysis: type={task_analysis.task_type.value}, "
                    f"complexity={task_analysis.complexity.score}, "
                    f"confidence={task_analysis.confidence:.2f}"
                )
            
            # Step 2: Select model and provider
            model_name, provider_type, selection_reasoning = self._select_model(
                user_request, task_analysis, force_provider, force_model
            )
            
            # Step 3: Get provider instance
            provider_name = provider_type.value if hasattr(provider_type, 'value') else str(provider_type)
            provider = self.provider_factory.get_provider(model_name, provider_name)
            
            # Step 4: Estimate cost
            cost_estimate = self._estimate_cost(
                model_name, provider_name, user_request, task_analysis
            )
            
            # Step 5: Build routing reasoning
            reasoning = self._build_routing_reasoning(
                selection_reasoning, task_analysis, cost_estimate
            )
            
            # Step 6: Create routing decision
            decision = RoutingDecision(
                model_name=model_name,
                provider_type=provider_type,
                provider_name=provider_name,
                reasoning=reasoning,
                task_analysis=task_analysis,
                decision_source=(
                    DecisionSource.USER_OVERRIDE if force_provider or force_model
                    else DecisionSource.RULE_BASED
                ),
                session_id=context.session_id if context else None,
                user_id=context.user_id if context else None,
                estimated_cost_usd=cost_estimate.estimated_cost_usd if cost_estimate else None,
                confidence_score=(
                    task_analysis.confidence if task_analysis
                    else 0.5
                ),
                metadata={
                    "request_id": request_id,
                    "request_length": len(user_request),
                    "task_analysis_time_ms": task_analysis_time,
                    "force_provider": force_provider,
                    "force_model": force_model,
                    "config_mode": self.config.mode
                }
            )
            
            # Step 7: Show decision (if transparency enabled)
            display_output = ""
            if self.config.transparency_enabled:
                display_output = self.transparency_layer.show_decision(decision)
                decision.metadata["display_output"] = display_output
            
            # Step 8: Cache decision (if enabled)
            if self.config.cache_decisions and cache_key:
                self._cache_decision(cache_key, decision)
            
            # Update timing statistics
            routing_time = (time.time() - start_time) * 1000
            self.stats["routing_time_ms"] += routing_time
            decision.metadata["routing_time_ms"] = routing_time
            
            logger.info(
                f"Routing decision: model={model_name}, provider={provider_name}, "
                f"reason={reasoning.primary_reason}, time={routing_time:.1f}ms"
            )
            
            return decision
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Routing failed for request: {user_request[:100]}... Error: {e}")
            
            # Create fallback decision
            return self._create_fallback_decision(
                user_request, context, request_id, str(e)
            )
    
    def _select_model(
        self,
        user_request: str,
        task_analysis: Optional[TaskAnalysis],
        force_provider: Optional[str],
        force_model: Optional[str]
    ) -> Tuple[str, ProviderType, Dict[str, Any]]:
        """
        Select model and provider based on request and analysis.
        
        Args:
            user_request: User request
            task_analysis: Task analysis result
            force_provider: Forced provider (if any)
            force_model: Forced model (if any)
            
        Returns:
            Tuple of (model_name, provider_type, selection_reasoning)
        """
        reasoning = {
            "primary_reason": "",
            "secondary_reasons": [],
            "factors": {}
        }
        
        # Handle forced selections
        if force_model:
            # Try to determine provider for forced model
            try:
                provider_type = self.provider_factory._route_model(force_model)
                reasoning["primary_reason"] = f"User specified model: {force_model}"
                return force_model, provider_type, reasoning
            except Exception:
                # Fall back to default if forced model fails
                pass
        
        if force_provider:
            # Use default model for forced provider
            provider_type = ProviderType(force_provider.lower())
            default_models = {
                ProviderType.OLLAMA: "llama3.2",
                ProviderType.DEEPSEEK: "deepseek-chat",
                ProviderType.ANTHROPIC: "claude-3-5-sonnet-20241022",
                ProviderType.OPENROUTER: "openrouter/auto"
            }
            model_name = default_models.get(provider_type, "llama3.2")
            reasoning["primary_reason"] = f"User specified provider: {force_provider}"
            return model_name, provider_type, reasoning
        
        # Phase 1: Simple rule-based selection
        
        # Check if we should use local models (preference)
        if self.config.prefer_local_models:
            # Try Ollama first
            try:
                model_name = self._select_model_for_task(task_analysis, ProviderType.OLLAMA)
                reasoning["primary_reason"] = "Using local model (preferred)"
                reasoning["secondary_reasons"].append("Local models are faster and free")
                return model_name, ProviderType.OLLAMA, reasoning
            except Exception as e:
                if self.config.allow_cloud_fallback:
                    logger.debug(f"Local model not suitable, falling back to cloud: {e}")
                else:
                    raise
        
        # Task-based selection
        if task_analysis and task_analysis.confidence >= self.config.min_confidence_threshold:
            suggested_models = self.task_analyzer.suggest_models_for_task(task_analysis)
            
            # Try suggested models in order
            for model in suggested_models:
                try:
                    provider_type = self.provider_factory._route_model(model)
                    
                    # Check if provider is enabled
                    if not self.provider_factory._is_provider_enabled(provider_type):
                        continue
                    
                    reasoning["primary_reason"] = (
                        f"Selected based on task type: {task_analysis.task_type.value}"
                    )
                    reasoning["secondary_reasons"].append(
                        f"Task complexity: {task_analysis.complexity.score}/10"
                    )
                    reasoning["factors"]["task_type"] = task_analysis.task_type.value
                    reasoning["factors"]["complexity"] = task_analysis.complexity.score
                    reasoning["factors"]["confidence"] = task_analysis.confidence
                    
                    return model, provider_type, reasoning
                except Exception:
                    continue
        
        # Default fallback: Use Ollama if available, otherwise first available provider
        try:
            model_name = "llama3.2"
            reasoning["primary_reason"] = "Using default model"
            reasoning["secondary_reasons"].append("No specific task type identified")
            return model_name, ProviderType.OLLAMA, reasoning
        except Exception:
            # Try other providers
            for provider in [ProviderType.DEEPSEEK, ProviderType.ANTHROPIC, ProviderType.OPENROUTER]:
                try:
                    if self.provider_factory._is_provider_enabled(provider):
                        default_models = {
                            ProviderType.DEEPSEEK: "deepseek-chat",
                            ProviderType.ANTHROPIC: "claude-3-5-sonnet-20241022",
                            ProviderType.OPENROUTER: "openrouter/auto"
                        }
                        model_name = default_models.get(provider, "deepseek-chat")
                        reasoning["primary_reason"] = f"Using {provider.value} as fallback"
                        return model_name, provider, reasoning
                except Exception:
                    continue
        
        # Last resort: Use whatever provider factory suggests
        model_name = "llama3.2"
        provider_type = self.provider_factory._route_model(model_name)
        reasoning["primary_reason"] = "Using system default"
        return model_name, provider_type, reasoning
    
    def _select_model_for_task(
        self,
        task_analysis: Optional[TaskAnalysis],
        provider_type: ProviderType
    ) -> str:
        """
        Select specific model for task from given provider.
        
        Args:
            task_analysis: Task analysis
            provider_type: Provider type
            
        Returns:
            Model name
            
        Raises:
            ValueError: If no suitable model found
        """
        # Provider-specific model selection logic
        if provider_type == ProviderType.OLLAMA:
            # Ollama models
            if task_analysis:
                if task_analysis.task_type == TaskType.PLANNING:
                    return "llama3.3:70b"  # Larger model for planning
                elif task_analysis.task_type == TaskType.CODING:
                    return "qwen2.5:32b"  # Good for coding
                elif task_analysis.complexity.score >= 7:
                    return "llama3.3:70b"  # Larger model for complex tasks
            
            return "llama3.2"  # Default Ollama model
        
        elif provider_type == ProviderType.DEEPSEEK:
            # DeepSeek models
            if task_analysis:
                if task_analysis.task_type == TaskType.PLANNING:
                    return "deepseek-reasoner"
                elif task_analysis.task_type in [TaskType.CODING, TaskType.DEBUGGING, TaskType.REFACTORING]:
                    return "deepseek-coder"
            
            return "deepseek-chat"  # Default DeepSeek model
        
        elif provider_type == ProviderType.ANTHROPIC:
            # Anthropic models
            if task_analysis:
                if task_analysis.complexity.score >= 8:
                    return "claude-3-5-sonnet-20241022"
                else:
                    return "claude-3-haiku-20240307"  # Cheaper for simpler tasks
            
            return "claude-3-5-sonnet-20241022"  # Default Claude
        
        elif provider_type == ProviderType.OPENROUTER:
            # OpenRouter models
            return "openrouter/auto"  # Let OpenRouter decide
        
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    def _estimate_cost(
        self,
        model_name: str,
        provider_name: str,
        user_request: str,
        task_analysis: Optional[TaskAnalysis]
    ) -> Optional[CostEstimate]:
        """
        Estimate cost for model usage.
        
        Args:
            model_name: Model name
            provider_name: Provider name
            user_request: User request text
            task_analysis: Task analysis
            
        Returns:
            CostEstimate or None
        """
        if not self.config.cost_optimization_enabled:
            return None
        
        try:
            # Estimate tokens based on request length and task complexity
            input_tokens = len(user_request) // 4  # Rough estimate: 4 chars per token
            
            # Estimate output tokens based on task complexity
            if task_analysis:
                base_output = 500  # Default 500 tokens
                complexity_factor = task_analysis.complexity.score / 5.0  # 1-2x multiplier
                output_tokens = int(base_output * complexity_factor)
            else:
                output_tokens = 500
            
            # Get cost estimate
            cost_estimate = estimate_model_cost(
                model_name, provider_name, input_tokens, output_tokens
            )
            
            if cost_estimate:
                # Check if cost exceeds threshold
                if cost_estimate.estimated_cost_usd > self.config.max_cost_per_task:
                    logger.warning(
                        f"Estimated cost ${cost_estimate.estimated_cost_usd:.4f} "
                        f"exceeds maximum ${self.config.max_cost_per_task}"
                    )
                
                if (self.config.warn_on_high_cost and 
                    cost_estimate.estimated_cost_usd > self.config.high_cost_threshold):
                    logger.warning(
                        f"High cost warning: ${cost_estimate.estimated_cost_usd:.4f} "
                        f"for model {model_name}"
                    )
            
            return cost_estimate
            
        except Exception as e:
            logger.debug(f"Cost estimation failed: {e}")
            return None
    
    def _build_routing_reasoning(
        self,
        selection_reasoning: Dict[str, Any],
        task_analysis: Optional[TaskAnalysis],
        cost_estimate: Optional[CostEstimate]
    ) -> RoutingReasoning:
        """
        Build complete routing reasoning.
        
        Args:
            selection_reasoning: Model selection reasoning
            task_analysis: Task analysis
            cost_estimate: Cost estimate
            
        Returns:
            RoutingReasoning object
        """
        reasoning = RoutingReasoning(
            primary_reason=selection_reasoning.get("primary_reason", "System decision"),
            secondary_reasons=selection_reasoning.get("secondary_reasons", []),
            task_type=task_analysis.task_type if task_analysis else None,
            complexity_score=task_analysis.complexity.score if task_analysis else None,
            confidence=task_analysis.confidence if task_analysis else None
        )
        
        # Add cost consideration
        if cost_estimate:
            if cost_estimate.estimated_cost_usd == 0:
                reasoning.cost_consideration = "Free (local model)"
            elif cost_estimate.estimated_cost_usd < 0.01:
                reasoning.cost_consideration = f"Low cost (${cost_estimate.estimated_cost_usd:.4f})"
            elif cost_estimate.estimated_cost_usd < 0.1:
                reasoning.cost_consideration = f"Moderate cost (${cost_estimate.estimated_cost_usd:.4f})"
            else:
                reasoning.cost_consideration = f"Higher cost (${cost_estimate.estimated_cost_usd:.4f})"
        
        return reasoning
    
    def _generate_cache_key(
        self,
        user_request: str,
        context: Optional[RoutingContext]
    ) -> str:
        """
        Generate cache key for request.
        
        Args:
            user_request: User request
            context: Routing context
            
        Returns:
            Cache key string
        """
        # Simple cache key based on request hash and context summary
        import hashlib
        
        request_hash = hashlib.md5(user_request.encode()).hexdigest()[:16]
        
        if context:
            context_summary = f"{context.session_id or ''}:{context.user_id or ''}"
            context_hash = hashlib.md5(context_summary.encode()).hexdigest()[:8]
            return f"route_{request_hash}_{context_hash}"
        else:
            return f"route_{request_hash}"
    
    def _check_cache(self, cache_key: str) -> Optional[RoutingDecision]:
        """
        Check if decision is in cache and still valid.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached decision or None
        """
        if cache_key in self.decision_cache:
            decision, timestamp = self.decision_cache[cache_key]
            
            # Check if cache entry is still valid
            if time.time() - timestamp < self.config.cache_ttl_seconds:
                return decision
            else:
                # Remove expired entry
                del self.decision_cache[cache_key]
        
        return None
    
    def _cache_decision(self, cache_key: str, decision: RoutingDecision) -> None:
        """
        Cache routing decision.
        
        Args:
            cache_key: Cache key
            decision: Routing decision
        """
        # Clean cache if it's too large
        if len(self.decision_cache) >= self.config.max_cache_size:
            # Remove oldest entries
            oldest_keys = sorted(
                self.decision_cache.keys(),
                key=lambda k: self.decision_cache[k][1]
            )[:self.config.max_cache_size // 2]
            for key in oldest_keys:
                del self.decision_cache[key]
        
        # Add to cache
        self.decision_cache[cache_key] = (decision, time.time())
    
    def _create_fallback_decision(
        self,
        user_request: str,
        context: Optional[RoutingContext],
        request_id: str,
        error_message: str
    ) -> RoutingDecision:
        """
        Create fallback decision when routing fails.
        
        Args:
            user_request: User request
            context: Routing context
            request_id: Request ID
            error_message: Error message
            
        Returns:
            Fallback routing decision
        """
        # Default fallback to Ollama
        model_name = "llama3.2"
        provider_type = ProviderType.OLLAMA
        
        reasoning = RoutingReasoning(
            primary_reason="Fallback due to routing error",
            secondary_reasons=[f"Error: {error_message[:100]}"],
            provider_availability="Using default fallback provider"
        )
        
        return RoutingDecision(
            model_name=model_name,
            provider_type=provider_type,
            provider_name=provider_type.value,
            reasoning=reasoning,
            decision_source=DecisionSource.FALLBACK,
            session_id=context.session_id if context else None,
            user_id=context.user_id if context else None,
            confidence_score=0.1,
            metadata={
                "request_id": request_id,
                "error": error_message,
                "is_fallback": True
            }
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics.
        
        Returns:
            Dictionary of statistics
        """
        stats = self.stats.copy()
        
        # Calculate averages
        if stats["total_requests"] > 0:
            stats["avg_task_analysis_time_ms"] = (
                stats["task_analysis_time_ms"] / stats["total_requests"]
            )
            stats["avg_routing_time_ms"] = (
                stats["routing_time_ms"] / stats["total_requests"]
            )
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / (stats["cache_hits"] + stats["cache_misses"])
                if (stats["cache_hits"] + stats["cache_misses"]) > 0
                else 0
            )
            stats["error_rate"] = stats["errors"] / stats["total_requests"]
        
        # Add cache statistics
        stats["cache_size"] = len(self.decision_cache)
        stats["cache_config"] = {
            "enabled": self.config.cache_decisions,
            "ttl_seconds": self.config.cache_ttl_seconds,
            "max_size": self.config.max_cache_size
        }
        
        # Add transparency statistics
        stats["transparency"] = self.transparency_layer.get_statistics()
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear the decision cache."""
        self.decision_cache.clear()
        logger.info("Routing decision cache cleared")
    
    def reset_statistics(self) -> None:
        """Reset all statistics."""
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "task_analysis_time_ms": 0.0,
            "routing_time_ms": 0.0,
            "errors": 0
        }
        logger.info("Routing statistics reset")


# Global instance for convenience
_default_orchestrator: Optional[RoutingOrchestrator] = None

def get_orchestrator(config: Optional[RoutingConfig] = None) -> RoutingOrchestrator:
    """
    Get or create the global routing orchestrator.
    
    Args:
        config: Optional routing configuration
        
    Returns:
        RoutingOrchestrator instance
    """
    global _default_orchestrator
    if _default_orchestrator is None or config is not None:
        _default_orchestrator = RoutingOrchestrator(config)
    return _default_orchestrator

def route_request(
    user_request: str,
    context: Optional[RoutingContext] = None,
    force_provider: Optional[str] = None,
    force_model: Optional[str] = None
) -> RoutingDecision:
    """
    Convenience function to route a request.
    
    Args:
        user_request: User's natural language request
        context: Optional routing context
        force_provider: Force specific provider
        force_model: Force specific model
        
    Returns:
        RoutingDecision object
    """
    orchestrator = get_orchestrator()
    return orchestrator.route_request(user_request, context, force_provider, force_model)