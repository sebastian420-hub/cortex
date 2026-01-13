# Cortex Tool Error Handling Audit Report
Generated: 2026-01-13T04:30:45.973326
Total files analyzed: 12

## Executive Summary
- Average compliance score: 73.3/100
- Compliant files (≥70): 12/12
- Non-compliant files: 0/12
- Total manual error returns: 0

## File-by-File Analysis

### [PASS] ask_user_tool.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\ask_user_tool.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 77: create_error_response - `return create_error_response("No questions provided", ErrorType.VALIDATION)`
  - Line 80: create_error_response - `return create_error_response(`
  - Line 121: create_error_response - `return create_error_response(`
  - Line 128: create_error_response - `return create_error_response(`
  - Line 135: create_error_response - `return create_error_response(`
  - ... and 3 more

### [PASS] glob_tool.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\glob_tool.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 57: create_error_response - `return create_error_response(str(e), ErrorType.SECURITY, {"path": path})`
  - Line 60: create_error_response - `return create_error_response(`
  - Line 65: create_error_response - `return create_error_response(`
  - Line 115: create_error_response - `return create_error_response(`

### [PASS] grep_tool.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\grep_tool.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 82: create_error_response - `return create_error_response(str(e), ErrorType.SECURITY, {"path": path})`
  - Line 85: create_error_response - `return create_error_response(`
  - Line 92: create_error_response - `return create_error_response(`
  - Line 245: create_error_response - `return create_error_response(`
  - Line 294: create_error_response - `return create_error_response(`

### [PASS] search_tools.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\search_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 24: create_error_response - `return create_error_response(`
  - Line 29: create_error_response - `return create_error_response(`
  - Line 54: create_error_response - `return create_error_response(str(e), ErrorType.SECURITY, {"path": path})`
  - Line 56: create_error_response - `return create_error_response(str(e), ErrorType.EXECUTION, {"path": path})`
  - Line 118: create_error_response - `return create_error_response(`
  - ... and 1 more

### [PASS] skill_tools.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\skill_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 188: create_error_response - `return create_error_response(`
  - Line 196: create_error_response - `return create_error_response(`
  - Line 204: create_error_response - `return create_error_response(`
  - Line 211: create_error_response - `return create_error_response(`
  - Line 218: create_error_response - `return create_error_response(`
  - ... and 1 more

### [PASS] test_tools.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\test_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 72: create_error_response - `return create_error_response(`
  - Line 118: create_error_response - `return create_error_response(`
  - Line 129: create_error_response - `return create_error_response(`
  - Line 135: create_error_response - `return create_error_response(`

### [PASS] todo_tool.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\todo_tool.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 89: create_error_response - `return create_error_response(`
  - Line 100: create_error_response - `return create_error_response(`

### [PASS] web_tools.py (70/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\web_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 121: create_error_response - `return create_error_response(`
  - Line 129: create_error_response - `return create_error_response("URL is required", ErrorType.VALIDATION, {"url": url})`
  - Line 137: create_error_response - `return create_error_response(f"Invalid URL: {url}", ErrorType.VALIDATION, {"url": url})`
  - Line 203: create_error_response - `return create_error_response(`
  - Line 244: create_error_response - `return create_error_response(`
  - ... and 9 more

### [PASS] command_tools.py (80/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\command_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 66: create_permission_denial - `return create_permission_denial(`
  - Line 82: create_error_response - `return create_error_response(`
  - Line 92: create_error_response - `return create_error_response(`
  - Line 101: create_permission_denial - `return create_permission_denial(`
  - Line 139: create_error_response - `return create_error_response(`
  - ... and 2 more

### [PASS] edit_tool.py (80/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\edit_tool.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 62: create_permission_denial - `return create_permission_denial(`
  - Line 68: create_error_response - `return create_error_response(`
  - Line 75: create_error_response - `return create_error_response(`
  - Line 83: create_error_response - `return create_error_response(str(e), ErrorType.SECURITY, {"file_path": file_path})`
  - Line 86: create_error_response - `return create_error_response(`
  - ... and 7 more

### [PASS] file_tools.py (80/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\file_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 59: create_error_response - `return create_error_response(`
  - Line 64: create_error_response - `return create_error_response(`
  - Line 91: create_error_response - `return create_error_response(`
  - Line 165: create_error_response - `return create_error_response(str(e), ErrorType.SECURITY, {"path": path})`
  - Line 167: create_error_response - `return create_error_response(`
  - ... and 8 more

### [PASS] git_tools.py (80/100)
**File**: `C:\Users\lwinz\OneDrive\Desktop\LocalTerminalAgent\cortex\tools\git_tools.py`
**Imports errors module**: True
**Uses create_error_response**: True
**Manual error returns**: 0
**Error patterns found**:
  - Line 38: create_error_response - `return create_error_response(`
  - Line 58: create_error_response - `return create_error_response(`
  - Line 65: create_error_response - `return create_error_response(str(e), ErrorType.EXECUTION, retryable=True)`
  - Line 87: create_error_response - `return create_error_response(`
  - Line 110: create_error_response - `return create_error_response(`
  - ... and 57 more

## Compliance Breakdown

- Excellent (90-100): 0 files (0.0%)
- Good (70-89): 12 files (100.0%)
- Fair (50-69): 0 files (0.0%)
- Poor (0-49): 0 files (0.0%)

## Priority Fixes

## Recommended Action Items

1. **Immediate fixes** (files with score < 70):

2. **Standardization steps**:
   - Ensure all tools import from utils.errors
   - Replace manual error dictionaries with create_error_response()
   - Add error context for better debugging
   - Use consistent error_type values

3. **Validation**:
   - Run this audit script after changes
   - Add error handling tests
   - Verify no silent exceptions