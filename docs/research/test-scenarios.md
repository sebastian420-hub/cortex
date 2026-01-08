# Test Scenarios and Execution Path Analysis

## Overview
This document defines test scenarios for common workflows and traces their execution paths through the LocalAgent codebase.

## 1. Scenario: Simple File Read

### 1.1 User Request
```
"Read the file config.yaml"
```

### 1.2 Expected Behavior
1. Agent calls `read_file` tool with `{"path": "config.yaml"}`
2. Tool reads file and returns content
3. Agent displays content to user
4. Loop exits

### 1.3 Execution Trace

**Iteration 1:**
- **History**: `[system, user: "Read config.yaml"]`
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "config.yaml"}}}]}`
- **Tool Execution**: `read_file("config.yaml")`
- **Tool Result**: `{"success": true, "content": "...", "lines": 10, "size": 234}`
- **History Updated**: `[system, user, assistant (with tool_call), tool (result)]`

**Iteration 2:**
- **History**: Full history including tool result (as JSON string)
- **Model Response**: `{content: "Here is the content of config.yaml:\n\n..."}`
- **No tool_calls**: Loop exits
- **Display**: Final answer shown to user

### 1.4 Potential Issues
- Model might not parse JSON string correctly
- Model might call tool again unnecessarily
- Model might not provide final answer

## 2. Scenario: File Not Found

### 2.1 User Request
```
"Read the file missing.py"
```

### 2.2 Expected Behavior
1. Agent calls `read_file` tool
2. Tool returns error: file not found
3. Agent handles error and informs user
4. Loop exits

### 2.3 Execution Trace

**Iteration 1:**
- **History**: `[system, user: "Read missing.py"]`
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "missing.py"}}}]}`
- **Tool Execution**: `read_file("missing.py")`
- **Tool Result**: `{"error": "File not found: missing.py"}`
- **History Updated**: `[system, user, assistant (with tool_call), tool (error result)]`

**Iteration 2:**
- **History**: Full history including error result
- **Model Response**: `{content: "The file missing.py was not found. It may not exist in the project directory."}`
- **No tool_calls**: Loop exits

### 2.4 Potential Issues
- Model might not recognize error format
- Model might retry same operation (infinite loop)
- Model might try alternative paths unnecessarily
- Model might not clearly communicate error to user

## 3. Scenario: Read Then Write

### 3.1 User Request
```
"Add logging to api.py"
```

### 3.2 Expected Behavior
1. Agent reads `api.py`
2. Agent modifies content to add logging
3. Agent writes modified content back
4. Agent provides summary
5. Loop exits

### 3.3 Execution Trace

**Iteration 1:**
- **History**: `[system, user: "Add logging to api.py"]`
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "api.py"}}}]}`
- **Tool Execution**: `read_file("api.py")`
- **Tool Result**: `{"success": true, "content": "..."}`
- **History Updated**: `[system, user, assistant (with tool_call), tool (result)]`

**Iteration 2:**
- **History**: Full history including file content
- **Model Response**: `{tool_calls: [{function: {name: "write_file", arguments: {path: "api.py", content: "..."}}}]}`
- **Tool Execution**: `write_file("api.py", "...")`
  - Shows diff preview
  - Asks user approval (if NORMAL mode)
  - Writes file
- **Tool Result**: `{"success": true, "bytes_written": 1234}`
- **History Updated**: `[..., assistant (with tool_call), tool (result)]`

**Iteration 3:**
- **History**: Full history including write result
- **Model Response**: `{content: "I've added logging to api.py. The changes include..."}`
- **No tool_calls**: Loop exits

### 3.4 Potential Issues
- Model might not read file first (violates system prompt)
- Model might write without reading (incorrect changes)
- Model might not provide final summary
- Model might continue calling tools unnecessarily
- User might cancel write, but model doesn't handle cancellation

## 4. Scenario: Multi-Step Refactoring

### 4.1 User Request
```
"Refactor the authentication module to use JWT tokens"
```

### 4.2 Expected Behavior
1. Agent searches for auth-related files
2. Agent reads relevant files
3. Agent makes changes to multiple files
4. Agent runs tests
5. Agent provides summary
6. Loop exits

### 4.3 Execution Trace

**Iteration 1:**
- **Model Response**: `{tool_calls: [{function: {name: "search_files", arguments: {query: "authentication"}}}]}`
- **Tool Result**: `{"success": true, "results": "...", "match_count": 5}`

**Iteration 2:**
- **Model Response**: `{tool_calls: [{function: {name: "list_files", arguments: {pattern: "*auth*"}}}]}`
- **Tool Result**: `{"success": true, "files": ["auth.py", "auth_utils.py"], "count": 2}`

**Iteration 3:**
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "auth.py"}}}]}`
- **Tool Result**: `{"success": true, "content": "..."}`

**Iteration 4:**
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "auth_utils.py"}}}]}`
- **Tool Result**: `{"success": true, "content": "..."}`

**Iteration 5:**
- **Model Response**: `{tool_calls: [{function: {name: "write_file", arguments: {path: "auth.py", content: "..."}}}]}`
- **Tool Result**: `{"success": true, "bytes_written": 2345}`

**Iteration 6:**
- **Model Response**: `{tool_calls: [{function: {name: "write_file", arguments: {path: "auth_utils.py", content: "..."}}}]}`
- **Tool Result**: `{"success": true, "bytes_written": 1234}`

**Iteration 7:**
- **Model Response**: `{tool_calls: [{function: {name: "run_tests", arguments: {}}}]}`
- **Tool Result**: `{"success": true, "output": "...", "exit_code": 0}`

**Iteration 8:**
- **Model Response**: `{content: "I've successfully refactored the authentication module..."}`
- **No tool_calls**: Loop exits

### 4.4 Potential Issues
- Model might skip important steps
- Model might not read all relevant files
- Model might make changes without understanding full context
- Model might not run tests
- Model might hit max iterations before completing
- History might get truncated, losing context

## 5. Scenario: Tool Failure Recovery

### 5.1 User Request
```
"Read config.yaml and update the API key"
```

### 5.2 Scenario: File Not Found

**Iteration 1:**
- **Tool Call**: `read_file("config.yaml")`
- **Tool Result**: `{"error": "File not found: config.yaml"}`

**Iteration 2:**
- **Model Sees Error**: Must parse JSON string to understand error
- **Expected**: Model searches for config files or asks user
- **Potential Issue**: Model might retry same operation

### 5.3 Scenario: Permission Denied

**Iteration 1:**
- **Tool Call**: `write_file("config.yaml", "...")`
- **Tool Result**: `{"success": false, "message": "Plan mode - no writes allowed"}`

**Iteration 2:**
- **Model Sees Error**: Must understand this is permission denial, not error
- **Expected**: Model informs user about permission mode
- **Potential Issue**: Model might interpret as error and retry

### 5.4 Scenario: Command Execution Failure

**Iteration 1:**
- **Tool Call**: `execute_command("git status")`
- **Tool Result**: `{"success": false, "output": "...", "exit_code": 1}`

**Iteration 2:**
- **Model Sees Error**: Must understand command failed
- **Expected**: Model handles error appropriately
- **Potential Issue**: Model might not recognize failure format

## 6. Scenario: Infinite Loop Prevention

### 6.1 User Request
```
"Read the file that doesn't exist"
```

### 6.2 Execution Trace (Problematic)

**Iteration 1:**
- **Tool Call**: `read_file("nonexistent.py")`
- **Tool Result**: `{"error": "File not found: nonexistent.py"}`

**Iteration 2:**
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "nonexistent.py"}}}]}`
- **Tool Result**: `{"error": "File not found: nonexistent.py"}`

**Iteration 3:**
- **Model Response**: `{tool_calls: [{function: {name: "read_file", arguments: {path: "nonexistent.py"}}}]}`
- **Tool Result**: `{"error": "File not found: nonexistent.py"}`

**...continues until max iterations...**

### 6.3 Current Prevention
- Max iterations limit (default: 20)
- No detection of repeated failures
- No detection of same tool called multiple times

### 6.4 Potential Issues
- Model might retry same operation indefinitely
- No early detection of stuck state
- Wastes iterations on impossible operations

## 7. Scenario: Empty Response Handling

### 7.1 User Request
```
"List all Python files"
```

### 7.2 Execution Trace (Edge Case)

**Iteration 1:**
- **Tool Call**: `list_files(pattern="*.py")`
- **Tool Result**: `{"success": true, "files": [...], "count": 10}`

**Iteration 2:**
- **Model Response**: `{content: "", tool_calls: []}`
- **Current Behavior**: Loop continues (implicitly)
- **Issue**: Empty content + no tools should exit or ask model

## 8. Scenario: Both Content and Tools

### 8.1 User Request
```
"Explain how the API works"
```

### 8.2 Execution Trace (Edge Case)

**Iteration 1:**
- **Model Response**: `{content: "Let me read the API file first...", tool_calls: [{function: {name: "read_file", ...}}]}`
- **Current Behavior**: Tools executed, content ignored
- **Issue**: Model's explanatory text is lost

## 9. Key Observations from Scenarios

### 9.1 Successful Patterns
- Simple read operations work well
- Multi-step operations can work if model follows system prompt
- Tool results properly influence next decisions

### 9.2 Problematic Patterns
- Error handling relies entirely on model interpretation
- No detection of infinite loops or stuck states
- Empty responses not handled
- Both content and tools not handled optimally
- Permission denials look like errors

### 9.3 Missing Mechanisms
- No validation of tool results before continuing
- No detection of repeated failures
- No progress tracking
- No early exit on impossible operations
- No recovery guidance for model

## 10. Recommendations for Test Scenarios

### 10.1 Add Validation
- Validate tool results before adding to history
- Check for success/failure
- Detect repeated failures

### 10.2 Add Loop Guards
- Detect same tool called multiple times
- Detect repeated errors
- Detect no progress made

### 10.3 Handle Edge Cases
- Empty content + no tools
- Both content and tools
- Permission denials

### 10.4 Improve Error Communication
- Standardize error formats
- Include error context
- Provide recovery guidance

