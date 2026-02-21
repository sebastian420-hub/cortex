"""Agent initialization module - handles complex agent setup"""

import logging
from pathlib import Path
from typing import Optional, Dict, Callable

from ..config import AgentConfig
from .conversation import ConversationManager
from .providers import ProviderFactory, ProviderError
from .rate_limiter import get_rate_limiter, RateLimitConfig
from ..cache.file_cache import get_file_cache
from .loop_guards import LoopGuard
from .recovery import (
    CheckpointManager,
    SessionHealthMonitor,
    RecoveryOrchestrator,
)
from .summarization import (
    create_summarizer,
    SummarizationStrategy,
)
from .memory import create_memory_bank, MemoryBank
from .memory_layers import StateManager, EnhancedMemoryBank
from .planning import PlanningEngine
from .orchestration import (
    OrchestrationManager,
    DelegationContext,
)
from .models import get_model_registry
from ..tools import get_registry
from ..hooks import HookManager
from ..output import OutputFormat, create_formatter
from ..ui.console import console

logger = logging.getLogger(__name__)

# Import routing system (optional)
try:
    from .routing import RoutingOrchestrator, RoutingConfig

    ROUTING_AVAILABLE = True
except ImportError:
    ROUTING_AVAILABLE = False
    RoutingOrchestrator = None
    RoutingConfig = None


class AgentInitializer:
    """
    Handles complex agent initialization logic.

    This class extracts the initialization complexity from the main Cortex class,
    making it easier to test and maintain. All components are initialized here
    and then exposed as properties.

    Responsibilities:
    - Initialize all managers (conversation, memory, recovery, etc.)
    - Load project context
    - Set up providers
    - Configure rate limiters
    - Initialize caching system
    - Set up orchestration system
    - Configure planning and layered memory systems
    """

    def __init__(
        self,
        model: str,
        project_dir: Path,
        permission_mode: str,
        config: AgentConfig,
        hook_manager: HookManager,
        output_format: OutputFormat,
        project_context: str = None,
        enable_planning: bool = False,
        enable_layered_memory: bool = False,
        planning_callbacks: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialize all agent components.

        Args:
            model: LLM model to use
            project_dir: Project directory path
            permission_mode: Permission mode (NORMAL, AUTO_APPROVE, PLAN)
            config: Agent configuration
            hook_manager: Hook manager for event handling
            output_format: Output format (TEXT, JSON, etc.)
            project_context: Pre-loaded project context (optional)
            enable_planning: Whether to enable the planning engine
            enable_layered_memory: Whether to use enhanced layered memory
            planning_callbacks: Optional callbacks for the planning engine
        """
        self.model = model
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.config = config
        self.hook_manager = hook_manager
        self.output_format = output_format
        self.project_context = project_context
        self.enable_planning = enable_planning
        self.enable_layered_memory = enable_layered_memory
        self.planning_callbacks = planning_callbacks or {}

        # Initialize history directory
        self.history_dir = Path.home() / ".cortex" / "sessions"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Initialize all components
        self.provider = self._init_provider()
        self.memory_bank = self._init_memory_bank()
        self.state_manager = self._init_state_manager()
        self.conversation = self._init_conversation()
        self.checkpoint_manager = self._init_checkpoint_manager()
        self.health_monitor = SessionHealthMonitor()
        self.recovery_orchestrator = self._init_recovery_orchestrator()
        self.loop_guard = self._init_loop_guard()
        self.parallel_executor = None  # Will be set by agent
        self.rate_limiter = self._init_rate_limiter()
        self.file_cache = self._init_file_cache()
        self.router = self._init_routing()
        self.tool_registry = get_registry()
        self.formatter = create_formatter(output_format, console=console)

        # Initialize planning engine
        self.planning_engine = self._init_planning_engine()

        # Initialize orchestration system
        self.orchestration = None
        self.model_registry = None
        self.delegation_tracker = None
        self.delegation_context = None
        self.orchestration_enabled = False
        self._init_orchestration()

        # Timeout configuration
        self.timeout_config = self.config.get_timeout_config()

    def _init_memory_bank(self) -> MemoryBank:
        """Initialize memory bank for tracking decisions and facts"""
        if self.enable_layered_memory:
            return EnhancedMemoryBank(max_items=100)
        return create_memory_bank(max_items=50)

    def _init_state_manager(self) -> StateManager:
        """Initialize state manager for task tracking"""
        return StateManager(project_dir=self.project_dir)

    def _init_planning_engine(self) -> Optional[PlanningEngine]:
        """Initialize planning engine if enabled"""
        if not self.enable_planning:
            return None

        return PlanningEngine(
            project_dir=self.project_dir,
            skill_loader=self.planning_callbacks.get("skill_loader"),
            tool_executor=self.planning_callbacks.get("tool_executor"),
            reflection_callback=self.planning_callbacks.get("reflection_callback"),
            step_callback=self.planning_callbacks.get("step_callback"),
        )

    def _init_conversation(self) -> ConversationManager:
        """
        Initialize conversation manager with summarization support.

        Note: Requires system_prompt_generator to be passed from agent
        after initialization, so we defer that.
        """
        warn_on_truncation = self.config.session_retention.get("warn_on_truncation", True)

        # Create summarizer for intelligent context management
        summarization_config = getattr(self.config, "summarization", {})
        enable_summarization = summarization_config.get("enabled", True)
        strategy_name = summarization_config.get("strategy", "simple")

        if strategy_name == "llm":
            strategy = SummarizationStrategy.LLM_BASED
        elif strategy_name == "hybrid":
            strategy = SummarizationStrategy.HYBRID
        else:
            strategy = SummarizationStrategy.SIMPLE

        summarizer = (
            create_summarizer(strategy, self.provider, self.model) if enable_summarization else None
        )

        # Note: system_prompt will be set by agent after PromptGenerator is initialized
        return ConversationManager(
            system_prompt="",  # Placeholder, will be updated by agent
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages,
            model=self.model,
            warn_on_truncation=warn_on_truncation,
            on_truncation=None,  # Will be set by agent
            summarizer=summarizer,
            enable_summarization=enable_summarization,
            summarization_threshold=summarization_config.get("threshold", 0.8),
        )

    def _init_checkpoint_manager(self) -> CheckpointManager:
        """Initialize checkpoint manager for session recovery"""
        recovery_config = getattr(self.config, "recovery", {})
        checkpoint_dir = self.history_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)

        return CheckpointManager(
            checkpoint_dir=checkpoint_dir,
            max_checkpoints=recovery_config.get("max_checkpoints", 10),
            auto_checkpoint_interval=recovery_config.get("auto_checkpoint_interval", 50),
            compression_enabled=recovery_config.get("compression_enabled", True),
            retention_days=recovery_config.get("retention_days", 7),
        )

    def _init_recovery_orchestrator(self) -> RecoveryOrchestrator:
        """Initialize recovery orchestrator"""
        return RecoveryOrchestrator(self.checkpoint_manager, self.health_monitor)

    def _init_loop_guard(self) -> LoopGuard:
        """Initialize loop guard with recovery manager if enabled"""
        recovery_manager = None
        if self.config.error_recovery.get("enable_smart_recovery", False):
            from .recovery_strategies import create_recovery_manager_from_config

            recovery_manager = create_recovery_manager_from_config(self.config.error_recovery)

        return LoopGuard(
            max_repeats=self.config.error_recovery.get("max_repeats", 3),
            stuck_threshold=self.config.error_recovery.get("stuck_threshold", 5),
            buffer_size=self.config.error_recovery.get("buffer_size", 10),
            recovery_manager=recovery_manager,
        )

    def _init_rate_limiter(self):
        """Initialize rate limiter if enabled"""
        rate_limit_config = self.config.rate_limit
        rate_limiter_enabled = rate_limit_config.get("enabled", False)

        if rate_limiter_enabled:
            rate_limit_cfg = RateLimitConfig(
                requests_per_minute=rate_limit_config.get("requests_per_minute", 60),
                tokens_per_minute=rate_limit_config.get("tokens_per_minute", 100000),
                burst_multiplier=rate_limit_config.get("burst_multiplier", 1.5),
            )
            limiter = get_rate_limiter(rate_limit_cfg)
            logger.info(
                f"Rate limiting enabled: {rate_limit_config.get('requests_per_minute')} RPM, "
                f"{rate_limit_config.get('tokens_per_minute')} TPM"
            )
            return limiter
        else:
            return None

    def _init_file_cache(self):
        """Initialize file cache with optional Redis support"""
        cache_warming_config = self.config.cache_warming

        # Prepare cache configuration (support Redis)
        cache_config = {**self.config.file_cache}

        # Add Redis settings if Redis cache is enabled
        if self.config.redis_cache.get("enabled", False):
            cache_config["use_redis"] = True
            cache_config["redis_host"] = self.config.redis_cache.get("host", "localhost")
            cache_config["redis_port"] = self.config.redis_cache.get("port", 6379)
            cache_config["redis_db"] = self.config.redis_cache.get("db", 0)
            cache_config["redis_password"] = self.config.redis_cache.get("password")
            cache_config["redis_ttl"] = self.config.redis_cache.get("ttl", 3600)
            cache_config["redis_fallback"] = self.config.redis_cache.get("fallback_to_local", True)

        file_cache = get_file_cache(cache_config)

        # Cache warming if enabled
        if cache_warming_config.get("enabled", False):
            try:
                cache_stats = file_cache.pre_cache(
                    patterns=cache_warming_config.get("patterns"),
                    source=cache_warming_config.get("source", "git_history"),
                    max_files=cache_warming_config.get("max_files", 50),
                    directory=(
                        Path(cache_warming_config.get("directory"))
                        if cache_warming_config.get("directory")
                        else None
                    ),
                )
                if cache_stats["cached"] > 0:
                    logger.info(f"Cache warming complete: {cache_stats['cached']} files cached")
            except Exception as e:
                logger.warning(f"Cache warming failed: {e}")

        return file_cache

    def _init_provider(self):
        """Initialize model provider"""
        provider_override = getattr(self.config, "provider", None)
        try:
            provider = ProviderFactory.get_provider(self.model, provider_override)
            # Validate API key for cloud providers
            if not provider.validate_api_key():
                raise ProviderError(
                    f"API key not set for {ProviderFactory.get_provider_name(self.model)} "
                    f"provider. Please set the required environment variable."
                )
            return provider
        except ProviderError as e:
            raise ProviderError(f"Failed to initialize provider: {e}") from e

    def _init_routing(self):
        """Initialize intelligent routing if enabled"""
        router = None
        routing_config = self.config.get_routing_config()

        if ROUTING_AVAILABLE and routing_config.get("enabled", False):
            try:
                router = RoutingOrchestrator(
                    RoutingConfig(
                        enabled=True,
                        mode=routing_config.get("mode", "rule_based"),
                        prefer_local_models=routing_config.get("prefer_local_models", True),
                        allow_cloud_fallback=routing_config.get("allow_cloud_fallback", True),
                        task_analysis_enabled=routing_config.get("task_analysis_enabled", True),
                        cost_optimization_enabled=routing_config.get(
                            "cost_optimization_enabled", True
                        ),
                        transparency_enabled=routing_config.get("transparency_enabled", True),
                        cache_decisions=routing_config.get("cache_decisions", True),
                        log_decisions=routing_config.get("log_decisions", False),
                        log_file=routing_config.get("log_file"),
                    )
                )
                logger.info("Intelligent model routing enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize routing system: {e}")

        return router

    def _init_orchestration(self) -> None:
        """Initialize the model orchestration system"""
        orchestration_config = getattr(self.config, "orchestration", {})
        self.orchestration_enabled = orchestration_config.get("enabled", True)

        if not self.orchestration_enabled:
            self.orchestration = None
            self.model_registry = None
            self.delegation_tracker = None
            return

        # Initialize model registry
        self.model_registry = get_model_registry()

        # Initialize orchestration manager
        default_coordinator = orchestration_config.get("default_model", "xiaomi/mimo-v2-flash:free")
        max_delegations = orchestration_config.get("max_delegations_per_request", 5)

        self.orchestration = OrchestrationManager(
            default_coordinator=default_coordinator,
            max_delegations=max_delegations,
        )

        # Delegation tracker will be created per-request
        self.delegation_tracker = None

        # Track current delegation context
        self.delegation_context: Optional[DelegationContext] = None

        logger.info(f"Model orchestration initialized (coordinator: {default_coordinator})")

    def is_routing_enabled(self) -> bool:
        """Check if routing is enabled"""
        return self.router is not None

    def is_rate_limiting_enabled(self) -> bool:
        """Check if rate limiting is enabled"""
        return self.rate_limiter is not None
