# Tool Execution Deep Dive Analysis

## Overview
This document provides a detailed analysis of tool execution issues, error handling patterns, and response format inconsistencies across all tool implementations.

## 1. Tool Error Handling Patterns

### 1.1 Error Format Inconsistencies

Tools use **three different error formats**:

#### Pattern 1: Simple Error Dict
**Used by**: ReadFileTool, SearchFilesTool, GitStatusTool, GitDiffTool, GitLogTool

```python
return {"error": "Error message here"}
```

#### Pattern 2: Success Flag with Message
**Used by**: WriteFileTool, GitCommitTool (for plan mode and cancellations)

```python
return {"success": False, "message": "Error message"}
```

#### Pattern 3: Mixed Format
**Used by**: GitCommitTool (for actual failures)

```python
return {
    "success": False,
    "error": "Error message",
    "output": "..."
}
```

**Critical Issue**: The model must handle three different error formats, making it difficult to reliably detect failures.

### 1.2 Success Indicator Inconsistencies

Not all tools include a `success` field:

**Tools WITH success field:**
- ReadFileTool: `{"success": True, ...}`
- WriteFileTool: `{"success": True/False, ...}`
- ExecuteCommandTool: `{"success": True/False, ...}`
- GitStatusTool: `{"success": True, ...}`
- GitDiffTool: `{"success": True, ...}`
- GitCommitTool: `{"success": True/False, ...}`
- GitLogTool: `{"success": True, ...}`
- RunTestsTool: `{"success": True/False, ...}`

**Tools WITHOUT success field:**
- ListFilesTool: Returns `{"success": True, ...}` (has it)
- SearchFilesTool: Returns `{"success": True, ...}` (has it)

**Observation**: All tools actually include `success`, but error cases sometimes omit it in favor of `{"error": "..."}`.

## 2. Individual Tool Analysis

### 2.1 ReadFileTool

**Location**: `tools/file_tools.py` lines 15-57

**Success Response:**
```python
{
    "success": True,
    "content": "...",
    "lines": 45,
    "size": 1234
}
```

**Error Responses:**
```python
{"error": "File not found: path"}
{"error": "Path is not a file: path"}
{"error": "Access denied: path is outside project directory"}
{"error": "Invalid path: path"}
{"error": str(e)}  # Generic exception
```

**Issues:**
- ✅ Consistent error format (`{"error": "..."}`)
- ✅ Clear error messages
- ❌ No distinction between file not found (expected) vs. permission error (unexpected)
- ❌ Generic exception handling loses error context

### 2.2 WriteFileTool

**Location**: `tools/file_tools.py` lines 60-119

**Success Response:**
```python
{"success": True, "bytes_written": 1234}
```

**Error/Denial Responses:**
```python
{"success": False, "message": "Plan mode - no writes allowed"}
{"success": False, "message": "Cancelled by user"}
{"error": "Access denied: ..."}
{"error": str(e)}
```

**Issues:**
- ❌ **Mixed error formats**: Uses both `{"success": False, "message": "..."}` and `{"error": "..."}`
- ❌ Permission denials look like errors to the model
- ❌ User cancellation looks like an error
- ✅ Shows diff preview before writing (good UX)

### 2.3 ExecuteCommandTool

**Location**: `tools/command_tools.py` lines 14-78

**Success Response:**
```python
{
    "success": True,
    "output": "...",
    "exit_code": 0
}
```

**Error Responses:**
```python
{"success": False, "message": "Plan mode - no commands allowed"}
{"success": False, "message": "Cancelled by user"}
{"error": "Dangerous command blocked for safety"}
{"error": "Command timed out after 30 seconds"}
{"error": str(e)}
```

**Issues:**
- ❌ **Mixed error formats** again
- ✅ Has timeout protection (30 seconds)
- ✅ Has dangerous command detection
- ❌ Permission denials look like errors

### 2.4 ListFilesTool

**Location**: `tools/search_tools.py` lines 14-53

**Success Response:**
```python
{
    "success": True,
    "files": [...],
    "count": 10
}
```

**Error Responses:**
```python
{"error": "Path not found: path"}
{"error": "Path is not a directory: path"}
{"error": str(e)}
```

**Issues:**
- ✅ Consistent error format
- ✅ Clear error messages

### 2.5 SearchFilesTool

**Location**: `tools/search_tools.py` lines 56-112

**Success Response:**
```python
{
    "success": True,
    "results": "...",
    "match_count": 5
}
```

**Error Responses:**
```python
{"error": str(e)}  # Only generic exception
```

**Issues:**
- ❌ Only generic error handling - loses specific error context
- ✅ Consistent success format

### 2.6 GitStatusTool

**Location**: `tools/git_tools.py` lines 13-45

**Success Response:**
```python
{
    "success": True,
    "output": "...",
    "has_changes": True
}
```

**Error Responses:**
```python
{"error": "Not a git repository or git command failed"}
{"error": str(e)}
```

**Issues:**
- ✅ Consistent error format
- ❌ Generic "git command failed" doesn't specify what failed
- ❌ No distinction between "not a git repo" (expected) vs. "git error" (unexpected)

### 2.7 GitDiffTool

**Location**: `tools/git_tools.py` lines 48-87

**Success Response:**
```python
{
    "success": True,
    "output": "...",
    "has_changes": True
}
```

**Error Responses:**
```python
{"error": "Git diff failed"}
{"error": str(e)}
```

**Issues:**
- ✅ Consistent error format
- ❌ Generic "Git diff failed" doesn't specify why
- ❌ No distinction between "no changes" (success with empty output) vs. "error"

### 2.8 GitCommitTool

**Location**: `tools/git_tools.py` lines 90-139

**Success Response:**
```python
{
    "success": True,
    "output": "..."
}
```

**Error/Denial Responses:**
```python
{"success": False, "message": "Plan mode - no commits allowed"}
{"success": False, "message": "Cancelled by user"}
{
    "success": False,
    "error": result.stderr or "Commit failed",
    "output": result.stdout
}
{"error": str(e)}
```

**Issues:**
- ❌ **Three different error formats** in one tool!
- ❌ Permission denials use different format than actual errors
- ✅ Includes stderr in error response (helpful)

### 2.9 GitLogTool

**Location**: `tools/git_tools.py` lines 142-174

**Success Response:**
```python
{
    "success": True,
    "output": "...",
    "commits": [...]
}
```

**Error Responses:**
```python
{"error": "Git log failed"}
{"error": str(e)}
```

**Issues:**
- ✅ Consistent error format
- ❌ Generic error message

### 2.10 RunTestsTool

**Location**: `tools/test_tools.py` lines 12-117

**Success Response:**
```python
{
    "success": True,  # or False if tests fail
    "output": "...",
    "exit_code": 0,
    "framework": "pytest"
}
```

**Error Responses:**
```python
{"error": "Could not detect test framework. Install pytest or use unittest."}
{"error": "Tests timed out after 120 seconds"}
{"error": str(e)}
```

**Issues:**
- ✅ Consistent error format
- ✅ Has timeout protection (120 seconds)
- ✅ Good framework detection logic
- ❌ Test failures return `{"success": False, ...}` which is correct, but model might interpret as error

## 3. Common Patterns and Issues

### 3.1 Exception Handling Pattern

**Common Pattern:**
```python
try:
    # Tool operation
    return {"success": True, ...}
except SecurityError as e:
    return {"error": str(e)}
except Exception as e:
    return {"error": str(e)}
```

**Issues:**
- Catches all exceptions, losing specific error types
- No distinction between recoverable and non-recoverable errors
- Generic `str(e)` may not be informative

### 3.2 Permission Mode Handling

**Common Pattern:**
```python
if self.permission_mode == PermissionMode.PLAN:
    return {"success": False, "message": "Plan mode - no writes allowed"}

if self.permission_mode == PermissionMode.NORMAL and self.console:
    if not Confirm.ask(...):
        return {"success": False, "message": "Cancelled by user"}
```

**Issues:**
- Permission denials use `{"success": False, "message": "..."}` format
- Actual errors use `{"error": "..."}` format
- Model can't distinguish between permission denial and actual error
- Model might retry operations that were denied due to permissions

### 3.3 Subprocess Error Handling

**Common Pattern (Git tools, ExecuteCommandTool):**
```python
result = subprocess.run(...)
if result.returncode != 0:
    return {"error": "Command failed"}
```

**Issues:**
- Doesn't include stderr in error (except GitCommitTool)
- Generic error message doesn't explain what went wrong
- No distinction between expected failures (e.g., no git repo) and unexpected failures

### 3.4 Path Validation

**Common Pattern:**
```python
try:
    full_path = validate_path(self.project_dir, path)
except SecurityError as e:
    return {"error": str(e)}
```

**Issues:**
- SecurityError is properly caught
- But other path-related errors (e.g., invalid characters) might not be caught

## 4. Error Response Format Analysis

### 4.1 Format Distribution

| Format | Tools Using It | Count |
|--------|---------------|-------|
| `{"error": "..."}` | ReadFileTool, ListFilesTool, SearchFilesTool, GitStatusTool, GitDiffTool, GitLogTool, RunTestsTool | 7 |
| `{"success": False, "message": "..."}` | WriteFileTool, ExecuteCommandTool, GitCommitTool (permission denials) | 3 |
| Mixed | GitCommitTool (actual failures) | 1 |

### 4.2 Model Interpretation Challenges

The model must:
1. Check for `{"error": "..."}` key
2. Check for `{"success": False}` key
3. Check for `{"success": False, "message": "..."}` key
4. Distinguish between permission denials and actual errors
5. Parse JSON strings to access these fields

**Critical Issue**: This complexity makes it easy for the model to misinterpret results, leading to:
- Retrying operations that should not be retried
- Not retrying operations that should be retried
- Confusion about what actually happened

## 5. Tool Result JSON Stringification

### 5.1 Current Implementation

**Location**: `conversation.py` line 53

```python
self.history.append({
    "role": "tool",
    "tool_call_id": tool_call_id,
    "content": json.dumps(result)  # Result is stringified!
})
```

**Issue**: Tool results are JSON-stringified before being added to conversation history. This means:

1. The model receives results as strings, not structured objects
2. The model must parse JSON to access result fields
3. Parsing errors could occur if JSON is malformed
4. The model can't directly access nested fields

**Example:**
```python
# Tool returns:
{"success": True, "content": "..."}

# Added to history as:
{"role": "tool", "content": '{"success": true, "content": "..."}'}

# Model must parse JSON string to access fields
```

## 6. Edge Case Handling

### 6.1 Missing Files

**ReadFileTool**: Returns `{"error": "File not found: path"}`

**Issue**: Model might not understand this is an expected condition (file doesn't exist yet) vs. an error (file should exist but doesn't).

### 6.2 Empty Results

**ListFilesTool**: Returns `{"success": True, "files": [], "count": 0}`

**Issue**: Empty result is valid, but model might interpret as failure.

**SearchFilesTool**: Returns `{"success": True, "results": "", "match_count": 0}`

**Issue**: Empty string vs. empty list inconsistency.

### 6.3 Timeouts

**ExecuteCommandTool**: 30 second timeout
**RunTestsTool**: 120 second timeout
**Git tools**: 10 second timeout

**Issue**: Different timeouts for different operations. No timeout for file operations (could hang on network mounts).

### 6.4 Permission Denials

All write/execute tools return `{"success": False, "message": "..."}` for permission denials.

**Issue**: Model can't distinguish between:
- Permission denied (should not retry)
- Actual error (might retry with different approach)
- User cancellation (should not retry)

## 7. Recommendations

### 7.1 Standardize Error Format

**Proposed Standard Format:**
```python
{
    "success": bool,  # Always present
    "error": Optional[str],  # Present only on error
    "error_type": Optional[str],  # "permission", "not_found", "validation", "execution"
    # ... tool-specific fields
}
```

### 7.2 Distinguish Error Types

Add `error_type` field to help model understand:
- `"permission"`: Permission denied, don't retry
- `"not_found"`: Resource not found, might be expected
- `"validation"`: Invalid input, retry with corrected input
- `"execution"`: Execution failed, might retry
- `"timeout"`: Operation timed out, might retry

### 7.3 Pass Structured Results

Instead of JSON stringification, pass structured objects:
```python
self.history.append({
    "role": "tool",
    "tool_call_id": tool_call_id,
    "content": result  # Pass dict directly, not JSON string
})
```

### 7.4 Improve Error Messages

Include more context in error messages:
- What operation failed
- Why it failed
- What the model should do next

### 7.5 Add Result Validation

Before adding tool results to history, validate:
- Result has expected structure
- Success/error is clearly indicated
- Required fields are present

