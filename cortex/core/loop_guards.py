"""Loop guard system to prevent infinite loops and detect stuck states"""

from typing import List, Tuple, Dict, Any, Set


class LoopGuard:
    """Tracks tool calls and errors to detect infinite loops and stuck states"""
    
    def __init__(self, max_repeats: int = 3):
        """
        Initialize loop guard.
        
        Args:
            max_repeats: Maximum number of times same tool/error can repeat before triggering
        """
        self.tool_call_history: List[Tuple[str, Dict[str, Any]]] = []
        self.error_history: List[Dict[str, Any]] = []
        self.max_repeats = max_repeats
        # Progress tracking
        self.unique_operations: Set[str] = set()  # Track unique operations
        self.files_read: Set[str] = set()  # Track files read
        self.files_written: Set[str] = set()  # Track files written
        self.iteration_count: int = 0
    
    def check_repeated_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        Check if same tool called too many times with same arguments.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            True if tool called too many times, False otherwise
        """
        # Check last N calls (where N = max_repeats)
        recent_calls = [
            (name, args) for name, args in self.tool_call_history[-self.max_repeats:]
            if name == tool_name and args == arguments
        ]
        return len(recent_calls) >= self.max_repeats
    
    def check_repeated_error(self, error: Dict[str, Any]) -> bool:
        """
        Check if same error repeated too many times.
        
        Args:
            error: Error dictionary from tool result
            
        Returns:
            True if error repeated too many times, False otherwise
        """
        # Extract error message for comparison
        error_msg = error.get("error", "")
        error_type = error.get("error_type", "")
        
        # Check last N errors
        recent_errors = [
            e for e in self.error_history[-self.max_repeats:]
            if e.get("error") == error_msg and e.get("error_type") == error_type
        ]
        return len(recent_errors) >= self.max_repeats
    
    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """
        Record a tool call in history.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
        """
        self.tool_call_history.append((tool_name, arguments))
        # Keep only last 10 calls to prevent memory growth
        if len(self.tool_call_history) > 10:
            self.tool_call_history.pop(0)
    
    def record_error(self, error: Dict[str, Any]) -> None:
        """
        Record an error in history.
        
        Args:
            error: Error dictionary from tool result
        """
        self.error_history.append(error)
        # Keep only last 10 errors to prevent memory growth
        if len(self.error_history) > 10:
            self.error_history.pop(0)
    
    def check_stuck_state(self) -> bool:
        """
        Detect if agent is stuck (no progress in recent iterations).
        
        Returns:
            True if stuck, False otherwise
        """
        # If we've done many iterations but no unique operations, we're stuck
        # Having at least one unique operation indicates progress
        if self.iteration_count > 5 and len(self.unique_operations) == 0:
            return True
        return False
    
    def check_progress(self) -> bool:
        """
        Check if making progress toward goal.
        
        Returns:
            True if making progress, False otherwise
        """
        # Progress indicators:
        # - New files read/written
        # - New unique operations
        # - Decreasing error rate
        return len(self.unique_operations) > 0
    
    def record_operation(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Record a unique operation for progress tracking."""
        op_key = f"{tool_name}:{str(sorted(arguments.items()))}"
        self.unique_operations.add(op_key)
        
        # Track file operations
        if tool_name == "read_file" and "path" in arguments:
            self.files_read.add(arguments["path"])
        elif tool_name == "write_file" and "path" in arguments:
            self.files_written.add(arguments["path"])
    
    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration_count += 1
    
    def reset(self) -> None:
        """Reset guard history (useful for testing or new conversation)"""
        self.tool_call_history.clear()
        self.error_history.clear()
        self.unique_operations.clear()
        self.files_read.clear()
        self.files_written.clear()
        self.iteration_count = 0

