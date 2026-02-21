"""
Cost Tracking Infrastructure for Phase 1.

This module provides cost estimation and tracking for model usage.
It includes pricing data, cost estimation algorithms, and usage tracking.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import json
import logging
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class CostGranularity(Enum):
    """Granularity level for cost tracking."""

    TOKEN = "token"  # Per-token costs (most accurate)
    REQUEST = "request"  # Per-request estimates
    SESSION = "session"  # Per-session totals
    PROJECT = "project"  # Per-project totals
    USER = "user"  # Per-user totals


@dataclass
class ModelPricing:
    """Pricing information for a specific model."""

    model_name: str
    provider: str
    input_cost_per_1k_tokens: float  # Cost per 1k input tokens in USD
    output_cost_per_1k_tokens: float  # Cost per 1k output tokens in USD
    context_window: int  # Maximum context size in tokens
    supports_streaming: bool = True
    notes: Optional[str] = None
    last_updated: float = field(default_factory=time.time)

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, include_context_overhead: bool = True
    ) -> float:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            include_context_overhead: Whether to include context overhead

        Returns:
            Estimated cost in USD
        """
        # Calculate base token costs
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k_tokens
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k_tokens

        # Add context overhead if requested (typically 10-20% for large contexts)
        total_cost = input_cost + output_cost
        if include_context_overhead and input_tokens > 0:
            # Assume 15% overhead for context management
            context_overhead = total_cost * 0.15
            total_cost += context_overhead

        return total_cost


@dataclass
class CostEstimate:
    """Cost estimate for a model usage."""

    model_name: str
    provider: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    confidence: float  # 0.0 to 1.0
    estimation_method: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostRecord:
    """Record of actual cost incurred."""

    model_name: str
    provider: str
    actual_input_tokens: Optional[int] = None
    actual_output_tokens: Optional[int] = None
    actual_cost_usd: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PricingRegistry:
    """Registry of model pricing information."""

    def __init__(self):
        """Initialize pricing registry with default pricing data."""
        self.pricing_data: Dict[str, ModelPricing] = {}
        self._load_default_pricing()

    def _load_default_pricing(self) -> None:
        """Load default pricing information."""
        # Ollama models (local, free)
        self.register(
            ModelPricing(
                model_name="llama3.2",
                provider="ollama",
                input_cost_per_1k_tokens=0.0,
                output_cost_per_1k_tokens=0.0,
                context_window=8192,
                supports_streaming=True,
                notes="Local model, no API cost",
            )
        )

        self.register(
            ModelPricing(
                model_name="llama3.3:70b",
                provider="ollama",
                input_cost_per_1k_tokens=0.0,
                output_cost_per_1k_tokens=0.0,
                context_window=8192,
                supports_streaming=True,
                notes="Local model, no API cost",
            )
        )

        self.register(
            ModelPricing(
                model_name="qwen2.5:32b",
                provider="ollama",
                input_cost_per_1k_tokens=0.0,
                output_cost_per_1k_tokens=0.0,
                context_window=32768,
                supports_streaming=True,
                notes="Local model, no API cost",
            )
        )

        # DeepSeek models (cloud, low cost)
        self.register(
            ModelPricing(
                model_name="deepseek-chat",
                provider="deepseek",
                input_cost_per_1k_tokens=0.00014,  # $0.14 per million tokens
                output_cost_per_1k_tokens=0.00028,  # $0.28 per million tokens
                context_window=128000,
                supports_streaming=True,
                notes="DeepSeek Chat model pricing",
            )
        )

        self.register(
            ModelPricing(
                model_name="deepseek-coder",
                provider="deepseek",
                input_cost_per_1k_tokens=0.00014,
                output_cost_per_1k_tokens=0.00028,
                context_window=128000,
                supports_streaming=True,
                notes="DeepSeek Coder model pricing",
            )
        )

        self.register(
            ModelPricing(
                model_name="deepseek-reasoner",
                provider="deepseek",
                input_cost_per_1k_tokens=0.00014,
                output_cost_per_1k_tokens=0.00028,
                context_window=128000,
                supports_streaming=True,
                notes="DeepSeek Reasoner model pricing",
            )
        )

        # Anthropic models (cloud, higher cost)
        self.register(
            ModelPricing(
                model_name="claude-3-5-sonnet-20241022",
                provider="anthropic",
                input_cost_per_1k_tokens=0.003,  # $3 per million tokens
                output_cost_per_1k_tokens=0.015,  # $15 per million tokens
                context_window=200000,
                supports_streaming=True,
                notes="Claude 3.5 Sonnet pricing",
            )
        )

        self.register(
            ModelPricing(
                model_name="claude-3-haiku-20240307",
                provider="anthropic",
                input_cost_per_1k_tokens=0.00025,  # $0.25 per million tokens
                output_cost_per_1k_tokens=0.00125,  # $1.25 per million tokens
                context_window=200000,
                supports_streaming=True,
                notes="Claude 3 Haiku pricing",
            )
        )

        # OpenRouter models (varies by model)
        self.register(
            ModelPricing(
                model_name="openrouter/auto",
                provider="openrouter",
                input_cost_per_1k_tokens=0.001,  # Average estimate
                output_cost_per_1k_tokens=0.003,  # Average estimate
                context_window=128000,
                supports_streaming=True,
                notes="OpenRouter auto-routing average pricing",
            )
        )
        self.register(
            ModelPricing(
                model_name="devstral-2512",
                provider="openrouter",
                input_cost_per_1k_tokens=0.0,
                output_cost_per_1k_tokens=0.0,
                context_window=256000,
                supports_streaming=True,
                notes="Devstral 2 2512 free model via OpenRouter",
            )
        )
        self.register(
            ModelPricing(
                model_name="devstral-small",
                provider="openrouter",
                input_cost_per_1k_tokens=0.0,
                output_cost_per_1k_tokens=0.0,
                context_window=128000,
                supports_streaming=True,
                notes="Devstral Small free model via OpenRouter",
            )
        )

    def register(self, pricing: ModelPricing) -> None:
        """
        Register pricing information for a model.

        Args:
            pricing: ModelPricing object
        """
        key = f"{pricing.provider}:{pricing.model_name}"
        self.pricing_data[key] = pricing
        logger.debug(f"Registered pricing for {key}")

    def get_pricing(self, model_name: str, provider: str) -> Optional[ModelPricing]:
        """
        Get pricing information for a model.

        Args:
            model_name: Model name
            provider: Provider name

        Returns:
            ModelPricing object or None if not found
        """
        key = f"{provider}:{model_name}"
        return self.pricing_data.get(key)

    def estimate_model_cost(
        self, model_name: str, provider: str, input_tokens: int, output_tokens: int
    ) -> Optional[CostEstimate]:
        """
        Estimate cost for using a model.

        Args:
            model_name: Model name
            provider: Provider name
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            CostEstimate object or None if pricing not available
        """
        pricing = self.get_pricing(model_name, provider)
        if not pricing:
            return None

        estimated_cost = pricing.estimate_cost(input_tokens, output_tokens)

        # Calculate confidence based on whether we have actual pricing
        confidence = 0.9 if pricing.input_cost_per_1k_tokens > 0 else 0.7

        return CostEstimate(
            model_name=model_name,
            provider=provider,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            confidence=confidence,
            estimation_method="pricing_registry",
            metadata={
                "pricing_key": f"{provider}:{model_name}",
                "input_cost_per_1k": pricing.input_cost_per_1k_tokens,
                "output_cost_per_1k": pricing.output_cost_per_1k_tokens,
            },
        )

    def list_models_by_cost(self, min_tokens: int = 1000) -> List[Tuple[str, str, float]]:
        """
        List models sorted by estimated cost for given token usage.

        Args:
            min_tokens: Minimum tokens to estimate cost for

        Returns:
            List of (model_name, provider, estimated_cost) tuples
        """
        costs = []
        for key, pricing in self.pricing_data.items():
            # Estimate cost for given token usage (assume 50/50 input/output)
            input_tokens = min_tokens // 2
            output_tokens = min_tokens // 2
            cost = pricing.estimate_cost(input_tokens, output_tokens)
            costs.append((pricing.model_name, pricing.provider, cost))

        # Sort by cost (ascending)
        costs.sort(key=lambda x: x[2])
        return costs


class CostTracker:
    """Tracks costs across sessions, users, and projects."""

    def __init__(self, storage_file: Optional[str] = None):
        """
        Initialize the cost tracker.

        Args:
            storage_file: Optional file to persist cost records
        """
        self.storage_file = storage_file
        self.pricing_registry = PricingRegistry()
        self.cost_records: List[CostRecord] = []

        # Load existing records if file exists
        if storage_file:
            try:
                self._load_records()
            except Exception as e:
                logger.warning(f"Failed to load cost records: {e}")

    def record_usage(
        self,
        model_name: str,
        provider: str,
        estimated_cost_usd: Optional[float] = None,
        actual_input_tokens: Optional[int] = None,
        actual_output_tokens: Optional[int] = None,
        actual_cost_usd: Optional[float] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostRecord:
        """
        Record model usage and cost.

        Args:
            model_name: Name of the model used
            provider: Provider of the model
            estimated_cost_usd: Estimated cost (if known)
            actual_input_tokens: Actual input tokens used
            actual_output_tokens: Actual output tokens used
            actual_cost_usd: Actual cost (if known)
            session_id: Optional session identifier
            user_id: Optional user identifier
            project_id: Optional project identifier
            request_id: Optional request identifier
            metadata: Optional additional metadata

        Returns:
            CostRecord object
        """
        # Generate request ID if not provided
        if not request_id:
            request_id = self._generate_request_id()

        # Calculate actual cost from tokens if not provided but tokens are
        if (
            actual_cost_usd is None
            and actual_input_tokens is not None
            and actual_output_tokens is not None
        ):
            pricing = self.pricing_registry.get_pricing(model_name, provider)
            if pricing:
                actual_cost_usd = pricing.estimate_cost(actual_input_tokens, actual_output_tokens)

        # Create cost record
        record = CostRecord(
            model_name=model_name,
            provider=provider,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            actual_cost_usd=actual_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            request_id=request_id,
            metadata=metadata or {},
            timestamp=time.time(),
        )

        # Store record
        self.cost_records.append(record)

        # Persist if storage file is configured
        if self.storage_file:
            self._persist_record(record)

        # Log the cost
        self._log_record(record)

        return record

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        timestamp = int(time.time() * 1000)
        random_part = hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]
        return f"req_{timestamp}_{random_part}"

    def _persist_record(self, record: CostRecord) -> None:
        """Persist cost record to storage file."""
        try:
            record_dict = asdict(record)

            with open(self.storage_file, "a", encoding="utf-8") as f:
                json_line = json.dumps(record_dict, ensure_ascii=False, default=str)
                f.write(json_line + "\n")
        except Exception as e:
            logger.error(f"Failed to persist cost record: {e}")

    def _load_records(self) -> None:
        """Load cost records from storage file."""
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record_dict = json.loads(line.strip())
                        record = CostRecord(**record_dict)
                        self.cost_records.append(record)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine

    def _log_record(self, record: CostRecord) -> None:
        """Log cost record to application logger."""
        if record.actual_cost_usd:
            log_message = (
                f"Cost recorded: model={record.model_name}, "
                f"cost=${record.actual_cost_usd:.6f}, "
                f"provider={record.provider}"
            )
        elif record.estimated_cost_usd:
            log_message = (
                f"Cost estimated: model={record.model_name}, "
                f"est_cost=${record.estimated_cost_usd:.6f}, "
                f"provider={record.provider}"
            )
        else:
            log_message = (
                f"Usage recorded: model={record.model_name}, " f"provider={record.provider}"
            )

        logger.info(log_message)

    def get_total_cost(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        time_range: Optional[Tuple[float, float]] = None,
        granularity: CostGranularity = CostGranularity.SESSION,
    ) -> Dict[str, Any]:
        """
        Get total cost for given filters.

        Args:
            session_id: Filter by session ID
            user_id: Filter by user ID
            project_id: Filter by project ID
            time_range: Filter by time range (start, end)
            granularity: Granularity level for breakdown

        Returns:
            Dictionary with cost statistics
        """
        # Filter records
        filtered = self.cost_records

        if session_id:
            filtered = [r for r in filtered if r.session_id == session_id]

        if user_id:
            filtered = [r for r in filtered if r.user_id == user_id]

        if project_id:
            filtered = [r for r in filtered if r.project_id == project_id]

        if time_range:
            start, end = time_range
            filtered = [r for r in filtered if start <= r.timestamp <= end]

        if not filtered:
            return {"total_records": 0, "total_cost_usd": 0.0}

        # Calculate totals
        total_estimated = sum(r.estimated_cost_usd or 0 for r in filtered)
        total_actual = sum(r.actual_cost_usd or 0 for r in filtered)

        # Use actual cost where available, otherwise estimated
        total_cost = total_actual if total_actual > 0 else total_estimated

        # Group by granularity
        breakdown = self._group_by_granularity(filtered, granularity)

        # Calculate per-model breakdown
        model_breakdown: Dict[str, float] = {}
        for record in filtered:
            cost = record.actual_cost_usd or record.estimated_cost_usd or 0
            key = f"{record.provider}:{record.model_name}"
            model_breakdown[key] = model_breakdown.get(key, 0) + cost

        # Calculate time-based statistics
        timestamps = [r.timestamp for r in filtered]
        time_stats = {
            "first_record": min(timestamps) if timestamps else None,
            "last_record": max(timestamps) if timestamps else None,
            "record_count": len(timestamps),
            "average_time_between_records": None,
        }

        if len(timestamps) > 1:
            time_diffs = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
            time_stats["average_time_between_records"] = sum(time_diffs) / len(time_diffs)

        return {
            "total_records": len(filtered),
            "total_cost_usd": total_cost,
            "total_estimated_cost_usd": total_estimated,
            "total_actual_cost_usd": total_actual,
            "granularity": granularity.value,
            "breakdown": breakdown,
            "model_breakdown": model_breakdown,
            "time_statistics": time_stats,
        }

    def _group_by_granularity(
        self, records: List[CostRecord], granularity: CostGranularity
    ) -> Dict[str, float]:
        """Group records by the specified granularity."""
        grouped: Dict[str, float] = {}

        for record in records:
            cost = record.actual_cost_usd or record.estimated_cost_usd or 0

            if granularity == CostGranularity.TOKEN:
                # Per-token grouping not implemented in Phase 1
                key = "per_token"
                grouped[key] = grouped.get(key, 0) + cost

            elif granularity == CostGranularity.REQUEST:
                key = record.request_id or str(record.timestamp)
                grouped[key] = grouped.get(key, 0) + cost

            elif granularity == CostGranularity.SESSION:
                key = record.session_id or "unknown_session"
                grouped[key] = grouped.get(key, 0) + cost

            elif granularity == CostGranularity.PROJECT:
                key = record.project_id or "unknown_project"
                grouped[key] = grouped.get(key, 0) + cost

            elif granularity == CostGranularity.USER:
                key = record.user_id or "unknown_user"
                grouped[key] = grouped.get(key, 0) + cost

        return grouped

    def get_cost_trends(self, days: int = 7, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cost trends over time.

        Args:
            days: Number of days to analyze
            user_id: Optional user ID to filter by

        Returns:
            List of daily cost summaries
        """
        end_time = time.time()
        start_time = end_time - (days * 24 * 60 * 60)

        # Filter records by time and user
        filtered = [
            r
            for r in self.cost_records
            if start_time <= r.timestamp <= end_time and (user_id is None or r.user_id == user_id)
        ]

        # Group by day
        daily_costs: Dict[str, Dict[str, Any]] = {}

        for record in filtered:
            # Convert timestamp to date string
            date_str = datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d")

            if date_str not in daily_costs:
                daily_costs[date_str] = {
                    "date": date_str,
                    "total_cost": 0.0,
                    "record_count": 0,
                    "models_used": set(),
                    "providers_used": set(),
                }

            daily = daily_costs[date_str]
            cost = record.actual_cost_usd or record.estimated_cost_usd or 0
            daily["total_cost"] += cost
            daily["record_count"] += 1
            daily["models_used"].add(record.model_name)
            daily["providers_used"].add(record.provider)

        # Convert sets to lists for JSON serialization
        result = []
        for date_str, daily in sorted(daily_costs.items()):
            daily["models_used"] = list(daily["models_used"])
            daily["providers_used"] = list(daily["providers_used"])
            result.append(daily)

        return result

    def estimate_request_cost(
        self, model_name: str, provider: str, input_text: str, expected_output_length: int = 500
    ) -> Optional[CostEstimate]:
        """
        Estimate cost for a request based on text length.

        Args:
            model_name: Model name
            provider: Provider name
            input_text: Input text
            expected_output_length: Expected output length in characters

        Returns:
            CostEstimate object or None
        """
        # Rough estimate: 4 characters per token on average
        input_tokens = len(input_text) // 4
        output_tokens = expected_output_length // 4

        return self.pricing_registry.estimate_model_cost(
            model_name, provider, input_tokens, output_tokens
        )

    def clear_records(self) -> None:
        """Clear all cost records (use with caution)."""
        self.cost_records.clear()
        logger.warning("All cost records cleared")


# Global instances for convenience
_default_pricing_registry: Optional[PricingRegistry] = None
_default_cost_tracker: Optional[CostTracker] = None


def get_pricing_registry() -> PricingRegistry:
    """
    Get or create the global pricing registry.

    Returns:
        PricingRegistry instance
    """
    global _default_pricing_registry
    if _default_pricing_registry is None:
        _default_pricing_registry = PricingRegistry()
    return _default_pricing_registry


def get_cost_tracker(storage_file: Optional[str] = None) -> CostTracker:
    """
    Get or create the global cost tracker.

    Args:
        storage_file: Optional storage file path

    Returns:
        CostTracker instance
    """
    global _default_cost_tracker
    if _default_cost_tracker is None:
        _default_cost_tracker = CostTracker(storage_file)
    return _default_cost_tracker


def estimate_model_cost(
    model_name: str, provider: str, input_tokens: int, output_tokens: int
) -> Optional[CostEstimate]:
    """
    Convenience function to estimate model cost.

    Args:
        model_name: Model name
        provider: Provider name
        input_tokens: Input tokens
        output_tokens: Output tokens

    Returns:
        CostEstimate or None
    """
    registry = get_pricing_registry()
    return registry.estimate_model_cost(model_name, provider, input_tokens, output_tokens)
