# Refactoring Plan: Large File Decomposition

**Created**: 2026-02-07
**Status**: Ready for Implementation
**Priority**: High

---

## Executive Summary

This document provides detailed refactoring plans for breaking down two large files in the Cortex codebase:

1. **cortex/agent.py** (~1400 lines) → 5 focused modules
2. **cortex/cli.py** (~1200 lines) → 4 focused modules

**Goals**:
- Improve maintainability and readability
- Enable easier testing of individual components
- Follow Single Responsibility Principle
- Maintain 100% backward compatibility
- Zero changes to public API

**Timeline**: 2-3 days for complete refactoring + testing

---

## Part 1: Refactoring `cortex/agent.py`

### Current State Analysis

**File**: [cortex/agent.py](../cortex/agent.py)
**Lines**: ~1400
**Responsibilities** (too many):
- Agent initialization (100 lines)
- System prompt generation (150 lines)
- Message processing loop (300 lines)
- Tool execution orchestration (200 lines)
- Model switching logic (100 lines)
- Permission handling (150 lines)
- Session management (100 lines)
- Utility methods (300 lines)

**Code Smells**:
- God object (too many responsibilities)
- Long methods (`_process_message` ~200 lines)
- Mixed abstraction levels
- Difficult to test individual components

### Proposed New Structure

```
cortex/
├── agent.py                    # Main Cortex class (orchestrator only, ~300 lines)
├── core/
│   ├── agent_init.py          # Agent initialization & configuration
│   ├── agent_messaging.py     # Message processing logic
│   ├── agent_tools.py         # Tool execution orchestration
│   ├── agent_permissions.py   # Permission system
│   └── agent_prompts.py       # System prompt generation
```

### Detailed Module Breakdown

#### 1. `cortex/agent.py` (New - Orchestrator Only)

**Purpose**: Main agent class - delegates to specialized components
**Size**: ~300 lines
**Responsibilities**:
- High-level conversation loop
- Delegate to specialized managers
- Public API methods
- Backward compatibility wrapper

**Public API** (unchanged):
```python
class Cortex:
    """Main Cortex class - handles conversation loop and tool execution"""

    def __init__(self, model: str, project_dir: str, permission_mode: str,
                 config: Optional[AgentConfig] = None, ...):
        """Initialize agent with all dependencies"""

    # Public methods (keep these exactly as-is for compatibility)
    def run(self, prompt: str) -> None:
        """Main entry point"""

    def switch_model(self, model: str, provider: Optional[str] = None):
        """Switch to a different model"""

    def clear_conversation(self):
        """Clear conversation history"""

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""

    def validate_session_health(self) -> Dict[str, Any]:
        """Validate session health"""

    def request_shutdown(self):
        """Request graceful shutdown"""

    # Internal methods (delegate to components)
    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Delegate to MessageProcessor"""
        return self._message_processor.process(user_message, use_streaming)

    def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Delegate to ToolExecutor"""
        return self._tool_executor.execute_batch(tool_calls)
```

**Implementation**:
```python
# cortex/agent.py (refactored)
from .core.agent_init import AgentInitializer
from .core.agent_messaging import MessageProcessor
from .core.agent_tools import ToolExecutor
from .core.agent_permissions import PermissionManager
from .core.agent_prompts import PromptGenerator

class Cortex:
    """Main Cortex class - orchestrates conversation and tool execution"""

    def __init__(self, model: str = "llama3.2", project_dir: str = ".",
                 permission_mode: str = PermissionMode.NORMAL,
                 config: Optional[AgentConfig] = None,
                 hook_manager: Optional[HookManager] = None,
                 output_format: OutputFormat = OutputFormat.TEXT,
                 on_max_iterations_reached: Optional[Callable] = None):

        # Use AgentInitializer to set up all components
        initializer = AgentInitializer(
            model=model,
            project_dir=project_dir,
            permission_mode=permission_mode,
            config=config,
            hook_manager=hook_manager,
            output_format=output_format
        )

        # Initialize components via delegation
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.config = config or AgentConfig()

        # Component managers (private)
        self._initializer = initializer
        self._prompt_generator = PromptGenerator(self)
        self._permission_manager = PermissionManager(self)
        self._tool_executor = ToolExecutor(self)
        self._message_processor = MessageProcessor(self)

        # Shared state (kept on main class for backward compatibility)
        self.conversation = initializer.conversation
        self.memory_bank = initializer.memory_bank
        self.state_manager = initializer.state_manager
        self.loop_guard = initializer.loop_guard
        self.hook_manager = initializer.hook_manager

        # Callbacks
        self._on_max_iterations_reached = on_max_iterations_reached

    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Process a user message - delegates to MessageProcessor"""
        return self._message_processor.process(user_message, use_streaming)

    def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tool calls - delegates to ToolExecutor"""
        return self._tool_executor.execute_batch(tool_calls)

    def _get_system_prompt(self) -> str:
        """Generate system prompt - delegates to PromptGenerator"""
        return self._prompt_generator.generate()

    def _check_permission(self, tool_name: str, args: Dict) -> bool:
        """Check tool permission - delegates to PermissionManager"""
        return self._permission_manager.check(tool_name, args)
```

---

#### 2. `cortex/core/agent_init.py` (New)

**Purpose**: Agent initialization & dependency setup
**Size**: ~250 lines
**Responsibilities**:
- Initialize all managers (conversation, memory, recovery, etc.)
- Load project context
- Set up providers
- Configure rate limiters

**Key Classes**:
```python
class AgentInitializer:
    """Handles complex agent initialization logic"""

    def __init__(self, model: str, project_dir: str, permission_mode: str,
                 config: AgentConfig, hook_manager: HookManager,
                 output_format: OutputFormat):
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.config = config

        # Initialize all components
        self.conversation = self._init_conversation()
        self.memory_bank = self._init_memory_bank()
        self.state_manager = self._init_state_manager()
        self.loop_guard = self._init_loop_guard()
        self.checkpoint_manager = self._init_checkpoints()
        self.health_monitor = SessionHealthMonitor()
        self.recovery_orchestrator = self._init_recovery()
        self.provider = self._init_provider()
        self.rate_limiter = self._init_rate_limiter()
        self.file_cache = self._init_file_cache()
        self.tool_registry = self._init_tool_registry()

    def _init_conversation(self) -> ConversationManager:
        """Initialize conversation manager with summarization"""
        system_prompt = self._load_project_context()
        summarizer = self._create_summarizer()

        return ConversationManager(
            system_prompt=system_prompt,
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages,
            model=self.model,
            summarizer=summarizer,
            ...
        )

    def _init_memory_bank(self) -> MemoryBank:
        """Initialize memory bank for facts/decisions"""
        return create_memory_bank(max_items=50)

    def _init_loop_guard(self) -> LoopGuard:
        """Initialize loop detection system"""
        recovery_manager = None
        if self.config.error_recovery.get("enable_smart_recovery", False):
            recovery_manager = create_recovery_manager_from_config(
                self.config.error_recovery
            )

        return LoopGuard(
            max_repeats=self.config.error_recovery.get("max_repeats", 3),
            stuck_threshold=self.config.error_recovery.get("stuck_threshold", 5),
            recovery_manager=recovery_manager
        )

    def _load_project_context(self) -> str:
        """Load AGENT.md and create base system prompt"""
        # Extract from current agent.py
        ...
```

---

#### 3. `cortex/core/agent_messaging.py` (New)

**Purpose**: Message processing & conversation loop logic
**Size**: ~400 lines
**Responsibilities**:
- Process user messages
- Call LLM provider
- Handle streaming responses
- Manage conversation flow
- Iteration limits

**Key Classes**:
```python
class MessageProcessor:
    """Handles message processing and conversation flow"""

    def __init__(self, agent: 'Cortex'):
        self.agent = agent
        self.iteration_count = 0

    def process(self, user_message: str, use_streaming: bool = False) -> None:
        """
        Main message processing loop

        Extracted from Cortex._process_message()
        """
        # Add user message to history
        self.agent.conversation.add_message("user", user_message)

        # Trigger hooks
        self._trigger_user_prompt_hook(user_message)

        # Main agent loop
        self.iteration_count = 0
        max_iterations = self.agent.config.max_iterations

        while self.iteration_count < max_iterations:
            self.iteration_count += 1

            # Check for shutdown
            if self.agent._shutdown_requested:
                break

            # Call LLM
            response = self._call_llm(use_streaming)

            # Handle response
            if self._should_stop(response):
                break

            # Execute tools if needed
            if self._has_tool_calls(response):
                tool_results = self.agent._execute_tools(response['tool_calls'])
                self._add_tool_results_to_history(tool_results)
            else:
                # Final response
                self._display_final_response(response)
                break

        # Check if max iterations reached
        if self.iteration_count >= max_iterations:
            self._handle_max_iterations()

    def _call_llm(self, use_streaming: bool = False) -> Dict[str, Any]:
        """Call LLM provider with current conversation"""
        messages = self.agent.conversation.get_messages()
        tools = self._get_available_tools()

        # Apply routing if enabled
        if self.agent._routing_enabled:
            decision = self.agent._routing_orchestrator.route(
                RoutingContext(
                    messages=messages,
                    tools=tools,
                    current_model=self.agent.model
                )
            )
            if decision.should_route:
                self.agent.switch_model(decision.target_model)

        # Call provider
        try:
            if use_streaming:
                return self._call_streaming()
            else:
                return self.agent._provider.chat(
                    model=self.agent.model,
                    messages=messages,
                    tools=tools
                )
        except Exception as e:
            return self._handle_llm_error(e)

    def _call_streaming(self) -> Dict[str, Any]:
        """Handle streaming response"""
        # Extract streaming logic from agent.py
        ...

    def _handle_max_iterations(self):
        """Handle max iterations reached"""
        if self.agent._on_max_iterations_reached:
            additional = self.agent._on_max_iterations_reached(
                self.iteration_count,
                self.agent.config.max_iterations
            )
            if additional:
                self.agent.config.max_iterations += additional
                return  # Continue

        console.print("[yellow]⚠️ Max iterations reached[/yellow]")
```

---

#### 4. `cortex/core/agent_tools.py` (New)

**Purpose**: Tool execution orchestration
**Size**: ~300 lines
**Responsibilities**:
- Execute tool calls
- Handle parallel execution
- Permission checks
- Error handling & recovery
- Hook triggers

**Key Classes**:
```python
class ToolExecutor:
    """Handles tool execution with permissions and error handling"""

    def __init__(self, agent: 'Cortex'):
        self.agent = agent
        self.parallel_executor = self._init_parallel_executor()

    def execute_batch(self, tool_calls: List[Dict]) -> List[Dict]:
        """
        Execute a batch of tool calls with permission checks

        Extracted from Cortex._execute_tools()
        """
        results = []

        # Check for parallel execution
        if self._should_execute_parallel(tool_calls):
            return self._execute_parallel(tool_calls)

        # Sequential execution
        for tool_call in tool_calls:
            result = self.execute_single(tool_call)
            results.append(result)

            # Check for critical errors
            if result.get('error') and self._is_critical_error(result):
                break

        return results

    def execute_single(self, tool_call: Dict) -> Dict:
        """Execute a single tool call"""
        tool_name = tool_call['function']['name']
        args = json.loads(tool_call['function']['arguments'])

        # Pre-execution hook
        hook_result = self._trigger_pre_tool_hook(tool_name, args)
        if hook_result.action == HookAction.BLOCK:
            return self._create_blocked_result(tool_name, hook_result.message)

        # Permission check
        if not self.agent._permission_manager.check(tool_name, args):
            return self._create_permission_denied_result(tool_name)

        # Execute tool
        try:
            tool = self.agent._tool_registry.get_tool(tool_name)
            result = tool.execute(**args)

            # Post-execution hook
            self._trigger_post_tool_hook(tool_name, args, result)

            return self._create_success_result(tool_name, result)

        except Exception as e:
            return self._create_error_result(tool_name, e)

    def _execute_parallel(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tools in parallel"""
        # Convert to ToolCall objects
        calls = [
            ToolCall(
                name=tc['function']['name'],
                arguments=json.loads(tc['function']['arguments']),
                id=tc.get('id', f"call_{i}")
            )
            for i, tc in enumerate(tool_calls)
        ]

        # Execute in parallel
        results = self.parallel_executor.execute(calls)

        return results

    def _should_execute_parallel(self, tool_calls: List[Dict]) -> bool:
        """Determine if tools can be executed in parallel"""
        # Check config
        if not self.agent.config.parallel_execution.get('enabled', False):
            return False

        # Check for dependencies (read-after-write, write-after-write)
        return not self._has_dependencies(tool_calls)
```

---

#### 5. `cortex/core/agent_permissions.py` (New)

**Purpose**: Permission system & user approval
**Size**: ~200 lines
**Responsibilities**:
- Check permissions for tools
- Handle user approval dialogs
- Permission modes (NORMAL, AUTO_APPROVE, PLAN)
- Dangerous operation detection

**Key Classes**:
```python
class PermissionManager:
    """Manages permission checks and user approvals"""

    def __init__(self, agent: 'Cortex'):
        self.agent = agent
        self.approved_operations = set()  # Cache approvals

    def check(self, tool_name: str, args: Dict) -> bool:
        """
        Check if tool execution is permitted

        Extracted from Cortex._check_permission()
        """
        # AUTO_APPROVE mode - always allow
        if self.agent.permission_mode == PermissionMode.AUTO_APPROVE:
            return True

        # PLAN mode - block destructive operations
        if self.agent.permission_mode == PermissionMode.PLAN:
            if self._is_destructive(tool_name):
                console.print(
                    "[yellow]⚠️ Operation blocked in PLAN mode[/yellow]"
                )
                return False
            return True

        # NORMAL mode - ask user for dangerous operations
        if self._is_dangerous(tool_name, args):
            return self._ask_user_approval(tool_name, args)

        return True

    def _is_dangerous(self, tool_name: str, args: Dict) -> bool:
        """Detect dangerous operations"""
        dangerous_tools = {
            'execute_command': self._is_dangerous_command,
            'write_file': self._is_dangerous_write,
            'edit_file': self._is_dangerous_edit,
        }

        checker = dangerous_tools.get(tool_name)
        if checker:
            return checker(args)

        return False

    def _is_dangerous_command(self, args: Dict) -> bool:
        """Check if command is dangerous"""
        command = args.get('command', '')
        dangerous_patterns = ['rm -rf', 'sudo', 'format', 'del /f']
        return any(pattern in command for pattern in dangerous_patterns)

    def _ask_user_approval(self, tool_name: str, args: Dict) -> bool:
        """Prompt user for approval"""
        from rich.prompt import Confirm

        # Check cache
        operation_hash = self._hash_operation(tool_name, args)
        if operation_hash in self.approved_operations:
            return True

        # Show details
        console.print(Panel(
            f"[yellow]Tool:[/yellow] {tool_name}\n"
            f"[yellow]Arguments:[/yellow] {json.dumps(args, indent=2)}",
            title="⚠️ Permission Required",
            border_style="yellow"
        ))

        approved = Confirm.ask("[cyan]Allow this operation?[/cyan]")

        if approved:
            self.approved_operations.add(operation_hash)

        return approved
```

---

#### 6. `cortex/core/agent_prompts.py` (New)

**Purpose**: System prompt generation
**Size**: ~200 lines
**Responsibilities**:
- Generate system prompts
- Include project context
- Add memory bank contents
- Model-specific adaptations

**Key Classes**:
```python
class PromptGenerator:
    """Generates system prompts with context and memory"""

    def __init__(self, agent: 'Cortex'):
        self.agent = agent

    def generate(self) -> str:
        """
        Generate complete system prompt

        Extracted from Cortex._get_system_prompt()
        """
        sections = []

        # Base system prompt
        sections.append(self._get_base_prompt())

        # Project context
        if self.agent.project_context:
            sections.append(self._format_project_context())

        # Memory bank
        if self.agent.memory_bank and self.agent.memory_bank.items:
            sections.append(self._format_memory_bank())

        # State context (if using StateManager)
        if hasattr(self.agent, 'state_manager'):
            state_context = self.agent.state_manager.get_context_for_prompt()
            if state_context:
                sections.append(state_context)

        # Permission mode instructions
        sections.append(self._get_permission_instructions())

        # Model-specific adaptations
        prompt = "\n\n".join(sections)
        return adapt_prompt_for_model(prompt, self.agent.model)

    def _get_base_prompt(self) -> str:
        """Get base system prompt"""
        return """You are Cortex, an AI coding assistant.

Your capabilities:
- Read, write, and edit files
- Execute commands (with user permission)
- Search codebases with glob and grep
- Make git commits
- Run tests
- Web search and fetch

Guidelines:
- Always explain your actions
- Ask for clarification when needed
- Be concise and focused
- Prioritize code quality and safety
"""

    def _format_project_context(self) -> str:
        """Format project context from AGENT.md"""
        return f"""# Project Context

{self.agent.project_context}
"""

    def _format_memory_bank(self) -> str:
        """Format memory bank for prompt"""
        return f"""# Memory Bank (Important Facts)

{self.agent.memory_bank.get_full_display()}
"""

    def _get_permission_instructions(self) -> str:
        """Get permission mode specific instructions"""
        if self.agent.permission_mode == PermissionMode.PLAN:
            return """# PLAN MODE
You are in read-only planning mode. You can:
- Read files and search code
- Analyze and suggest solutions
- Create plans

You CANNOT:
- Write or edit files
- Execute commands
- Make git commits
"""
        elif self.agent.permission_mode == PermissionMode.AUTO_APPROVE:
            return """# AUTO-APPROVE MODE
All operations are auto-approved. Use caution.
"""
        else:
            return """# NORMAL MODE
Dangerous operations require user approval.
"""
```

---

### Migration Strategy

#### Phase 1: Extract Components (Day 1)

1. **Create new module files**:
   ```bash
   touch cortex/core/agent_init.py
   touch cortex/core/agent_messaging.py
   touch cortex/core/agent_tools.py
   touch cortex/core/agent_permissions.py
   touch cortex/core/agent_prompts.py
   ```

2. **Copy relevant code** from `agent.py` to new modules

3. **Add backward compatibility imports** in `agent.py`:
   ```python
   # Maintain backward compatibility - re-export everything
   from .core.agent_init import AgentInitializer
   from .core.agent_messaging import MessageProcessor
   from .core.agent_tools import ToolExecutor
   from .core.agent_permissions import PermissionManager
   from .core.agent_prompts import PromptGenerator
   ```

#### Phase 2: Refactor Main Class (Day 2)

1. **Modify `Cortex.__init__`** to use `AgentInitializer`

2. **Replace method implementations** with delegations:
   ```python
   def _process_message(self, msg, streaming):
       return self._message_processor.process(msg, streaming)
   ```

3. **Keep all public methods unchanged**

#### Phase 3: Testing (Day 2-3)

1. **Unit tests for each new module**:
   ```python
   # tests/unit/core/test_agent_tools.py
   def test_tool_executor_single():
       agent = Mock()
       executor = ToolExecutor(agent)
       result = executor.execute_single({
           'function': {'name': 'read_file', 'arguments': '{"path": "test.py"}'}
       })
       assert result['success']
   ```

2. **Integration tests** to ensure Cortex still works end-to-end

3. **Backward compatibility tests**:
   ```python
   def test_backward_compatibility():
       # Old way still works
       agent = Cortex(model="llama3.2")
       assert hasattr(agent, 'conversation')
       assert hasattr(agent, '_process_message')
   ```

---

## Part 2: Refactoring `cortex/cli.py`

### Current State Analysis

**File**: [cortex/cli.py](../cortex/cli.py)
**Lines**: ~1200
**Responsibilities** (too many):
- CLI argument parsing (100 lines)
- Configuration loading (100 lines)
- Provider validation (60 lines)
- Session management (100 lines)
- Interactive REPL loop (140 lines)
- Command handling (560 lines) ← **Biggest issue**
- Signal handlers (60 lines)

**Code Smell**: The `handle_command()` function is 560 lines with 40+ different commands!

### Proposed New Structure

```
cortex/
├── cli.py                 # Main CLI entry point (~200 lines)
├── cli/
│   ├── __init__.py
│   ├── commands/          # Command handlers (NEW)
│   │   ├── __init__.py
│   │   ├── base.py        # Base command class
│   │   ├── session.py     # /save, /load, /sessions
│   │   ├── model.py       # /model, /profile, /mode
│   │   ├── ui.py          # /ui, /clear
│   │   ├── stats.py       # /stats, /routing, /storage
│   │   ├── memory.py      # /memory, /focus, /thinking
│   │   ├── cache.py       # /cache, /cleanup
│   │   ├── transaction.py # /rollback, /transactions
│   │   ├── recovery.py    # /session validate/repair/rollback/checkpoint
│   │   └── help.py        # /help
│   │
│   ├── parser.py          # Argument parser setup
│   ├── config_loader.py   # Configuration loading
│   └── validators.py      # Provider & setup validation
```

### Detailed Module Breakdown

#### 1. `cortex/cli.py` (Refactored - Main Entry Point)

**Purpose**: CLI entry point - minimal orchestration
**Size**: ~200 lines
**Responsibilities**:
- Parse arguments
- Load configuration
- Create agent
- Start REPL or one-shot mode

**Implementation**:
```python
# cortex/cli.py (refactored)
import sys
from pathlib import Path
from .cli.parser import create_argument_parser
from .cli.config_loader import load_configuration
from .cli.validators import validate_provider_setup
from .cli.commands import CommandRegistry
from .ui.repl import REPL
from .storage.sessions import SessionManager

__version__ = "1.0.0"

def main():
    """Main CLI entry point"""
    # Parse arguments
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle special commands
    if args.list_providers:
        from .cli.validators import list_providers
        list_providers()
        sys.exit(0)

    if args.list_sessions:
        session_manager = SessionManager(Path.home() / ".cortex" / "sessions")
        session_manager.show_sessions()
        sys.exit(0)

    # Load configuration
    config = load_configuration(args)

    # Validate provider setup
    if not validate_provider_setup(config.model, config.provider):
        sys.exit(1)

    # Create agent
    agent = create_agent(config, args)

    # Run
    if args.prompt:
        run_one_shot(agent, args)
    else:
        run_interactive(agent, args)

def create_agent(config: AgentConfig, args) -> Cortex:
    """Create and configure agent"""
    # Extract from current cli.py lines 391-412
    ...

def run_one_shot(agent: Cortex, args):
    """Run one-shot mode"""
    # Extract from current cli.py lines 458-486
    ...

def run_interactive(agent: Cortex, args):
    """Run interactive REPL"""
    from .cli.interactive import InteractiveSession

    session = InteractiveSession(agent, args)
    session.run()
```

---

#### 2. `cortex/cli/commands/` (New - Command System)

**Purpose**: Modular command handlers using Command Pattern
**Size**: ~600 lines total (split across 10 files)

**Base Command Class**:
```python
# cortex/cli/commands/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from rich.console import Console

class Command(ABC):
    """Base class for all CLI commands"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (e.g., 'help', 'model')"""
        pass

    @property
    @abstractmethod
    def aliases(self) -> List[str]:
        """Command aliases (e.g., ['?'] for help)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description for help text"""
        pass

    @abstractmethod
    def execute(self, args: List[str], context: 'CommandContext') -> None:
        """Execute the command"""
        pass

    def help(self) -> str:
        """Detailed help text"""
        return self.description

class CommandContext:
    """Context passed to command handlers"""

    def __init__(self, agent, session_manager, repl, console):
        self.agent = agent
        self.session_manager = session_manager
        self.repl = repl
        self.console = console
```

**Command Registry**:
```python
# cortex/cli/commands/__init__.py
from .base import Command, CommandContext
from .session import SaveCommand, LoadCommand, SessionsCommand
from .model import ModelCommand, ProfileCommand, ModeCommand
from .ui import UICommand, ClearCommand
from .stats import StatsCommand, RoutingCommand, StorageCommand
from .memory import MemoryCommand, FocusCommand, ThinkingCommand
from .cache import CacheCommand, CleanupCommand
from .transaction import RollbackCommand, TransactionsCommand
from .recovery import SessionRecoveryCommand
from .help import HelpCommand

class CommandRegistry:
    """Registry of all available commands"""

    def __init__(self):
        self.commands = {}
        self._register_all_commands()

    def _register_all_commands(self):
        """Register all built-in commands"""
        for cmd_class in [
            HelpCommand, ClearCommand, ModelCommand, ProfileCommand,
            ModeCommand, UICommand, SaveCommand, LoadCommand,
            SessionsCommand, StatsCommand, RoutingCommand,
            MemoryCommand, FocusCommand, ThinkingCommand,
            CacheCommand, CleanupCommand, StorageCommand,
            RollbackCommand, TransactionsCommand, SessionRecoveryCommand
        ]:
            cmd = cmd_class()
            self.commands[cmd.name] = cmd
            for alias in cmd.aliases:
                self.commands[alias] = cmd

    def execute(self, command_str: str, context: CommandContext):
        """Parse and execute a command"""
        parts = command_str.strip().split()
        if not parts or not parts[0].startswith('/'):
            return

        cmd_name = parts[0][1:].lower()  # Remove leading '/'
        args = parts[1:]

        cmd = self.commands.get(cmd_name)
        if cmd:
            cmd.execute(args, context)
        else:
            context.console.print(f"[red]Unknown command: /{cmd_name}[/red]")
            context.console.print("[dim]Type /help for available commands[/dim]")
```

**Example Commands**:

```python
# cortex/cli/commands/model.py
from .base import Command
from ...core.providers import ProviderError

class ModelCommand(Command):
    """Switch to a different model"""

    @property
    def name(self) -> str:
        return "model"

    @property
    def aliases(self) -> List[str]:
        return ["m"]

    @property
    def description(self) -> str:
        return "Switch to a different model"

    def execute(self, args: List[str], context):
        if args:
            new_model = args[0]
            try:
                context.agent.switch_model(new_model, context.agent.config.provider)
                context.console.print(f"[green]✓[/green] Model switched to: {new_model}")
                # Update system prompt
                context.agent.conversation.history[0]["content"] = \
                    context.agent._get_system_prompt()
            except ProviderError as e:
                context.console.print(f"[red]Error switching model:[/red] {e}")
        else:
            context.console.print(f"Current model: {context.agent.model}")
            context.console.print("[dim]Usage: /model <model_name>[/dim]")

    def help(self) -> str:
        return """Switch to a different LLM model.

Usage:
  /model <model_name>    Switch to specified model
  /model                 Show current model

Examples:
  /model llama3.2        Switch to Llama 3.2 (Ollama)
  /model deepseek-chat   Switch to DeepSeek Chat
  /model claude-3-5-sonnet  Switch to Claude
"""


# cortex/cli/commands/stats.py
class StatsCommand(Command):
    """Display session statistics"""

    @property
    def name(self) -> str:
        return "stats"

    @property
    def aliases(self) -> List[str]:
        return []

    @property
    def description(self) -> str:
        return "Display session statistics"

    def execute(self, args: List[str], context):
        from rich.table import Table

        stats = context.agent.conversation.get_truncation_stats()

        table = Table(title="Session Statistics", show_header=True,
                     header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        # Token statistics
        table.add_row("Current Tokens", f"{stats['current_token_count']:,}")
        table.add_row("Max Tokens", f"{stats['max_tokens']:,}")
        table.add_row("Utilization", f"{stats['token_utilization']:.1f}%")
        table.add_row("Remaining", f"{stats['tokens_remaining']:,}")
        table.add_row("", "")

        # Message statistics
        table.add_row("Messages", str(stats['current_message_count']))
        table.add_row("Avg Tokens/Msg", f"{stats['avg_tokens_per_message']:.0f}")
        table.add_row("", "")

        # Optimization statistics
        table.add_row("Truncations", str(stats['truncation_count']))
        table.add_row("Summarizations", str(stats['summarization_count']))
        table.add_row("Messages Removed", str(stats['total_messages_removed']))

        context.console.print(table)


# cortex/cli/commands/recovery.py
class SessionRecoveryCommand(Command):
    """Session recovery and health management"""

    @property
    def name(self) -> str:
        return "session"

    @property
    def aliases(self) -> List[str]:
        return []

    @property
    def description(self) -> str:
        return "Session recovery and health management"

    def execute(self, args: List[str], context):
        if not args:
            self._show_help(context.console)
            return

        subcommand = args[0]

        if subcommand == "validate":
            self._validate(context)
        elif subcommand == "repair":
            self._repair(context, args[1:])
        elif subcommand == "rollback":
            self._rollback(context, args[1:])
        elif subcommand == "checkpoint":
            self._checkpoint(context)
        else:
            self._show_help(context.console)

    def _validate(self, context):
        """Validate session health"""
        context.console.print("[cyan]🔍 Validating session health...[/cyan]")
        health_report = context.agent.validate_session_health()

        if health_report["healthy"]:
            context.console.print("[green]✅ Session is healthy[/green]")
        else:
            context.console.print("[red]❌ Session has issues[/red]")

        # Display issues
        if health_report.get("issues"):
            context.console.print("\n[bold]Issues Found:[/bold]")
            for issue in health_report["issues"]:
                severity_color = {
                    "critical": "red",
                    "warning": "yellow",
                    "info": "blue"
                }.get(issue.get("severity", "info"), "white")
                context.console.print(
                    f"  [{severity_color}]• {issue['message']}[/{severity_color}]"
                )

        # Display recommendations
        if health_report.get("recommendations"):
            context.console.print("\n[bold]Recommendations:[/bold]")
            for rec in health_report["recommendations"]:
                context.console.print(f"  [cyan]• {rec}[/cyan]")

    def _repair(self, context, args):
        """Attempt session repair"""
        # Extract from current cli.py lines 1096-1127
        ...

    def help(self) -> str:
        return """Session recovery and health management.

Subcommands:
  validate   Check session health
  repair     Attempt automatic repair
  rollback   Rollback to checkpoint
  checkpoint Create manual checkpoint

Examples:
  /session validate
  /session repair
  /session rollback cp_123
  /session checkpoint
"""
```

---

#### 3. `cortex/cli/parser.py` (New)

**Purpose**: Argument parser configuration
**Size**: ~150 lines
**Responsibilities**:
- Define CLI arguments
- Set up argument groups
- Configure help text

```python
# cortex/cli/parser.py
import argparse

def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        description="Cortex - A unified agent for coding, cybersecurity, and personal assistance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_get_examples_text()
    )

    # Version
    from cortex import __version__
    parser.add_argument("--version", action="version",
                       version=f"Cortex {__version__}")

    # Model selection
    model_group = parser.add_argument_group("Model Selection")
    model_group.add_argument("--model", "-m", default=None,
                            help="Model to use (auto-detects provider)")
    model_group.add_argument("--provider",
                            choices=["ollama", "deepseek", "anthropic", "openrouter"],
                            help="Override provider auto-detection")
    model_group.add_argument("--list-providers", action="store_true",
                            help="List available providers and models")

    # Operation modes
    mode_group = parser.add_argument_group("Operation Modes")
    mode_group.add_argument("--auto-approve", action="store_true",
                           help="Auto-approve all actions (dangerous!)")
    mode_group.add_argument("--plan-mode", action="store_true",
                           help="Start in plan mode (read-only)")
    mode_group.add_argument("--enhanced", action="store_true",
                           help="Use enhanced agent with planning")
    mode_group.add_argument("--routing", action="store_true",
                           help="Enable intelligent model routing")

    # Input/Output
    io_group = parser.add_argument_group("Input/Output")
    io_group.add_argument("--prompt", "-p", help="One-shot prompt")
    io_group.add_argument("--output-format", "-o",
                         choices=["text", "json", "stream-json"],
                         help="Output format")
    io_group.add_argument("--ui-mode",
                         choices=["minimal", "normal", "debug"],
                         help="UI display mode")

    # Configuration
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument("--config", "-c", type=str,
                             help="Path to configuration file (YAML)")
    config_group.add_argument("--project-dir", type=str,
                             help="Project directory (default: current)")

    # Session management
    session_group = parser.add_argument_group("Session Management")
    session_group.add_argument("--save-session", type=str,
                              help="Save session with given name")
    session_group.add_argument("--load-session", type=str,
                              help="Load a saved session")
    session_group.add_argument("--list-sessions", action="store_true",
                              help="List all saved sessions")

    # Advanced features
    advanced_group = parser.add_argument_group("Advanced")
    advanced_group.add_argument("--streaming", action="store_true",
                               help="Use streaming responses (experimental)")
    advanced_group.add_argument("--async", dest="use_async",
                               action="store_true",
                               help="Use async execution (experimental)")
    advanced_group.add_argument("--no-hooks", action="store_true",
                               help="Disable hook system")
    advanced_group.add_argument("--hooks-config", type=str,
                               help="Path to hooks configuration file")

    return parser

def _get_examples_text() -> str:
    """Get examples text for help"""
    return """
Examples:
  cortex                              # Start interactive session
  cortex --model llama3.3:70b         # Use different model
  cortex --auto-approve               # Skip permissions (dangerous!)
  cortex -p "your task"               # One-shot mode
  cortex --config config.yaml         # Use config file
  cortex --save-session mywork        # Save session
  cortex --load-session mywork        # Load session
  cortex -o json -p "list files"      # JSON output for scripting
  cortex --hooks-config hooks.yaml    # Custom hooks config
  cortex --no-hooks                   # Disable hook system
"""
```

---

#### 4. `cortex/cli/config_loader.py` (New)

**Purpose**: Configuration loading & merging
**Size**: ~100 lines

```python
# cortex/cli/config_loader.py
from pathlib import Path
from typing import Optional
from ..config import AgentConfig
from rich.console import Console

console = Console()

def load_configuration(args) -> AgentConfig:
    """
    Load configuration from multiple sources with priority

    Priority (lowest to highest):
    1. Default values in code
    2. config/default.yaml
    3. ~/.cortex/config.yaml
    4. --config file.yaml
    5. Environment variables
    6. CLI arguments
    """
    # Try default config first
    config_path = None
    if args.config:
        config_path = Path(args.config)
    else:
        # Auto-load config/default.yaml if it exists
        default_config = Path(__file__).parent.parent.parent / "config" / "default.yaml"
        if default_config.exists():
            config_path = default_config

    # Load base config
    if config_path:
        config = AgentConfig.load(config_path)
        console.print(f"[dim]Loaded config from {config_path}[/dim]")
    else:
        config = AgentConfig()

    # Override with CLI arguments
    apply_cli_overrides(config, args)

    # Apply routing configuration
    if args.routing:
        configure_routing(config, args)

    return config

def apply_cli_overrides(config: AgentConfig, args):
    """Apply CLI argument overrides to config"""
    if args.model:
        config.model = args.model

    if args.provider:
        config.provider = args.provider

    if args.output_format:
        config.output_format = args.output_format

def configure_routing(config: AgentConfig, args):
    """Configure intelligent routing"""
    config.routing["enabled"] = True

    # Enable self-orchestration
    if not hasattr(config, "orchestration"):
        config.orchestration = {}
    config.orchestration["enabled"] = True

    # Set default coordinator model if needed
    if not args.model:
        config.model = "xiaomi/mimo-v2-flash:free"
        config.provider = "openrouter"
        console.print(
            "[cyan]Model orchestration enabled - "
            "using xiaomi/mimo-v2-flash:free as coordinator[/cyan]"
        )
    else:
        console.print("[cyan]Model orchestration enabled (self-switching models)[/cyan]")
```

---

#### 5. `cortex/cli/interactive.py` (New)

**Purpose**: Interactive REPL session management
**Size**: ~200 lines

```python
# cortex/cli/interactive.py
import sys
import signal
from pathlib import Path
from datetime import datetime
from rich.prompt import Confirm
from ..ui.repl import REPL
from ..storage.history import get_history_file
from .commands import CommandRegistry, CommandContext

class InteractiveSession:
    """Manages interactive REPL session"""

    def __init__(self, agent, args):
        self.agent = agent
        self.args = args
        self.session_manager = SessionManager(Path.home() / ".cortex" / "sessions")

        # Set up REPL
        history_file = get_history_file(Path.home())
        self.repl = REPL(str(history_file))

        # Command registry
        self.commands = CommandRegistry()
        self.command_context = CommandContext(
            agent=agent,
            session_manager=self.session_manager,
            repl=self.repl,
            console=console
        )

        # Set up callbacks
        self._setup_callbacks()

        # Register signal handlers
        self._setup_signal_handlers()

    def run(self):
        """Run interactive session"""
        # Show banner
        self.repl.show_banner(
            project_name=self.agent.project_dir.name,
            model=self.agent.model,
            permission_mode=self.agent.permission_mode,
        )

        # Main loop
        while True:
            try:
                if self.agent._shutdown_requested:
                    break

                # Get user input
                user_input = self.repl.prompt("\n> ")

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    self.commands.execute(user_input, self.command_context)
                    continue

                # Process with agent
                self._process_message(user_input)

            except KeyboardInterrupt:
                if self._confirm_exit():
                    break
            except EOFError:
                self.agent.request_shutdown()
                self.agent._cleanup()
                break

    def _process_message(self, user_input: str):
        """Process user message with agent"""
        if self.args.use_async:
            self._process_async(user_input)
        else:
            self._process_sync(user_input)

    def _process_sync(self, user_input: str):
        """Synchronous message processing"""
        if hasattr(self.agent, 'process_with_planning'):
            self.agent.process_with_planning(
                user_input,
                use_streaming=self.args.streaming
            )
        else:
            self.agent._process_message(
                user_input,
                use_streaming=self.args.streaming
            )

    def _confirm_exit(self) -> bool:
        """Confirm exit and optionally save session"""
        if not Confirm.ask("\n[yellow]Exit Cortex?[/yellow]"):
            return False

        self.agent.request_shutdown()
        self.agent._cleanup()

        # Auto-save if dirty
        if self.agent._session_dirty:
            self._auto_save_session()

        console.print("[cyan]👋 Goodbye![/cyan]")
        return True
```

---

### Migration Strategy for CLI

#### Phase 1: Extract Command System (Day 1)

1. **Create command module structure**:
   ```bash
   mkdir -p cortex/cli/commands
   touch cortex/cli/commands/{__init__,base,session,model,ui,stats,memory,cache,transaction,recovery,help}.py
   ```

2. **Implement base command class** and registry

3. **Extract each command** from `handle_command()` into separate files

4. **Test each command individually**

#### Phase 2: Extract Support Modules (Day 1)

1. **Create** `parser.py`, `config_loader.py`, `validators.py`

2. **Move code** from `main()` to appropriate modules

3. **Test configuration loading**

#### Phase 3: Refactor Main CLI (Day 2)

1. **Simplify** `cli.py` to use new modules

2. **Replace** `handle_command()` with `CommandRegistry.execute()`

3. **Test end-to-end**

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/core/test_agent_tools.py
def test_tool_executor_permission_denied():
    """Test that permission denied blocks execution"""
    agent = Mock()
    agent.permission_mode = PermissionMode.PLAN
    agent._permission_manager = PermissionManager(agent)

    executor = ToolExecutor(agent)
    result = executor.execute_single({
        'function': {
            'name': 'execute_command',
            'arguments': '{"command": "rm -rf /"}'
        }
    })

    assert not result['success']
    assert 'permission' in result['error'].lower()

# tests/unit/cli/commands/test_model_command.py
def test_model_command_switch():
    """Test model switching command"""
    agent = Mock()
    context = CommandContext(agent=agent, console=Mock(), ...)

    cmd = ModelCommand()
    cmd.execute(['deepseek-chat'], context)

    agent.switch_model.assert_called_once_with('deepseek-chat', agent.config.provider)
```

### Integration Tests

```python
# tests/integration/test_refactored_agent.py
def test_full_conversation_flow():
    """Test that refactored agent works end-to-end"""
    agent = Cortex(model="llama3.2")

    # Simulate conversation
    agent._process_message("What files are in the current directory?")

    # Verify conversation was added
    assert len(agent.conversation.history) > 1

    # Verify tool was executed
    assert any('read_file' in str(msg) for msg in agent.conversation.history)
```

### Backward Compatibility Tests

```python
# tests/compatibility/test_public_api.py
def test_backward_compatible_imports():
    """Ensure old imports still work"""
    from cortex.agent import Cortex
    from cortex.cli import main

    # Should not raise ImportError
    assert Cortex is not None
    assert main is not None

def test_backward_compatible_initialization():
    """Ensure old initialization still works"""
    # Old way
    agent = Cortex(
        model="llama3.2",
        project_dir=".",
        permission_mode="normal"
    )

    # Should have all expected attributes
    assert hasattr(agent, 'conversation')
    assert hasattr(agent, 'memory_bank')
    assert hasattr(agent, '_process_message')
```

---

## Benefits Summary

### Maintainability
- ✅ Each module has single responsibility
- ✅ Easier to find and modify code
- ✅ Reduced cognitive load

### Testability
- ✅ Unit test individual components
- ✅ Mock dependencies easily
- ✅ Faster test execution

### Extensibility
- ✅ Add new commands by creating new file
- ✅ Override components via dependency injection
- ✅ Plugin system easier to implement

### Code Quality
- ✅ Reduced duplication
- ✅ Better type hints
- ✅ Clearer interfaces

---

## Risks & Mitigations

### Risk 1: Breaking Backward Compatibility
**Mitigation**:
- Keep all public methods on Cortex class
- Re-export from new modules
- Comprehensive compatibility test suite

### Risk 2: Import Cycles
**Mitigation**:
- Use protocol/ABC for type hints
- Import at function level if needed
- Clear dependency graph

### Risk 3: Performance Regression
**Mitigation**:
- Benchmark before/after
- Profile hot paths
- Lazy loading where appropriate

---

## Success Criteria

- ✅ All existing tests pass
- ✅ No changes to public API
- ✅ Code coverage maintained or improved
- ✅ No performance regression (±5%)
- ✅ Documentation updated
- ✅ Type hints at 90%+

---

## Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Day 1** | 8 hours | Extract agent components, create command system |
| **Day 2** | 8 hours | Refactor main classes, write unit tests |
| **Day 3** | 4 hours | Integration testing, documentation |

**Total**: 2-3 days

---

## Next Steps

1. **Review this plan** with team
2. **Create feature branch**: `refactor/decompose-large-files`
3. **Start with agent.py** (higher priority)
4. **Then cli.py**
5. **Update documentation**
6. **Create PR** with before/after metrics

---

**Document Status**: Ready for Review
**Last Updated**: 2026-02-07
