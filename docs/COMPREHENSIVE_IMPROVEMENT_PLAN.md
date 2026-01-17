# Comprehensive Improvement Plan for Cortex Agent System

**Created**: January 2026
**Scope**: Planning Engine, Base Cortex, Prompt System, Codebase Quality
**Priority**: High → Medium → Low

---

## Executive Summary

This plan addresses four major areas requiring improvement:

1. **Planning Engine** - UI/output issues, incomplete implementations, bugs
2. **Base Cortex Enhancement** - Add StateManager for better task tracking
3. **Prompt System** - Dynamic adaptation, model-specific optimization
4. **Codebase Quality** - Error handling, race conditions, technical debt

---

## Part 1: Planning Engine Finalization

### 1.1 Critical UI/Output Issues

| Issue | Location | Priority | Fix |
|-------|----------|----------|-----|
| No progress display during execution | `planning.py:execute_plan()` | HIGH | Add console output for each step |
| Step results collected but not shown | `planning.py:312-340` | HIGH | Display results after each step |
| No spinner/feedback during steps | `agent_enhanced.py:process_with_planning()` | HIGH | Add Rich spinner/progress bar |
| Plan creation shows no detail | `planning.py:create_plan()` | MEDIUM | Show step breakdown |
| Execution summary too terse | `planning.py:392` | MEDIUM | Expand completion message |

### 1.2 Implementation Gaps

```
Current State:
├── create_plan() ─────── Creates 1 generic step (not intelligent)
├── execute_plan() ────── Placeholder loop, no real execution
├── monitor_plan() ────── Returns static data
└── update_plan() ──────── Modifies plan but no re-planning logic
```

**Required Fixes:**

#### A. Intelligent Plan Decomposition (planning.py:210-280)

```python
# CURRENT (broken):
def _decompose_goal(self, goal: str, constraints: List[str]) -> List[PlanStep]:
    # Creates single generic step
    return [PlanStep(
        id=f"step_1",
        description=f"Execute: {goal}",
        step_type=StepType.ACTION,
        ...
    )]

# REQUIRED:
def _decompose_goal(self, goal: str, constraints: List[str]) -> List[PlanStep]:
    """Use LLM to intelligently decompose goal into steps."""
    decomposition_prompt = f"""
    Break down this goal into concrete steps:
    Goal: {goal}
    Constraints: {constraints}

    Return JSON array of steps with:
    - description: what to do
    - step_type: ACTION|SUBTASK|DECISION|CHECKPOINT
    - tools_needed: list of tool names
    - dependencies: list of step IDs this depends on
    """
    # Call LLM and parse response
    steps = self._call_decomposition_llm(decomposition_prompt)
    return [PlanStep(**step) for step in steps]
```

#### B. Real Step Execution (planning.py:312-360)

```python
# CURRENT (placeholder):
for step in steps_to_execute:
    step.status = StepStatus.IN_PROGRESS
    # ... no actual execution
    step.status = StepStatus.COMPLETED

# REQUIRED:
for step in steps_to_execute:
    step.status = StepStatus.IN_PROGRESS
    console.print(f"[cyan]▶ Step {step.id}:[/] {step.description}")

    try:
        # Execute based on step type
        if step.step_type == StepType.ACTION:
            result = self._execute_action_step(step)
        elif step.step_type == StepType.SUBTASK:
            result = self._execute_subtask(step)
        elif step.step_type == StepType.DECISION:
            result = self._execute_decision(step)
        elif step.step_type == StepType.CHECKPOINT:
            result = self._verify_checkpoint(step)

        step.result = result
        step.status = StepStatus.COMPLETED
        console.print(f"[green]✓[/] Step completed: {result[:100]}...")

    except Exception as e:
        step.status = StepStatus.FAILED
        step.result = str(e)
        console.print(f"[red]✗[/] Step failed: {e}")
        if stop_on_failure:
            break
```

#### C. Progress Display Component (NEW FILE: cortex/ui/plan_progress.py)

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.panel import Panel

class PlanProgressDisplay:
    """Rich-based progress display for plan execution."""

    def __init__(self, plan: Plan):
        self.plan = plan
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )

    def show_plan_overview(self):
        """Display plan structure before execution."""
        console.print(Panel(
            self._format_plan_tree(),
            title=f"📋 Plan: {self.plan.goal[:50]}...",
            border_style="blue"
        ))

    def update_step(self, step: PlanStep, status: str):
        """Update display for step status change."""
        icons = {"pending": "○", "in_progress": "◐", "completed": "●", "failed": "✗"}
        colors = {"pending": "dim", "in_progress": "yellow", "completed": "green", "failed": "red"}
        console.print(f"[{colors[status]}]{icons[status]}[/] {step.description}")
```

### 1.3 Planning Engine Fix Priority

```
Week 1: Critical UI Fixes
├── Add step-by-step console output
├── Add spinner during execution
└── Show plan summary on creation

Week 2: Execution Logic
├── Implement real ACTION execution
├── Add SUBTASK delegation
└── Add DECISION branching

Week 3: Polish
├── Add progress bar component
├── Add execution time tracking
└── Add plan export (markdown/json)
```

---

## Part 2: Base Cortex StateManager Addition

### 2.1 Current State

```
Base Cortex (agent.py):
├── MemoryBank ────────── Simple key-value store
├── conversation ──────── Message history
└── NO StateManager ────── Cannot track goals/focus/iterations
```

### 2.2 Required Changes

#### A. Modify agent.py Initialization

```python
# Location: cortex/agent.py:__init__() around line 85

# ADD import at top:
from cortex.core.memory_layers import StateManager

# ADD in __init__:
def __init__(self, model: str, project_dir: str, ...):
    # ... existing code ...

    # Initialize StateManager for task tracking
    self.state_manager = StateManager(
        project_dir=self.project_dir,
        enable_persistence=False  # Base agent doesn't need persistence
    )

    # Track current task context
    self.state_manager.set_focus("IDLE")
```

#### B. Update process_message() to Track State

```python
# Location: cortex/agent.py:process_message() around line 280

def process_message(self, user_message: str, ...):
    # Track user intent
    self.state_manager.set_focus("PROCESSING")
    self.state_manager.record_user_intent(user_message)

    # ... existing processing ...

    # Track tool usage
    if tool_calls:
        for tool_call in tool_calls:
            self.state_manager.record_tool_execution(tool_call.name)

    # Update focus on completion
    self.state_manager.set_focus("IDLE")
```

#### C. Add Todo Tracking to StateManager

```python
# Location: cortex/core/memory_layers.py - Extend StateManager

class StateManager:
    def __init__(self, ...):
        # ... existing ...
        self.todos: List[Todo] = []
        self.current_goal: Optional[str] = None

    def add_todo(self, task: str, priority: str = "medium") -> str:
        """Add a todo item."""
        todo = Todo(
            id=f"todo_{len(self.todos)+1}",
            task=task,
            priority=priority,
            status="pending",
            created_at=datetime.now()
        )
        self.todos.append(todo)
        return todo.id

    def complete_todo(self, todo_id: str):
        """Mark todo as completed."""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.status = "completed"
                todo.completed_at = datetime.now()
                break

    def get_pending_todos(self) -> List[Todo]:
        """Get all pending todos."""
        return [t for t in self.todos if t.status == "pending"]

    def get_state_summary(self) -> str:
        """Get summary for context injection."""
        pending = self.get_pending_todos()
        return f"""
Current Focus: {self.focus}
Active Goal: {self.current_goal or 'None'}
Pending Tasks: {len(pending)}
{chr(10).join(f'  - {t.task}' for t in pending[:5])}
"""
```

### 2.3 Implementation Steps

```
1. Add StateManager import to agent.py
2. Initialize StateManager in __init__
3. Add state tracking calls in process_message
4. Add Todo data class to models
5. Extend StateManager with todo methods
6. Add state summary injection to system prompt
7. Update tests
```

---

## Part 3: Prompt System Improvements

### 3.1 Current Architecture Gaps

```
Current State:
├── Hardcoded system_prompt in agent.py
├── No model-specific adaptation
├── Tools listed but not explained
├── No examples in prompts
└── Static - same prompt for all tasks

Required State:
├── Externalized prompt templates
├── Model capability detection
├── Tool documentation with examples
├── Dynamic context injection
└── Task-type-specific prompts
```

### 3.2 Dynamic Prompt System Design

#### A. Model Capability Detection (NEW: cortex/core/model_capabilities.py)

```python
"""Model capability profiles for prompt optimization."""

MODEL_CAPABILITIES = {
    # High-capability models - can handle complex prompts
    "claude-3-5-sonnet": {
        "context_window": 200000,
        "tool_following": "excellent",
        "reasoning": "excellent",
        "prompt_style": "detailed",
        "supports_json_mode": True,
        "max_tools_per_prompt": 50,
    },
    "gpt-4-turbo": {
        "context_window": 128000,
        "tool_following": "excellent",
        "reasoning": "excellent",
        "prompt_style": "detailed",
        "supports_json_mode": True,
        "max_tools_per_prompt": 50,
    },
    # Medium capability - need clearer prompts
    "llama3.2": {
        "context_window": 8192,
        "tool_following": "good",
        "reasoning": "good",
        "prompt_style": "concise",
        "supports_json_mode": False,
        "max_tools_per_prompt": 20,
    },
    # Smaller models - need explicit guidance
    "mistral-7b": {
        "context_window": 8192,
        "tool_following": "moderate",
        "reasoning": "moderate",
        "prompt_style": "explicit",
        "supports_json_mode": False,
        "max_tools_per_prompt": 10,
    },
}

def get_model_profile(model_name: str) -> dict:
    """Get capability profile for model, with fallback defaults."""
    # Normalize model name
    model_lower = model_name.lower()

    # Try exact match
    if model_lower in MODEL_CAPABILITIES:
        return MODEL_CAPABILITIES[model_lower]

    # Try prefix match
    for key, profile in MODEL_CAPABILITIES.items():
        if model_lower.startswith(key) or key in model_lower:
            return profile

    # Default profile for unknown models
    return {
        "context_window": 4096,
        "tool_following": "moderate",
        "reasoning": "moderate",
        "prompt_style": "concise",
        "supports_json_mode": False,
        "max_tools_per_prompt": 15,
    }
```

#### B. Prompt Template System (NEW: cortex/core/prompts/)

```
cortex/core/prompts/
├── __init__.py
├── base.py              # Base prompt builder
├── templates/
│   ├── system_base.md   # Core system instructions
│   ├── tools_detailed.md    # For high-capability models
│   ├── tools_concise.md     # For medium models
│   ├── tools_explicit.md    # For smaller models
│   ├── planning.md      # Planning-specific guidance
│   └── memory.md        # Memory system guidance
└── adapters/
    ├── claude.py        # Claude-specific optimizations
    ├── gpt.py           # GPT-specific optimizations
    └── ollama.py        # Local model optimizations
```

#### C. Dynamic Prompt Builder (NEW: cortex/core/prompts/base.py)

```python
"""Dynamic prompt builder with model adaptation."""

from pathlib import Path
from typing import List, Dict, Optional
from cortex.core.model_capabilities import get_model_profile

class PromptBuilder:
    """Builds prompts adapted to model capabilities."""

    def __init__(self, model_name: str, project_dir: Path):
        self.model_name = model_name
        self.project_dir = project_dir
        self.profile = get_model_profile(model_name)
        self.template_dir = Path(__file__).parent / "templates"

    def build_system_prompt(
        self,
        tools: List[dict],
        enable_planning: bool = False,
        enable_memory: bool = False,
        state_context: Optional[str] = None
    ) -> str:
        """Build complete system prompt adapted to model."""

        sections = []

        # 1. Base system instructions
        sections.append(self._load_template("system_base.md"))

        # 2. Tool documentation (adapted to model capability)
        tool_section = self._build_tool_section(tools)
        sections.append(tool_section)

        # 3. Planning guidance (if enabled)
        if enable_planning:
            sections.append(self._load_template("planning.md"))

        # 4. Memory guidance (if enabled)
        if enable_memory:
            sections.append(self._load_template("memory.md"))

        # 5. State context (if available)
        if state_context:
            sections.append(f"## Current State\n{state_context}")

        # 6. Model-specific adaptations
        sections.append(self._get_model_specific_guidance())

        return "\n\n---\n\n".join(sections)

    def _build_tool_section(self, tools: List[dict]) -> str:
        """Build tool documentation adapted to model capability."""

        style = self.profile["prompt_style"]
        max_tools = self.profile["max_tools_per_prompt"]

        # Prioritize tools if too many
        if len(tools) > max_tools:
            tools = self._prioritize_tools(tools, max_tools)

        if style == "detailed":
            return self._format_tools_detailed(tools)
        elif style == "concise":
            return self._format_tools_concise(tools)
        else:  # explicit
            return self._format_tools_explicit(tools)

    def _format_tools_detailed(self, tools: List[dict]) -> str:
        """Full documentation with examples for capable models."""
        sections = ["# Available Tools\n"]

        for tool in tools:
            sections.append(f"""
## {tool['name']}

{tool.get('description', 'No description')}

**Parameters:**
{self._format_parameters(tool.get('parameters', {}))}

**Example:**
```json
{self._generate_example(tool)}
```
""")
        return "\n".join(sections)

    def _format_tools_concise(self, tools: List[dict]) -> str:
        """Shorter format for medium models."""
        lines = ["# Tools\n"]
        for tool in tools:
            params = ", ".join(tool.get('parameters', {}).get('required', []))
            lines.append(f"- **{tool['name']}**({params}): {tool.get('description', '')[:100]}")
        return "\n".join(lines)

    def _format_tools_explicit(self, tools: List[dict]) -> str:
        """Very explicit format with step-by-step for smaller models."""
        sections = ["# Tools - READ CAREFULLY\n"]
        sections.append("To use a tool, you MUST format your response EXACTLY like this:\n")
        sections.append("```\n<tool_call>\n<name>tool_name</name>\n<arguments>{\"param\": \"value\"}</arguments>\n</tool_call>\n```\n")

        for tool in tools:
            sections.append(f"""
## {tool['name']}
WHAT IT DOES: {tool.get('description', '')}
REQUIRED: {', '.join(tool.get('parameters', {}).get('required', []))}
EXAMPLE CALL:
<tool_call>
<name>{tool['name']}</name>
<arguments>{self._generate_example(tool)}</arguments>
</tool_call>
""")
        return "\n".join(sections)
```

### 3.3 Tool Visibility Improvements

#### Current Problem
Models don't always "see" or understand available tools because:
1. Tool list is at the end of a long prompt
2. No usage examples
3. No guidance on WHEN to use each tool
4. Parameter descriptions are minimal

#### Solution: Tool Usage Guide Section

```markdown
# TOOL USAGE GUIDE

## Quick Reference - Which Tool for What

| Task | Tool | Example |
|------|------|---------|
| Read a file | `read_file` | `read_file(path="/src/main.py")` |
| Search code | `grep_search` | `grep_search(pattern="def process", path=".")` |
| Find files | `glob_files` | `glob_files(pattern="**/*.py")` |
| Edit file | `edit_file` | `edit_file(path="...", old="...", new="...")` |
| Run command | `bash` | `bash(command="pytest tests/")` |
| Create plan | `create_plan` | `create_plan(goal="Implement auth")` |

## Tool Decision Tree

```
Need to understand code?
├── Know the file? → read_file
├── Know the pattern? → grep_search
└── Know the extension? → glob_files

Need to modify code?
├── Small change? → edit_file
├── New file? → write_file
└── Multiple files? → create_plan first

Need to run something?
├── Tests? → bash(command="pytest")
├── Build? → bash(command="npm run build")
└── Other? → bash(command="...")
```

## Common Mistakes to Avoid

❌ DON'T: Try to edit a file you haven't read
✅ DO: Always read_file first, then edit_file

❌ DON'T: Use bash for file operations
✅ DO: Use read_file, edit_file, write_file

❌ DON'T: Make multiple edits without checking
✅ DO: Read file after edit to verify
```

### 3.4 Implementation Roadmap

```
Phase 1 (Week 1-2): Foundation
├── Create model_capabilities.py
├── Create prompt templates directory
├── Extract prompts from hardcoded strings
└── Add basic PromptBuilder

Phase 2 (Week 3-4): Model Adaptation
├── Add model profile detection
├── Implement 3 prompt styles (detailed/concise/explicit)
├── Add tool prioritization logic
└── Test with different models

Phase 3 (Week 5-6): Tool Visibility
├── Add tool usage guide to prompts
├── Add decision tree guidance
├── Add common mistakes section
└── Generate tool examples automatically

Phase 4 (Week 7-8): Dynamic Context
├── Add state context injection
├── Add task-type detection
├── Add conversation-aware adaptation
└── Performance testing and optimization
```

---

## Part 4: Codebase Quality Fixes

### 4.1 Critical Issues (Fix Immediately)

| Issue | Location | Fix |
|-------|----------|-----|
| Bare except clauses | Multiple files | Add specific exception types |
| Race condition in streaming | `providers.py:380` | Add proper thread synchronization |
| Unvalidated user input | `cli.py:245` | Add input sanitization |
| Missing error handling | `planning.py:execute_plan` | Add try/except with recovery |

### 4.2 Detailed Fixes

#### A. Replace Bare Except Clauses

```python
# BAD (current in multiple files):
try:
    result = some_operation()
except:
    pass

# GOOD:
try:
    result = some_operation()
except (ValueError, KeyError) as e:
    logger.warning(f"Operation failed: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

**Files to fix:**
- `cortex/agent.py`: Lines 312, 445, 567
- `cortex/core/providers.py`: Lines 189, 234
- `cortex/tools/bash_tool.py`: Lines 78, 123
- `cortex/core/planning.py`: Lines 298, 342

#### B. Fix Race Condition in Streaming

```python
# Location: cortex/core/providers.py around line 380

# CURRENT (race condition):
def stream_response(self, ...):
    self.is_streaming = True
    for chunk in response:
        yield chunk
    self.is_streaming = False

# FIXED:
import threading

def stream_response(self, ...):
    with self._streaming_lock:
        self.is_streaming = True
    try:
        for chunk in response:
            yield chunk
    finally:
        with self._streaming_lock:
            self.is_streaming = False
```

#### C. Add Input Sanitization

```python
# Location: cortex/cli.py

def sanitize_input(user_input: str) -> str:
    """Sanitize user input to prevent injection."""
    # Remove null bytes
    user_input = user_input.replace('\x00', '')
    # Limit length
    if len(user_input) > 100000:
        user_input = user_input[:100000]
    # Remove control characters (except newlines)
    user_input = ''.join(
        char for char in user_input
        if char == '\n' or (ord(char) >= 32 and ord(char) < 127) or ord(char) > 127
    )
    return user_input
```

### 4.3 Medium Priority Fixes

| Issue | Location | Description |
|-------|----------|-------------|
| Inconsistent logging | Throughout | Standardize log levels and formats |
| Missing type hints | `planning.py`, `memory_layers.py` | Add comprehensive type hints |
| Duplicate code | Tool executors | Extract common patterns |
| Hard-coded paths | Config loading | Use Path objects consistently |
| Missing docstrings | Many functions | Add comprehensive documentation |

### 4.4 Low Priority (Technical Debt)

- Refactor large functions (>50 lines)
- Add more unit tests (current coverage ~60%)
- Add integration tests for tool chains
- Implement proper dependency injection
- Add configuration validation schema

---

## Part 5: Implementation Priority Matrix

```
                    IMPACT
                    High    │    Medium    │    Low
         ───────────────────┼──────────────┼─────────────
         │ Planning UI     │ Model        │ Docstrings
   High  │ Tool Visibility │ Capabilities │ Code Style
         │ State Manager   │              │
URGENCY  ├─────────────────┼──────────────┼─────────────
         │ Error Handling  │ Prompt       │ Test
  Medium │ Race Condition  │ Templates    │ Coverage
         │                 │              │
         ├─────────────────┼──────────────┼─────────────
         │ Input Sanitize  │ Logging      │ Refactoring
   Low   │                 │ Type Hints   │
         │                 │              │
```

---

## Part 6: Recommended Implementation Order

### Sprint 1 (Week 1-2): Critical Fixes
1. ✅ Fix Planning Engine UI output
2. ✅ Add StateManager to base Cortex
3. ✅ Fix bare except clauses
4. ✅ Fix race condition in streaming

### Sprint 2 (Week 3-4): Prompt Foundation
1. Create model_capabilities.py
2. Extract prompts to templates
3. Implement PromptBuilder
4. Add tool usage guide

### Sprint 3 (Week 5-6): Integration
1. Wire up dynamic prompts
2. Add state context injection
3. Test with multiple models
4. Add model-specific adapters

### Sprint 4 (Week 7-8): Polish
1. Add progress display component
2. Improve plan execution logic
3. Add comprehensive tests
4. Documentation and examples

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Tool usage rate | ~40% | >80% |
| Planning tool adoption | ~5% | >50% |
| Error rate | ~15% | <5% |
| Test coverage | ~60% | >85% |
| User satisfaction | Unknown | Track feedback |

---

## Appendix: File Change Summary

### Files to Create
- `cortex/core/model_capabilities.py`
- `cortex/core/prompts/__init__.py`
- `cortex/core/prompts/base.py`
- `cortex/core/prompts/templates/*.md`
- `cortex/ui/plan_progress.py`

### Files to Modify
- `cortex/agent.py` - Add StateManager
- `cortex/agent_enhanced.py` - Use PromptBuilder
- `cortex/core/planning.py` - Fix execution, add UI
- `cortex/core/providers.py` - Fix race condition
- `cortex/core/memory_layers.py` - Add todo tracking
- `cortex/cli.py` - Add input sanitization
- `cortex/tools/*.py` - Fix error handling

### Tests to Add
- `tests/unit/core/test_prompt_builder.py`
- `tests/unit/core/test_model_capabilities.py`
- `tests/integration/test_planning_ui.py`
- `tests/integration/test_dynamic_prompts.py`
