# Recommendations for LocalAgent Improvements

## Overview
This document provides prioritized recommendations for improving LocalAgent based on the comprehensive codebase research.

## Priority Levels

- **P0**: Critical - Fix immediately, blocks core functionality
- **P1**: High - Fix soon, significantly impacts user experience
- **P2**: Medium - Fix when possible, improves reliability
- **P3**: Low - Nice to have, minor improvements

## 1. Critical Fixes (P0)

### 1.1 Standardize Error Response Formats

**Priority**: P0  
**Effort**: Medium  
**Impact**: High

**Problem**: Three different error formats make it difficult for the model to reliably detect failures.

**Solution**:
1. Define standard error format:
```python
{
    "success": bool,  # Always present
    "error": Optional[str],  # Present only on error
    "error_type": Optional[str],  # "permission", "not_found", "validation", "execution", "timeout"
    "error_context": Optional[Dict],  # Additional error context
    # ... tool-specific fields
}
```

2. Update all tools to use this format
3. Distinguish permission denials from errors:
```python
{
    "success": False,
    "error_type": "permission",
    "message": "Plan mode - no writes allowed"
}
```

**Files to Modify**:
- `tools/file_tools.py`
- `tools/command_tools.py`
- `tools/search_tools.py`
- `tools/git_tools.py`
- `tools/test_tools.py`

**Benefits**:
- Model can reliably detect failures
- Model can distinguish error types
- Model knows which errors to retry

---

### 1.2 Add Loop Guards

**Priority**: P0  
**Effort**: Medium  
**Impact**: High

**Problem**: No detection of infinite loops or stuck states beyond max iterations.

**Solution**:
1. Track tool call history per iteration
2. Detect repeated tool calls:
```python
if same_tool_called_n_times(tool_name, arguments, threshold=3):
    # Stop loop, report issue
```

3. Detect repeated errors:
```python
if same_error_repeated_n_times(error, threshold=3):
    # Stop loop, report issue
```

4. Detect no progress:
```python
if no_state_change_for_n_iterations(threshold=5):
    # Warn user, ask if should continue
```

**Files to Modify**:
- `agent.py` - Add loop guard logic
- `core/conversation.py` - Track tool call history

**Benefits**:
- Prevents infinite loops
- Early detection of stuck states
- Better user experience

---

### 1.3 Pass Structured Tool Results

**Priority**: P0  
**Effort**: Low  
**Impact**: High

**Problem**: Tool results are JSON-stringified, requiring model to parse.

**Solution**:
Change `conversation.py:53`:
```python
# Before:
"content": json.dumps(result)

# After:
"content": result  # Pass dict directly
```

**Note**: Verify Ollama supports structured content in tool results. If not, may need to keep JSON but ensure consistent format.

**Files to Modify**:
- `conversation.py:53`

**Benefits**:
- Model can directly access result fields
- No JSON parsing required
- Simpler for model to understand

---

## 2. High Priority Fixes (P1)

### 2.1 Improve System Prompt with Error Handling Guidance

**Priority**: P1  
**Effort**: Low  
**Impact**: High

**Problem**: System prompt doesn't guide error handling.

**Solution**:
Add to system prompt:
```
Error Handling:
- If a tool returns {"error": "..."}, the operation failed
- If error_type is "permission", do not retry - inform user about permission mode
- If error_type is "not_found", consider alternative approaches
- If error_type is "validation", retry with corrected input
- If error_type is "execution" or "timeout", you may retry once
- If same error occurs 3 times, stop and explain the issue to the user
```

**Files to Modify**:
- `agent.py:76-100` - Update system prompt

**Benefits**:
- Model knows how to handle errors
- Reduces infinite loops
- Better error recovery

---

### 2.2 Add Tool Result Validation

**Priority**: P1  
**Effort**: Medium  
**Impact**: Medium

**Problem**: Tool results added to history without validation.

**Solution**:
1. Define result schema for each tool
2. Validate result before adding to history:
```python
def validate_tool_result(tool_name: str, result: Dict) -> bool:
    schema = TOOL_RESULT_SCHEMAS.get(tool_name)
    if not schema:
        return True  # No schema defined
    return validate_against_schema(result, schema)
```

3. If validation fails, add error message to history instead

**Files to Modify**:
- `agent.py:188-192` - Add validation before adding result
- Create `tools/schemas.py` - Define result schemas

**Benefits**:
- Prevents invalid data in history
- Catches tool bugs early
- Better error messages

---

### 2.3 Handle Empty Response Edge Cases

**Priority**: P1  
**Effort**: Low  
**Impact**: Medium

**Problem**: Empty content + no tools continues loop unnecessarily.

**Solution**:
Update `agent.py:193-204`:
```python
if not response_message.get("tool_calls"):
    final_text = response_message.get("content", "")
    if final_text:
        console.print(Panel(...))
        return
    else:
        # Empty response - ask model or exit
        console.print("[yellow]Model returned empty response[/yellow]")
        # Option 1: Exit with message
        return
        # Option 2: Add message asking model to provide answer
```

**Files to Modify**:
- `agent.py:193-204`

**Benefits**:
- Prevents unnecessary loop iterations
- Better handling of edge cases
- Clearer behavior

---

### 2.4 Improve Token Estimation

**Priority**: P1  
**Effort**: Medium  
**Impact**: Medium

**Problem**: Rough token estimation may cause premature truncation or context loss.

**Solution**:
1. Use tiktoken library for accurate tokenization:
```python
import tiktoken

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

2. Or use Ollama's tokenizer if available
3. Fallback to character-based estimation if libraries unavailable

**Files to Modify**:
- `context.py:7-18` - Improve token estimation
- `requirements.txt` - Add tiktoken if using

**Benefits**:
- More accurate token counting
- Better context management
- Less premature truncation

---

## 3. Medium Priority Fixes (P2)

### 3.1 Add Error Classification

**Priority**: P2  
**Effort**: Medium  
**Impact**: Medium

**Problem**: All errors treated the same, no distinction between recoverable and non-recoverable.

**Solution**:
1. Define error types:
```python
class ErrorType:
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    NETWORK = "network"
```

2. Classify errors in tools:
```python
except FileNotFoundError:
    return {
        "success": False,
        "error": "File not found",
        "error_type": ErrorType.NOT_FOUND
    }
```

**Files to Modify**:
- All tool implementations
- `utils/errors.py` - Add error types

**Benefits**:
- Better error handling
- Appropriate retry strategies
- Model knows which errors to retry

---

### 3.2 Add Automatic Retry for Transient Errors

**Priority**: P2  
**Effort**: Medium  
**Impact**: Medium

**Problem**: No automatic retry for transient failures.

**Solution**:
1. Add retry decorator for tools:
```python
@retry_on_transient_errors(max_retries=3)
def execute(self, ...):
    # Tool operation
```

2. Retry only for specific error types:
- Network errors
- Timeout errors
- File lock errors

**Files to Modify**:
- `utils/errors.py` - Add retry decorator
- Tool implementations - Add retry where appropriate

**Benefits**:
- Automatic recovery from transient failures
- Better reliability
- Less burden on model

---

### 3.3 Add Progress Tracking

**Priority**: P2  
**Effort**: Medium  
**Impact**: Low

**Problem**: No way to track progress or detect stuck states.

**Solution**:
1. Track state changes:
```python
class ProgressTracker:
    def __init__(self):
        self.states = []
    
    def add_state(self, state: Dict):
        self.states.append(state)
    
    def has_progress(self, n: int = 5) -> bool:
        # Check if state changed in last N iterations
        ...
```

2. Use in agent loop to detect stuck states

**Files to Modify**:
- `agent.py` - Add progress tracking
- Create `core/progress.py` - Progress tracking logic

**Benefits**:
- Detect stuck states
- Provide progress feedback
- Better user experience

---

### 3.4 Improve History Truncation

**Priority**: P2  
**Effort**: High  
**Impact**: Medium

**Problem**: Simple truncation loses important context.

**Solution**:
1. Implement message importance ranking
2. Keep important messages even if older
3. Summarize dropped messages (future enhancement)

**Files to Modify**:
- `context.py:21-75` - Improve truncation logic

**Benefits**:
- Preserve important context
- Better conversation continuity
- Less context loss

---

## 4. Low Priority Improvements (P3)

### 4.1 Parallel Tool Execution

**Priority**: P3  
**Effort**: Medium  
**Impact**: Low

**Problem**: Tools execute sequentially even if independent.

**Solution**:
1. Detect independent tools
2. Execute in parallel using asyncio or threading
3. Collect results and add to history

**Files to Modify**:
- `agent.py:183-192` - Add parallel execution

**Benefits**:
- Faster execution for independent tools
- Better performance

---

### 4.2 Handle Both Content and Tools

**Priority**: P3  
**Effort**: Low  
**Impact**: Low

**Problem**: When model returns both content and tools, content is ignored.

**Solution**:
Display content before executing tools:
```python
if response_message.get("content"):
    console.print(Markdown(response_message["content"]))
if response_message.get("tool_calls"):
    # Execute tools
```

**Files to Modify**:
- `agent.py:175-192`

**Benefits**:
- Model's reasoning visible to user
- More transparent operation

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
1. Standardize error formats
2. Add loop guards
3. Pass structured tool results

### Phase 2: High Priority (Week 2)
1. Improve system prompt
2. Add tool result validation
3. Handle edge cases
4. Improve token estimation

### Phase 3: Medium Priority (Week 3-4)
1. Add error classification
2. Add automatic retry
3. Add progress tracking
4. Improve history truncation

### Phase 4: Low Priority (As time permits)
1. Parallel tool execution
2. Handle both content and tools

## Success Metrics

After implementing fixes, measure:
- Reduction in infinite loops
- Reduction in tool execution errors
- Improvement in task completion rate
- Reduction in max iterations reached
- User satisfaction with error messages

## Testing Strategy

1. **Unit Tests**: Test error format standardization
2. **Integration Tests**: Test loop guards with various scenarios
3. **End-to-End Tests**: Test complete workflows with error scenarios
4. **Regression Tests**: Ensure fixes don't break existing functionality

