"""
Delegation rules for model assignment validation.

This module provides strict rules governing when and how models should be
delegated for plan steps. Rules are prioritized as:
1. MANDATORY: Cannot be overridden (security, etc.)
2. STRONGLY_RECOMMENDED: Should be followed unless good reason
3. RECOMMENDED: Best practice to follow
4. PROHIBITED: Never do this

Rules are deterministic and enforce safety-critical constraints.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import re
import logging

from .planning_enhanced import ModelAwarePlanStep, RiskLevel

logger = logging.getLogger(__name__)


class RuleSeverity(str, Enum):
    """Severity level for rule violations."""
    
    CRITICAL = "critical"    # Must fix - security/safety violation
    HIGH = "high"            # Should fix - quality/reliability issue
    MEDIUM = "medium"        # Consider fixing - best practice
    LOW = "low"              # Optional - optimization suggestion


class RuleType(str, Enum):
    """Type of delegation rule."""
    
    MANDATORY = "mandatory"          # Cannot be overridden
    STRONGLY_RECOMMENDED = "strongly_recommended"  # Should follow unless good reason
    RECOMMENDED = "recommended"      # Best practice
    PROHIBITED = "prohibited"        # Never do this
    OPTIMIZATION = "optimization"    # Cost/performance optimization


@dataclass
class RuleViolation:
    """A violation of a delegation rule."""
    
    rule_name: str
    rule_type: RuleType
    severity: RuleSeverity
    message: str
    required_model: Optional[str] = None
    actual_model: Optional[str] = None
    suggested_model: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_name": self.rule_name,
            "rule_type": self.rule_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "required_model": self.required_model,
            "actual_model": self.actual_model,
            "suggested_model": self.suggested_model,
            "context": self.context,
        }
    
    def __str__(self) -> str:
        """String representation."""
        severity_icon = {
            RuleSeverity.CRITICAL: "🚨",
            RuleSeverity.HIGH: "⚠️",
            RuleSeverity.MEDIUM: "ℹ️",
            RuleSeverity.LOW: "💡",
        }.get(self.severity, "")
        
        return f"{severity_icon} [{self.severity.value}] {self.message}"


@dataclass
class ValidationResult:
    """Result of delegation validation."""
    
    valid: bool
    violations: List[RuleViolation] = field(default_factory=list)
    suggested_model: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "suggested_model": self.suggested_model,
        }
    
    def has_critical_violations(self) -> bool:
        """Check if there are any critical violations."""
        return any(v.severity == RuleSeverity.CRITICAL for v in self.violations)
    
    def get_highest_severity(self) -> Optional[RuleSeverity]:
        """Get the highest severity level among violations."""
        if not self.violations:
            return None
        
        severity_order = [
            RuleSeverity.CRITICAL,
            RuleSeverity.HIGH,
            RuleSeverity.MEDIUM,
            RuleSeverity.LOW,
        ]
        
        for severity in severity_order:
            if any(v.severity == severity for v in self.violations):
                return severity
        
        return None


class DelegationRules:
    """
    Strict rules governing model delegation decisions.
    
    This class enforces safety-critical constraints and best practices
    for model assignment in planning steps.
    """
    
    # Security-related keywords (case-insensitive)
    SECURITY_KEYWORDS = [
        "security", "vulnerability", "authentication", "authorization",
        "audit", "penetration", "attack", "exploit", "malicious",
        "encryption", "cryptography", "hash", "salt", "jwt", "oauth",
        "token", "credentials", "password", "secret", "key",
        "xss", "csrf", "sqli", "injection", "buffer overflow",
    ]
    
    # Architecture/complexity keywords
    COMPLEXITY_KEYWORDS = [
        "architecture", "design", "system", "complex", "complicated",
        "distributed", "scalable", "concurrent", "parallel", "async",
        "microservices", "monolith", "refactor", "migration",
        "performance", "optimization", "bottleneck",
    ]
    
    # Review/quality keywords
    REVIEW_KEYWORDS = [
        "review", "audit", "check", "verify", "validate", "inspect",
        "quality", "best practice", "standard", "compliance",
        "test", "testing", "coverage", "tdd", "bdd",
    ]
    
    # Implementation/coding keywords
    IMPLEMENTATION_KEYWORDS = [
        "implement", "code", "write", "create", "build", "develop",
        "debug", "fix", "patch", "update", "modify", "change",
        "add", "remove", "delete", "refactor", "optimize",
    ]
    
    # Simple tasks (should not delegate)
    SIMPLE_KEYWORDS = [
        "simple", "quick", "small", "minor", "trivial", "basic",
        "clarify", "explain", "describe", "summarize", "document",
        "chat", "talk", "discuss", "hello", "hi", "thanks",
    ]
    
    def __init__(self):
        """Initialize delegation rules."""
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns for keyword matching."""
        # Case-insensitive word boundary patterns
        self.security_pattern = re.compile(
            r'\b(' + '|'.join(self.SECURITY_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.complexity_pattern = re.compile(
            r'\b(' + '|'.join(self.COMPLEXITY_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.review_pattern = re.compile(
            r'\b(' + '|'.join(self.REVIEW_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.implementation_pattern = re.compile(
            r'\b(' + '|'.join(self.IMPLEMENTATION_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.simple_pattern = re.compile(
            r'\b(' + '|'.join(self.SIMPLE_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
    
    def validate_step(self, step: ModelAwarePlanStep, current_model: str) -> ValidationResult:
        """
        Validate model assignment for a plan step.
        
        Args:
            step: The plan step to validate
            current_model: The model currently executing
            
        Returns:
            ValidationResult with any violations and suggestions
        """
        violations = []
        
        # Apply all rule checks
        self._check_mandatory_rules(step, violations)
        self._check_prohibited_delegations(step, current_model, violations)
        self._check_recommended_assignments(step, violations)
        self._check_cost_limits(step, violations)
        self._check_risk_levels(step, violations)
        
        # Determine if valid (no critical violations)
        has_critical = any(v.severity == RuleSeverity.CRITICAL for v in violations)
        valid = not has_critical
        
        # Suggest best model if violations found
        suggested_model = None
        if violations:
            suggested_model = self._suggest_best_model(step, current_model)
        
        return ValidationResult(
            valid=valid,
            violations=violations,
            suggested_model=suggested_model,
        )
    
    def _check_mandatory_rules(self, step: ModelAwarePlanStep, violations: List[RuleViolation]):
        """Check mandatory rules that cannot be overridden."""
        
        # Rule 1: Security tasks MUST use security model
        if self._is_security_task(step):
            required_model = "dolphin-24b"
            if step.required_model != required_model:
                violations.append(RuleViolation(
                    rule_name="security_mandatory",
                    rule_type=RuleType.MANDATORY,
                    severity=RuleSeverity.CRITICAL,
                    message="Security tasks MUST use security-specialized model (dolphin-24b)",
                    required_model=required_model,
                    actual_model=step.required_model,
                ))
        
        # Rule 2: Critical risk steps MUST use reasoning model
        if step.risk_level == RiskLevel.CRITICAL:
            required_model = "deepseek-reasoner"
            if step.required_model != required_model:
                violations.append(RuleViolation(
                    rule_name="critical_risk_mandatory",
                    rule_type=RuleType.MANDATORY,
                    severity=RuleSeverity.CRITICAL,
                    message="Critical risk steps MUST use reasoning specialist (deepseek-reasoner)",
                    required_model=required_model,
                    actual_model=step.required_model,
                ))
    
    def _check_prohibited_delegations(self, step: ModelAwarePlanStep, current_model: str, 
                                     violations: List[RuleViolation]):
        """Check for prohibited delegation patterns."""
        
        # Rule 1: Don't delegate simple tasks
        if self._is_simple_task(step) and step.required_model and step.required_model != current_model:
            violations.append(RuleViolation(
                rule_name="simple_task_prohibited",
                rule_type=RuleType.PROHIBITED,
                severity=RuleSeverity.HIGH,
                message="Simple tasks should not be delegated",
                actual_model=step.required_model,
            ))
        
        # Rule 2: Don't delegate context-switching tasks
        if self._is_context_switching_task(step) and step.required_model and step.required_model != current_model:
            violations.append(RuleViolation(
                rule_name="context_switching_prohibited",
                rule_type=RuleType.PROHIBITED,
                severity=RuleSeverity.MEDIUM,
                message="Context-switching tasks (clarify, explain) should not be delegated",
                actual_model=step.required_model,
            ))
        
        # Rule 3: Don't delegate to same model (wasteful)
        if step.required_model == current_model:
            violations.append(RuleViolation(
                rule_name="self_delegation_prohibited",
                rule_type=RuleType.PROHIBITED,
                severity=RuleSeverity.LOW,
                message="Delegating to the same model is wasteful",
                actual_model=step.required_model,
            ))
    
    def _check_recommended_assignments(self, step: ModelAwarePlanStep, violations: List[RuleViolation]):
        """Check recommended model assignments."""
        
        # Rule 1: Complex tasks SHOULD use reasoning model
        if self._is_complex_task(step) and not step.required_model:
            violations.append(RuleViolation(
                rule_name="complex_task_recommended",
                rule_type=RuleType.STRONGLY_RECOMMENDED,
                severity=RuleSeverity.HIGH,
                message="Complex tasks should use reasoning specialist (deepseek-reasoner)",
                suggested_model="deepseek-reasoner",
            ))
        
        # Rule 2: Implementation tasks CAN use coding model
        if self._is_implementation_task(step) and not step.required_model:
            violations.append(RuleViolation(
                rule_name="implementation_recommended",
                rule_type=RuleType.RECOMMENDED,
                severity=RuleSeverity.MEDIUM,
                message="Implementation tasks can use coding specialist (grok-code-fast-1)",
                suggested_model="grok-code-fast-1",
            ))
        
        # Rule 3: Review tasks SHOULD use review model
        if self._is_review_task(step) and not step.required_model:
            violations.append(RuleViolation(
                rule_name="review_task_recommended",
                rule_type=RuleType.STRONGLY_RECOMMENDED,
                severity=RuleSeverity.HIGH,
                message="Review tasks should use review specialist (gpt-5.1-codex-mini)",
                suggested_model="gpt-5.1-codex-mini",
            ))
    
    def _check_cost_limits(self, step: ModelAwarePlanStep, violations: List[RuleViolation]):
        """Check cost limit violations."""
        # Maximum cost per step (USD)
        MAX_COST_PER_STEP = 5.0
        
        if step.max_cost_usd and step.max_cost_usd > MAX_COST_PER_STEP:
            violations.append(RuleViolation(
                rule_name="cost_limit_exceeded",
                rule_type=RuleType.OPTIMIZATION,
                severity=RuleSeverity.MEDIUM,
                message=f"Step cost limit ${step.max_cost_usd:.2f} exceeds maximum ${MAX_COST_PER_STEP:.2f}",
            ))
    
    def _check_risk_levels(self, step: ModelAwarePlanStep, violations: List[RuleViolation]):
        """Check risk level requirements."""
        
        # High/Critical risk steps should have review required
        if step.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] and not step.review_required:
            violations.append(RuleViolation(
                rule_name="high_risk_review_required",
                rule_type=RuleType.STRONGLY_RECOMMENDED,
                severity=RuleSeverity.HIGH,
                message=f"High risk ({step.risk_level.value}) steps should require review",
            ))
        
        # Security-related steps should have security review
        if step.security_related and step.review_model != "dolphin-24b":
            violations.append(RuleViolation(
                rule_name="security_review_required",
                rule_type=RuleType.STRONGLY_RECOMMENDED,
                severity=RuleSeverity.HIGH,
                message="Security-related steps should be reviewed by security model",
                suggested_model="dolphin-24b",
            ))
    
    def _is_security_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task is security-related."""
        if step.security_related:
            return True
        
        if self.security_pattern.search(step.description):
            return True
        
        return False
    
    def _is_complex_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task is complex."""
        if step.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True
        
        if self.complexity_pattern.search(step.description):
            return True
        
        return False
    
    def _is_review_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task is a review/audit."""
        if self.review_pattern.search(step.description):
            return True
        
        return False
    
    def _is_implementation_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task is implementation/coding."""
        if self.implementation_pattern.search(step.description):
            return True
        
        return False
    
    def _is_simple_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task is simple."""
        if self.simple_pattern.search(step.description):
            return True
        
        # Short descriptions are often simple
        if len(step.description.split()) < 5:
            return True
        
        return False
    
    def _is_context_switching_task(self, step: ModelAwarePlanStep) -> bool:
        """Check if task involves context switching."""
        context_switching_words = ["clarify", "explain", "describe", "what", "how", "why"]
        pattern = re.compile(r'\b(' + '|'.join(context_switching_words) + r')\b', re.IGNORECASE)
        return bool(pattern.search(step.description))
    
    def _suggest_best_model(self, step: ModelAwarePlanStep, current_model: str) -> str:
        """
        Suggest the best model for a step based on rules.
        
        Priority:
        1. Security tasks → dolphin-24b
        2. Complex tasks → deepseek-reasoner
        3. Review tasks → gpt-5.1-codex-mini
        4. Implementation tasks → grok-code-fast-1
        5. Simple tasks → current_model (don't delegate)
        """
        if self._is_security_task(step):
            return "dolphin-24b"
        
        if self._is_complex_task(step):
            return "deepseek-reasoner"
        
        if self._is_review_task(step):
            return "gpt-5.1-codex-mini"
        
        if self._is_implementation_task(step):
            return "grok-code-fast-1"
        
        # For simple tasks or no clear specialization, don't delegate
        return current_model
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get a summary of all rules."""
        return {
            "mandatory_rules": [
                {
                    "name": "security_mandatory",
                    "description": "Security tasks MUST use dolphin-24b",
                    "keywords": self.SECURITY_KEYWORDS,
                },
                {
                    "name": "critical_risk_mandatory",
                    "description": "Critical risk steps MUST use deepseek-reasoner",
                },
            ],
            "prohibited_rules": [
                {
                    "name": "simple_task_prohibited",
                    "description": "Simple tasks should not be delegated",
                    "keywords": self.SIMPLE_KEYWORDS,
                },
                {
                    "name": "context_switching_prohibited",
                    "description": "Context-switching tasks should not be delegated",
                },
            ],
            "recommended_rules": [
                {
                    "name": "complex_task_recommended",
                    "description": "Complex tasks should use deepseek-reasoner",
                    "keywords": self.COMPLEXITY_KEYWORDS,
                },
                {
                    "name": "implementation_recommended",
                    "description": "Implementation tasks can use grok-code-fast-1",
                    "keywords": self.IMPLEMENTATION_KEYWORDS,
                },
                {
                    "name": "review_task_recommended",
                    "description": "Review tasks should use gpt-5.1-codex-mini",
                    "keywords": self.REVIEW_KEYWORDS,
                },
            ],
            "cost_limits": {
                "max_cost_per_step": 5.0,  # USD
            },
            "risk_requirements": {
                "high_risk_requires_review": True,
                "security_requires_security_review": True,
            },
        }