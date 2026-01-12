# Cortex Design Specifications

## Overview

This document contains comprehensive design specifications for making Cortex a production-ready AI coding assistant with features comparable to Claude Code.

**Version:** 2.0 Design
**Status:** Planning
**Last Updated:** 2025-01-09

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Core Robustness](#phase-1-core-robustness)
3. [Phase 2: Advanced Features](#phase-2-advanced-features)
4. [Phase 3: Code Refactoring](#phase-3-code-refactoring)
5. [Phase 4: Extended Features](#phase-4-extended-features)
6. [Implementation Priority](#implementation-priority)
7. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer (cli.py)                       │
│  - Argument parsing, REPL, Signal handling                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Agent Layer (agent.py)                     │
│  - Orchestration, conversation, tool execution              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Core Layer (core/)                        │
│  - Security, providers, context, recovery, loop guards      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Tools Layer (tools/)                       │
│  - File, command, git, search, test tools                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  Storage Layer (storage/)                    │
│  - Sessions, history, cleanup                               │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture (v2.0)

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer (cli.py)                       │
│  - Argument parsing, REPL, Signal handling                  │
│  + Skill/Command routing                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                Skills Layer (skills/) [NEW]                  │
│  - /commit, /review-pr, /init, extensible commands          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Agent Layer (agent.py)                     │
│  - Orchestration (refactored, <300 lines)                   │
│  + Plan mode workflow                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               Subagent Layer (subagent/) [ENHANCED]          │
│  - Explore, Plan, Bash typed agents                         │
│  - Background task execution                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Core Layer (core/)                        │
│  + Summarization engine                                     │
│  + System prompt builder                                    │
│  + Tool executor (extracted)                                │
│  + Message processor (extracted)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Tools Layer (tools/)                       │
│  + AskUserQuestion tool                                     │
│  + TodoWrite tool                                           │
│  + WebSearch/WebFetch tools                                 │
│  + Multimodal tools                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  Storage Layer (storage/)                    │
│  + Secure file permissions                                  │
│  + Todo persistence                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Robustness

### 1.1 Context Summarization System

**Purpose:** Instead of simply truncating old messages when context is full, intelligently summarize them to preserve important information.

**File:** `cortex/core/summarization.py`

#### Design

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class SummarizationStrategy(Enum):
    """Strategy for summarization"""
    SIMPLE = "simple"           # Basic extraction of key points
    LLM_BASED = "llm_based"     # Use LLM to summarize
    HYBRID = "hybrid"           # Combine both approaches


@dataclass
class SummaryChunk:
    """A summarized chunk of conversation"""
    original_message_count: int
    original_token_count: int
    summary_token_count: int
    summary_content: str
    key_decisions: List[str]
    files_modified: List[str]
    errors_encountered: List[str]
    timestamp_start: str
    timestamp_end: str


class ConversationSummarizer(ABC):
    """Base class for conversation summarization"""

    @abstractmethod
    def summarize(
        self,
        messages: List[Dict[str, Any]],
        max_summary_tokens: int = 500
    ) -> SummaryChunk:
        """Summarize a list of messages"""
        pass

    @abstractmethod
    def should_summarize(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int,
        max_tokens: int
    ) -> bool:
        """Determine if summarization should occur"""
        pass


class SimpleSummarizer(ConversationSummarizer):
    """Extract key information without LLM"""

    def summarize(self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500) -> SummaryChunk:
        # Extract:
        # - Files read/written (from tool calls)
        # - Commands executed
        # - Errors encountered
        # - Key user requests
        pass

    def should_summarize(self, messages, current_tokens, max_tokens) -> bool:
        # Summarize when at 80% capacity
        return current_tokens > (max_tokens * 0.8)


class LLMSummarizer(ConversationSummarizer):
    """Use LLM to create intelligent summaries"""

    def __init__(self, provider, model: str):
        self.provider = provider
        self.model = model

    def summarize(self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500) -> SummaryChunk:
        # Send messages to LLM with summarization prompt
        # Extract structured summary
        pass


class HybridSummarizer(ConversationSummarizer):
    """Combine simple extraction with LLM refinement"""

    def __init__(self, provider, model: str):
        self.simple = SimpleSummarizer()
        self.llm = LLMSummarizer(provider, model)

    def summarize(self, messages: List[Dict[str, Any]], max_summary_tokens: int = 500) -> SummaryChunk:
        # First: Simple extraction
        # Then: LLM refinement if provider available
        pass
```

#### Integration with ConversationManager

```python
# In cortex/core/conversation.py

class ConversationManager:
    def __init__(
        self,
        # ... existing params ...
        summarizer: Optional[ConversationSummarizer] = None,
        enable_summarization: bool = True
    ):
        self.summarizer = summarizer or SimpleSummarizer()
        self.enable_summarization = enable_summarization
        self.summaries: List[SummaryChunk] = []

    def _optimize(self) -> None:
        """Optimize with summarization instead of pure truncation"""
        current_tokens = get_conversation_tokens(self.history, self.model)

        if self.enable_summarization and self.summarizer.should_summarize(
            self.history, current_tokens, self.max_tokens
        ):
            # Get messages to summarize (older messages, keep recent)
            messages_to_summarize = self.history[1:-self.keep_recent]  # Skip system, keep recent

            if len(messages_to_summarize) > 5:  # Only summarize if enough messages
                summary = self.summarizer.summarize(messages_to_summarize)
                self.summaries.append(summary)

                # Replace old messages with summary message
                summary_message = {
                    "role": "system",
                    "content": f"[CONVERSATION SUMMARY]\n{summary.summary_content}\n\n"
                              f"Files modified: {', '.join(summary.files_modified)}\n"
                              f"Key decisions: {'; '.join(summary.key_decisions)}"
                }

                # Rebuild history: system + summary + recent
                self.history = [
                    self.history[0],  # System prompt
                    summary_message,
                    *self.history[-self.keep_recent:]  # Recent messages
                ]
        else:
            # Fallback to truncation
            # ... existing truncation logic ...
```

#### Configuration

```yaml
# config.yaml
summarization:
  enabled: true
  strategy: "hybrid"  # simple, llm_based, hybrid
  trigger_threshold: 0.8  # Summarize at 80% token capacity
  max_summary_tokens: 500
  preserve_tool_results: true  # Keep recent tool results intact
  preserve_errors: true  # Always include errors in summary
```

---

### 1.2 Structured Ask User Questions Tool

**Purpose:** Allow the agent to ask users structured multiple-choice questions during task execution, getting precise input without ambiguity.

**File:** `cortex/tools/ask_user_tool.py`

#### Design

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from .base import Tool

class QuestionType(Enum):
    SINGLE_SELECT = "single"
    MULTI_SELECT = "multi"
    TEXT_INPUT = "text"
    CONFIRMATION = "confirm"


@dataclass
class QuestionOption:
    """An option for a question"""
    label: str
    description: str
    value: Optional[str] = None  # Defaults to label if not set

    def __post_init__(self):
        if self.value is None:
            self.value = self.label


@dataclass
class Question:
    """A structured question"""
    question: str
    header: str  # Short label (max 12 chars) like "Auth method"
    options: List[QuestionOption]
    multi_select: bool = False
    allow_other: bool = True  # Allow custom text input


@dataclass
class QuestionAnswer:
    """User's answer to a question"""
    question_header: str
    selected_options: List[str]
    custom_input: Optional[str] = None


class AskUserQuestionTool(Tool):
    """
    Tool for asking structured questions to the user.

    This tool pauses execution and presents the user with options,
    allowing for precise input without ambiguity.
    """

    name = "ask_user_question"
    description = "Ask the user structured questions with multiple choice options"

    schema = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "List of questions to ask (1-4 questions)",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The complete question to ask"
                        },
                        "header": {
                            "type": "string",
                            "description": "Short label (max 12 chars)",
                            "maxLength": 12
                        },
                        "options": {
                            "type": "array",
                            "description": "Available choices (2-4 options)",
                            "minItems": 2,
                            "maxItems": 4,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "description": {"type": "string"}
                                },
                                "required": ["label", "description"]
                            }
                        },
                        "multiSelect": {
                            "type": "boolean",
                            "default": False,
                            "description": "Allow multiple selections"
                        }
                    },
                    "required": ["question", "header", "options"]
                }
            }
        },
        "required": ["questions"]
    }

    def execute(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute the question tool.

        Displays questions to user and collects responses.
        """
        answers = []

        for q_data in questions:
            question = Question(
                question=q_data["question"],
                header=q_data["header"],
                options=[
                    QuestionOption(
                        label=opt["label"],
                        description=opt["description"]
                    )
                    for opt in q_data["options"]
                ],
                multi_select=q_data.get("multiSelect", False)
            )

            answer = self._ask_question(question)
            answers.append(answer)

        return {
            "success": True,
            "answers": [
                {
                    "header": a.question_header,
                    "selected": a.selected_options,
                    "custom_input": a.custom_input
                }
                for a in answers
            ]
        }

    def _ask_question(self, question: Question) -> QuestionAnswer:
        """Display question and get user input"""
        from rich.panel import Panel
        from rich.prompt import Prompt

        # Display question header
        self.console.print(f"\n[bold cyan]{question.header}[/bold cyan]")
        self.console.print(f"[white]{question.question}[/white]\n")

        # Display options
        for i, opt in enumerate(question.options, 1):
            self.console.print(f"  [yellow]{i}[/yellow]. {opt.label}")
            self.console.print(f"     [dim]{opt.description}[/dim]")

        # Always show "Other" option
        other_num = len(question.options) + 1
        self.console.print(f"  [yellow]{other_num}[/yellow]. Other (custom input)")

        # Get selection
        if question.multi_select:
            prompt_text = "Select options (comma-separated numbers)"
        else:
            prompt_text = "Select an option"

        selection = Prompt.ask(f"\n{prompt_text}")

        # Parse selection
        selected_options = []
        custom_input = None

        try:
            indices = [int(x.strip()) for x in selection.split(",")]

            for idx in indices:
                if idx == other_num:
                    custom_input = Prompt.ask("Enter custom input")
                    selected_options.append("other")
                elif 1 <= idx <= len(question.options):
                    selected_options.append(question.options[idx - 1].value)
        except ValueError:
            # Treat as custom input if not a number
            custom_input = selection
            selected_options.append("other")

        return QuestionAnswer(
            question_header=question.header,
            selected_options=selected_options,
            custom_input=custom_input
        )
```

#### Usage Examples

```python
# Agent calls this tool when needing clarification

# Example 1: Authentication method
{
    "questions": [{
        "question": "Which authentication method should we use?",
        "header": "Auth method",
        "options": [
            {"label": "JWT (Recommended)", "description": "Stateless tokens, good for APIs"},
            {"label": "Session-based", "description": "Server-side sessions with cookies"},
            {"label": "OAuth 2.0", "description": "Third-party authentication"}
        ],
        "multiSelect": False
    }]
}

# Example 2: Features to implement (multi-select)
{
    "questions": [{
        "question": "Which features do you want to enable?",
        "header": "Features",
        "options": [
            {"label": "Logging", "description": "Log all API requests"},
            {"label": "Rate limiting", "description": "Limit requests per user"},
            {"label": "Caching", "description": "Cache responses"},
            {"label": "Metrics", "description": "Collect performance metrics"}
        ],
        "multiSelect": True
    }]
}
```

---

### 1.3 Todo Tracking Tool

**Purpose:** Track tasks and progress during a session, giving users visibility into what the agent is working on.

**File:** `cortex/tools/todo_tool.py`

#### Design

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from .base import Tool


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TodoItem:
    """A single todo item"""
    content: str
    status: TodoStatus
    active_form: str  # Present continuous form (e.g., "Running tests")
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "status": self.status.value,
            "activeForm": self.active_form,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TodoManager:
    """Manages the todo list for a session"""

    def __init__(self):
        self.todos: List[TodoItem] = []
        self._display_callback = None

    def set_display_callback(self, callback):
        """Set callback for displaying todo updates"""
        self._display_callback = callback

    def update(self, todos: List[Dict[str, Any]]) -> None:
        """Update the entire todo list"""
        new_todos = []

        for item in todos:
            status = TodoStatus(item["status"])

            # Find existing item to preserve timestamps
            existing = self._find_by_content(item["content"])

            if existing:
                todo = TodoItem(
                    content=item["content"],
                    status=status,
                    active_form=item["activeForm"],
                    created_at=existing.created_at
                )
                if status == TodoStatus.COMPLETED and existing.status != TodoStatus.COMPLETED:
                    todo.completed_at = datetime.now()
            else:
                todo = TodoItem(
                    content=item["content"],
                    status=status,
                    active_form=item["activeForm"]
                )

            new_todos.append(todo)

        self.todos = new_todos
        self._display()

    def _find_by_content(self, content: str) -> Optional[TodoItem]:
        """Find existing todo by content"""
        for todo in self.todos:
            if todo.content == content:
                return todo
        return None

    def _display(self) -> None:
        """Display current todo state"""
        if self._display_callback:
            self._display_callback(self.todos)

    def get_current_task(self) -> Optional[TodoItem]:
        """Get the currently in-progress task"""
        for todo in self.todos:
            if todo.status == TodoStatus.IN_PROGRESS:
                return todo
        return None

    def get_progress(self) -> Dict[str, int]:
        """Get progress statistics"""
        return {
            "total": len(self.todos),
            "pending": sum(1 for t in self.todos if t.status == TodoStatus.PENDING),
            "in_progress": sum(1 for t in self.todos if t.status == TodoStatus.IN_PROGRESS),
            "completed": sum(1 for t in self.todos if t.status == TodoStatus.COMPLETED)
        }


class TodoWriteTool(Tool):
    """
    Tool for managing task lists during a session.

    The agent uses this to:
    - Plan complex multi-step tasks
    - Track progress on each step
    - Give users visibility into what's happening
    """

    name = "todo_write"
    description = "Manage and track tasks for the current session"

    schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "The complete updated todo list",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task description (imperative form, e.g., 'Run tests')"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Current status of the task"
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "Present continuous form (e.g., 'Running tests')"
                        }
                    },
                    "required": ["content", "status", "activeForm"]
                }
            }
        },
        "required": ["todos"]
    }

    def __init__(self, *args, todo_manager: TodoManager = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.todo_manager = todo_manager or TodoManager()

    def execute(self, todos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update the todo list"""

        # Validate: only one in_progress at a time
        in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
        if in_progress_count > 1:
            return {
                "success": False,
                "error": "Only one task can be in_progress at a time",
                "error_type": "validation"
            }

        self.todo_manager.update(todos)

        progress = self.todo_manager.get_progress()
        current = self.todo_manager.get_current_task()

        return {
            "success": True,
            "progress": progress,
            "current_task": current.active_form if current else None
        }
```

#### Display Component

```python
# In cortex/ui/todo_display.py

from rich.panel import Panel
from rich.table import Table
from rich.console import Console

def display_todos(todos: List[TodoItem], console: Console) -> None:
    """Display todo list in terminal"""

    if not todos:
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Status", width=3)
    table.add_column("Task")

    status_icons = {
        TodoStatus.PENDING: "[dim]○[/dim]",
        TodoStatus.IN_PROGRESS: "[cyan]◐[/cyan]",
        TodoStatus.COMPLETED: "[green]●[/green]"
    }

    for todo in todos:
        icon = status_icons[todo.status]

        if todo.status == TodoStatus.IN_PROGRESS:
            text = f"[cyan]{todo.active_form}[/cyan]"
        elif todo.status == TodoStatus.COMPLETED:
            text = f"[dim strikethrough]{todo.content}[/dim strikethrough]"
        else:
            text = f"[white]{todo.content}[/white]"

        table.add_row(icon, text)

    # Calculate progress
    completed = sum(1 for t in todos if t.status == TodoStatus.COMPLETED)
    total = len(todos)

    panel = Panel(
        table,
        title=f"[bold]Tasks ({completed}/{total})[/bold]",
        border_style="dim"
    )

    console.print(panel)
```

#### Integration with Agent

```python
# In cortex/agent.py

class Cortex:
    def __init__(self, ...):
        # ... existing init ...

        # Initialize todo manager
        self.todo_manager = TodoManager()
        self.todo_manager.set_display_callback(
            lambda todos: display_todos(todos, console)
        )

    def _get_system_prompt(self) -> str:
        # Add todo instructions to system prompt
        todo_instructions = """
## Task Management

Use the todo_write tool to track progress on multi-step tasks:
- Create todos when starting complex tasks (3+ steps)
- Mark tasks as in_progress BEFORE starting work
- Mark tasks as completed IMMEDIATELY after finishing
- Only ONE task should be in_progress at a time

Example:
1. User asks to "fix all type errors in the project"
2. You find 5 type errors
3. Create todo list with 5 items
4. Work through each one, updating status as you go
"""
        return base_prompt + todo_instructions
```

---

### 1.4 Secure Session File Permissions

**Purpose:** Ensure session files containing conversation history are only readable by the owner.

**File:** `cortex/storage/sessions.py` (modification)

#### Changes

```python
# Add to cortex/storage/sessions.py

import os
import stat
from pathlib import Path

class SessionStorage:
    """Handles session persistence with secure file permissions"""

    # File permission mask: owner read/write only (0600)
    FILE_PERMISSION = stat.S_IRUSR | stat.S_IWUSR

    # Directory permission mask: owner only (0700)
    DIR_PERMISSION = stat.S_IRWXU

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self._ensure_secure_directory()

    def _ensure_secure_directory(self) -> None:
        """Create storage directory with secure permissions"""
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, mode=self.DIR_PERMISSION)
        else:
            # Fix permissions on existing directory
            if os.name != 'nt':  # Skip on Windows
                os.chmod(self.storage_dir, self.DIR_PERMISSION)

    def _secure_file(self, file_path: Path) -> None:
        """Set secure permissions on a file"""
        if os.name != 'nt':  # Skip on Windows (uses different ACL system)
            os.chmod(file_path, self.FILE_PERMISSION)

    def save_session(self, session_id: str, data: Dict[str, Any]) -> Path:
        """Save session with secure file permissions"""
        file_path = self.storage_dir / f"{session_id}.json"

        # Write to temp file first (atomic write)
        temp_path = file_path.with_suffix('.tmp')

        try:
            # Set restrictive umask before creating file
            if os.name != 'nt':
                old_umask = os.umask(0o077)

            try:
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            finally:
                if os.name != 'nt':
                    os.umask(old_umask)

            # Ensure permissions are correct
            self._secure_file(temp_path)

            # Atomic rename
            temp_path.replace(file_path)

            return file_path

        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data"""
        file_path = self.storage_dir / f"{session_id}.json"

        if not file_path.exists():
            return None

        # Verify permissions before reading (security check)
        if os.name != 'nt':
            file_stat = file_path.stat()
            if file_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                # File is readable by group or others - security warning
                import logging
                logging.warning(
                    f"Session file {file_path} has insecure permissions. "
                    "Consider running: chmod 600 {file_path}"
                )

        with open(file_path, 'r') as f:
            return json.load(f)
```

#### Windows Considerations

```python
# For Windows, use different approach
if os.name == 'nt':
    import win32security
    import ntsecuritycon as con

    def _secure_file_windows(self, file_path: Path) -> None:
        """Set secure permissions on Windows"""
        try:
            # Get current user's SID
            user_sid = win32security.GetTokenInformation(
                win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(),
                    win32security.TOKEN_QUERY
                ),
                win32security.TokenUser
            )[0]

            # Create DACL with only current user access
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_ALL_ACCESS,
                user_sid
            )

            # Apply to file
            sd = win32security.GetFileSecurity(
                str(file_path),
                win32security.DACL_SECURITY_INFORMATION
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                str(file_path),
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
        except ImportError:
            # pywin32 not installed, skip Windows-specific security
            pass
```

---

## Phase 2: Advanced Features

See: [PHASE2_SPECS.md](./PHASE2_SPECS.md)

---

## Phase 3: Code Refactoring

See: [PHASE3_SPECS.md](./PHASE3_SPECS.md)

---

## Phase 4: Extended Features

See: [PHASE4_SPECS.md](./PHASE4_SPECS.md)

---

## Implementation Priority

### Critical Path (Must Have)

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Session file permissions | 1 hour | High | P0 |
| Todo tracking tool | 4 hours | High | P0 |
| Ask user questions tool | 4 hours | High | P0 |
| Extract system prompt | 2 hours | Medium | P1 |

### High Value (Should Have)

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Context summarization | 8 hours | High | P1 |
| Split agent.py | 4 hours | Medium | P1 |
| Typed subagents | 12 hours | High | P1 |
| TypedDict types | 4 hours | Medium | P2 |

### Nice to Have

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Slash commands | 8 hours | Medium | P2 |
| Background tasks | 8 hours | Medium | P2 |
| Web search/fetch | 8 hours | Low | P3 |
| Multimodal support | 12 hours | Low | P3 |
| MCP protocol | 20 hours | Low | P4 |

---

## Testing Strategy

### Unit Tests Required

```
tests/
├── test_summarization.py      # Context summarization
├── test_ask_user_tool.py      # Ask user questions
├── test_todo_tool.py          # Todo tracking
├── test_session_security.py   # File permissions
├── test_subagents.py          # Typed subagents
├── test_skills.py             # Slash commands
└── test_background_tasks.py   # Background execution
```

### Integration Tests

```
tests/integration/
├── test_full_workflow.py          # Complete agent loop
├── test_summarization_flow.py     # Summarization triggers
├── test_todo_workflow.py          # Todo through full task
└── test_subagent_delegation.py    # Subagent handoff
```

### Security Tests

```
tests/security/
├── test_file_permissions.py   # Session file security
├── test_path_traversal.py     # Path validation
└── test_command_injection.py  # Command safety
```

---

## Next Steps

1. Review this specification document
2. Prioritize features based on your needs
3. Start with Phase 1 (core robustness)
4. Proceed to Phase 2-4 as needed

For detailed specifications on each phase, see the linked documents.
