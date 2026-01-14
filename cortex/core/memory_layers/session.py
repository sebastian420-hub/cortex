"""Session memory for Cortex agent.

Session memory extends the base MemoryBank with:
- Tracking of failed approaches and what was learned
- Successful patterns and strategies
- Session-level insights and progress
- Integration with working memory for context

This represents the "conversation history" and learning within a single session.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import uuid

from ..memory import MemoryBank, MemoryItem, MemoryType, MemorySource


class SessionMemoryType(str, Enum):
    """Extended memory types for session memory."""
    
    FAILED_APPROACH = "failed_approach"  # What didn't work and why
    SUCCESSFUL_PATTERN = "successful_pattern"  # What worked well
    SESSION_INSIGHT = "session_insight"  # High-level insight from session
    PROGRESS_MARKER = "progress_marker"  # Mark progress in complex tasks
    CONTEXT_SUMMARY = "context_summary"  # Summary of assembled context


@dataclass
class FailedApproach:
    """Record of a failed approach with analysis."""
    
    approach: str  # What was tried
    error: str  # What went wrong
    root_cause: Optional[str] = None  # Why it failed (if known)
    alternative_suggested: Optional[str] = None  # What to try instead
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "approach": self.approach,
            "error": self.error,
            "root_cause": self.root_cause,
            "alternative_suggested": self.alternative_suggested,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailedApproach":
        """Create from dictionary."""
        return cls(
            approach=data["approach"],
            error=data["error"],
            root_cause=data.get("root_cause"),
            alternative_suggested=data.get("alternative_suggested"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SuccessfulPattern:
    """Record of a successful pattern or strategy."""
    
    pattern: str  # Description of the pattern
    context: str  # Context where it worked
    effectiveness: float = 1.0  # 0.0 to 1.0
    applications: int = 1  # Number of times successfully applied
    last_applied: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern": self.pattern,
            "context": self.context,
            "effectiveness": self.effectiveness,
            "applications": self.applications,
            "last_applied": self.last_applied,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SuccessfulPattern":
        """Create from dictionary."""
        return cls(
            pattern=data["pattern"],
            context=data["context"],
            effectiveness=data.get("effectiveness", 1.0),
            applications=data.get("applications", 1),
            last_applied=data.get("last_applied", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class EnhancedMemoryBank(MemoryBank):
    """
    Extended memory bank with session-level capabilities.
    
    This extends the base MemoryBank with:
    1. Tracking of failed approaches (what didn't work)
    2. Recording successful patterns (what worked well)
    3. Session insights (high-level learnings)
    4. Progress tracking for complex tasks
    5. Context assembly summaries
    """
    
    def __init__(self, max_items: int = 100):
        """
        Initialize enhanced memory bank.
        
        Args:
            max_items: Maximum items to retain (oldest pruned first)
        """
        super().__init__(max_items)
        self.failed_approaches: List[FailedApproach] = []
        self.successful_patterns: List[SuccessfulPattern] = []
        self.session_insights: List[MemoryItem] = []
        self.progress_markers: Dict[str, str] = {}  # task_id -> progress_description
        self.context_summaries: Dict[str, str] = {}  # context_key -> summary
        
    def record_failed_approach(
        self,
        approach: str,
        error: str,
        root_cause: Optional[str] = None,
        alternative_suggested: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a failed approach with analysis.
        
        Args:
            approach: What was tried
            error: What went wrong
            root_cause: Why it failed (if known)
            alternative_suggested: What to try instead
            metadata: Additional metadata
        """
        failed_approach = FailedApproach(
            approach=approach,
            error=error,
            root_cause=root_cause,
            alternative_suggested=alternative_suggested,
            metadata=metadata or {},
        )
        
        # Keep only most recent failed approaches (limit to 10)
        self.failed_approaches.append(failed_approach)
        if len(self.failed_approaches) > 10:
            self.failed_approaches = self.failed_approaches[-10:]
        
        # Also add as a regular memory item
        self.add(MemoryItem(
            type=MemoryType.ERROR,
            content=f"Failed approach: {approach}. Error: {error}",
            source=MemorySource.TOOL_RESULT,
            confidence=1.0,
            metadata={"failed_approach": True, **metadata} if metadata else {"failed_approach": True},
        ))
    
    def record_successful_pattern(
        self,
        pattern: str,
        context: str,
        effectiveness: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a successful pattern or strategy.
        
        Args:
            pattern: Description of the pattern
            context: Context where it worked
            effectiveness: Effectiveness score 0.0 to 1.0
            metadata: Additional metadata
        """
        # Check if similar pattern already exists
        for existing in self.successful_patterns:
            if self._is_similar_pattern(existing.pattern, pattern):
                # Update existing pattern
                existing.applications += 1
                existing.last_applied = datetime.now().isoformat()
                # Slightly adjust effectiveness toward new value
                existing.effectiveness = (existing.effectiveness + effectiveness) / 2
                return
        
        # Add new pattern
        successful_pattern = SuccessfulPattern(
            pattern=pattern,
            context=context,
            effectiveness=effectiveness,
            applications=1,
            metadata=metadata or {},
        )
        
        self.successful_patterns.append(successful_pattern)
        
        # Keep patterns sorted by effectiveness and recency
        self.successful_patterns.sort(
            key=lambda x: (x.effectiveness, x.last_applied),
            reverse=True
        )
        
        # Limit to top 20 patterns
        if len(self.successful_patterns) > 20:
            self.successful_patterns = self.successful_patterns[:20]
    
    def add_session_insight(
        self,
        insight: str,
        confidence: float = 1.0,
        source: MemorySource = MemorySource.INFERRED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a session-level insight.
        
        Args:
            insight: The insight text
            confidence: Confidence score 0.0 to 1.0
            source: Source of the insight
            metadata: Additional metadata
        """
        memory_item = MemoryItem(
            type=MemoryType.CONTEXT,
            content=insight,
            source=source,
            confidence=confidence,
            metadata={"session_insight": True, **metadata} if metadata else {"session_insight": True},
        )
        
        self.session_insights.append(memory_item)
        self.add(memory_item)
    
    def mark_progress(self, task_id: str, progress: str) -> None:
        """
        Mark progress on a complex task.
        
        Args:
            task_id: Identifier for the task
            progress: Description of progress made
        """
        self.progress_markers[task_id] = progress
        
        # Also add as a memory item
        self.add(MemoryItem(
            type=MemoryType.CONTEXT,
            content=f"Progress on {task_id}: {progress}",
            source=MemorySource.INFERRED,
            confidence=1.0,
            metadata={"progress_marker": True, "task_id": task_id},
        ))
    
    def add_context_summary(self, context_key: str, summary: str) -> None:
        """
        Add a summary of assembled context.
        
        Args:
            context_key: Key identifying the context
            summary: Summary text
        """
        self.context_summaries[context_key] = summary
        
        # Also add as a memory item
        self.add(MemoryItem(
            type=MemoryType.CONTEXT,
            content=f"Context summary for {context_key}: {summary[:100]}...",
            source=MemorySource.INFERRED,
            confidence=1.0,
            metadata={"context_summary": True, "context_key": context_key},
        ))
    
    def extract_learnings_from_tool_results(self, tool_results: List[Dict[str, Any]]) -> None:
        """
        Extract learnings from tool execution results.
        
        Args:
            tool_results: List of tool result dictionaries
        """
        for result in tool_results:
            if not isinstance(result, dict):
                continue
            
            success = result.get("success", False)
            tool_name = result.get("tool_name", "unknown")
            
            if not success:
                error = result.get("error", "Unknown error")
                error_type = result.get("error_type", "execution")
                
                # Record failed approach
                self.record_failed_approach(
                    approach=f"Tool: {tool_name}",
                    error=f"{error_type}: {error}",
                    metadata={
                        "tool_name": tool_name,
                        "error_type": error_type,
                        "result": result,
                    },
                )
            else:
                # Check for patterns in successful execution
                result_data = result.get("data", {})
                
                # Look for file operations
                if "path" in result_data and tool_name in ["read_file", "write_file", "edit"]:
                    pattern = f"File operation {tool_name} on {result_data.get('path')}"
                    context = f"Successfully used {tool_name} tool"
                    self.record_successful_pattern(pattern, context)
                
                # Look for search operations
                elif "matches" in result_data and tool_name in ["grep", "search_files"]:
                    pattern_count = result_data.get("match_count", 0)
                    pattern = f"Search with {tool_name} found {pattern_count} matches"
                    context = f"Successfully used {tool_name} for discovery"
                    self.record_successful_pattern(pattern, context)
    
    def get_session_summary(self) -> str:
        """
        Get comprehensive session summary for planning.
        
        Returns:
            Formatted summary of session memory
        """
        sections = []
        
        # Base memory summary
        base_summary = super().get_summary()
        if base_summary:
            sections.append(base_summary)
        
        # Failed approaches
        if self.failed_approaches:
            failed_list = []
            for i, fa in enumerate(self.failed_approaches[-3:], 1):
                failed_list.append(f"{i}. {fa.approach}: {fa.error}")
                if fa.alternative_suggested:
                    failed_list.append(f"   → Try: {fa.alternative_suggested}")
            
            sections.append("Recent Failed Approaches:\\n" + "\\n".join(failed_list))
        
        # Successful patterns
        if self.successful_patterns:
            pattern_list = []
            for i, sp in enumerate(self.successful_patterns[:3], 1):
                pattern_list.append(f"{i}. {sp.pattern} (used {sp.applications} times)")
            
            sections.append("Successful Patterns:\\n" + "\\n".join(pattern_list))
        
        # Session insights
        if self.session_insights:
            insight_list = []
            for i, insight in enumerate(self.session_insights[-3:], 1):
                insight_list.append(f"{i}. {insight.content}")
            
            sections.append("Session Insights:\\n" + "\\n".join(insight_list))
        
        # Progress markers
        if self.progress_markers:
            progress_list = []
            for task_id, progress in list(self.progress_markers.items())[-3:]:
                progress_list.append(f"- {task_id}: {progress}")
            
            sections.append("Recent Progress:\\n" + "\\n".join(progress_list))
        
        return "\\n\\n".join(sections)
    
    def get_failed_approaches_for_context(self, context: str) -> List[FailedApproach]:
        """
        Get failed approaches relevant to a specific context.
        
        Args:
            context: Context to match against
            
        Returns:
            List of relevant failed approaches
        """
        relevant = []
        context_lower = context.lower()
        
        for fa in self.failed_approaches:
            if (context_lower in fa.approach.lower() or 
                context_lower in fa.error.lower() or
                (fa.alternative_suggested and context_lower in fa.alternative_suggested.lower())):
                relevant.append(fa)
        
        return relevant
    
    def get_successful_patterns_for_context(self, context: str) -> List[SuccessfulPattern]:
        """
        Get successful patterns relevant to a specific context.
        
        Args:
            context: Context to match against
            
        Returns:
            List of relevant successful patterns
        """
        relevant = []
        context_lower = context.lower()
        
        for sp in self.successful_patterns:
            if (context_lower in sp.pattern.lower() or 
                context_lower in sp.context.lower()):
                relevant.append(sp)
        
        return relevant
    
    def clear_session_data(self) -> None:
        """Clear session-specific data (but keep base memories)."""
        self.failed_approaches.clear()
        self.successful_patterns.clear()
        self.session_insights.clear()
        self.progress_markers.clear()
        self.context_summaries.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        base_dict = super().to_dict()
        
        enhanced_dict = {
            **base_dict,
            "failed_approaches": [fa.to_dict() for fa in self.failed_approaches],
            "successful_patterns": [sp.to_dict() for sp in self.successful_patterns],
            "session_insights": [si.to_dict() for si in self.session_insights],
            "progress_markers": self.progress_markers,
            "context_summaries": self.context_summaries,
        }
        
        return enhanced_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedMemoryBank":
        """Create from dictionary."""
        # Extract enhanced data
        failed_approaches_data = data.pop("failed_approaches", [])
        successful_patterns_data = data.pop("successful_patterns", [])
        session_insights_data = data.pop("session_insights", [])
        progress_markers = data.pop("progress_markers", {})
        context_summaries = data.pop("context_summaries", {})
        
        # Create base memory bank
        emb = cls(max_items=data.get("max_items", 100))
        
        # Restore base items
        if "items" in data:
            emb.items = [MemoryItem.from_dict(item) for item in data["items"]]
        
        # Restore enhanced data
        emb.failed_approaches = [FailedApproach.from_dict(fa) for fa in failed_approaches_data]
        emb.successful_patterns = [SuccessfulPattern.from_dict(sp) for sp in successful_patterns_data]
        emb.session_insights = [MemoryItem.from_dict(si) for si in session_insights_data]
        emb.progress_markers = progress_markers
        emb.context_summaries = context_summaries
        
        return emb
    
    def _is_similar_pattern(self, pattern1: str, pattern2: str, threshold: float = 0.6) -> bool:
        """
        Check if two patterns are similar.
        
        Args:
            pattern1: First pattern description
            pattern2: Second pattern description
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            True if patterns are similar
        """
        words1 = set(pattern1.lower().split())
        words2 = set(pattern2.lower().split())
        
        if not words1 or not words2:
            return pattern1.lower() == pattern2.lower()
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return (intersection / union) >= threshold if union > 0 else False