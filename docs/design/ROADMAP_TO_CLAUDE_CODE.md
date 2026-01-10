# Cortex Roadmap: Becoming Claude Code

This document outlines the gaps between Cortex and Claude Code, with prioritized implementation phases.

---

## Current Issues: Search Tools Are Broken

### Problem Analysis (`cortex/tools/search_tools.py`)

1. **Windows Incompatibility**
   - Uses `rg` (ripgrep) and `grep` via shell - these don't exist on Windows by default
   - Shell command syntax differs between Windows (cmd/PowerShell) and Unix

2. **Shell Injection & Escaping Issues**
   ```python
   # Current broken code:
   f"rg -n -C 2 {pattern_arg} '{query}'"  # Fails with special chars
   ```
   - Special regex characters break the query
   - Single quotes don't work on Windows
   - No proper argument escaping

3. **Limited Functionality**
   - No output mode options (files only, content, count)
   - No case-insensitive search option
   - Hardcoded context lines (2)
   - No multiline pattern support
   - 10s timeout too short for large codebases

### Immediate Fixes Needed

```python
# Recommended approach: Use Python's native capabilities
import subprocess
import shlex
import platform

class SearchFilesTool(Tool):
    def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str = None,
        output_mode: str = "files_with_matches",  # or "content", "count"
        case_insensitive: bool = False,
        context_lines: int = 0,
        multiline: bool = False,
    ) -> Dict[str, Any]:
        # Use pathlib + re for pure Python fallback
        # Or properly escape args for ripgrep
```

---

## Feature Gap Analysis: Cortex vs Claude Code

### Legend
- Priority: P0 (Critical), P1 (High), P2 (Medium), P3 (Nice-to-have)

---

## Phase 1: Fix Critical Search & File Tools (P0)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **Grep Tool** | Regex search with modes (files/content/count), context lines, multiline | Basic broken search | Major |
| **Glob Tool** | Fast file pattern matching, sorted by mtime | Basic list_files | Major |
| **Edit Tool** | Surgical string replacement | Only full file rewrite | Major |
| **Read Tool** | Offset/limit for large files, image/PDF support | Basic read, no offsets | Medium |

### Implementation Tasks

#### 1.1 New Grep Tool
```python
class GrepTool(Tool):
    """Powerful search tool built on ripgrep (with Python fallback)"""

    def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str = None,           # File pattern filter
        type: str = None,           # File type (py, js, etc.)
        output_mode: str = "files_with_matches",
        case_insensitive: bool = False,
        context_before: int = 0,    # -B
        context_after: int = 0,     # -A
        context: int = 0,           # -C
        multiline: bool = False,
        head_limit: int = 0,        # Limit results
    ) -> Dict[str, Any]:
```

#### 1.2 New Glob Tool
```python
class GlobTool(Tool):
    """Fast file pattern matching"""

    def execute(
        self,
        pattern: str,              # e.g., "**/*.py"
        path: str = ".",
        sort_by_mtime: bool = True,
    ) -> Dict[str, Any]:
```

#### 1.3 Edit Tool (Surgical Edits)
```python
class EditTool(Tool):
    """Exact string replacement in files"""

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> Dict[str, Any]:
```

#### 1.4 Enhanced Read Tool
```python
class ReadFileTool(Tool):
    def execute(
        self,
        path: str,
        offset: int = 0,          # Start line
        limit: int = 2000,        # Max lines
    ) -> Dict[str, Any]:
```

---

## Phase 2: Agent Intelligence & Codebase Understanding (P0-P1)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **Explore Agent** | Sub-agent for codebase exploration | Task tool exists | Partial |
| **Plan Mode** | Enter/Exit plan mode workflow | Plan permission mode | Partial |
| **Context Summarization** | Auto-summarize long conversations | File exists but unused | Major |
| **Better System Prompt** | Detailed tool usage guidelines | Basic prompt | Medium |

### Implementation Tasks

#### 2.1 Explore Agent Pattern
- Create specialized prompts for exploration tasks
- Sub-agent spawning with focused context
- Return structured codebase analysis

#### 2.2 Enhanced System Prompt
Current prompt is ~350 lines. Claude Code's is much more detailed with:
- Specific tool usage guidelines
- Git commit/PR workflows
- Code quality guidelines
- Security considerations

#### 2.3 Context Summarization Integration
- Hook `summarization.py` into ConversationManager
- Trigger summarization when context exceeds threshold
- Preserve key information while reducing tokens

---

## Phase 3: Web & External Tools (P1)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **WebFetch** | Fetch URL, convert to markdown, analyze | None | Major |
| **WebSearch** | Search web for information | None | Major |

### Implementation Tasks

#### 3.1 WebFetch Tool
```python
class WebFetchTool(Tool):
    """Fetch and process web content"""

    def execute(
        self,
        url: str,
        prompt: str,  # What to extract/analyze
    ) -> Dict[str, Any]:
```

#### 3.2 WebSearch Tool
```python
class WebSearchTool(Tool):
    """Search the web"""

    def execute(
        self,
        query: str,
        allowed_domains: List[str] = None,
        blocked_domains: List[str] = None,
    ) -> Dict[str, Any]:
```

---

## Phase 4: Advanced Editing & Notebooks (P2)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **NotebookEdit** | Edit Jupyter notebook cells | None | Medium |
| **Image Reading** | Read/analyze images | None | Medium |
| **PDF Reading** | Read/analyze PDFs | None | Medium |

---

## Phase 5: Background Tasks & Parallelism (P2)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **Background Bash** | Run commands in background | None | Medium |
| **TaskOutput** | Get output from background tasks | None | Medium |
| **KillShell** | Kill background processes | None | Low |
| **Parallel Tool Calls** | Execute multiple tools in parallel | Sequential only | Medium |

---

## Phase 6: Skills & Extensibility (P3)

| Feature | Claude Code | Cortex Status | Gap |
|---------|-------------|---------------|-----|
| **Skill System** | /commit, /review-pr, custom skills | None | Major |
| **MCP Support** | Model Context Protocol servers | None | Major |
| **Hooks Expansion** | More hook points | Basic hooks | Low |

---

## Implementation Priority Matrix

### Must Have (Week 1-2)
1. **Fix Search Tools** - Make them actually work on Windows/Unix
2. **Add Glob Tool** - Essential for file discovery
3. **Add Edit Tool** - Surgical edits vs full rewrites
4. **Enhance Read Tool** - Offset/limit support

### Should Have (Week 3-4)
5. **Better System Prompt** - More detailed tool guidance
6. **Context Summarization** - Prevent context overflow
7. **Explore Agent** - Sub-agent for codebase exploration
8. **WebFetch** - External documentation access

### Nice to Have (Week 5+)
9. **WebSearch** - Web search capability
10. **Background Tasks** - Parallel execution
11. **Skill System** - Extensible commands
12. **Notebook Support** - Jupyter editing

---

## Detailed Implementation Plan

### Step 1: Fix SearchFilesTool (Critical)

**File:** `cortex/tools/search_tools.py`

```python
import re
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List

class GrepTool(Tool):
    """
    Powerful search tool built on ripgrep with Python fallback.

    Supports:
    - Regex patterns
    - Multiple output modes
    - File filtering by glob or type
    - Context lines
    - Case sensitivity
    - Multiline matching
    """

    timeout_category = "search"
    default_timeout = 30

    def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: Optional[str] = None,
        file_type: Optional[str] = None,
        output_mode: str = "files_with_matches",
        case_insensitive: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        context: int = 0,
        multiline: bool = False,
        head_limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Execute search with ripgrep or Python fallback."""

        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY)

        # Try ripgrep first, fall back to Python
        if self._has_ripgrep():
            return self._search_with_ripgrep(
                pattern, full_path, glob, file_type, output_mode,
                case_insensitive, context_before, context_after, context,
                multiline, head_limit, offset
            )
        else:
            return self._search_with_python(
                pattern, full_path, glob, output_mode,
                case_insensitive, head_limit, offset
            )

    def _has_ripgrep(self) -> bool:
        """Check if ripgrep is available."""
        try:
            subprocess.run(
                ["rg", "--version"],
                capture_output=True,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _search_with_ripgrep(self, ...) -> Dict[str, Any]:
        """Use ripgrep for fast searching."""
        args = ["rg"]

        # Output mode
        if output_mode == "files_with_matches":
            args.append("-l")
        elif output_mode == "count":
            args.append("-c")
        # else: content mode (default)

        # Options
        if case_insensitive:
            args.append("-i")
        if multiline:
            args.extend(["-U", "--multiline-dotall"])
        if context > 0:
            args.extend(["-C", str(context)])
        if context_before > 0:
            args.extend(["-B", str(context_before)])
        if context_after > 0:
            args.extend(["-A", str(context_after)])
        if glob:
            args.extend(["-g", glob])
        if file_type:
            args.extend(["-t", file_type])

        # Add pattern and path (properly escaped)
        args.extend([pattern, str(full_path)])

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.get_timeout()
        )

        # Process output...

    def _search_with_python(self, ...) -> Dict[str, Any]:
        """Pure Python fallback for systems without ripgrep."""
        flags = re.IGNORECASE if case_insensitive else 0
        if multiline:
            flags |= re.MULTILINE | re.DOTALL

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return create_error_response(
                f"Invalid regex pattern: {e}",
                ErrorType.VALIDATION
            )

        results = []
        for file_path in self._find_files(full_path, glob):
            try:
                content = file_path.read_text(errors='ignore')
                matches = list(regex.finditer(content))
                if matches:
                    if output_mode == "files_with_matches":
                        results.append(str(file_path.relative_to(self.project_dir)))
                    elif output_mode == "count":
                        results.append(f"{file_path}: {len(matches)}")
                    else:
                        # Content mode with line numbers
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            results.append(f"{file_path}:{line_num}: {match.group()}")
            except Exception:
                continue

        return create_success_response({
            "results": results[offset:offset + head_limit] if head_limit else results[offset:],
            "total_matches": len(results)
        })
```

### Step 2: Add GlobTool

```python
class GlobTool(Tool):
    """Fast file pattern matching sorted by modification time."""

    def execute(
        self,
        pattern: str,
        path: str = ".",
    ) -> Dict[str, Any]:
        """Find files matching glob pattern."""
        try:
            full_path = validate_path(self.project_dir, path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY)

        if not full_path.is_dir():
            return create_error_response(
                f"Not a directory: {path}",
                ErrorType.VALIDATION
            )

        # Find matching files
        matches = list(full_path.glob(pattern))

        # Sort by modification time (newest first)
        matches.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Convert to relative paths
        files = [
            str(f.relative_to(self.project_dir))
            for f in matches
            if f.is_file()
        ]

        return create_success_response({
            "files": files,
            "count": len(files)
        })
```

### Step 3: Add EditTool

```python
class EditTool(Tool):
    """Surgical string replacement in files."""

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> Dict[str, Any]:
        """Replace exact string in file."""

        if self.permission_mode == PermissionMode.PLAN:
            return create_permission_denial(
                "Plan mode - no edits allowed",
                "edit",
                {"file_path": file_path}
            )

        try:
            full_path = validate_path(self.project_dir, file_path)
        except SecurityError as e:
            return create_error_response(str(e), ErrorType.SECURITY)

        if not full_path.exists():
            return create_error_response(
                f"File not found: {file_path}",
                ErrorType.NOT_FOUND
            )

        content = full_path.read_text()

        # Check if old_string exists
        if old_string not in content:
            return create_error_response(
                f"String not found in file: {old_string[:50]}...",
                ErrorType.VALIDATION,
                {"hint": "Make sure the string matches exactly, including whitespace"}
            )

        # Check uniqueness (unless replace_all)
        if not replace_all:
            count = content.count(old_string)
            if count > 1:
                return create_error_response(
                    f"String appears {count} times. Use replace_all=true or provide more context.",
                    ErrorType.VALIDATION
                )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements = 1

        # Ask permission in NORMAL mode
        if self.permission_mode == PermissionMode.NORMAL and self.console:
            # Show diff preview
            self._show_diff(old_string, new_string)
            if not Confirm.ask(f"Apply edit to {file_path}?"):
                return create_permission_denial(
                    "Edit cancelled by user",
                    "edit",
                    {"file_path": file_path}
                )

        # Write file
        full_path.write_text(new_content)

        return create_success_response({
            "file": file_path,
            "replacements": replacements
        })
```

---

## Summary

### Immediate Actions (This Sprint)

1. **Fix `SearchFilesTool`** - Cross-platform, proper escaping, fallback
2. **Add `GlobTool`** - Fast file finding with mtime sorting
3. **Add `EditTool`** - Surgical string replacement
4. **Enhance `ReadFileTool`** - Add offset/limit parameters
5. **Update tool schemas** in `__init__.py`
6. **Add tests** for all new tools

### Success Criteria

- [ ] Search works on Windows without ripgrep
- [ ] Search works with special characters in patterns
- [ ] Agent can find files by pattern quickly
- [ ] Agent can make surgical edits without rewriting entire files
- [ ] Agent can read large files in chunks
- [ ] All tools have comprehensive tests

---

## Architecture Notes

### Tool Registration Pattern
All new tools should:
1. Inherit from `Tool` base class
2. Implement `execute(**kwargs)` method
3. Return standardized response via `create_success_response` or `create_error_response`
4. Be registered in `registry.py`
5. Have schema defined in `__init__.py`

### Error Handling
Use the standardized error types:
- `ErrorType.SECURITY` - Security violations
- `ErrorType.NOT_FOUND` - Resource not found
- `ErrorType.VALIDATION` - Invalid input
- `ErrorType.EXECUTION` - Runtime errors
- `ErrorType.TIMEOUT` - Operation timeout
- `ErrorType.PERMISSION` - Permission denied
