# Phase 2: Advanced Features Specifications

## Overview

This document contains detailed specifications for advanced features that bring Cortex closer to Claude Code functionality.

---

## 2.1 Typed Subagents System

### Purpose

Create specialized subagents with different capabilities, tool access, and system prompts. Each agent type is optimized for specific tasks.

### Architecture

```
cortex/subagent/
├── __init__.py
├── base.py              # BaseSubagent class
├── types.py             # SubagentType enum and configs
├── explore_agent.py     # Fast codebase exploration
├── plan_agent.py        # Architecture planning
├── bash_agent.py        # Command execution specialist
├── manager.py           # Subagent orchestration
└── context.py           # Context isolation (existing)
```

### Subagent Type Definitions

```python
# cortex/subagent/types.py

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Set, Optional


class SubagentType(Enum):
    """Available subagent types"""
    EXPLORE = "explore"           # Fast codebase exploration
    PLAN = "plan"                 # Architecture planning
    BASH = "bash"                 # Command execution
    GENERAL = "general"           # General purpose (default)


@dataclass
class SubagentConfig:
    """Configuration for a subagent type"""
    type: SubagentType
    name: str
    description: str

    # Tool access control
    allowed_tools: Set[str]
    denied_tools: Set[str] = field(default_factory=set)

    # Resource limits
    max_iterations: int = 10
    max_tokens: int = 50000
    timeout_seconds: int = 300

    # Behavior
    can_write_files: bool = True
    can_execute_commands: bool = True
    can_spawn_subagents: bool = False

    # Model selection (optional override)
    preferred_model: Optional[str] = None
    model_tier: str = "default"  # default, fast, powerful


# Predefined configurations
SUBAGENT_CONFIGS = {
    SubagentType.EXPLORE: SubagentConfig(
        type=SubagentType.EXPLORE,
        name="Explore Agent",
        description="Fast agent specialized for exploring codebases. "
                    "Use for finding files, searching code, understanding structure.",
        allowed_tools={
            "read_file", "list_files", "search_files",
            "git_status", "git_log", "git_diff"
        },
        denied_tools={"write_file", "execute_command"},
        max_iterations=15,
        max_tokens=30000,
        timeout_seconds=120,
        can_write_files=False,
        can_execute_commands=False,
        can_spawn_subagents=False,
        model_tier="fast"  # Use faster model for exploration
    ),

    SubagentType.PLAN: SubagentConfig(
        type=SubagentType.PLAN,
        name="Plan Agent",
        description="Software architect agent for designing implementation plans. "
                    "Returns step-by-step plans, identifies critical files.",
        allowed_tools={
            "read_file", "list_files", "search_files",
            "git_status", "git_log", "git_diff"
        },
        denied_tools={"write_file", "execute_command"},
        max_iterations=20,
        max_tokens=50000,
        timeout_seconds=300,
        can_write_files=False,
        can_execute_commands=False,
        can_spawn_subagents=False,
        model_tier="powerful"  # Use more capable model for planning
    ),

    SubagentType.BASH: SubagentConfig(
        type=SubagentType.BASH,
        name="Bash Agent",
        description="Command execution specialist for running bash commands. "
                    "Use for git operations, builds, package management.",
        allowed_tools={
            "execute_command", "read_file", "list_files",
            "git_status", "git_diff", "git_commit", "git_log"
        },
        denied_tools={"write_file"},  # Prefer commands over direct file writes
        max_iterations=10,
        max_tokens=20000,
        timeout_seconds=600,  # Longer timeout for builds
        can_write_files=False,
        can_execute_commands=True,
        can_spawn_subagents=False,
        model_tier="fast"
    ),

    SubagentType.GENERAL: SubagentConfig(
        type=SubagentType.GENERAL,
        name="General Agent",
        description="General-purpose agent for complex, multi-step tasks. "
                    "Has access to all tools.",
        allowed_tools={"*"},  # All tools
        denied_tools=set(),
        max_iterations=20,
        max_tokens=100000,
        timeout_seconds=600,
        can_write_files=True,
        can_execute_commands=True,
        can_spawn_subagents=True,
        model_tier="default"
    ),
}
```

### Base Subagent Class

```python
# cortex/subagent/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass
from datetime import datetime
import uuid

from .types import SubagentConfig, SubagentType
from ..core.conversation import ConversationManager
from ..core.providers import ModelProvider


@dataclass
class SubagentResult:
    """Result from a subagent execution"""
    agent_id: str
    agent_type: SubagentType
    success: bool
    result: str
    tool_calls_made: int
    tokens_used: int
    duration_ms: float
    error: Optional[str] = None


class BaseSubagent(ABC):
    """Base class for all subagents"""

    def __init__(
        self,
        config: SubagentConfig,
        provider: ModelProvider,
        project_dir: str,
        parent_context: Optional[List[Dict[str, Any]]] = None
    ):
        self.agent_id = str(uuid.uuid4())[:8]
        self.config = config
        self.provider = provider
        self.project_dir = project_dir
        self.parent_context = parent_context or []

        # Initialize conversation with subagent-specific prompt
        self.conversation = ConversationManager(
            system_prompt=self._get_system_prompt(),
            max_tokens=config.max_tokens,
            keep_recent=10,
            model=self._get_model()
        )

        # Inject parent context if provided
        if parent_context:
            self._inject_context(parent_context)

        # Tracking
        self.tool_calls_made = 0
        self.start_time: Optional[datetime] = None

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this subagent type"""
        pass

    def _get_model(self) -> str:
        """Get the model to use based on config"""
        if self.config.preferred_model:
            return self.config.preferred_model

        # Map tier to model (configurable)
        tier_models = {
            "fast": "llama3.2",        # Fast, local
            "default": "llama3.3:70b",  # Balanced
            "powerful": "deepseek-chat" # Most capable
        }
        return tier_models.get(self.config.model_tier, "llama3.2")

    def _inject_context(self, context: List[Dict[str, Any]]) -> None:
        """Inject relevant context from parent conversation"""
        # Summarize parent context
        context_summary = self._summarize_context(context)
        if context_summary:
            self.conversation.add_user_message(
                f"[Parent Context]\n{context_summary}"
            )

    def _summarize_context(self, context: List[Dict[str, Any]]) -> str:
        """Summarize parent context for injection"""
        # Extract key information
        summaries = []

        for msg in context[-10:]:  # Last 10 messages
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and content:
                summaries.append(f"User asked: {content[:200]}...")
            elif role == "assistant" and content:
                summaries.append(f"Previous response: {content[:200]}...")

        return "\n".join(summaries) if summaries else ""

    def _filter_tools(self, all_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter tools based on subagent config"""
        if "*" in self.config.allowed_tools:
            # All tools except denied
            return [
                t for t in all_tools
                if t["function"]["name"] not in self.config.denied_tools
            ]

        # Only allowed tools
        return [
            t for t in all_tools
            if t["function"]["name"] in self.config.allowed_tools
            and t["function"]["name"] not in self.config.denied_tools
        ]

    def execute(self, task: str) -> SubagentResult:
        """Execute the subagent task"""
        self.start_time = datetime.now()

        try:
            result = self._run_agent_loop(task)

            duration = (datetime.now() - self.start_time).total_seconds() * 1000

            return SubagentResult(
                agent_id=self.agent_id,
                agent_type=self.config.type,
                success=True,
                result=result,
                tool_calls_made=self.tool_calls_made,
                tokens_used=self.conversation.get_token_count(),
                duration_ms=duration
            )

        except Exception as e:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000

            return SubagentResult(
                agent_id=self.agent_id,
                agent_type=self.config.type,
                success=False,
                result="",
                tool_calls_made=self.tool_calls_made,
                tokens_used=self.conversation.get_token_count(),
                duration_ms=duration,
                error=str(e)
            )

    @abstractmethod
    def _run_agent_loop(self, task: str) -> str:
        """Run the agent loop - implemented by subclasses"""
        pass
```

### Explore Agent

```python
# cortex/subagent/explore_agent.py

from .base import BaseSubagent
from .types import SUBAGENT_CONFIGS, SubagentType


class ExploreAgent(BaseSubagent):
    """
    Fast agent specialized for codebase exploration.

    Capabilities:
    - Find files by patterns
    - Search code for keywords
    - Read and analyze files
    - Understand project structure

    Restrictions:
    - Cannot write files
    - Cannot execute commands
    - Limited iterations (fast turnaround)
    """

    def __init__(self, provider, project_dir, parent_context=None, thoroughness="medium"):
        config = SUBAGENT_CONFIGS[SubagentType.EXPLORE]

        # Adjust based on thoroughness
        if thoroughness == "quick":
            config.max_iterations = 5
            config.max_tokens = 15000
        elif thoroughness == "very thorough":
            config.max_iterations = 25
            config.max_tokens = 50000

        super().__init__(config, provider, project_dir, parent_context)
        self.thoroughness = thoroughness

    def _get_system_prompt(self) -> str:
        return f"""You are an Explore Agent - a fast, focused assistant for codebase exploration.

## Your Role
You help users quickly find and understand code in their project.

## Capabilities
- Read files (read_file)
- List files with glob patterns (list_files)
- Search for text across files (search_files)
- View git status and history (git_status, git_log, git_diff)

## Restrictions
- You CANNOT write or modify files
- You CANNOT execute shell commands
- You should complete exploration within {self.config.max_iterations} iterations

## Working Directory
{self.project_dir}

## Thoroughness Level: {self.thoroughness}
{"Quick scan - find obvious matches fast" if self.thoroughness == "quick" else
 "Medium exploration - check multiple locations" if self.thoroughness == "medium" else
 "Very thorough - comprehensive search across all naming conventions"}

## Guidelines
1. Start with broad searches, then narrow down
2. Use glob patterns effectively (e.g., **/*.py, src/**/*.ts)
3. When searching, try multiple keyword variations
4. Summarize findings clearly at the end
5. Report file paths with line numbers when relevant

When you have found what you're looking for, provide a clear summary and stop."""

    def _run_agent_loop(self, task: str) -> str:
        """Run exploration loop"""
        self.conversation.add_user_message(task)

        for iteration in range(self.config.max_iterations):
            # Get model response
            messages = self.conversation.get_history()
            tools = self._filter_tools(self._get_all_tools())

            response = self.provider.chat(
                model=self._get_model(),
                messages=messages,
                tools=tools
            )

            message = response["message"]
            self.conversation.add_assistant_message(
                content=message.get("content", ""),
                tool_calls=message.get("tool_calls")
            )

            # Handle tool calls
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    self.tool_calls_made += 1
                    result = self._execute_tool(tool_call)
                    self.conversation.add_tool_result(
                        tool_call.get("id", f"call_{iteration}"),
                        result
                    )
            else:
                # No tool calls - exploration complete
                return message.get("content", "Exploration complete.")

        return "Reached maximum iterations for exploration."

    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """Execute a tool within exploration restrictions"""
        # Implementation uses existing tool system
        # but filtered to only allowed tools
        pass

    def _get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools"""
        from ..tools import TOOLS
        return TOOLS
```

### Plan Agent

```python
# cortex/subagent/plan_agent.py

from .base import BaseSubagent
from .types import SUBAGENT_CONFIGS, SubagentType


class PlanAgent(BaseSubagent):
    """
    Software architect agent for designing implementation plans.

    Capabilities:
    - Explore codebase to understand architecture
    - Analyze existing patterns and conventions
    - Create detailed implementation plans
    - Identify risks and dependencies

    Output:
    - Step-by-step implementation plan
    - Files to create/modify
    - Potential risks and mitigations
    """

    def __init__(self, provider, project_dir, parent_context=None):
        config = SUBAGENT_CONFIGS[SubagentType.PLAN]
        super().__init__(config, provider, project_dir, parent_context)

    def _get_system_prompt(self) -> str:
        return f"""You are a Plan Agent - a software architect that designs implementation plans.

## Your Role
You analyze codebases and create detailed implementation plans for features and changes.

## Capabilities
- Read files to understand existing code
- Search for patterns and conventions
- Analyze project structure
- View git history for context

## Restrictions
- You CANNOT write files (planning only)
- You CANNOT execute commands
- Your output should be a comprehensive plan

## Working Directory
{self.project_dir}

## Planning Process
1. **Understand the Request**: Clarify what needs to be built
2. **Explore the Codebase**: Find relevant existing code
3. **Identify Patterns**: Note conventions and patterns used
4. **Design the Solution**: Create implementation approach
5. **Document the Plan**: Output structured plan

## Plan Output Format
Your final output MUST include:

### Summary
Brief description of the implementation

### Files to Create
- path/to/new/file.py - Description of purpose

### Files to Modify
- path/to/existing/file.py - What changes needed

### Implementation Steps
1. Step one with details
2. Step two with details
...

### Dependencies
- External packages needed
- Internal modules to import

### Risks and Mitigations
- Risk 1: Description -> Mitigation
- Risk 2: Description -> Mitigation

### Testing Approach
- How to test this implementation

When your plan is complete, present it clearly and stop."""

    def _run_agent_loop(self, task: str) -> str:
        """Run planning loop"""
        # Add structured planning prompt
        planning_prompt = f"""Please create an implementation plan for the following task:

{task}

Follow the planning process:
1. First, explore the codebase to understand the current architecture
2. Identify relevant files and patterns
3. Design a solution that fits the existing codebase
4. Document your plan in the required format"""

        self.conversation.add_user_message(planning_prompt)

        # Run planning loop
        for iteration in range(self.config.max_iterations):
            messages = self.conversation.get_history()
            tools = self._filter_tools(self._get_all_tools())

            response = self.provider.chat(
                model=self._get_model(),
                messages=messages,
                tools=tools
            )

            message = response["message"]
            self.conversation.add_assistant_message(
                content=message.get("content", ""),
                tool_calls=message.get("tool_calls")
            )

            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    self.tool_calls_made += 1
                    result = self._execute_tool(tool_call)
                    self.conversation.add_tool_result(
                        tool_call.get("id", f"call_{iteration}"),
                        result
                    )
            else:
                # Planning complete
                return message.get("content", "Plan complete.")

        return "Reached maximum iterations for planning."
```

### Subagent Manager

```python
# cortex/subagent/manager.py

from typing import Dict, Any, Optional, List
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass

from .types import SubagentType, SUBAGENT_CONFIGS
from .base import SubagentResult
from .explore_agent import ExploreAgent
from .plan_agent import PlanAgent
from .bash_agent import BashAgent


@dataclass
class RunningSubagent:
    """Tracks a running subagent"""
    agent_id: str
    agent_type: SubagentType
    future: Future
    started_at: datetime
    task: str


class SubagentManager:
    """
    Manages subagent lifecycle and execution.

    Features:
    - Spawn subagents of different types
    - Run subagents in background
    - Track running subagents
    - Retrieve results
    """

    def __init__(self, provider, project_dir: str, max_concurrent: int = 3):
        self.provider = provider
        self.project_dir = project_dir
        self.max_concurrent = max_concurrent

        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._running: Dict[str, RunningSubagent] = {}
        self._results: Dict[str, SubagentResult] = {}
        self._lock = threading.Lock()

    def spawn(
        self,
        agent_type: SubagentType,
        task: str,
        parent_context: Optional[List[Dict[str, Any]]] = None,
        run_in_background: bool = False,
        **kwargs
    ) -> Union[SubagentResult, str]:
        """
        Spawn a subagent.

        Args:
            agent_type: Type of agent to spawn
            task: Task description
            parent_context: Context from parent conversation
            run_in_background: If True, returns agent_id immediately
            **kwargs: Additional arguments for specific agent types

        Returns:
            SubagentResult if synchronous, agent_id if background
        """
        # Create agent instance
        agent = self._create_agent(agent_type, parent_context, **kwargs)

        if run_in_background:
            return self._run_background(agent, task)
        else:
            return agent.execute(task)

    def _create_agent(
        self,
        agent_type: SubagentType,
        parent_context: Optional[List[Dict[str, Any]]],
        **kwargs
    ):
        """Create agent instance based on type"""
        agent_classes = {
            SubagentType.EXPLORE: ExploreAgent,
            SubagentType.PLAN: PlanAgent,
            SubagentType.BASH: BashAgent,
        }

        agent_class = agent_classes.get(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return agent_class(
            provider=self.provider,
            project_dir=self.project_dir,
            parent_context=parent_context,
            **kwargs
        )

    def _run_background(self, agent, task: str) -> str:
        """Run agent in background, return agent_id"""
        def _execute():
            result = agent.execute(task)
            with self._lock:
                self._results[agent.agent_id] = result
                if agent.agent_id in self._running:
                    del self._running[agent.agent_id]
            return result

        future = self._executor.submit(_execute)

        with self._lock:
            self._running[agent.agent_id] = RunningSubagent(
                agent_id=agent.agent_id,
                agent_type=agent.config.type,
                future=future,
                started_at=datetime.now(),
                task=task
            )

        return agent.agent_id

    def get_result(self, agent_id: str, block: bool = True, timeout: float = 30.0) -> Optional[SubagentResult]:
        """Get result from a subagent"""
        # Check completed results first
        with self._lock:
            if agent_id in self._results:
                return self._results[agent_id]

            running = self._running.get(agent_id)

        if not running:
            return None

        if block:
            try:
                result = running.future.result(timeout=timeout)
                return result
            except Exception as e:
                return SubagentResult(
                    agent_id=agent_id,
                    agent_type=running.agent_type,
                    success=False,
                    result="",
                    tool_calls_made=0,
                    tokens_used=0,
                    duration_ms=0,
                    error=str(e)
                )
        else:
            if running.future.done():
                return running.future.result()
            return None

    def list_running(self) -> List[Dict[str, Any]]:
        """List currently running subagents"""
        with self._lock:
            return [
                {
                    "agent_id": r.agent_id,
                    "type": r.agent_type.value,
                    "task": r.task[:100],
                    "running_for": (datetime.now() - r.started_at).total_seconds()
                }
                for r in self._running.values()
            ]

    def kill(self, agent_id: str) -> bool:
        """Kill a running subagent"""
        with self._lock:
            running = self._running.get(agent_id)
            if running:
                running.future.cancel()
                del self._running[agent_id]
                return True
        return False

    def shutdown(self) -> None:
        """Shutdown the manager"""
        self._executor.shutdown(wait=False)
```

### Updated Task Tool

```python
# cortex/subagent/task_tool.py (updated)

from typing import Dict, Any, Optional, List
from ..tools.base import Tool
from .manager import SubagentManager
from .types import SubagentType


class TaskTool(Tool):
    """
    Tool for delegating tasks to specialized subagents.

    Supports:
    - Different agent types (explore, plan, bash, general)
    - Background execution
    - Agent resumption
    - Result retrieval
    """

    name = "task"
    description = "Launch a specialized agent to handle complex tasks"

    schema = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Short (3-5 word) description of the task"
            },
            "prompt": {
                "type": "string",
                "description": "Detailed task description"
            },
            "subagent_type": {
                "type": "string",
                "enum": ["explore", "plan", "bash", "general"],
                "description": "Type of specialized agent to use"
            },
            "run_in_background": {
                "type": "boolean",
                "default": False,
                "description": "Run in background and return agent_id"
            },
            "resume": {
                "type": "string",
                "description": "Agent ID to resume from previous execution"
            },
            "model": {
                "type": "string",
                "enum": ["sonnet", "opus", "haiku"],
                "description": "Optional model override"
            }
        },
        "required": ["description", "prompt", "subagent_type"]
    }

    def __init__(self, *args, subagent_manager: SubagentManager = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = subagent_manager

    def execute(
        self,
        description: str,
        prompt: str,
        subagent_type: str,
        run_in_background: bool = False,
        resume: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute task delegation"""

        # Map string to enum
        type_map = {
            "explore": SubagentType.EXPLORE,
            "plan": SubagentType.PLAN,
            "bash": SubagentType.BASH,
            "general": SubagentType.GENERAL
        }

        agent_type = type_map.get(subagent_type)
        if not agent_type:
            return {
                "success": False,
                "error": f"Unknown subagent type: {subagent_type}",
                "error_type": "validation"
            }

        # Handle resume
        if resume:
            result = self.manager.get_result(resume, block=True, timeout=30.0)
            if result:
                return {
                    "success": result.success,
                    "result": result.result,
                    "agent_id": result.agent_id,
                    "error": result.error
                }
            return {
                "success": False,
                "error": f"Agent {resume} not found or still running",
                "error_type": "not_found"
            }

        # Get parent context
        parent_context = self._get_parent_context()

        # Spawn agent
        result = self.manager.spawn(
            agent_type=agent_type,
            task=prompt,
            parent_context=parent_context,
            run_in_background=run_in_background
        )

        if run_in_background:
            # Result is agent_id
            return {
                "success": True,
                "agent_id": result,
                "message": f"Agent started in background. Use agent_id '{result}' to check status."
            }
        else:
            # Result is SubagentResult
            return {
                "success": result.success,
                "result": result.result,
                "agent_id": result.agent_id,
                "tool_calls": result.tool_calls_made,
                "tokens_used": result.tokens_used,
                "duration_ms": result.duration_ms,
                "error": result.error
            }

    def _get_parent_context(self) -> List[Dict[str, Any]]:
        """Get context from parent agent"""
        if hasattr(self, 'parent_agent') and self.parent_agent:
            return self.parent_agent.get_conversation_history()[-20:]
        return []
```

---

## 2.2 Slash Commands / Skills System

### Purpose

Provide extensible, user-invokable commands that trigger specialized workflows (like `/commit`, `/review-pr`, `/init`).

### Architecture

```
cortex/skills/
├── __init__.py
├── base.py              # BaseSkill class
├── registry.py          # Skill discovery and loading
├── commit.py            # /commit - smart git commit
├── review_pr.py         # /review-pr - PR review
├── init.py              # /init - project setup
├── help.py              # /help - show available skills
└── status.py            # /status - show session status
```

### Base Skill Class

```python
# cortex/skills/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class SkillResult:
    """Result from skill execution"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseSkill(ABC):
    """
    Base class for all skills (slash commands).

    Skills are user-invokable commands that trigger specialized workflows.
    They have access to the agent and can execute multi-step processes.
    """

    # Skill metadata
    name: str = ""  # e.g., "commit"
    aliases: List[str] = []  # e.g., ["ci", "c"]
    description: str = ""
    usage: str = ""  # e.g., "/commit [-m message]"

    def __init__(self, agent: 'Cortex'):
        self.agent = agent
        self.console = agent.console if hasattr(agent, 'console') else None

    @abstractmethod
    def execute(self, args: str = "") -> SkillResult:
        """
        Execute the skill.

        Args:
            args: Command-line style arguments passed to the skill

        Returns:
            SkillResult with success status and message
        """
        pass

    def get_help(self) -> str:
        """Get help text for this skill"""
        return f"""**/{self.name}** - {self.description}

Usage: {self.usage}

{self.__doc__ or ''}"""

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation"""
        from rich.prompt import Confirm
        return Confirm.ask(message)

    def prompt(self, message: str, default: str = "") -> str:
        """Prompt user for input"""
        from rich.prompt import Prompt
        return Prompt.ask(message, default=default)
```

### Skill Registry

```python
# cortex/skills/registry.py

from typing import Dict, Type, Optional, List
from pathlib import Path
import importlib
import inspect

from .base import BaseSkill


class SkillRegistry:
    """
    Discovers and manages available skills.

    Skills can be:
    - Built-in (in cortex/skills/)
    - User-defined (in ~/.cortex/skills/)
    - Project-specific (in .cortex/skills/)
    """

    def __init__(self):
        self._skills: Dict[str, Type[BaseSkill]] = {}
        self._aliases: Dict[str, str] = {}  # alias -> skill name

    def register(self, skill_class: Type[BaseSkill]) -> None:
        """Register a skill class"""
        name = skill_class.name
        if not name:
            raise ValueError(f"Skill {skill_class} has no name")

        self._skills[name] = skill_class

        # Register aliases
        for alias in skill_class.aliases:
            self._aliases[alias] = name

    def get(self, name: str) -> Optional[Type[BaseSkill]]:
        """Get a skill class by name or alias"""
        # Check direct name first
        if name in self._skills:
            return self._skills[name]

        # Check aliases
        if name in self._aliases:
            return self._skills[self._aliases[name]]

        return None

    def list_all(self) -> List[Dict[str, str]]:
        """List all registered skills"""
        return [
            {
                "name": name,
                "description": cls.description,
                "usage": cls.usage,
                "aliases": cls.aliases
            }
            for name, cls in self._skills.items()
        ]

    def discover_builtin(self) -> None:
        """Discover built-in skills"""
        from . import commit, review_pr, init, help, status

        for module in [commit, review_pr, init, help, status]:
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BaseSkill) and
                    obj is not BaseSkill):
                    self.register(obj)

    def discover_user_skills(self, user_dir: Path) -> None:
        """Discover user-defined skills from ~/.cortex/skills/"""
        skills_dir = user_dir / "skills"
        if not skills_dir.exists():
            return

        for py_file in skills_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    py_file.stem, py_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseSkill) and
                        obj is not BaseSkill):
                        self.register(obj)
            except Exception as e:
                import logging
                logging.warning(f"Failed to load skill from {py_file}: {e}")


# Global registry
_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get the global skill registry"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.discover_builtin()
    return _registry
```

### Commit Skill

```python
# cortex/skills/commit.py

from typing import Dict, Any, Optional, List
import subprocess
import re

from .base import BaseSkill, SkillResult


class CommitSkill(BaseSkill):
    """
    Smart git commit with AI-generated messages.

    Features:
    - Analyzes staged changes
    - Generates descriptive commit message
    - Follows repository conventions
    - Asks for confirmation before committing
    """

    name = "commit"
    aliases = ["ci", "c"]
    description = "Create a git commit with AI-generated message"
    usage = "/commit [-m message] [--no-verify]"

    def execute(self, args: str = "") -> SkillResult:
        """Execute the commit skill"""

        # Parse arguments
        custom_message = self._parse_message_arg(args)
        no_verify = "--no-verify" in args

        # Step 1: Check git status
        status = self._get_git_status()
        if not status["has_changes"]:
            return SkillResult(
                success=False,
                message="No changes to commit",
                error="Working directory is clean"
            )

        # Step 2: Show what will be committed
        self._display_changes(status)

        # Step 3: Generate or use provided message
        if custom_message:
            commit_message = custom_message
        else:
            commit_message = self._generate_commit_message(status)

        # Step 4: Show proposed commit
        self.console.print(f"\n[bold]Proposed commit message:[/bold]")
        self.console.print(f"[cyan]{commit_message}[/cyan]\n")

        # Step 5: Confirm
        if not self.confirm("Proceed with commit?"):
            return SkillResult(
                success=False,
                message="Commit cancelled by user"
            )

        # Step 6: Execute commit
        result = self._execute_commit(commit_message, no_verify)

        return result

    def _parse_message_arg(self, args: str) -> Optional[str]:
        """Parse -m message argument"""
        match = re.search(r'-m\s+["\'](.+?)["\']', args)
        if match:
            return match.group(1)
        return None

    def _get_git_status(self) -> Dict[str, Any]:
        """Get detailed git status"""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True,
            cwd=self.agent.project_dir
        )

        staged = []
        unstaged = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            index_status = line[0]
            work_status = line[1]
            filename = line[3:]

            if index_status != " " and index_status != "?":
                staged.append({"status": index_status, "file": filename})
            if work_status != " ":
                unstaged.append({"status": work_status, "file": filename})

        # Get diff of staged changes
        diff_result = subprocess.run(
            ["git", "diff", "--staged", "--stat"],
            capture_output=True, text=True,
            cwd=self.agent.project_dir
        )

        return {
            "has_changes": bool(staged or unstaged),
            "staged": staged,
            "unstaged": unstaged,
            "diff_stat": diff_result.stdout
        }

    def _display_changes(self, status: Dict[str, Any]) -> None:
        """Display changes to be committed"""
        self.console.print("[bold]Changes to be committed:[/bold]")

        status_icons = {
            "M": "[yellow]modified[/yellow]",
            "A": "[green]new file[/green]",
            "D": "[red]deleted[/red]",
            "R": "[blue]renamed[/blue]"
        }

        for item in status["staged"]:
            icon = status_icons.get(item["status"], item["status"])
            self.console.print(f"  {icon}: {item['file']}")

        if status["unstaged"]:
            self.console.print("\n[dim]Unstaged changes (not included):[/dim]")
            for item in status["unstaged"]:
                self.console.print(f"  [dim]{item['file']}[/dim]")

    def _generate_commit_message(self, status: Dict[str, Any]) -> str:
        """Generate commit message using AI"""
        # Get recent commits for style
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True, text=True,
            cwd=self.agent.project_dir
        )

        # Get detailed diff
        diff_result = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True, text=True,
            cwd=self.agent.project_dir
        )

        # Construct prompt for AI
        prompt = f"""Generate a git commit message for these changes.

Recent commits (for style reference):
{log_result.stdout[:500]}

Changes summary:
{status['diff_stat']}

Detailed diff (truncated):
{diff_result.stdout[:2000]}

Rules:
1. First line: short summary (50 chars max)
2. If needed, blank line then detailed description
3. Use imperative mood ("Add feature" not "Added feature")
4. Focus on WHY, not just WHAT
5. Match the style of recent commits

Output ONLY the commit message, no explanations."""

        # Use agent's provider to generate
        response = self.agent.provider.chat(
            model=self.agent.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes git commit messages."},
                {"role": "user", "content": prompt}
            ],
            tools=[]
        )

        return response["message"]["content"].strip()

    def _execute_commit(self, message: str, no_verify: bool) -> SkillResult:
        """Execute the git commit"""
        cmd = ["git", "commit", "-m", message]
        if no_verify:
            cmd.append("--no-verify")

        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=self.agent.project_dir
        )

        if result.returncode == 0:
            return SkillResult(
                success=True,
                message=f"Commit created successfully",
                data={"output": result.stdout}
            )
        else:
            return SkillResult(
                success=False,
                message="Commit failed",
                error=result.stderr
            )
```

### CLI Integration

```python
# In cortex/cli.py

from .skills import get_registry, BaseSkill

def handle_command(self, command: str) -> bool:
    """Handle user commands including skills"""

    if command.startswith("/"):
        parts = command[1:].split(maxsplit=1)
        skill_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Check if it's a skill
        registry = get_registry()
        skill_class = registry.get(skill_name)

        if skill_class:
            skill = skill_class(self.agent)
            result = skill.execute(args)

            if result.success:
                console.print(f"[green]{result.message}[/green]")
            else:
                console.print(f"[red]{result.message}[/red]")
                if result.error:
                    console.print(f"[dim]{result.error}[/dim]")

            return True

        # Check built-in commands
        # ... existing command handling ...

    return False
```

---

## 2.3 Background Task Execution

### Purpose

Allow long-running tasks to execute in the background while the user continues interacting.

### Architecture

```python
# cortex/core/background.py

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import queue
import uuid
from concurrent.futures import ThreadPoolExecutor, Future


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Represents a background task"""
    task_id: str
    description: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    output_buffer: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0.0 to 1.0


class BackgroundTaskManager:
    """
    Manages background task execution.

    Features:
    - Start tasks in background threads
    - Track task status and progress
    - Retrieve output incrementally
    - Kill running tasks
    - Notification on completion
    """

    def __init__(
        self,
        max_workers: int = 5,
        on_complete: Optional[Callable[[str, TaskStatus], None]] = None
    ):
        self.max_workers = max_workers
        self.on_complete = on_complete

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, BackgroundTask] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()

    def start_task(
        self,
        callable: Callable[..., Any],
        description: str = "",
        *args,
        **kwargs
    ) -> str:
        """
        Start a task in the background.

        Args:
            callable: Function to execute
            description: Human-readable description
            *args, **kwargs: Arguments to pass to callable

        Returns:
            task_id for tracking
        """
        task_id = str(uuid.uuid4())[:8]

        task = BackgroundTask(
            task_id=task_id,
            description=description,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )

        with self._lock:
            self._tasks[task_id] = task

        # Wrap callable to track status
        def wrapped():
            with self._lock:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()

            try:
                result = callable(*args, **kwargs)

                with self._lock:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    task.result = result
                    task.progress = 1.0

                if self.on_complete:
                    self.on_complete(task_id, TaskStatus.COMPLETED)

                return result

            except Exception as e:
                with self._lock:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = str(e)

                if self.on_complete:
                    self.on_complete(task_id, TaskStatus.FAILED)

                raise

        future = self._executor.submit(wrapped)

        with self._lock:
            self._futures[task_id] = future

        return task_id

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            return {
                "task_id": task.task_id,
                "description": task.description,
                "status": task.status.value,
                "progress": task.progress,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error": task.error
            }

    def get_result(
        self,
        task_id: str,
        block: bool = True,
        timeout: float = 30.0
    ) -> Optional[Any]:
        """
        Get task result.

        Args:
            task_id: Task to get result from
            block: Wait for completion if still running
            timeout: Maximum time to wait

        Returns:
            Task result or None
        """
        with self._lock:
            task = self._tasks.get(task_id)
            future = self._futures.get(task_id)

        if not task or not future:
            return None

        if task.status == TaskStatus.COMPLETED:
            return task.result

        if task.status == TaskStatus.FAILED:
            raise Exception(task.error)

        if block:
            try:
                return future.result(timeout=timeout)
            except Exception:
                return None

        return None

    def get_output(self, task_id: str) -> List[str]:
        """Get output buffer for a task"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return task.output_buffer.copy()
        return []

    def append_output(self, task_id: str, line: str) -> None:
        """Append to task output buffer (called from within task)"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.output_buffer.append(line)

    def update_progress(self, task_id: str, progress: float) -> None:
        """Update task progress (called from within task)"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.progress = min(1.0, max(0.0, progress))

    def kill_task(self, task_id: str) -> bool:
        """Kill a running task"""
        with self._lock:
            task = self._tasks.get(task_id)
            future = self._futures.get(task_id)

            if not task or not future:
                return False

            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return False

            cancelled = future.cancel()

            if cancelled or task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                return True

        return False

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status"""
        with self._lock:
            tasks = self._tasks.values()
            if status:
                tasks = [t for t in tasks if t.status == status]

            return [
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "status": t.status.value,
                    "progress": t.progress
                }
                for t in tasks
            ]

    def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """Remove old completed tasks"""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        removed = 0

        with self._lock:
            to_remove = [
                task_id for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                and task.completed_at and task.completed_at < cutoff
            ]

            for task_id in to_remove:
                del self._tasks[task_id]
                if task_id in self._futures:
                    del self._futures[task_id]
                removed += 1

        return removed

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the task manager"""
        self._executor.shutdown(wait=wait)
```

### Task Output Tool

```python
# cortex/tools/task_output_tool.py

class TaskOutputTool(Tool):
    """Tool for retrieving background task output"""

    name = "task_output"
    description = "Get output from a running or completed background task"

    schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID to get output from"
            },
            "block": {
                "type": "boolean",
                "default": True,
                "description": "Wait for completion"
            },
            "timeout": {
                "type": "number",
                "default": 30000,
                "description": "Max wait time in milliseconds"
            }
        },
        "required": ["task_id"]
    }

    def __init__(self, *args, task_manager: BackgroundTaskManager = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_manager = task_manager

    def execute(
        self,
        task_id: str,
        block: bool = True,
        timeout: int = 30000
    ) -> Dict[str, Any]:
        """Get task output"""

        status = self.task_manager.get_status(task_id)
        if not status:
            return {
                "success": False,
                "error": f"Task {task_id} not found",
                "error_type": "not_found"
            }

        output = self.task_manager.get_output(task_id)

        if block and status["status"] == "running":
            try:
                result = self.task_manager.get_result(
                    task_id,
                    block=True,
                    timeout=timeout / 1000
                )
                status = self.task_manager.get_status(task_id)
                output = self.task_manager.get_output(task_id)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": "execution"
                }

        return {
            "success": True,
            "status": status,
            "output": output
        }
```

---

## 2.4 Enhanced Plan Mode

### Purpose

Full planning workflow with explicit approval before implementation.

### Workflow

```
1. User requests feature: "Add authentication"
2. Agent enters plan mode (triggered by EnterPlanMode tool or automatically)
3. Agent explores codebase (read-only)
4. Agent creates plan in structured format
5. Agent calls ExitPlanMode tool
6. User sees plan and approves/rejects/modifies
7. If approved: Agent implements the plan
8. If rejected: Agent asks for guidance
```

### Plan Mode State

```python
# cortex/core/plan_mode.py

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PlanPhase(Enum):
    NOT_IN_PLAN = "not_in_plan"
    EXPLORING = "exploring"
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ImplementationStep:
    """A single step in the implementation plan"""
    order: int
    description: str
    files_affected: List[str]
    estimated_changes: str  # e.g., "Add 50 lines", "Modify 2 functions"
    dependencies: List[int] = field(default_factory=list)  # Step numbers this depends on


@dataclass
class ImplementationPlan:
    """Complete implementation plan"""
    title: str
    summary: str
    steps: List[ImplementationStep]
    files_to_create: List[str]
    files_to_modify: List[str]
    dependencies: List[str]  # External packages
    risks: List[str]
    testing_approach: str
    created_at: datetime = field(default_factory=datetime.now)


class PlanModeManager:
    """Manages plan mode state and workflow"""

    def __init__(self):
        self.phase = PlanPhase.NOT_IN_PLAN
        self.current_plan: Optional[ImplementationPlan] = None
        self.plan_file_path: Optional[str] = None
        self.exploration_notes: List[str] = []

    def enter_plan_mode(self) -> bool:
        """Enter plan mode"""
        if self.phase != PlanPhase.NOT_IN_PLAN:
            return False

        self.phase = PlanPhase.EXPLORING
        self.exploration_notes = []
        return True

    def transition_to_drafting(self) -> bool:
        """Transition from exploring to drafting"""
        if self.phase != PlanPhase.EXPLORING:
            return False

        self.phase = PlanPhase.DRAFTING
        return True

    def submit_plan(self, plan: ImplementationPlan, file_path: str) -> bool:
        """Submit plan for approval"""
        if self.phase not in (PlanPhase.EXPLORING, PlanPhase.DRAFTING):
            return False

        self.current_plan = plan
        self.plan_file_path = file_path
        self.phase = PlanPhase.AWAITING_APPROVAL
        return True

    def approve_plan(self) -> bool:
        """User approves the plan"""
        if self.phase != PlanPhase.AWAITING_APPROVAL:
            return False

        self.phase = PlanPhase.APPROVED
        return True

    def reject_plan(self, feedback: str = "") -> bool:
        """User rejects the plan"""
        if self.phase != PlanPhase.AWAITING_APPROVAL:
            return False

        self.phase = PlanPhase.REJECTED
        return True

    def exit_plan_mode(self) -> bool:
        """Exit plan mode entirely"""
        self.phase = PlanPhase.NOT_IN_PLAN
        self.current_plan = None
        self.plan_file_path = None
        self.exploration_notes = []
        return True

    def get_allowed_tools(self) -> Set[str]:
        """Get tools allowed in current phase"""
        if self.phase in (PlanPhase.EXPLORING, PlanPhase.DRAFTING):
            # Read-only tools during planning
            return {
                "read_file", "list_files", "search_files",
                "git_status", "git_log", "git_diff",
                "ask_user_question"
            }
        elif self.phase == PlanPhase.APPROVED:
            # All tools during implementation
            return {"*"}
        else:
            return {"*"}
```

### Enter Plan Mode Tool

```python
# cortex/tools/plan_tools.py

class EnterPlanModeTool(Tool):
    """Tool for entering plan mode"""

    name = "enter_plan_mode"
    description = "Enter plan mode to design an implementation before coding"

    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def __init__(self, *args, plan_manager: PlanModeManager = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_manager = plan_manager

    def execute(self) -> Dict[str, Any]:
        """Enter plan mode"""
        if self.plan_manager.enter_plan_mode():
            return {
                "success": True,
                "message": "Entered plan mode. You can now explore the codebase and design your implementation.",
                "allowed_tools": list(self.plan_manager.get_allowed_tools())
            }
        else:
            return {
                "success": False,
                "error": f"Cannot enter plan mode from current phase: {self.plan_manager.phase.value}",
                "error_type": "validation"
            }


class ExitPlanModeTool(Tool):
    """Tool for exiting plan mode with a completed plan"""

    name = "exit_plan_mode"
    description = "Submit your implementation plan for user approval"

    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self) -> Dict[str, Any]:
        """Exit plan mode and request approval"""
        if self.plan_manager.phase not in (PlanPhase.EXPLORING, PlanPhase.DRAFTING):
            return {
                "success": False,
                "error": "Not currently in plan mode",
                "error_type": "validation"
            }

        # Signal that plan is ready for review
        # The CLI will handle displaying the plan and getting approval
        return {
            "success": True,
            "message": "Plan submitted for review",
            "requires_user_approval": True,
            "plan_file": self.plan_manager.plan_file_path
        }
```

### Integration with Agent

```python
# In cortex/agent.py

class Cortex:
    def __init__(self, ...):
        # ... existing init ...
        self.plan_manager = PlanModeManager()

    def _filter_tools_for_plan_mode(self, tools: List[Dict]) -> List[Dict]:
        """Filter tools based on plan mode phase"""
        allowed = self.plan_manager.get_allowed_tools()

        if "*" in allowed:
            return tools

        return [t for t in tools if t["function"]["name"] in allowed]

    def _process_message(self, user_message: str, ...):
        # ... existing code ...

        # Filter tools if in plan mode
        if self.plan_manager.phase != PlanPhase.NOT_IN_PLAN:
            tools = self._filter_tools_for_plan_mode(TOOLS)
        else:
            tools = TOOLS

        # ... rest of processing ...
```

---

## Summary

Phase 2 adds these major capabilities:

1. **Typed Subagents**: Specialized agents (Explore, Plan, Bash) with different capabilities
2. **Slash Commands**: Extensible `/commit`, `/review-pr` style commands
3. **Background Tasks**: Run long operations in background with progress tracking
4. **Enhanced Plan Mode**: Full planning workflow with approval before implementation

These features bring Cortex significantly closer to Claude Code's functionality while maintaining a clean, modular architecture.
