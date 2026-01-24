# Reasoning-Only Message Handling Bug Fix

## Problem
Users were seeing confusing warnings and errors when using reasoning models:

```
WARNING:cortex.core.conversation:Attempted to add invalid assistant message (no content or tool_calls). Converting reasoning_content to content if available.
[THINK] <tool_call>
Model returned empty response. Exiting.
```

## Root Cause

The issue occurred when reasoning models (like DeepSeek, MiMo) returned:
- ✅ `reasoning_content` (thinking/internal monologue)
- ❌ No `content` (final response text)
- ❌ No `tool_calls` (actual tool invocations)

This happens in two scenarios:

### Scenario 1: Model Confusion (Bug)
The model writes `<tool_call>` or other tool syntax **in the reasoning text** instead of properly formatting tool calls. This is a provider parsing issue or model incompatibility.

**Example reasoning_content:**
```
Let me call the read_file tool... <tool_call>read_file</tool_call>
```

### Scenario 2: Legitimate Reasoning-Only Response (Not a Bug)
The model is thinking but hasn't produced output yet. This is normal behavior for some reasoning models.

**Example reasoning_content:**
```
I need to analyze this code structure first before providing an answer...
```

## The Fix

### 1. **Improved Detection** (`cortex/core/conversation.py`)

Now distinguishes between the two scenarios:

```python
# Check if reasoning contains tool syntax (indicates model confusion)
tool_syntax_patterns = ['<tool_call>', '</tool_call>', 'function_call', 'tool_use', '<function_call>']
has_tool_syntax = any(pattern in reasoning_content.lower() for pattern in tool_syntax_patterns)

if has_tool_syntax:
    logger.warning(
        "Model returned reasoning with tool syntax but no actual tool_calls. "
        "This may indicate a provider parsing issue or model confusion. "
        f"Reasoning preview: {reasoning_content[:150]}..."
    )
else:
    # Normal reasoning-only response
    logger.debug("Reasoning-only assistant message (no content or tool_calls). "
                "Converting reasoning_content to content.")
```

### 2. **Better User Feedback** (`cortex/agent.py`)

When the model has reasoning but no content:

```python
if has_tool_syntax:
    self._output_warning(
        "Model attempted to use tools in reasoning but didn't properly format tool calls. "
        "This may be a provider issue or model incompatibility."
    )
else:
    # Normal reasoning-only response (thinking was already displayed)
    logger.debug("Reasoning-only response received, exiting cleanly")
```

### 3. **Reduced Noise**

- **Before**: Always showed WARNING for reasoning-only messages
- **After**:
  - Only warns when tool syntax is detected (actual problem)
  - Uses DEBUG level for normal reasoning-only responses
  - Provides clear explanation when there IS a problem

## What Users Will See Now

### Normal Reasoning-Only Response (No warnings)
```
[THINK] I need to analyze this code structure first...
```
No warning, exits cleanly.

### Model Confusion (Helpful warning)
```
[THINK] <tool_call>read_file</tool_call>
WARNING: Model attempted to use tools in reasoning but didn't properly format tool calls.
This may be a provider issue or model incompatibility.
```

## When This Happens

This typically occurs with:
- **Provider issues**: Provider not correctly parsing tool calls from model response
- **Model incompatibility**: Model not properly trained for tool use format
- **Prompt issues**: System prompt not clear about tool formatting

## Debugging Steps

If you see the warning about "tool syntax in reasoning":

1. **Check your provider**: Ensure it supports tool calls properly
2. **Check the model**: Verify it's compatible with function calling
3. **Check logs**: Enable debug logging to see full reasoning content
4. **Try different model**: Some models handle tools better than others

## Files Modified

- `cortex/core/conversation.py` - Improved message validation with tool syntax detection
- `cortex/agent.py` - Better user feedback for both sync and async paths

## Testing

All tests pass:
- ✅ `tests/test_phase4_features.py` (37 tests)
- ✅ `tests/test_conversation.py` (5 tests)

## Impact

- **Reduced noise**: Normal reasoning-only responses no longer trigger warnings
- **Better diagnostics**: Actual problems are clearly identified
- **Helps debugging**: Provider/model issues are highlighted with context
