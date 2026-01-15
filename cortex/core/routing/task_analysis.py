"""
Basic Task Analysis Engine for Phase 1.

This provides simple keyword-based task classification to determine the type
of task being requested by the user. In Phase 1, this is rule-based; in later
phases, it will be replaced with AI-powered analysis.
"""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks that Cortex can handle."""
    PLANNING = "planning"
    SECURITY = "security"
    CODING = "coding"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ANALYSIS = "analysis"
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass
class TaskComplexity:
    """Complexity assessment of a task."""
    score: int  # 1-10 scale
    reasoning: str
    factors: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskAnalysis:
    """Result of task analysis."""
    task_type: TaskType
    complexity: TaskComplexity
    keywords: List[str]
    confidence: float  # 0.0 to 1.0
    raw_input: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskAnalysisEngine:
    """
    Basic task analysis engine using keyword matching.
    
    In Phase 1, this uses simple keyword matching to classify tasks.
    In later phases, this will be enhanced with NLP and AI-powered analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the task analysis engine.
        
        Args:
            config: Configuration dictionary for customizing analysis rules
        """
        self.config = config or {}
        
        # Define task classification rules (keyword -> task type)
        self.task_rules = {
            TaskType.PLANNING: [
                "plan", "strategy", "design", "architecture", "roadmap",
                "timeline", "schedule", "milestone", "approach", "methodology"
            ],
            TaskType.SECURITY: [
                "security", "vulnerability", "penetration", "attack", "threat",
                "risk", "secure", "authentication", "authorization", "encryption",
                "jwt", "oauth", "sso", "firewall", "malware", "exploit", "cve"
            ],
            TaskType.CODING: [
                "code", "implement", "write", "function", "method", "class",
                "module", "api", "endpoint", "service", "library", "package",
                "algorithm", "data structure", "logic", "program", "script"
            ],
            TaskType.DEBUGGING: [
                "debug", "fix", "error", "bug", "issue", "problem", "crash",
                "exception", "stack trace", "log", "trace", "diagnose",
                "troubleshoot", "investigate", "resolve"
            ],
            TaskType.REFACTORING: [
                "refactor", "clean up", "optimize", "improve", "restructure",
                "reorganize", "simplify", "modernize", "update", "migrate",
                "rewrite", "redesign", "overhaul"
            ],
            TaskType.DOCUMENTATION: [
                "document", "explain", "comment", "describe", "manual",
                "guide", "tutorial", "readme", "api doc", "specification",
                "requirements", "user guide", "technical writing"
            ],
            TaskType.TESTING: [
                "test", "verify", "validate", "quality", "assurance", "qa",
                "unit test", "integration test", "test case", "coverage",
                "automation", "pytest", "unittest", "assert", "check"
            ],
            TaskType.ANALYSIS: [
                "analyze", "review", "examine", "assess", "evaluate",
                "inspect", "study", "research", "understand", "comprehend",
                "parse", "interpret", "metrics", "statistics", "data"
            ]
        }
        
        # Load custom rules from config
        if "task_rules" in self.config:
            for task_type_str, keywords in self.config["task_rules"].items():
                try:
                    task_type = TaskType(task_type_str.lower())
                    self.task_rules[task_type] = keywords
                except ValueError:
                    logger.warning(f"Unknown task type in config: {task_type_str}")
        
        # Complexity estimation patterns
        self.complexity_patterns = {
            "simple": [
                r"\bsimple\b", r"\bbasic\b", r"\bquick\b", r"\beasy\b",
                r"\bminor\b", r"\bsmall\b", r"\btrivial\b", r"\bstraightforward\b"
            ],
            "complex": [
                r"\bcomplex\b", r"\bdifficult\b", r"\bhard\b", r"\bchallenging\b",
                r"\bmajor\b", r"\blarge\b", r"\bsignificant\b", r"\bcomplicated\b",
                r"\badvanced\b", r"\bsophisticated\b"
            ],
            "urgent": [
                r"\burgent\b", r"\bimmediate\b", r"\basap\b", r"\bemergency\b",
                r"\bcritical\b", r"\bimportant\b", r"\bpriority\b", r"\brush\b"
            ]
        }
    
    def analyze(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> TaskAnalysis:
        """
        Analyze a user's request to determine task type and complexity.
        
        Args:
            user_input: The user's natural language request
            context: Optional context information (not used in Phase 1)
            
        Returns:
            TaskAnalysis object with classification results
        """
        if not user_input or not user_input.strip():
            return self._create_unknown_analysis(user_input)
        
        user_input_lower = user_input.lower()
        
        # Step 1: Classify task type
        task_type, matched_keywords, confidence = self._classify_task(user_input_lower)
        
        # Step 2: Estimate complexity
        complexity = self._estimate_complexity(user_input_lower)
        
        # Step 3: Check for security sensitivity
        security_sensitive = self._check_security_sensitivity(user_input_lower)
        
        # Step 4: Create analysis result
        analysis = TaskAnalysis(
            task_type=task_type,
            complexity=complexity,
            keywords=matched_keywords,
            confidence=confidence,
            raw_input=user_input,
            metadata={
                "security_sensitive": security_sensitive,
                "word_count": len(user_input.split()),
                "has_code_context": self._has_code_context(user_input),
                "classification_method": "keyword_matching"
            }
        )
        
        logger.debug(
            f"Task analysis: type={task_type.value}, complexity={complexity.score}, "
            f"confidence={confidence:.2f}, security={security_sensitive}"
        )
        
        return analysis
    
    def _classify_task(self, user_input: str) -> tuple[TaskType, List[str], float]:
        """
        Classify task type using keyword matching.
        
        Args:
            user_input: Lowercase user input
            
        Returns:
            Tuple of (task_type, matched_keywords, confidence_score)
        """
        matched_keywords = []
        task_scores: Dict[TaskType, int] = {task_type: 0 for task_type in self.task_rules}
        
        # Count keyword matches for each task type
        for task_type, keywords in self.task_rules.items():
            for keyword in keywords:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, user_input):
                    task_scores[task_type] += 1
                    matched_keywords.append(keyword)
        
        # Find task type with highest score
        if not matched_keywords:
            return TaskType.GENERAL, [], 0.5
        
        max_score = max(task_scores.values())
        if max_score == 0:
            return TaskType.GENERAL, [], 0.5
        
        # Get all task types with max score (handle ties)
        top_tasks = [task_type for task_type, score in task_scores.items() 
                    if score == max_score]
        
        # If multiple tasks tied, choose the first one
        selected_task = top_tasks[0]
        
        # Calculate confidence based on score and uniqueness
        total_keywords = sum(task_scores.values())
        confidence = max_score / total_keywords if total_keywords > 0 else 0.5
        
        # Reduce confidence if multiple tasks have similar scores
        if len(top_tasks) > 1:
            confidence *= 0.7  # Reduce confidence for ambiguous tasks
        
        # Clamp confidence to reasonable range
        confidence = max(0.3, min(0.9, confidence))
        
        return selected_task, matched_keywords, confidence
    
    def _estimate_complexity(self, user_input: str) -> TaskComplexity:
        """
        Estimate task complexity based on keyword patterns.
        
        Args:
            user_input: Lowercase user input
            
        Returns:
            TaskComplexity object with score and reasoning
        """
        # Start with baseline complexity
        score = 3  # Default: medium-low complexity
        factors = {}
        
        # Check for simple patterns
        simple_matches = sum(
            1 for pattern in self.complexity_patterns["simple"]
            if re.search(pattern, user_input)
        )
        if simple_matches > 0:
            score -= 1
            factors["simple_keywords"] = simple_matches
        
        # Check for complex patterns
        complex_matches = sum(
            1 for pattern in self.complexity_patterns["complex"]
            if re.search(pattern, user_input)
        )
        if complex_matches > 0:
            score += complex_matches
            factors["complex_keywords"] = complex_matches
        
        # Check for urgent patterns
        urgent_matches = sum(
            1 for pattern in self.complexity_patterns["urgent"]
            if re.search(pattern, user_input)
        )
        if urgent_matches > 0:
            score += 1  # Urgent tasks often require more careful handling
            factors["urgent_keywords"] = urgent_matches
        
        # Adjust based on input length (longer requests often more complex)
        word_count = len(user_input.split())
        if word_count > 50:
            score += 1
            factors["long_input"] = word_count
        elif word_count < 10:
            score -= 1
            factors["short_input"] = word_count
        
        # Clamp score to 1-10 range
        score = max(1, min(10, score))
        
        # Build reasoning
        reasoning_parts = []
        if simple_matches > 0:
            reasoning_parts.append(f"contains {simple_matches} simple keyword(s)")
        if complex_matches > 0:
            reasoning_parts.append(f"contains {complex_matches} complex keyword(s)")
        if urgent_matches > 0:
            reasoning_parts.append(f"contains {urgent_matches} urgent keyword(s)")
        
        reasoning = f"Complexity score {score}/10"
        if reasoning_parts:
            reasoning += " based on: " + ", ".join(reasoning_parts)
        else:
            reasoning += " (default baseline)"
        
        return TaskComplexity(
            score=score,
            reasoning=reasoning,
            factors=factors
        )
    
    def _check_security_sensitivity(self, user_input: str) -> bool:
        """
        Check if task involves security-sensitive content.
        
        Args:
            user_input: Lowercase user input
            
        Returns:
            True if task is security-sensitive
        """
        security_keywords = self.task_rules[TaskType.SECURITY]
        
        for keyword in security_keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, user_input):
                return True
        
        # Additional security context checks
        security_contexts = [
            r"\bpassword\b", r"\bsecret\b", r"\bkey\b", r"\btoken\b",
            r"\bcredential\b", r"\bauth\b", r"\bpermission\b", r"\baccess\b",
            r"\bprivilege\b", r"\badmin\b", r"\broot\b", r"\bsuperuser\b"
        ]
        
        for pattern in security_contexts:
            if re.search(pattern, user_input):
                return True
        
        return False
    
    def _has_code_context(self, user_input: str) -> bool:
        """
        Check if input suggests code-related context.
        
        Args:
            user_input: User input
            
        Returns:
            True if input suggests code context
        """
        code_indicators = [
            r"\.py\b", r"\.js\b", r"\.ts\b", r"\.java\b", r"\.cpp\b",
            r"\.go\b", r"\.rs\b", r"\.php\b", r"\.rb\b", r"\.cs\b",
            r"\bfunction\b", r"\bclass\b", r"\bdef\b", r"\bfn\b",
            r"\bimport\b", r"\brequire\b", r"\bexport\b", r"\bmodule\b"
        ]
        
        for pattern in code_indicators:
            if re.search(pattern, user_input, re.IGNORECASE):
                return True
        
        return False
    
    def _create_unknown_analysis(self, user_input: str) -> TaskAnalysis:
        """Create analysis for unknown/empty input."""
        return TaskAnalysis(
            task_type=TaskType.UNKNOWN,
            complexity=TaskComplexity(
                score=1,
                reasoning="Empty or invalid input",
                factors={"empty_input": True}
            ),
            keywords=[],
            confidence=0.1,
            raw_input=user_input,
            metadata={
                "security_sensitive": False,
                "word_count": 0,
                "has_code_context": False,
                "classification_method": "unknown_input"
            }
        )
    
    def get_task_type_description(self, task_type: TaskType) -> str:
        """
        Get human-readable description of task type.
        
        Args:
            task_type: Task type enum
            
        Returns:
            Description string
        """
        descriptions = {
            TaskType.PLANNING: "Planning and strategy tasks",
            TaskType.SECURITY: "Security analysis and vulnerability assessment",
            TaskType.CODING: "Code implementation and development",
            TaskType.DEBUGGING: "Debugging and issue resolution",
            TaskType.REFACTORING: "Code refactoring and optimization",
            TaskType.DOCUMENTATION: "Documentation and explanation",
            TaskType.TESTING: "Testing and quality assurance",
            TaskType.ANALYSIS: "Analysis and review",
            TaskType.GENERAL: "General assistance",
            TaskType.UNKNOWN: "Unknown task type"
        }
        return descriptions.get(task_type, "Unknown task type")
    
    def suggest_models_for_task(self, task_analysis: TaskAnalysis) -> List[str]:
        """
        Suggest appropriate models for a given task analysis.
        
        Args:
            task_analysis: Analyzed task
            
        Returns:
            List of suggested model names
        """
        # Phase 1: Simple model suggestions based on task type
        suggestions = {
            TaskType.PLANNING: ["deepseek-reasoner", "claude-3-5-sonnet"],
            TaskType.SECURITY: ["deepseek-coder", "claude-3-5-sonnet"],
            TaskType.CODING: ["deepseek-coder", "llama3.2"],
            TaskType.DEBUGGING: ["deepseek-reasoner", "claude-3-5-sonnet"],
            TaskType.REFACTORING: ["deepseek-coder", "claude-3-5-sonnet"],
            TaskType.DOCUMENTATION: ["claude-3-5-sonnet", "llama3.2"],
            TaskType.TESTING: ["deepseek-coder", "llama3.2"],
            TaskType.ANALYSIS: ["deepseek-reasoner", "claude-3-5-sonnet"],
            TaskType.GENERAL: ["llama3.2", "deepseek-chat"],
            TaskType.UNKNOWN: ["llama3.2"]  # Default fallback
        }
        
        # Adjust based on complexity
        base_suggestions = suggestions.get(task_analysis.task_type, ["llama3.2"])
        
        # For high complexity tasks, prioritize more capable models
        if task_analysis.complexity.score >= 7:
            if TaskType.SECURITY in suggestions:
                # For complex security, prefer Claude
                return ["claude-3-5-sonnet", "deepseek-reasoner"]
            else:
                # For other complex tasks, prefer reasoning models
                return ["deepseek-reasoner", "claude-3-5-sonnet"]
        
        # For security-sensitive tasks, prefer security-aware models
        if task_analysis.metadata.get("security_sensitive", False):
            return ["claude-3-5-sonnet", "deepseek-reasoner"]
        
        return base_suggestions


# Global instance for convenience
_default_analyzer: Optional[TaskAnalysisEngine] = None

def get_task_analyzer(config: Optional[Dict[str, Any]] = None) -> TaskAnalysisEngine:
    """
    Get or create the global task analyzer instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        TaskAnalysisEngine instance
    """
    global _default_analyzer
    if _default_analyzer is None or config is not None:
        _default_analyzer = TaskAnalysisEngine(config)
    return _default_analyzer

def analyze_task(user_input: str, context: Optional[Dict[str, Any]] = None) -> TaskAnalysis:
    """
    Convenience function to analyze a task.
    
    Args:
        user_input: User's natural language request
        context: Optional context
        
    Returns:
        TaskAnalysis object
    """
    analyzer = get_task_analyzer()
    return analyzer.analyze(user_input, context)