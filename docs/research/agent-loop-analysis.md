# Agent Decision-Making Loop Analysis

## Overview
This document analyzes how the agent decides between using tools versus providing a final answer, and the factors that influence these decisions.

## 1. Decision Point

### 1.1 The Critical Check

**Location**: `agent.py` lines 181-204

```python
# Check if using tools
if response_message.get("tool_calls"):
    # Execute tools
    for tool_call in response_message["tool_calls"]:
        # ... execute tools ...
else:
    # No more tools - final response
    final_text = response_message.get("content", "")
    if final_text:
        console.print(Panel(...))
    return
```

**Decision Logic**:
- If `tool_calls` present → Execute tools, continue loop
- If no `tool_calls` → Display content, exit loop

**Critical Issue**: No handling for:
- Empty `content` and no `tool_calls` (continues loop unnecessarily)
- Both `content` and `tool_calls` present (executes tools, ignores content)
- Tool execution failures (continues loop anyway)

## 2. System Prompt Guidance

### 2.1 System Prompt Content

**Location**: `agent.py` lines 76-100

```python
return f"""You are a helpful coding assistant working in the directory: {self.project_dir}

Permission Mode: {self.permission_mode.upper()}
{mode_instructions[self.permission_mode]}

Project Context:
{self.project_context if self.project_context else "No project context file found."}

Guidelines:
1. ALWAYS read relevant files before making changes
2. Explain your plan before executing it
3. Write clean, well-documented code
4. When the task is complete, give a final summary without calling more tools
5. Use search_files to find relevant code when you don't know the file structure
6. Be conversational and helpful

Available tools: read_file, write_file, execute_command, list_files, search_files, git_status, git_diff, git_commit, git_log, run_tests"""
```

### 2.2 Guidance Analysis

**Strengths**:
- Clear instruction to read files before changes
- Explicit instruction to provide final summary when complete
- Lists available tools

**Weaknesses**:
- No guidance on when to stop using tools
- No guidance on handling tool errors
- No guidance on recognizing task completion
- No guidance on avoiding infinite loops
- Tool list is just names, no descriptions

### 2.3 Tool Descriptions

**Location**: `tools/__init__.py` lines 14-200

Tool definitions include descriptions, but these are only sent to the model in the `tools` parameter, not in the system prompt.

**Example**:
```python
{
    "name": "read_file",
    "description": "Read the contents of a file. Use this to understand existing code before making changes.",
    ...
}
```

**Issue**: Model has access to tool descriptions via function calling, but system prompt doesn't reinforce when/how to use tools.

## 3. Model Decision Factors

### 3.1 What Influences Tool Usage

The model decides to use tools based on:
1. **User Request**: What the user asked for
2. **System Prompt**: Guidelines in system prompt
3. **Tool Descriptions**: Function calling descriptions
4. **Conversation History**: What has been done so far
5. **Tool Results**: Results from previous tool calls

### 3.2 What Influences Final Answer

The model decides to provide final answer when:
1. **Task Complete**: Believes task is finished
2. **No Tools Needed**: Task doesn't require tools
3. **Cannot Proceed**: Stuck and can't continue
4. **System Prompt**: "When the task is complete, give a final summary"

**Issue**: No explicit signal that task is complete. Model must infer from context.

## 4. Tool vs. Final Answer Scenarios

### 4.1 Scenario: Simple Question

**User**: "What is the purpose of this project?"

**Expected**: Final answer (no tools needed)

**Model Behavior**: Should provide answer without tools

**Potential Issue**: Model might call `read_file` to read README, which is reasonable but not always necessary.

### 4.2 Scenario: File Operation

**User**: "Add logging to api.py"

**Expected**: 
1. Read api.py (tool)
2. Modify content (tool)
3. Write file (tool)
4. Final summary (no tools)

**Model Behavior**: Should use tools, then provide final answer

**Potential Issue**: 
- Might not read file first
- Might not provide final summary
- Might continue calling tools unnecessarily

### 4.3 Scenario: Multi-Step Task

**User**: "Refactor the authentication module"

**Expected**:
1. Search for auth files (tool)
2. Read relevant files (tool)
3. Make changes (tool)
4. Run tests (tool)
5. Final summary (no tools)

**Model Behavior**: Should use multiple tools, then provide final answer

**Potential Issue**:
- Might get stuck in loop
- Might not recognize when done
- Might skip important steps

### 4.4 Scenario: Tool Failure

**User**: "Read config.yaml"

**Tool Result**: `{"error": "File not found: config.yaml"}`

**Expected**: Model handles error and either:
- Tries alternative (e.g., search for config files)
- Reports error to user
- Provides final answer explaining issue

**Potential Issue**:
- Might retry same tool (infinite loop)
- Might give up prematurely
- Might not understand error format

## 5. Decision Logic Issues

### 5.1 Both Content and Tool Calls

**Scenario**: Model returns both `content` and `tool_calls`

**Current Behavior**: Tools are executed, content is ignored

**Code**: Lines 175-178 add both to history, but only tools are processed

**Issue**: Model's explanatory text is lost, only tool execution happens.

### 5.2 Empty Content, No Tools

**Scenario**: Model returns empty `content` and no `tool_calls`

**Current Behavior**: Loop continues (implicitly)

**Code**: Line 193 checks `if not response_message.get("tool_calls")`, but doesn't check if content is empty

**Issue**: Loop continues unnecessarily, might hit max iterations.

### 5.3 Tool Execution Failure

**Scenario**: Tool execution fails

**Current Behavior**: Result (with error) is added to history, loop continues

**Code**: Lines 188-192 execute tool and add result regardless of success/failure

**Issue**: No check if tool failed, no guidance to model about what to do.

## 6. Loop Termination Logic

### 6.1 Normal Termination

**Condition**: Model returns `content` without `tool_calls`

**Code**: Lines 193-204

```python
if not response_message.get("tool_calls"):
    final_text = response_message.get("content", "")
    if final_text:
        console.print(Panel(...))
    return
```

**Issue**: If `final_text` is empty, function returns anyway, but this might not be clear to model.

### 6.2 Abnormal Termination

**Conditions**:
- Model error → Exit immediately
- General exception → Exit immediately
- Max iterations → Exit with warning

**Issue**: No graceful degradation or partial completion reporting.

## 7. Tool Call Processing

### 7.1 Sequential Execution

**Location**: Lines 183-192

```python
for tool_call in response_message["tool_calls"]:
    tool_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]
    result = self.execute_tool(tool_name, arguments)
    tool_call_id = tool_call.get("id", f"call_{iteration}")
    self.conversation.add_tool_result(tool_call_id, result)
```

**Behavior**: Tools execute sequentially, results added immediately

**Issue**: 
- No parallel execution for independent tools
- If one tool fails, others still execute
- No validation of tool results before continuing

### 7.2 Tool Call ID Handling

**Code**: `tool_call.get("id", f"call_{iteration}")`

**Issue**: If model doesn't provide ID, uses `call_0`, `call_1`, etc. This might cause issues if model expects specific IDs.

## 8. Model Response Structure

### 8.1 Expected Response Format

From Ollama function calling format:

```python
{
    "message": {
        "role": "assistant",
        "content": "Optional text response",
        "tool_calls": [
            {
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "file.py"}
                }
            }
        ]
    }
}
```

### 8.2 Response Parsing

**Location**: Lines 171-172 (non-streaming) or 168 (streaming)

```python
response = self._call_model(messages, TOOLS)
response_message = response["message"]
```

**Issue**: No validation that response has expected structure.

## 9. Infinite Loop Prevention

### 9.1 Current Prevention

**Max Iterations**: Limits total iterations

**Location**: Line 150

```python
max_iterations = self.config.max_iterations
for iteration in range(max_iterations):
```

**Default**: Likely 20 from config

**Issue**: Only prevents infinite loops by hard limit, doesn't detect:
- Repeated tool calls
- Same errors
- No progress

### 9.2 Missing Prevention

**No Detection For**:
- Same tool called 3+ times with same arguments
- Tool errors repeated 3+ times
- No state change for multiple iterations
- Tool results indicating impossible task

## 10. Key Findings

### 10.1 Strengths

- Clear decision point (tool_calls present or not)
- System prompt provides some guidance
- Max iterations prevents infinite loops
- Tool results properly influence next decision

### 10.2 Critical Issues

1. **No Completion Signal**: Model must infer when task is complete
2. **No Error Handling Guidance**: System prompt doesn't guide error handling
3. **No Loop Guards**: No detection of stuck states
4. **Empty Response Handling**: Empty content + no tools continues loop
5. **Both Content and Tools**: Content ignored when tools present
6. **No Result Validation**: Tool results added without checking success
7. **Sequential Execution**: Tools execute one at a time
8. **No Progress Tracking**: Can't detect if making progress

## 11. Recommendations

### 11.1 Improve System Prompt

Add explicit guidance:
- When to stop using tools
- How to handle tool errors
- How to recognize task completion
- How to avoid infinite loops

### 11.2 Add Completion Detection

Detect when task is likely complete:
- All requested operations succeeded
- No pending tool calls
- Model provides summary

### 11.3 Add Loop Guards

Detect and handle:
- Repeated tool failures
- Same tool called multiple times
- No progress made
- Stuck states

### 11.4 Handle Edge Cases

- Empty content + no tools → Ask model or exit
- Both content and tools → Process both appropriately
- Tool failures → Guide model on next steps

### 11.5 Add Progress Tracking

Track what has been accomplished to help model make better decisions.

### 11.6 Validate Tool Results

Before continuing loop, validate tool results and provide feedback to model if needed.

