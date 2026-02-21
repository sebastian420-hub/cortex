# Cortex Model Orchestration System - Complete Design Document

## Executive Summary

This document outlines the design for a **self-orchestrating multi-model system** where models can switch themselves based on task requirements. This is fundamentally different from auto-routing - models are aware of their capabilities and decide when to hand off work.

---

## Research Findings

### Current State Analysis

#### 1. Existing Routing System (What We Have)
- **Location**: `cortex/core/routing/`
- **Approach**: Auto-routes every message based on keywords
- **Problem**: Too simplistic, switches too often, user didn't want this
- **Decision**: **REMOVE/REPLACE** - This approach is wrong

#### 2. Subagent System (Works Well)
- **Location**: `cortex/subagent/task_tool.py`
- **How it works**:
  - Spawns isolated Cortex instances
  - Different agent types: `explore`, `search`, `analyze`, `general`
  - Has model-specific prompts (`_get_subagent_prompt`)
  - Runs in PLAN mode (read-only)
- **Test Status**: 42/42 tests passing
- **Decision**: **KEEP** - Subagents serve a different purpose (parallel/isolated work)

#### 3. System Prompts
- **Main prompt**: `agent.py:_get_system_prompt()` - 120+ lines
- **Subagent prompts**: Per agent type, well-structured
- **Gap**: No model-specific prompt injection
- **Decision**: **ENHANCE** - Add prompt injection based on model

### DeepSeek Model Landscape (2025)

| Model | API Name | Capabilities | Best For |
|-------|----------|--------------|----------|
| DeepSeek V3.2 | `deepseek-chat` | Non-thinking mode, general | Default chat, general tasks |
| DeepSeek V3.2 | `deepseek-reasoner` | Thinking mode, chain-of-thought | Planning, complex reasoning |
| DeepSeek Coder | Merged into `deepseek-chat` | Same as V3.2 | (Use chat instead) |
| DeepSeek V3.1 | Via OpenRouter | Hybrid thinking, 128K context | Long context tasks |

**Key Insight**: `deepseek-coder` was merged into V2.5/V3 - it's the same as `deepseek-chat` now.

### Multi-Model Best Practices (2025)

From [IBM](https://www.ibm.com/think/tutorials/llm-agent-orchestration-with-langchain-and-granite), [orq.ai](https://orq.ai/blog/llm-orchestration), [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/):

1. **Specialized agents over general purpose** - Each model should excel at one thing
2. **Bigger model orchestrating smaller models** - Meta-controller pattern
3. **Dynamic routing based on task** - Not static rules
4. **Human-in-the-loop** - For critical decisions
5. **Clear handoff protocols** - Models should explain transitions

---

## Proposed Architecture

### Core Concept: Self-Orchestrating Models

```
┌─────────────────────────────────────────────────────────────────┐
│  User: "Plan and build a secure authentication API"            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  DeepSeek-Chat (Default Coordinator)                            │
│                                                                 │
│  "This is a complex task requiring planning first."             │
│  [Calls: delegate_to_model(                                     │
│      model="deepseek-reasoner",                                 │
│      task="Plan the authentication API architecture",           │
│      handoff_notes="Need detailed step-by-step plan")]          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  DeepSeek-Reasoner (Planning Phase)                             │
│                                                                 │
│  <thinking>                                                     │
│  Let me reason through the authentication requirements...       │
│  </thinking>                                                    │
│                                                                 │
│  "Here's the detailed plan:                                     │
│   1. JWT token generation                                       │
│   2. Refresh token rotation                                     │
│   3. Password hashing with bcrypt..."                           │
│                                                                 │
│  [Calls: delegate_to_model(                                     │
│      model="cortex-coder-14b",                                  │
│      task="Implement the authentication API",                   │
│      handoff_notes="Plan attached, implement step by step")]    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Cortex-Coder-14B (Implementation Phase)                        │
│                                                                 │
│  "I see the plan. Implementing JWT authentication..."           │
│  [Uses file tools to write code]                                │
│                                                                 │
│  "Implementation complete. Returning to coordinator."           │
│  [Calls: return_to_coordinator(                                 │
│      summary="Implemented auth API with JWT and refresh")]      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  DeepSeek-Chat (Coordinator) - Back in control                  │
│                                                                 │
│  "Authentication API implemented. Would you like me to:         │
│   1. Run tests                                                  │
│   2. Add documentation                                          │
│   3. Review for security?"                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Differences from Subagents

| Aspect | Subagents (Task Tool) | Model Delegation |
|--------|----------------------|------------------|
| **Context** | Isolated, limited | Full conversation preserved |
| **Control** | Parent spawns child | Model hands off to peer |
| **State** | Separate state | Shared state/files |
| **Return** | Result summary | Continues conversation |
| **Use Case** | Parallel research | Sequential phases |

### When to Use Each

```
┌─────────────────────────────────────────────────────────────────┐
│                     DECISION TREE                                │
│                                                                 │
│  Need to do work in parallel?                                   │
│  ├── YES → Use Subagent (Task tool)                             │
│  └── NO                                                         │
│      └── Need different model capabilities?                     │
│          ├── YES → Use Model Delegation                         │
│          └── NO → Continue with current model                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Design

### 1. Model Registry & Capabilities

```python
# cortex/core/models/registry.py

MODEL_REGISTRY = {
    # Coordinator (default)
    "deepseek-chat": {
        "provider": "deepseek",
        "role": "coordinator",
        "capabilities": ["general", "chat", "coordination", "tool_use"],
        "can_delegate_to": ["deepseek-reasoner", "cortex-coder-14b", "cortex-coder-32b"],
        "prompt_profile": "coordinator",
        "cost_tier": "low",
    },

    # Reasoning specialist
    "deepseek-reasoner": {
        "provider": "deepseek",
        "role": "specialist",
        "capabilities": ["planning", "reasoning", "analysis", "complex_problems"],
        "can_delegate_to": ["deepseek-chat", "cortex-coder-14b"],
        "prompt_profile": "reasoner",
        "cost_tier": "medium",
    },

    # Coding specialist (user's fine-tuned models)
    "cortex-coder-14b": {
        "provider": "ollama",  # Local
        "role": "specialist",
        "capabilities": ["coding", "debugging", "refactoring", "tool_use"],
        "can_delegate_to": ["deepseek-chat", "deepseek-reasoner"],
        "prompt_profile": "coder",
        "cost_tier": "free",
    },

    "cortex-coder-32b": {
        "provider": "ollama",
        "role": "specialist",
        "capabilities": ["coding", "debugging", "refactoring", "complex_code", "tool_use"],
        "can_delegate_to": ["deepseek-chat", "deepseek-reasoner"],
        "prompt_profile": "coder",
        "cost_tier": "free",
    },

    # High-quality reviewer (expensive, use sparingly)
    "claude-3-5-sonnet": {
        "provider": "anthropic",
        "role": "specialist",
        "capabilities": ["review", "security", "architecture", "quality"],
        "can_delegate_to": ["deepseek-chat"],
        "prompt_profile": "reviewer",
        "cost_tier": "high",
    },
}
```

### 2. Prompt Injection System

```python
# cortex/core/prompts/profiles.py

PROMPT_PROFILES = {
    "coordinator": """
## Your Role: Coordinator

You are the main coordinator model. Your job is to:
1. Understand user requests
2. Break down complex tasks into phases
3. Delegate to specialists when their capabilities are needed
4. Synthesize results and communicate with the user

### When to Delegate

- **Planning/Reasoning**: Delegate to `deepseek-reasoner` for complex planning
- **Coding**: Delegate to `cortex-coder-14b` or `cortex-coder-32b` for implementation
- **Review**: Delegate to `claude-3-5-sonnet` for security/quality review (expensive!)

### How to Delegate

Use the `delegate_to_model` tool:
```
delegate_to_model(
    model="deepseek-reasoner",
    task="Plan the implementation of X",
    handoff_notes="Context about what's needed"
)
```

You will regain control when the specialist returns.
""",

    "reasoner": """
## Your Role: Reasoning Specialist

You excel at:
- Deep thinking and planning
- Step-by-step reasoning
- Complex problem analysis
- Architecture design

### Your Workflow

1. Use <thinking> tags for your reasoning process
2. Create detailed, actionable plans
3. When planning is complete, delegate to a coding model for implementation
4. Or return to coordinator if the user needs to decide something

### How to Hand Off

When your reasoning/planning is complete:
```
delegate_to_model(
    model="cortex-coder-14b",
    task="Implement the plan",
    handoff_notes="Detailed plan attached above"
)
```
""",

    "coder": """
## Your Role: Coding Specialist

You are optimized for Cortex tool usage and coding tasks. You excel at:
- Writing clean, efficient code
- Using file tools (read, write, edit)
- Running commands and tests
- Debugging and refactoring

### Your Workflow

1. Understand the task/plan provided
2. Use tools efficiently to implement
3. Test your changes when possible
4. Return to coordinator when done

### Tool Efficiency

- Use `grep` before `read_file` to find relevant code
- Use `edit` for small changes, `write_file` for new files
- Run tests after making changes

### When to Return

When implementation is complete:
```
return_to_coordinator(
    summary="What was accomplished",
    files_changed=["list", "of", "files"]
)
```
""",

    "reviewer": """
## Your Role: Quality Reviewer

You are called for high-stakes review. You excel at:
- Security analysis
- Code quality assessment
- Architecture review
- Best practices enforcement

### Your Workflow

1. Carefully review the code/changes provided
2. Identify issues, risks, and improvements
3. Provide actionable feedback
4. Return to coordinator with findings

### Output Format

Structure your review as:
1. **Security Issues**: Critical problems
2. **Quality Issues**: Code smells, maintainability
3. **Suggestions**: Improvements
4. **Approval Status**: APPROVED / NEEDS_CHANGES / BLOCKED
""",
}
```

### 3. Delegation Tool

```python
# cortex/tools/delegation_tool.py

DELEGATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delegate_to_model",
        "description": (
            "Hand off the current task to a specialist model. "
            "Use when you need capabilities outside your specialty. "
            "Context and conversation history will be preserved."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "enum": ["deepseek-reasoner", "cortex-coder-14b", "cortex-coder-32b", "claude-3-5-sonnet"],
                    "description": "Target model to delegate to"
                },
                "task": {
                    "type": "string",
                    "description": "Clear description of what the specialist should do"
                },
                "handoff_notes": {
                    "type": "string",
                    "description": "Context, decisions made, and any relevant information for the specialist"
                },
            },
            "required": ["model", "task"]
        }
    }
}

RETURN_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "return_to_coordinator",
        "description": (
            "Return control to the coordinator model after completing your task. "
            "Provide a summary of what was accomplished."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished"
                },
                "files_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files that were modified"
                },
                "needs_review": {
                    "type": "boolean",
                    "description": "Whether changes should be reviewed before continuing"
                },
            },
            "required": ["summary"]
        }
    }
}
```

### 4. Loop Prevention

```python
# Max delegations per user request
MAX_DELEGATIONS_PER_REQUEST = 5

# Tracking structure
class DelegationTracker:
    def __init__(self, max_delegations: int = 5):
        self.max_delegations = max_delegations
        self.delegation_count = 0
        self.delegation_history = []  # [(from_model, to_model, reason), ...]

    def can_delegate(self) -> bool:
        return self.delegation_count < self.max_delegations

    def record_delegation(self, from_model: str, to_model: str, reason: str):
        self.delegation_count += 1
        self.delegation_history.append({
            "from": from_model,
            "to": to_model,
            "reason": reason,
            "count": self.delegation_count
        })

    def get_remaining(self) -> int:
        return self.max_delegations - self.delegation_count
```

### 5. Context Preservation

When delegating, pass:

1. **Conversation History** - Full message history
2. **State Summary** - Files examined, decisions made
3. **Handoff Notes** - From the delegating model
4. **Delegation Context** - Who delegated, why, remaining quota

```python
class DelegationContext:
    conversation_history: List[Dict]
    state_summary: Dict[str, Any]
    handoff_notes: str
    from_model: str
    delegation_tracker: DelegationTracker

    def to_system_context(self) -> str:
        return f"""
## Delegation Context

You were delegated this task by: {self.from_model}

### Handoff Notes
{self.handoff_notes}

### State Summary
Files examined: {self.state_summary.get('files_read', [])}
Decisions made: {self.state_summary.get('decisions', [])}

### Delegation Quota
Remaining delegations: {self.delegation_tracker.get_remaining()}
(Use wisely - when quota is exhausted, you must complete the task yourself)
"""
```

---

## Integration with Existing Systems

### What to Remove

1. **Current auto-routing in `_process_message()`** - Remove the 25 lines we just added
2. **Most of `cortex/core/routing/`** - Keep cost_tracking.py and task_analysis.py for analytics only

### What to Keep

1. **Subagent system** - Different purpose (parallel work)
2. **Provider system** - Still need to create providers
3. **Cost tracking** - Useful for analytics
4. **Task analysis** - Useful for logging/debugging

### What to Add

1. **Model Registry** - `cortex/core/models/registry.py`
2. **Prompt Profiles** - `cortex/core/prompts/profiles.py`
3. **Delegation Tool** - `cortex/tools/delegation_tool.py`
4. **Delegation Tracker** - In agent state

---

## Implementation Plan

### Phase 1: Foundation (Remove & Restructure)

1. Remove auto-routing from `_process_message()`
2. Create model registry with capabilities
3. Create prompt profiles system
4. Create delegation tool schema

### Phase 2: Delegation System

1. Implement `DelegateTool` class
2. Implement `ReturnToCoordinatorTool` class
3. Implement `DelegationTracker` for loop prevention
4. Implement context preservation during handoff

### Phase 3: Prompt Injection

1. Create prompt profile loader
2. Modify `_get_system_prompt()` to inject model-specific prompts
3. Add model capability awareness to prompts
4. Test with different model combinations

### Phase 4: Integration & Testing

1. Update CLI for default model (deepseek-chat)
2. Add `/delegation` command to show delegation history
3. Create comprehensive tests
4. Document the system

### Phase 5: Fine-tuned Model Support

1. Design interface for user's cortex-coder models
2. Add hot-reload for model registry
3. Support custom prompt profiles
4. Test with 14B and 32B models when available

---

## Configuration

```yaml
# config.yaml
orchestration:
  enabled: true
  default_model: "deepseek-chat"
  max_delegations_per_request: 5

  # Model-specific settings
  models:
    deepseek-chat:
      prompt_profile: "coordinator"

    deepseek-reasoner:
      prompt_profile: "reasoner"
      max_thinking_tokens: 8000

    cortex-coder-14b:
      prompt_profile: "coder"
      ollama_model: "cortex-coder:14b"  # Your fine-tuned model

    cortex-coder-32b:
      prompt_profile: "coder"
      ollama_model: "cortex-coder:32b"
```

---

## Comparison: Old vs New

| Aspect | Old (Auto-Routing) | New (Self-Orchestrating) |
|--------|-------------------|-------------------------|
| **Who decides** | System (keywords) | Model itself |
| **When** | Every message | When model recognizes need |
| **Context** | Lost on switch | Fully preserved |
| **Transitions** | Silent, abrupt | Explicit with handoff notes |
| **User control** | None | Can see/control |
| **Loop prevention** | Cooldown | Max count per request |
| **Flexibility** | Fixed rules | Models adapt |

---

## Open Questions

1. **Should coordinator always be deepseek-chat?**
   - Or should user be able to start with any model?

2. **What happens when max delegations reached?**
   - Current model must finish? Ask user?

3. **Should we track delegation costs?**
   - Show user: "This request used 3 models, cost $0.05"

4. **How to handle model unavailability?**
   - Ollama not running? API key missing?

---

## Appendix: Test Cases

```python
# tests/test_delegation.py

def test_coordinator_delegates_to_reasoner():
    """Coordinator should delegate planning tasks to reasoner"""

def test_reasoner_delegates_to_coder():
    """Reasoner should delegate implementation to coder"""

def test_coder_returns_to_coordinator():
    """Coder should return to coordinator when done"""

def test_max_delegations_enforced():
    """Should stop delegating after max_delegations"""

def test_context_preserved_across_delegation():
    """Conversation history should be available to delegate"""

def test_prompt_profile_injection():
    """Each model should get its specific prompt profile"""
```

---

## Sources

- [DeepSeek API Docs](https://api-docs.deepseek.com/)
- [LLM Orchestration Best Practices - orq.ai](https://orq.ai/blog/llm-orchestration)
- [OpenAI Agents SDK - Multi-Agent](https://openai.github.io/openai-agents-python/multi_agent/)
- [IBM LLM Agent Orchestration Tutorial](https://www.ibm.com/think/tutorials/llm-agent-orchestration-with-langchain-and-granite)
- [DeepSeek V3 Technical Tour](https://magazine.sebastianraschka.com/p/technical-deepseek)
