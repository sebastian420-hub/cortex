# Context Overflow Fix - Implementation Summary

## Problem Statement

The agent experienced critical failures when processing large file operations:

1. **Context Overload**: Tool results (especially from `glob` and `grep`) returned excessive data that overloaded the model's context window
2. **No Auto-Recovery**: When context overflow occurred, the agent would retry the same operation 3 times without reducing the context, wasting API calls and failing completely
3. **Poor Default Limits**: Tools had generous default limits (500 files for glob, unlimited for some operations) that encouraged large results

**Example Failure**:
```
Finding files: **/*.py
Finding files: **/*.md

Matching Files (1559)  # Way too many!
Matching Files (1197)

ERROR: Context length is 262144 tokens. However, you requested about 5559111 tokens
```

## Solution Overview

Implemented a **three-layer defense** against context overflow:

### Layer 1: Smarter Tool Defaults & Filtering
- Reduced default limits (glob: 500→200, grep: 50→100)
- Enhanced directory filtering to skip irrelevant folders
- Added binary file detection and skipping

### Layer 2: Automatic Result Truncation
- Created `result_truncation.py` utility that intelligently truncates tool results
- Applied **before** adding results to conversation history
- Preserves most important information while discarding excess

### Layer 3: Context Overflow Recovery
- Detects context overflow errors from providers
- Automatically truncates conversation history aggressively
- Retries with reduced context instead of failing

## Detailed Changes

### 1. Result Truncation Utility (`cortex/utils/result_truncation.py`)

**NEW FILE** - Intelligent truncation based on tool type:

```python
# File listing tools (glob, list_files)
- Max 100 files shown (from potentially thousands)
- Adds truncation message with original count
- Saves ~10K+ tokens on large directories

# Search tools (grep, search_files)
- Max 200 matches shown
- Preserves context about total matches
- Saves ~25K+ tokens on broad searches

# File reading (read_file)
- Max 200K characters per file
- Truncates at last complete line
- Suggests using offset/limit parameters

# Generic results
- Truncates string fields over 10K characters
- Limits lists to 500 items
```

**Token Estimation**: Uses 4 chars/token approximation for conservative estimates.

### 2. Agent Integration (`cortex/agent.py`)

#### 2.1 Import Truncation Utilities
```python
from .utils.result_truncation import truncate_tool_result, should_truncate_proactively
```

#### 2.2 Truncate Before Adding to Conversation
Applied at **4 locations** (sync + async paths):

```python
# Before: Direct addition
self.conversation.add_tool_result(tool_result.id, result)

# After: Truncate first
result = truncate_tool_result(tool_name, result)
self.conversation.add_tool_result(tool_result.id, result)
```

#### 2.3 Context Overflow Recovery in `_call_model`

**Removed**: `@retry_with_backoff` decorator (retried blindly)

**Added**: Smart retry logic with context detection:

```python
def _call_model(self, messages, tools):
    for attempt in range(max_retries):
        try:
            return self.provider.chat(...)
        except ProviderError as e:
            # Detect context overflow patterns
            if "context length" in str(e).lower() or "too many tokens" in str(e).lower():
                if attempt < max_retries - 1:
                    # Aggressive truncation: keep only system + last 5 messages
                    self.conversation.history = [
                        self.conversation.history[0],  # System prompt
                        *self.conversation.history[-5:]  # Recent context
                    ]
                    logger.warning("Auto-recovery: truncated conversation")
                    continue  # Retry with reduced context
                else:
                    raise ModelError("Context overflow persists after truncation")
```

**Key Features**:
- Detects overflow by error message keywords
- Reduces conversation to ~30% of max tokens
- Shows warning to user: "⚠ Context overflow - automatically reduced conversation history"
- Only retries after reducing context (not blindly)

### 3. Glob Tool Improvements (`cortex/tools/glob_tool.py`)

#### 3.1 Reduced Default Limit
```python
# Before
max_results: int = 500

# After
max_results: int = 200  # More conservative default
```

#### 3.2 Enhanced Directory Filtering

**Added filtering for**:
```python
ignored_dirs = {
    # Existing
    ".git", "node_modules", "__pycache__", "venv", "dist", "build",

    # NEW - Common non-code directories
    "vendor", "target",  # Package managers / build output
    ".gradle", ".next", ".nuxt",  # Framework build dirs
    "__snapshots__", "coverage", ".turbo",
}

# NEW - Binary file extensions
skip_extensions = {
    '.pyc', '.so', '.dll', '.exe',  # Binaries
    '.png', '.jpg', '.pdf', '.zip',  # Media/Archives
    '.mp3', '.mp4', '.db', '.lock',  # Data files
}

# NEW - Suspicious directory keywords
# Skips directories with "download", "temp", "backup", "archive", "old"
# Unless they contain source indicators ("src", "lib", "core", "app")
```

**Impact**: Prevents scanning user data folders that accidentally get included in broad searches (like "4-month getaway plan" in the user's example).

### 4. Grep Tool Improvements (`cortex/tools/grep_tool.py`)

#### 4.1 Increased Default Limit (More Practical)
```python
# Before
head_limit: int = 50

# After
head_limit: int = 100  # Better balance for searches
```

**Rationale**: 50 was too restrictive for legitimate searches, 100 is safer than unlimited while still useful.

## Expected Behavior After Fixes

### Scenario 1: Research Large Codebase
```
User: "Research about the local terminal agent repo"
Agent: glob(pattern="**/*.py")

OLD BEHAVIOR:
❌ Returns 1197 files
❌ Adds ~500K tokens to context
❌ Context overflow error
❌ Retries 3x with same data
❌ Complete failure

NEW BEHAVIOR:
✅ Returns max 200 files (truncated from 1197)
✅ Adds ~50K tokens to context
✅ Includes message: "File list truncated. Showing 200 of 1197 total files."
✅ Agent understands results are partial
✅ Can refine search with more specific patterns
```

### Scenario 2: Context Overflow Still Occurs
```
OLD BEHAVIOR:
❌ Retry 1: Same context → Error
❌ Retry 2: Same context → Error
❌ Retry 3: Same context → Error
❌ Complete failure

NEW BEHAVIOR:
⚠️  Attempt 1: Context overflow detected
✅ Auto-truncate: 50 messages → 6 messages (system + last 5)
✅ User sees: "⚠ Context overflow - automatically reduced conversation history"
✅ Retry 2: Succeeds with reduced context
✅ Agent continues working
```

### Scenario 3: Large File Read
```
User: "Read the entire 10MB file"
Agent: read_file(path="large.txt")

OLD BEHAVIOR:
❌ Reads entire file
❌ Adds ~2.5M tokens
❌ Context overflow

NEW BEHAVIOR:
✅ Truncates to 200K characters
✅ Adds truncation message: "Content truncated. Use offset/limit to read specific portions"
✅ Agent understands and can request specific sections
```

## Configuration & Tuning

All limits are configurable via function parameters:

```python
# Override defaults when needed
glob(pattern="**/*.py", max_results=500)  # More results
grep(pattern="TODO", head_limit=500)      # More matches
read_file(path="file.py", limit=5000)     # More lines
```

## Testing Recommendations

1. **Large Directory Test**: Run glob on root directory
2. **Broad Search Test**: grep for common term without filters
3. **Context Recovery Test**: Force overflow and verify auto-recovery
4. **Multiple Operations Test**: Run 3 glob operations in parallel

## Monitoring & Metrics

The system now logs:
- When results are truncated (with token savings)
- When context overflow is detected
- When auto-recovery is triggered
- Conversation size before/after truncation

Example logs:
```
WARNING: Truncated glob result: 1197 -> 200 files (saved ~125K tokens)
WARNING: Context overflow detected on attempt 1/3
WARNING: Auto-recovery: truncated conversation 50 -> 6 messages (~150K -> ~15K tokens)
```

## Future Enhancements

Potential improvements:
1. **Smart summarization**: Instead of truncating, summarize old messages
2. **Adaptive limits**: Reduce max_results automatically when context is near limit
3. **Priority-based truncation**: Keep error messages, drop successful results
4. **User configuration**: Allow per-project truncation preferences
5. **Proactive truncation**: Call `should_truncate_proactively()` before tool execution

## Files Changed

1. **NEW**: `cortex/utils/result_truncation.py` (210 lines)
2. **MODIFIED**: `cortex/agent.py` (+30 lines)
   - Import truncation utilities
   - Apply truncation at 4 locations
   - Replace retry decorator with smart recovery
3. **MODIFIED**: `cortex/tools/glob_tool.py` (+40 lines)
   - Reduce default max_results
   - Enhanced filtering
4. **MODIFIED**: `cortex/tools/grep_tool.py` (+2 lines)
   - Adjust default head_limit

**Total Impact**: ~280 lines added/modified

## Summary

This fix transforms the agent from **fragile** (fails catastrophically on large operations) to **resilient** (automatically adapts to prevent failures). The three-layer approach ensures that context overflow is prevented at multiple stages, and when it does occur, the agent recovers automatically rather than failing.

**Key Philosophy**:
- **Prevent** overflow with smart defaults
- **Mitigate** overflow with automatic truncation
- **Recover** from overflow with intelligent retry logic

The agent can now handle real-world scenarios where users ask broad questions about large codebases without manual intervention.
