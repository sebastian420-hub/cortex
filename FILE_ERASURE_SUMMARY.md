# File Erasure Issue - Executive Summary

## Quick Overview

The Cortex agent has **THREE CRITICAL VULNERABILITIES** that can cause file erasure:

### 1. 🔴 CRITICAL: Python Command Execution (execute_command tool)
- **File**: `cortex/tools/command_tools.py`
- **Issue**: Uses `subprocess.run(command, shell=True)` without Python-specific validation
- **Risk**: Commands like `python -c "open('file.py', 'w').close()"` can completely erase files
- **Likelihood**: MEDIUM - If agent attempts Python file operations

### 2. 🔴 CRITICAL: Empty Content Writing (write_file tool)
- **File**: `cortex/tools/file_tools.py`
- **Issue**: No validation that `content` parameter isn't empty before `full_path.write_text(content)`
- **Risk**: If content argument parsing fails → empty string → file completely overwritten
- **Likelihood**: LOW-MEDIUM - Depends on argument parsing robustness

### 3. 🟡 HIGH: Silent Backup Failures (base.py)
- **File**: `cortex/tools/base.py`, line 91
- **Issue**: `backup_file()` silently ignores missing transaction manager
- **Code**: `if self._transaction_manager is None: return True`
- **Risk**: No recovery possible if file is corrupted
- **Likelihood**: HIGH - transaction manager often not initialized

---

## Deleted Files Found

### From Git History
- **local-code.py** - DELETED (commit eb4adf3, Jan 7 2026)
  - Reason: "Superseded by modular package structure"
  - Status: Intentional cleanup, not caused by agent

---

## Root Cause: Argument Parsing

When the model calls `execute_command` or `write_file` with JSON arguments:

```
Tool Call: execute_command
Arguments (as JSON string): '{"command": "python -c \'..."}'
                                                     ↓
                            JSON parsing fails on quotes
                                                     ↓
                            command = "" or truncated
                                                     ↓
                            File erasure occurs
```

---

## Vulnerable Code Locations

| File | Function | Issue | Severity |
|------|----------|-------|----------|
| command_tools.py:55 | ExecuteCommandTool.execute() | `shell=True` + no Python validation | CRITICAL |
| file_tools.py:182 | WriteFileTool.execute() | No empty content validation | CRITICAL |
| edit_tool.py:133 | EditTool.execute() | No replacement verification | HIGH |
| base.py:91 | Tool.backup_file() | Silent skip if no transaction manager | HIGH |

---

## How to Reproduce

### Scenario 1: Python File Erasure
```python
# Model code that would erase a file
Tool: execute_command
Command: "python -c \"open('important.py', 'w').close()\""
Result: important.py → 0 bytes (completely erased)
```

### Scenario 2: Write Tool Truncation
```python
# If arguments parsing fails
Tool: write_file
Arguments: {"path": "config.py", "content": ""}  # Empty due to parsing error
Result: config.py → completely overwritten with empty content
```

### Scenario 3: Edit Tool Silent Failure
```python
# Whitespace mismatch
old_string: "def func():\n    pass"     (4 spaces)
File actual: "def func():\n\tpass"      (1 tab)
Result: No replacement occurs, file unchanged, backup not triggered
```

---

## Impact Assessment

| Scenario | Likelihood | Impact | User Impact |
|----------|-----------|--------|------------|
| Python command file erasure | MEDIUM | Complete file loss | Data loss |
| Empty content overwrite | LOW-MEDIUM | Complete file loss | Data loss |
| Backup failure | HIGH | No recovery | Permanent loss |
| Silent edit failure | HIGH | Wrong code state | Logic errors |

---

## Immediate Actions Required

### ⚠️ Priority 1: CRITICAL (Must Fix)

1. **Validate empty content in write_file**
   ```python
   # Add to file_tools.py WriteFileTool.execute()
   if not content or not content.strip():
       return create_error_response(
           "Content is empty or whitespace-only",
           ErrorType.VALIDATION,
           {"path": path}
       )
   ```

2. **Add Python command validation**
   ```python
   # Add to command_tools.py ExecuteCommandTool.execute()
   if command.strip().startswith("python"):
       dangerous_patterns = ["truncate()", "write('')", "remove(", "unlink("]
       if any(p in command for p in dangerous_patterns):
           return create_error_response(
               "Dangerous Python pattern detected",
               ErrorType.SECURITY,
               {"command": command}
           )
   ```

3. **Require transaction manager**
   ```python
   # Change in base.py Tool.backup_file()
   if self._transaction_manager is None:
       raise RuntimeError("Transaction manager required")
   ```

### ⚠️ Priority 2: HIGH (Should Fix)

4. **Verify replacements actually occurred**
   ```python
   # Add to edit_tool.py EditTool.execute()
   if old_string not in new_content:
       return create_error_response(
           "No replacement occurred - string not found",
           ErrorType.EXECUTION,
           {"file_path": file_path}
       )
   ```

5. **Remove shell=True usage**
   - Replace with list-based command execution
   - Use shlex.split() for safe command parsing

---

## Testing Recommendations

Add these tests to `tests/test_tools.py`:

```python
def test_write_file_empty_content():
    """Verify empty content is rejected"""
    tool = create_tool_instance("write_file", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(path="test.txt", content="")
    assert not result["success"]
    assert "empty" in result["error"].lower()

def test_execute_command_python_truncate():
    """Verify file truncation patterns are blocked"""
    tool = create_tool_instance("execute_command", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(command="python -c \"open('file.py', 'w').close()\"")
    assert not result["success"]
    assert "dangerous" in result["error"].lower()

def test_edit_tool_no_replacement():
    """Verify failure when replacement doesn't occur"""
    (tmp_path / "test.py").write_text("def func(): pass")
    tool = create_tool_instance("edit", tmp_path, PermissionMode.AUTO_APPROVE, console)
    result = tool.execute(
        file_path="test.py",
        old_string="def func2(): pass",  # Doesn't exist
        new_string="def other(): pass"
    )
    assert not result["success"]
    assert "not found" in result["error"].lower()
```

---

## Files with Potential Issues

```
NEEDS FIX:
├── cortex/tools/command_tools.py     ❌ Python command validation missing
├── cortex/tools/file_tools.py        ❌ Empty content validation missing
├── cortex/tools/edit_tool.py         ❌ Replacement verification missing
├── cortex/tools/base.py              ❌ Silent backup failure risk
└── cortex/core/transaction.py        ⚠️  Backup mechanism needs review

GOOD:
├── cortex/agent.py                   ✅ Has JSON parsing error handling
├── cortex/core/security.py           ✅ Has path validation
└── cortex/core/loop_guards.py        ✅ Has repeated operation detection
```

---

## Recovery Options

If files are erased:

### 1. Transaction Manager Backups
- Location: Not documented in code (likely in `.cortex/` directory)
- Status: Only works if transaction manager is initialized

### 2. File Cache
- Location: In-memory only
- Status: Lost on agent restart

### 3. Git History
- If repository, can recover with `git checkout`
- Not reliable for agent-erased files

**Recommendation**: No reliable recovery currently exists. Prevention is essential.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Critical vulnerabilities found | 3 |
| Files requiring fixes | 5 |
| Deleted files detected | 1 (intentional) |
| Test coverage gaps | 4+ tests missing |
| Likelihood of file loss | MEDIUM-HIGH |
| Impact severity | CRITICAL |

---

## Next Steps

1. ✅ **Read** this summary
2. 📄 **Review** the detailed research report: `RESEARCH_FILE_ERASURE_ISSUE.md`
3. 🔧 **Implement** Priority 1 fixes immediately
4. ✅ **Add** missing safety tests
5. 📋 **Audit** argument parsing throughout codebase
6. 🚀 **Deploy** fixes before production use

---

**Report Generated**: January 11, 2026  
**Status**: COMPLETE - READY FOR ACTION  
**Severity**: CRITICAL - Requires immediate attention
