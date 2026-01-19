"""Context window management with chunk-based injection and token budgeting."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

from .chunk import EditChunk, ChunkType, ChunkCollection
from .chunking import FileChunker, ChunkingStrategy
from cortex.core.context import count_message_tokens, estimate_tokens

logger = logging.getLogger(__name__)


class ContextInjectionStrategy(Enum):
    """Strategies for injecting context chunks."""
    
    ALL = "all"  # Inject all available chunks
    RELEVANT = "relevant"  # Inject only relevant chunks based on task
    LRU = "lru"  # Inject least recently used chunks
    BUDGET_AWARE = "budget_aware"  # Inject chunks within budget
    SMART = "smart"  # Intelligent selection


@dataclass
class TokenBudget:
    """
    Manages token budget for operations.
    
    Enforces limits per operation type and tracks usage.
    """
    
    total_tokens: int
    used_tokens: int = 0
    
    # Operation-specific limits
    limits: Dict[str, int] = field(default_factory=lambda: {
        "read": 10000,
        "edit": 5000,
        "analyze": 50000,
        "summarize": 20000,
        "search": 10000,
    })
    
    def can_allocate(self, tokens: int, operation_type: str = "general") -> bool:
        """
        Check if tokens can be allocated for an operation.
        
        Args:
            tokens: Number of tokens needed
            operation_type: Type of operation
        
        Returns:
            True if allocation is possible
        """
        limit = self.limits.get(operation_type, 10000)
        return self.used_tokens + tokens <= limit and self.used_tokens + tokens <= self.total_tokens
    
    def allocate(self, tokens: int, operation_type: str = "general") -> bool:
        """
        Allocate tokens for an operation.
        
        Args:
            tokens: Number of tokens to allocate
            operation_type: Type of operation
        
        Returns:
            True if allocation succeeded
        """
        if self.can_allocate(tokens, operation_type):
            self.used_tokens += tokens
            return True
        return False
    
    def release(self, tokens: int) -> None:
        """Release allocated tokens."""
        self.used_tokens = max(0, self.used_tokens - tokens)
    
    def get_remaining(self) -> int:
        """Get remaining token budget."""
        return self.total_tokens - self.used_tokens
    
    def get_utilization(self) -> float:
        """Get budget utilization as percentage."""
        if self.total_tokens == 0:
            return 0.0
        return (self.used_tokens / self.total_tokens) * 100


class ContextWindowManager:
    """
    Manages context window with chunk-based injection and token budgeting.
    
    Features:
    - Token budget enforcement
    - Intelligent chunk selection
    - Context visualization
    - Relevance-based injection
    """
    
    def __init__(
        self,
        max_tokens: int = 100000,
        injection_strategy: ContextInjectionStrategy = ContextInjectionStrategy.SMART,
        budget_per_operation: bool = True
    ):
        """
        Initialize context window manager.
        
        Args:
            max_tokens: Maximum tokens in context window
            injection_strategy: Strategy for selecting chunks to inject
            budget_per_operation: Whether to enforce per-operation budgets
        """
        self.max_tokens = max_tokens
        self.injection_strategy = injection_strategy
        self.budget_per_operation = budget_per_operation
        
        # Active chunks currently in context
        self.active_chunks: List[EditChunk] = []
        
        # Available chunks for potential injection
        self.available_chunks: List[EditChunk] = []
        
        # Chunk collections for bulk operations
        self.collections: Dict[str, ChunkCollection] = {}
        
        # Token budget tracking
        self.token_budget = TokenBudget(max_tokens)
        
        # Chunk usage tracking (LRU)
        self.chunk_access_times: Dict[str, float] = {}
        
        # Chunk relevance scores (for relevance-based injection)
        self.chunk_relevance: Dict[str, float] = {}
    
    def inject_context(
        self,
        messages: List[Dict[str, Any]],
        task: Optional[str] = None,
        operation_type: str = "general"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Inject relevant context chunks into messages.
        
        Args:
            messages: Current conversation messages
            task: Current task description
            operation_type: Type of operation being performed
        
        Returns:
            Tuple of (updated_messages, injection_info)
        """
        # Estimate current token usage
        current_tokens = self._estimate_messages_tokens(messages)
        
        # Determine available budget
        if self.budget_per_operation:
            remaining = self.token_budget.get_remaining()
        else:
            remaining = self.max_tokens - current_tokens
        
        if remaining <= 0:
            logger.warning("No remaining token budget for context injection")
            return messages, {"injected": 0, "skipped": 0, "budget_remaining": 0}
        
        # Select chunks to inject
        chunks_to_inject = self._select_chunks(task, remaining, operation_type)
        
        # Calculate tokens needed
        needed_tokens = sum(chunk.token_estimate for chunk in chunks_to_inject)
        
        if needed_tokens > remaining:
            logger.warning(f"Selected chunks need {needed_tokens} tokens, but only {remaining} available")
            # Filter to fit budget
            chunks_to_inject = self._filter_by_budget(chunks_to_inject, remaining)
            needed_tokens = sum(chunk.token_estimate for chunk in chunks_to_inject)
        
        # Allocate budget if per-operation tracking is enabled
        if self.budget_per_operation:
            if not self.token_budget.allocate(needed_tokens, operation_type):
                logger.warning(f"Failed to allocate {needed_tokens} tokens for {operation_type}")
                return messages, {"injected": 0, "skipped": len(self.available_chunks), "budget_remaining": self.token_budget.get_remaining()}
        
        # Inject chunks
        updated_messages = messages.copy()
        for chunk in chunks_to_inject:
            updated_messages.append(chunk.to_message())
            # Update access time
            self.chunk_access_times[chunk.chunk_id] = time.time()
        
        # Track as active chunks
        self.active_chunks.extend(chunks_to_inject)
        
        # Update chunk relevance scores
        if task:
            self._update_relevance_scores(task, chunks_to_inject)
        
        injection_info = {
            "injected": len(chunks_to_inject),
            "skipped": len(self.available_chunks) - len(chunks_to_inject),
            "tokens_injected": needed_tokens,
            "budget_remaining": self.token_budget.get_remaining() if self.budget_per_operation else remaining - needed_tokens,
            "chunks": [chunk.chunk_id for chunk in chunks_to_inject]
        }
        
        logger.info(f"Injected {len(chunks_to_inject)} chunks ({needed_tokens} tokens) for task: {task}")
        
        return updated_messages, injection_info
    
    def add_chunk(self, chunk: EditChunk) -> None:
        """Add a chunk to available chunks."""
        self.available_chunks.append(chunk)
        logger.debug(f"Added chunk {chunk.chunk_id} to available chunks")
    
    def add_chunks(self, chunks: List[EditChunk]) -> None:
        """Add multiple chunks to available chunks."""
        self.available_chunks.extend(chunks)
        logger.debug(f"Added {len(chunks)} chunks to available chunks")
    
    def add_collection(self, collection: ChunkCollection) -> None:
        """Add a chunk collection."""
        self.collections[collection.collection_id] = collection
        self.add_chunks(collection.chunks)
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[EditChunk]:
        """Retrieve a chunk by ID."""
        for chunk in self.available_chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        for chunk in self.active_chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None
    
    def clear_active_context(self) -> None:
        """Clear all active chunks from context."""
        for chunk in self.active_chunks:
            if self.budget_per_operation:
                self.token_budget.release(chunk.token_estimate)
        self.active_chunks = []
        logger.debug("Cleared active context chunks")
    
    def visualize(self, detailed: bool = False) -> str:
        """
        Visualize context window usage.
        
        Args:
            detailed: Whether to show detailed chunk information
        
        Returns:
            Formatted string with context usage information
        """
        total_tokens = sum(chunk.token_estimate for chunk in self.active_chunks)
        percentage = (total_tokens / self.max_tokens) * 100
        
        lines = [
            "┌─ Context Window Status ─────────────────────────────┐",
            f"│ Tokens: {total_tokens:>5}/{self.max_tokens:<5} ({percentage:>5.1f}%)                  │",
            f"│ Active Chunks: {len(self.active_chunks):>2}                                │",
            f"│ Available Chunks: {len(self.available_chunks):>2}                         │",
        ]
        
        if self.budget_per_operation:
            budget_util = self.token_budget.get_utilization()
            lines.append(f"│ Budget Util: {budget_util:>5.1f}%                             │")
        
        lines.append("└──────────────────────────────────────────────────────┘")
        
        if detailed and self.active_chunks:
            lines.append("")
            lines.append("Active Chunks:")
            for chunk in self.active_chunks:
                lines.append(f"  • {chunk.get_summary()}")
        
        return "\n".join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context window statistics."""
        return {
            "max_tokens": self.max_tokens,
            "total_tokens": sum(chunk.token_estimate for chunk in self.active_chunks),
            "active_chunks": len(self.active_chunks),
            "available_chunks": len(self.available_chunks),
            "budget_used": self.token_budget.used_tokens if self.budget_per_operation else 0,
            "budget_remaining": self.token_budget.get_remaining() if self.budget_per_operation else self.max_tokens,
            "utilization": (sum(chunk.token_estimate for chunk in self.active_chunks) / self.max_tokens) * 100,
        }
    
    def _select_chunks(
        self,
        task: Optional[str],
        budget: int,
        operation_type: str
    ) -> List[EditChunk]:
        """Select chunks based on injection strategy."""
        if not self.available_chunks:
            return []
        
        if self.injection_strategy == ContextInjectionStrategy.ALL:
            return self._select_all_chunks(budget)
        elif self.injection_strategy == ContextInjectionStrategy.RELEVANT:
            return self._select_relevant_chunks(task, budget)
        elif self.injection_strategy == ContextInjectionStrategy.LRU:
            return self._select_lru_chunks(budget)
        elif self.injection_strategy == ContextInjectionStrategy.BUDGET_AWARE:
            return self._select_budget_aware_chunks(budget)
        else:  # SMART
            return self._select_smart_chunks(task, budget, operation_type)
    
    def _select_all_chunks(self, budget: int) -> List[EditChunk]:
        """Select all available chunks within budget."""
        selected = []
        remaining = budget
        
        for chunk in self.available_chunks:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _select_relevant_chunks(
        self,
        task: Optional[str],
        budget: int
    ) -> List[EditChunk]:
        """Select chunks relevant to the current task."""
        if not task:
            return self._select_all_chunks(budget)
        
        # Score chunks by relevance to task
        scored = []
        for chunk in self.available_chunks:
            score = self._score_chunk_relevance(chunk, task)
            scored.append((score, chunk))
        
        # Sort by relevance score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Select within budget
        selected = []
        remaining = budget
        for score, chunk in scored:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _select_lru_chunks(self, budget: int) -> List[EditChunk]:
        """Select least recently used chunks."""
        # Sort by last access time (oldest first)
        sorted_chunks = sorted(
            self.available_chunks,
            key=lambda c: self.chunk_access_times.get(c.chunk_id, 0)
        )
        
        selected = []
        remaining = budget
        
        for chunk in sorted_chunks:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _select_budget_aware_chunks(self, budget: int) -> List[EditChunk]:
        """Select chunks that fit within budget optimally (largest first)."""
        # Sort by size (largest first) to maximize chunk count
        sorted_chunks = sorted(
            self.available_chunks,
            key=lambda c: c.token_estimate,
            reverse=True
        )
        
        selected = []
        remaining = budget
        
        for chunk in sorted_chunks:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _select_smart_chunks(
        self,
        task: Optional[str],
        budget: int,
        operation_type: str
    ) -> List[EditChunk]:
        """Intelligent chunk selection combining multiple strategies."""
        if not task:
            return self._select_budget_aware_chunks(budget)
        
        # Score chunks by relevance
        scored = []
        for chunk in self.available_chunks:
            score = self._score_chunk_relevance(chunk, task)
            # Adjust score based on chunk type relevance to operation
            type_score = self._score_chunk_type_relevance(chunk, operation_type)
            total_score = score * 0.7 + type_score * 0.3
            scored.append((total_score, chunk))
        
        # Sort by combined score
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Select within budget, preferring higher scores
        selected = []
        remaining = budget
        
        for score, chunk in scored:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _filter_by_budget(self, chunks: List[EditChunk], budget: int) -> List[EditChunk]:
        """Filter chunks to fit within budget."""
        selected = []
        remaining = budget
        
        for chunk in chunks:
            if chunk.token_estimate <= remaining:
                selected.append(chunk)
                remaining -= chunk.token_estimate
        
        return selected
    
    def _score_chunk_relevance(self, chunk: EditChunk, task: str) -> float:
        """
        Score chunk relevance to task.
        
        Returns score between 0.0 and 1.0
        """
        if not task:
            return 0.5
        
        task_lower = task.lower()
        
        # Base score from metadata
        score = 0.0
        
        # Check file path relevance
        if chunk.metadata.get('file_path'):
            file_path = chunk.metadata['file_path'].lower()
            if task_lower in file_path:
                score += 0.3
        
        # Check function name relevance
        if chunk.metadata.get('function'):
            func_name = chunk.metadata['function'].lower()
            if task_lower in func_name:
                score += 0.3
        
        # Check content relevance (simplified)
        chunk_lower = chunk.content.lower()
        words = task_lower.split()
        for word in words:
            if len(word) > 3 and word in chunk_lower:
                score += 0.1
                if score > 1.0:
                    score = 1.0
                    break
        
        return min(score, 1.0)
    
    def _score_chunk_type_relevance(
        self,
        chunk: EditChunk,
        operation_type: str
    ) -> float:
        """
        Score chunk type relevance to operation.
        
        Returns score between 0.0 and 1.0
        """
        relevance_map = {
            "read": {
                ChunkType.FILE_CONTENT: 1.0,
                ChunkType.SOURCE_CODE: 0.9,
                ChunkType.DOCUMENTATION: 0.8,
            },
            "edit": {
                ChunkType.SOURCE_CODE: 1.0,
                ChunkType.FILE_CONTENT: 0.9,
                ChunkType.CONFIGURATION: 0.8,
            },
            "analyze": {
                ChunkType.SOURCE_CODE: 1.0,
                ChunkType.FILE_CONTENT: 0.9,
                ChunkType.CONVERSATION_SUMMARY: 0.8,
            },
            "search": {
                ChunkType.FILE_CONTENT: 1.0,
                ChunkType.SOURCE_CODE: 0.9,
                ChunkType.DOCUMENTATION: 0.8,
            }
        }
        
        type_scores = relevance_map.get(operation_type, {})
        return type_scores.get(chunk.chunk_type, 0.5)
    
    def _update_relevance_scores(
        self,
        task: str,
        chunks: List[EditChunk]
    ) -> None:
        """Update relevance scores for selected chunks."""
        for chunk in chunks:
            score = self._score_chunk_relevance(chunk, task)
            self.chunk_relevance[chunk.chunk_id] = score
    
    def _estimate_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count for messages."""
        total = 0
        for msg in messages:
            # Use accurate message token counting with default model
            # TODO: Pass actual model name to ContextWindowManager
            total += count_message_tokens(msg, model="gpt-4")
        return total


def create_context_window_from_file(
    content: str,
    file_path: str,
    max_tokens: int = 100000,
    chunk_strategy: ChunkingStrategy = ChunkingStrategy.SMART
) -> ContextWindowManager:
    """
    Convenience function to create a context window from a file.
    
    Args:
        content: File content
        file_path: Path to the file
        max_tokens: Maximum tokens in context window
        chunk_strategy: Strategy for chunking the file
    
    Returns:
        ContextWindowManager with chunks from the file
    """
    # Chunk the file
    chunker = FileChunker(strategy=chunk_strategy)
    chunks = chunker.chunk_file(content, file_path)
    
    # Create context window
    context_window = ContextWindowManager(max_tokens=max_tokens)
    context_window.add_chunks(chunks)
    
    return context_window


def estimate_context_usage(
    context_window: ContextWindowManager,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Estimate context window usage with messages and chunks.
    
    Args:
        context_window: The context window manager
        messages: Current conversation messages
    
    Returns:
        Dictionary with usage statistics
    """
    message_tokens = context_window._estimate_messages_tokens(messages)
    chunk_tokens = sum(chunk.token_estimate for chunk in context_window.active_chunks)
    
    return {
        "message_tokens": message_tokens,
        "chunk_tokens": chunk_tokens,
        "total_tokens": message_tokens + chunk_tokens,
        "budget_remaining": context_window.token_budget.get_remaining(),
        "utilization": ((message_tokens + chunk_tokens) / context_window.max_tokens) * 100,
    }
