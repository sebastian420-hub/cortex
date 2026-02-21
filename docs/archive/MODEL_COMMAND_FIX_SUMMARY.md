# /model Command Fix Summary

## Problem Description

The `/model` command handler in `cortex/cli.py` was not being executed during tests, causing all test assertions for `agent.switch_model` to fail.

### Symptoms

1. **Test failures**: `AssertionError: Expected 'switch_model' to be called once. Called 0 times.`
2. **Debug logs not visible**: Logger debug messages weren't appearing in pytest output

## Root Cause Analysis

### The Bug: Prefix Matching Conflict

The issue was a **classic prefix matching bug** in the command handler logic:

```python
# BEFORE (BUGGY CODE)
elif cmd.startswith("/mode"):      # This matched "/model" first!
    # Handle /mode command
    ...
elif cmd.startswith("/model"):     # Never reached!
    # Handle /model command
    ...
```

**Explanation**: 
- When user types `/model deepseek-coder`, it gets converted to lowercase: `/model deepseek-coder`
- The first check `cmd.startswith("/mode")` returns `True` because `/model` does start with `/mode`
- The `/model` handler is never reached because the `/mode` handler executes first

### Debug Process

1. **Initial investigation**: Added logging to `handle_command` function
2. **Ran test with debug logging**: `pytest --log-cli-level=DEBUG`
3. **Observed logs**:
   ```
   DEBUG cortex.cli:cli.py:518 Handling command: '/model deepseek-coder'
   DEBUG cortex.cli:cli.py:521 Processed cmd: '/model deepseek-coder'
   ```
4. **Key insight**: No "Matched /model handler" log appeared, indicating the handler wasn't reached
5. **Found conflicting handlers**: `/mode` comes before `/model` and matches the prefix

## Solution

### Fix: Reorder Handlers

Move the more specific `/model` check **before** the less specific `/mode` check:

```python
# AFTER (FIXED CODE)
elif cmd.startswith("/model"):    # Check specific command first
    # Handle /model command
    ...
elif cmd.startswith("/mode"):     # Check general command second
    # Handle /mode command
    ...
```

### Changes Made

**File**: `cortex/cli.py`  
**Function**: `handle_command()`  
**Line**: ~535-565

**Change**: Swapped the order of two command handlers:
- Moved `/model` handler block (lines 544-560) to appear before `/mode` handler
- Moved `/mode` handler block (lines 535-543) to appear after `/model` handler

## Logging Improvements

### Problem 2: Debug Logs Not Visible

Debug logs weren't visible because:
1. Logger was initialized inside `handle_command` function but tests use module-level logger
2. Pytest captures output by default

### Solution

**To see debug logs in tests**, run pytest with:
```bash
python -m pytest tests/test_cli_commands.py -xvs --log-cli-level=DEBUG
```

Flags explained:
- `-x`: Stop on first failure
- `-v`: Verbose output
- `-s`: Don't capture output (show print statements)
- `--log-cli-level=DEBUG`: Show DEBUG level logs

### Added Debug Logging

Added strategic debug logs to help with future debugging:

```python
logger.debug(f"Handling command: '{command}'")
logger.debug(f"Processed cmd: '{cmd}'")
logger.debug(f"Matched /model handler, cmd='{cmd}'")
logger.debug(f"Split into parts: {parts}, len={len(parts)}")
logger.debug(f"Calling agent.switch_model with model='{new_model}', provider='{agent.config.provider}'")
logger.debug(f"No handler matched for cmd='{cmd}'")
```

## Test Results

### Before Fix
```
FAILED tests/test_cli_commands.py::test_handle_model_switch_success
AssertionError: Expected 'switch_model' to be called once. Called 0 times.
```

### After Fix
```
tests/test_cli_commands.py::test_handle_model_switch_success PASSED
tests/test_cli_commands.py::test_handle_model_switch_no_model_name PASSED
tests/test_cli_commands.py::test_handle_model_switch_provider_error PASSED
tests/test_cli_commands.py::test_handle_model_switch_unexpected_error PASSED

4 passed in 1.04s
```

## Prevention Guidelines

### Best Practices for Command Handler Order

1. **Most specific first**: Always place more specific command checks before general ones
2. **Use exact matches when possible**: Prefer `cmd == "/command"` over `cmd.startswith("/command")` when appropriate
3. **Group related commands**: Keep similar commands together for easier maintenance
4. **Add unit tests**: Test each command handler individually
5. **Use debug logging**: Add strategic logging to help future debugging

### Suggested Handler Order Pattern

```python
if cmd == "/exact_command":        # Exact matches first
    ...
elif cmd.startswith("/longcommand"): # Longer prefixes before shorter
    ...
elif cmd.startswith("/long"):       # Shorter prefixes after
    ...
elif cmd.startswith("/l"):          # Shortest prefixes last
    ...
```

## Similar Bugs to Watch For

Check for these similar patterns in the codebase:

```bash
# Find all command handlers
grep -n "elif cmd.startswith" cortex/cli.py

# Look for potential conflicts
# - /mem vs /memory
# - /mod vs /model vs /mode
# - /tran vs /transactions
```

### Current Command Conflicts to Review

Based on the current handlers, these pairs should be reviewed:
- ✅ `/model` vs `/mode` - **FIXED**
- ⚠️ `/memory` - No conflict (no `/mem` command)
- ⚠️ `/thinking` - No conflict (no `/think` command)
- ⚠️ `/transactions` - Exact match, no conflict with `/tran`

## Verification Checklist

- [x] All 4 `/model` command tests passing
- [x] Debug logging functional and visible with correct pytest flags
- [x] No regression in `/mode` command functionality
- [x] Documentation created for future reference

## Additional Notes

### Why the Bug Wasn't Caught Earlier

1. **Silent failure**: The code didn't crash, it just took the wrong path
2. **Logical flow**: `/mode` handler likely didn't break with `/model` input
3. **Test coverage**: Tests were added after the bug was introduced

### Learning Points

1. **Order matters**: The order of conditional checks is critical with prefix matching
2. **Debug early**: Add logging during development, not just when debugging
3. **Test-driven development**: Write tests before implementing features
4. **Code review**: A second pair of eyes would have caught this immediately

---

**Fixed**: 2026-01-12  
**Tests Passing**: 4/4  
**Status**: ✅ Complete
