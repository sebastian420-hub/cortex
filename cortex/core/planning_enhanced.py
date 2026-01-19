"""
Enhanced planning system with model delegation capabilities.

This module extends the existing Cortex planning system to support
model-aware planning and execution. It maintains 100% backward
compatibility while adding model delegation features.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Union
import logging

from .planning import PlanStep, PlanStepType, PlanStepStatus, Plan
from ..utils.errors import create_error_response, create_success_response, ErrorType

logger = logging.getLogger(__name__)


class ModelAssignmentReason(str, Enum):
    """Reason for model assignment."""
    
    SECURITY_REQUIRED = "security_required"          # Security tasks require security model
    COMPLEXITY_REQUIRED = "complexity_required"      # Complex tasks require reasoning model
    SPECIALIZATION = "specialization"               # Task requires specialized model
    COST_OPTIMIZATION = "cost_optimization"         # Cheaper model can handle task
    PERFORMANCE = "performance"                     # Faster model for time-sensitive task
    QUALITY = "quality"                             # Higher quality model needed
    USER_REQUEST = "user_request"                   # Explicit user request


class RiskLevel(str, Enum):
    """Risk level for plan steps."""
    
    LOW = "low"              # Minimal risk, simple changes
    MEDIUM = "medium"        # Moderate risk, typical changes
    HIGH = "high"            # High risk, significant changes
    CRITICAL = "critical"    # Critical risk, security/safety changes


@dataclass
class ModelAwarePlanStep(PlanStep):
    """
    Enhanced plan step with model delegation metadata.
    
    Extends the existing PlanStep class to support:
    - Model assignment for delegation
    - Review requirements
    - Risk assessment
    - Cost optimization
    
    Maintains 100% backward compatibility with existing PlanStep.
    """
    
    # Model assignment fields
    required_model: Optional[str] = None
    """Model that must execute this step (e.g., 'dolphin-24b', 'deepseek-reasoner')"""
    
    model_assignment_reason: Optional[str] = None
    """Reason for model assignment (from ModelAssignmentReason or custom)"""
    
    alternative_models: List[str] = field(default_factory=list)
    """Alternative models that could execute this step if primary unavailable"""
    
    # Review and validation
    review_required: bool = False
    """Whether this step requires review after execution"""
    
    review_model: Optional[str] = None
    """Model to perform review (defaults to 'gpt-5.1-codex-mini')"""
    
    auto_review: bool = True
    """Whether to automatically trigger review after execution"""
    
    # Risk assessment
    risk_level: RiskLevel = RiskLevel.MEDIUM
    """Risk level of this step"""
    
    security_related: bool = False
    """Whether this step involves security-sensitive operations"""
    
    # Cost optimization
    max_cost_usd: Optional[float] = None
    """Maximum allowed cost for this step in USD"""
    
    prefer_local: bool = True
    """Prefer local models when possible"""
    
    # Execution tracking
    delegated_to: Optional[str] = None
    """Model that actually executed the step (filled during execution)"""
    
    review_result: Optional[Dict[str, Any]] = None
    """Result of review if review_required is True"""
    
    def __post_init__(self):
        """Initialize after dataclass creation."""
        # Ensure alternative_models is a list
        if not isinstance(self.alternative_models, list):
            self.alternative_models = []
        
        # Convert risk_level string to RiskLevel enum if needed
        if isinstance(self.risk_level, str):
            try:
                self.risk_level = RiskLevel(self.risk_level.lower())
            except ValueError:
                self.risk_level = RiskLevel.MEDIUM
                logger.warning(f"Invalid risk_level '{self.risk_level}', defaulting to MEDIUM")
        
        # Set default review model if review required but not specified
        if self.review_required and not self.review_model:
            self.review_model = "gpt-5.1-codex-mini"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        
        Overrides parent method to include delegation fields while
        maintaining compatibility with existing serialization format.
        """
        # Get parent dict
        data = super().to_dict()
        
        # Add delegation fields to metadata for backward compatibility
        delegation_metadata = {
            "required_model": self.required_model,
            "model_assignment_reason": self.model_assignment_reason,
            "alternative_models": self.alternative_models,
            "review_required": self.review_required,
            "review_model": self.review_model,
            "auto_review": self.auto_review,
            "risk_level": self.risk_level.value,
            "security_related": self.security_related,
            "max_cost_usd": self.max_cost_usd,
            "prefer_local": self.prefer_local,
            "delegated_to": self.delegated_to,
        }
        
        # Remove None values
        delegation_metadata = {k: v for k, v in delegation_metadata.items() if v is not None}
        
        # Merge with existing metadata
        if "metadata" not in data:
            data["metadata"] = {}
        data["metadata"].update(delegation_metadata)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelAwarePlanStep":
        """
        Create from dictionary.
        
        Handles both existing PlanStep format and enhanced format.
        """
        # Check if this is an enhanced step (has delegation metadata)
        metadata = data.get("metadata", {})
        
        # Extract delegation fields from metadata
        required_model = metadata.get("required_model")
        model_assignment_reason = metadata.get("model_assignment_reason")
        alternative_models = metadata.get("alternative_models", [])
        review_required = metadata.get("review_required", False)
        review_model = metadata.get("review_model")
        auto_review = metadata.get("auto_review", True)
        
        # Risk level
        risk_level_str = metadata.get("risk_level", "medium")
        try:
            risk_level = RiskLevel(risk_level_str)
        except ValueError:
            risk_level = RiskLevel.MEDIUM
        
        # Other fields
        security_related = metadata.get("security_related", False)
        max_cost_usd = metadata.get("max_cost_usd")
        prefer_local = metadata.get("prefer_local", True)
        delegated_to = metadata.get("delegated_to")
        
        # Create the step
        step = cls(
            id=data["id"],
            description=data["description"],
            step_type=PlanStepType(data["step_type"]),
            status=PlanStepStatus(data["status"]),
            dependencies=data.get("dependencies", []),
            expected_outcome=data.get("expected_outcome"),
            actual_outcome=data.get("actual_outcome"),
            tool_name=data.get("tool_name"),
            tool_arguments=data.get("tool_arguments"),
            skill_name=data.get("skill_name"),
            skill_params=data.get("skill_params"),
            subtask_description=data.get("subtask_description"),
            decision_point=data.get("decision_point"),
            checkpoint_name=data.get("checkpoint_name"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            
            # Delegation fields
            required_model=required_model,
            model_assignment_reason=model_assignment_reason,
            alternative_models=alternative_models,
            review_required=review_required,
            review_model=review_model,
            auto_review=auto_review,
            risk_level=risk_level,
            security_related=security_related,
            max_cost_usd=max_cost_usd,
            prefer_local=prefer_local,
            delegated_to=delegated_to,
        )
        
        return step
    
    def mark_delegated(self, model: str) -> None:
        """Mark that this step was delegated to a specific model."""
        self.delegated_to = model
        logger.info(f"Step {self.id} delegated to {model}: {self.description}")
    
    def add_review_result(self, result: Dict[str, Any]) -> None:
        """Add review result to step."""
        self.review_result = result
        if self.actual_outcome:
            self.actual_outcome = f"{self.actual_outcome} | Review: {result.get('summary', 'Completed')}"
    
    def requires_delegation(self, current_model: str) -> bool:
        """
        Check if this step requires delegation.
        
        Args:
            current_model: The model currently executing
            
        Returns:
            True if step should be delegated to another model
        """
        if not self.required_model:
            return False
        
        return self.required_model != current_model
    
    def get_estimated_cost(self, model_registry: Optional[Any] = None) -> float:
        """
        Get estimated cost for this step.
        
        Args:
            model_registry: Optional registry to get model costs
            
        Returns:
            Estimated cost in USD, 0.0 if unknown
        """
        # If we have a max cost, return that as estimate
        if self.max_cost_usd is not None:
            return self.max_cost_usd
        
        # TODO: Implement actual cost estimation based on step complexity
        # and model pricing from registry
        return 0.0
    
    def __str__(self) -> str:
        """String representation including model info."""
        base_str = super().__str__()
        if self.required_model:
            return f"{base_str} [→ {self.required_model}]"
        return base_str


def convert_planstep_to_modelaware(step: PlanStep) -> ModelAwarePlanStep:
    """
    Convert a regular PlanStep to ModelAwarePlanStep.
    
    Args:
        step: Regular PlanStep to convert
        
    Returns:
        ModelAwarePlanStep with same data
    """
    return ModelAwarePlanStep.from_dict(step.to_dict())


def convert_plan_to_modelaware(plan: Plan) -> Plan:
    """
    Convert all steps in a plan to ModelAwarePlanStep.
    
    Args:
        plan: Plan to convert
        
    Returns:
        New Plan with ModelAwarePlanStep steps
    """
    # Create new plan with same data
    new_plan = Plan(
        id=plan.id,
        goal=plan.goal,
        description=plan.description,
        status=plan.status,
        created_at=plan.created_at,
        started_at=plan.started_at,
        completed_at=plan.completed_at,
        success_criteria=plan.success_criteria.copy(),
        constraints=plan.constraints.copy(),
        assumptions=plan.assumptions.copy(),
        priority=plan.priority,
        estimated_duration_minutes=plan.estimated_duration_minutes,
        actual_duration_minutes=plan.actual_duration_minutes,
        metadata=plan.metadata.copy(),
    )
    
    # Convert all steps
    for step in plan.steps:
        if isinstance(step, ModelAwarePlanStep):
            new_plan.add_step(step)
        else:
            new_plan.add_step(convert_planstep_to_modelaware(step))
    
    return new_plan