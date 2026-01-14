"""Working memory for Cortex agent.

Working memory is short-term memory that tracks:
- Current task context
- Files currently being examined
- Tool execution state
- Immediate insights and observations

This is the "scratchpad" of the agent's current thinking process.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple


class WorkingMemoryItemType(str, Enum):
    """Types of items in working memory."""
    
    FILE_CONTEXT = "file_context"      # File being examined with summary
    TOOL_CONTEXT = "tool_context"      # Current tool execution chain
    TASK_STATE = "task_state"          # State of current task
    INSIGHT = "insight"                # Immediate insight/observation
    QUESTION = "question"              # Open question being considered
    HYPOTHESIS = "hypothesis"          # Hypothesis being tested
    PLAN_STEP = "plan_step"            # Current plan step being executed


@dataclass
class FileContext:
    """Context about a file currently in working memory."""
    
    path: str
    summary: str
    lines_examined: Optional[Tuple[int, int]] = None  # (start, end) lines
    relevance_score: float = 1.0  # 0.0 to 1.0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "summary": self.summary,
            "lines_examined": self.lines_examined,
            "relevance_score": self.relevance_score,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileContext":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            summary=data["summary"],
            lines_examined=data.get("lines_examined"),
            relevance_score=data.get("relevance_score", 1.0),
            last_accessed=data.get("last_accessed", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolContext:
    """Context about current tool execution chain."""
    
    tool_name: str
    arguments: Dict[str, Any]
    purpose: str  # Why this tool is being used
    expected_outcome: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # IDs of dependent tools
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "purpose": self.purpose,
            "expected_outcome": self.expected_outcome,
            "dependencies": self.dependencies,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolContext":
        """Create from dictionary."""
        return cls(
            tool_name=data["tool_name"],
            arguments=data.get("arguments", {}),
            purpose=data.get("purpose", ""),
            expected_outcome=data.get("expected_outcome"),
            dependencies=data.get("dependencies", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class WorkingMemoryItem:
    """A single item in working memory."""
    
    id: str
    type: WorkingMemoryItemType
    content: Any  # Can be FileContext, ToolContext, string, dict, etc.
    priority: int = 1  # 1=low, 5=critical
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None  # When this item should be evicted
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        content_dict = self.content
        if hasattr(self.content, "to_dict"):
            content_dict = self.content.to_dict()
        elif not isinstance(content_dict, (dict, list, str, int, float, bool, type(None))):
            content_dict = str(content_dict)
            
        return {
            "id": self.id,
            "type": self.type.value,
            "content": content_dict,
            "priority": self.priority,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemoryItem":
        """Create from dictionary."""
        item_type = WorkingMemoryItemType(data["type"])
        content = data["content"]
        
        # Reconstruct typed content based on type
        if item_type == WorkingMemoryItemType.FILE_CONTEXT and isinstance(content, dict):
            content = FileContext.from_dict(content)
        elif item_type == WorkingMemoryItemType.TOOL_CONTEXT and isinstance(content, dict):
            content = ToolContext.from_dict(content)
        
        return cls(
            id=data["id"],
            type=item_type,
            content=content,
            priority=data.get("priority", 1),
            created_at=data.get("created_at", datetime.now().isoformat()),
            accessed_at=data.get("accessed_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
        )
    
    def touch(self) -> None:
        """Update accessed timestamp."""
        self.accessed_at = datetime.now().isoformat()


class WorkingMemory:
    """
    Short-term memory for current task execution.
    
    Working memory is a limited-capacity store that holds:
    - Files currently being examined (with summaries)
    - Current tool execution context
    - Task state and progress
    - Immediate insights and observations
    - Open questions and hypotheses
    
    Items in working memory are evicted based on:
    1. Age (older items removed first)
    2. Access frequency (frequently accessed items kept)
    3. Priority (high priority items kept)
    4. Expiration (items with explicit expiration)
    """
    
    def __init__(self, max_items: int = 20, default_ttl_minutes: int = 30):
        """
        Initialize working memory.
        
        Args:
            max_items: Maximum number of items to keep
            default_ttl_minutes: Default time-to-live in minutes for items
        """
        self.items: Dict[str, WorkingMemoryItem] = {}
        self.max_items = max_items
        self.default_ttl_minutes = default_ttl_minutes
        self.current_task: Optional[str] = None
        self.task_state: Dict[str, Any] = {}
        
    def add_file_context(
        self,
        file_path: str,
        summary: str,
        lines_examined: Optional[Tuple[int, int]] = None,
        relevance_score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a file context to working memory.
        
        Args:
            file_path: Path to the file
            summary: Brief summary of file contents/relevance
            lines_examined: Optional tuple of (start_line, end_line) examined
            relevance_score: Score from 0.0 to 1.0 indicating relevance
            metadata: Additional metadata about the file
            
        Returns:
            ID of the created memory item
        """
        file_context = FileContext(
            path=file_path,
            summary=summary,
            lines_examined=lines_examined,
            relevance_score=relevance_score,
            metadata=metadata or {},
        )
        
        item_id = f"file_{file_path}_{datetime.now().timestamp()}"
        item = WorkingMemoryItem(
            id=item_id,
            type=WorkingMemoryItemType.FILE_CONTEXT,
            content=file_context,
            priority=3,  # Medium priority for files
            expires_at=self._get_expiration_time(),
        )
        
        self.items[item_id] = item
        self._evict_if_needed()
        return item_id
    
    def add_tool_context(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        purpose: str,
        expected_outcome: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """
        Add a tool context to working memory.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            purpose: Why this tool is being used
            expected_outcome: Expected outcome of tool execution
            dependencies: IDs of dependent tool contexts
            
        Returns:
            ID of the created memory item
        """
        tool_context = ToolContext(
            tool_name=tool_name,
            arguments=arguments,
            purpose=purpose,
            expected_outcome=expected_outcome,
            dependencies=dependencies or [],
        )
        
        item_id = f"tool_{tool_name}_{datetime.now().timestamp()}"
        item = WorkingMemoryItem(
            id=item_id,
            type=WorkingMemoryItemType.TOOL_CONTEXT,
            content=tool_context,
            priority=4,  # High priority for active tool execution
            expires_at=self._get_expiration_time(minutes=5),  # Short TTL for tools
        )
        
        self.items[item_id] = item
        self._evict_if_needed()
        return item_id
    
    def add_insight(self, insight: str, priority: int = 2) -> str:
        """
        Add an insight to working memory.
        
        Args:
            insight: The insight text
            priority: Priority from 1-5
            
        Returns:
            ID of the created memory item
        """
        item_id = f"insight_{datetime.now().timestamp()}"
        item = WorkingMemoryItem(
            id=item_id,
            type=WorkingMemoryItemType.INSIGHT,
            content=insight,
            priority=priority,
            expires_at=self._get_expiration_time(),
        )
        
        self.items[item_id] = item
        self._evict_if_needed()
        return item_id
    
    def add_question(self, question: str, priority: int = 3) -> str:
        """
        Add a question to working memory.
        
        Args:
            question: The question text
            priority: Priority from 1-5
            
        Returns:
            ID of the created memory item
        """
        item_id = f"question_{datetime.now().timestamp()}"
        item = WorkingMemoryItem(
            id=item_id,
            type=WorkingMemoryItemType.QUESTION,
            content=question,
            priority=priority,
            expires_at=self._get_expiration_time(),
        )
        
        self.items[item_id] = item
        self._evict_if_needed()
        return item_id
    
    def add_hypothesis(self, hypothesis: str, priority: int = 3) -> str:
        """
        Add a hypothesis to working memory.
        
        Args:
            hypothesis: The hypothesis text
            priority: Priority from 1-5
            
        Returns:
            ID of the created memory item
        """
        item_id = f"hypothesis_{datetime.now().timestamp()}"
        item = WorkingMemoryItem(
            id=item_id,
            type=WorkingMemoryItemType.HYPOTHESIS,
            content=hypothesis,
            priority=priority,
            expires_at=self._get_expiration_time(),
        )
        
        self.items[item_id] = item
        self._evict_if_needed()
        return item_id
    
    def get_item(self, item_id: str) -> Optional[WorkingMemoryItem]:
        """Get an item by ID, updating its access time."""
        item = self.items.get(item_id)
        if item:
            item.touch()
        return item
    
    def get_files(self) -> List[FileContext]:
        """Get all file contexts."""
        files = []
        for item in self.items.values():
            if item.type == WorkingMemoryItemType.FILE_CONTEXT and isinstance(item.content, FileContext):
                item.touch()
                files.append(item.content)
        return files
    
    def get_tools(self) -> List[ToolContext]:
        """Get all tool contexts."""
        tools = []
        for item in self.items.values():
            if item.type == WorkingMemoryItemType.TOOL_CONTEXT and isinstance(item.content, ToolContext):
                item.touch()
                tools.append(item.content)
        return tools
    
    def get_insights(self) -> List[str]:
        """Get all insights."""
        insights = []
        for item in self.items.values():
            if item.type == WorkingMemoryItemType.INSIGHT and isinstance(item.content, str):
                item.touch()
                insights.append(item.content)
        return insights
    
    def get_questions(self) -> List[str]:
        """Get all questions."""
        questions = []
        for item in self.items.values():
            if item.type == WorkingMemoryItemType.QUESTION and isinstance(item.content, str):
                item.touch()
                questions.append(item.content)
        return questions
    
    def get_hypotheses(self) -> List[str]:
        """Get all hypotheses."""
        hypotheses = []
        for item in self.items.values():
            if item.type == WorkingMemoryItemType.HYPOTHESIS and isinstance(item.content, str):
                item.touch()
                hypotheses.append(item.content)
        return hypotheses
    
    def remove_item(self, item_id: str) -> bool:
        """Remove an item by ID."""
        if item_id in self.items:
            del self.items[item_id]
            return True
        return False
    
    def clear_expired(self) -> int:
        """Clear expired items from memory."""
        removed_count = 0
        now = datetime.now()
        
        items_to_remove = []
        for item_id, item in self.items.items():
            if item.expires_at:
                try:
                    expires_dt = datetime.fromisoformat(item.expires_at)
                    if expires_dt < now:
                        items_to_remove.append(item_id)
                except ValueError:
                    # Invalid date format, remove the item
                    items_to_remove.append(item_id)
        
        for item_id in items_to_remove:
            del self.items[item_id]
            removed_count += 1
            
        return removed_count
    
    def get_summary(self) -> str:
        """Get a summary of working memory contents."""
        if not self.items:
            return "Working memory is empty."
        
        summary_parts = []
        
        # Current task
        if self.current_task:
            summary_parts.append(f"Current task: {self.current_task}")
        
        # Files
        files = self.get_files()
        if files:
            file_list = [f"- {f.path}: {f.summary[:50]}..." if len(f.summary) > 50 else f"- {f.path}: {f.summary}" 
                        for f in files[:3]]
            if len(files) > 3:
                file_list.append(f"... and {len(files) - 3} more files")
            summary_parts.append("Files in context:\\n" + "\\n".join(file_list))
        
        # Tools
        tools = self.get_tools()
        if tools:
            tool_list = [f"- {t.tool_name}: {t.purpose[:50]}..." if len(t.purpose) > 50 else f"- {t.tool_name}: {t.purpose}"
                        for t in tools[:2]]
            if len(tools) > 2:
                tool_list.append(f"... and {len(tools) - 2} more tools")
            summary_parts.append("Recent tools:\\n" + "\\n".join(tool_list))
        
        # Insights
        insights = self.get_insights()
        if insights:
            insight_list = [f"- {i[:80]}..." if len(i) > 80 else f"- {i}" 
                          for i in insights[:2]]
            if len(insights) > 2:
                insight_list.append(f"... and {len(insights) - 2} more insights")
            summary_parts.append("Recent insights:\\n" + "\\n".join(insight_list))
        
        # Questions
        questions = self.get_questions()
        if questions:
            question_list = [f"- {q[:80]}..." if len(q) > 80 else f"- {q}" 
                           for q in questions[:2]]
            if len(questions) > 2:
                question_list.append(f"... and {len(questions) - 2} more questions")
            summary_parts.append("Open questions:\\n" + "\\n".join(question_list))
        
        return "\\n\\n".join(summary_parts)
    
    def clear(self) -> None:
        """Clear all working memory."""
        self.items.clear()
        self.current_task = None
        self.task_state.clear()
    
    def set_task(self, task: str) -> None:
        """Set the current task."""
        self.current_task = task
    
    def update_task_state(self, key: str, value: Any) -> None:
        """Update task state."""
        self.task_state[key] = value
    
    def get_task_state(self, key: str, default: Any = None) -> Any:
        """Get task state value."""
        return self.task_state.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "items": {k: v.to_dict() for k, v in self.items.items()},
            "max_items": self.max_items,
            "default_ttl_minutes": self.default_ttl_minutes,
            "current_task": self.current_task,
            "task_state": self.task_state,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemory":
        """Create from dictionary."""
        wm = cls(
            max_items=data.get("max_items", 20),
            default_ttl_minutes=data.get("default_ttl_minutes", 30),
        )
        
        wm.items = {
            k: WorkingMemoryItem.from_dict(v) 
            for k, v in data.get("items", {}).items()
        }
        wm.current_task = data.get("current_task")
        wm.task_state = data.get("task_state", {})
        
        return wm
    
    def _get_expiration_time(self, minutes: Optional[int] = None) -> str:
        """Get expiration time string."""
        ttl = minutes or self.default_ttl_minutes
        expires_dt = datetime.now().timestamp() + (ttl * 60)
        return datetime.fromtimestamp(expires_dt).isoformat()
    
    def _evict_if_needed(self) -> None:
        """Evict items if over capacity."""
        if len(self.items) <= self.max_items:
            return
        
        # Clear expired items first
        self.clear_expired()
        
        # If still over capacity, evict based on priority and access time
        if len(self.items) > self.max_items:
            items_list = list(self.items.items())
            
            # Sort by priority (ascending), then accessed_at (ascending)
            items_list.sort(key=lambda x: (
                x[1].priority,
                x[1].accessed_at
            ))
            
            # Remove lowest priority/oldest items
            items_to_remove = items_list[:len(items_list) - self.max_items]
            for item_id, _ in items_to_remove:
                del self.items[item_id]