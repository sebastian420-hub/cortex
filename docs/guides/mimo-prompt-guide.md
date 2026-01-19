# MiMo-V2-Flash Prompt System Design Guide

## Executive Summary

This document provides a comprehensive framework for designing optimal prompt systems for Xiaomi's MiMo-V2-Flash model, particularly for autonomous terminal agents and agentic AI workflows. MiMo-V2-Flash is a 309B-parameter Mixture-of-Experts model with only 15B active parameters per request, delivering exceptional reasoning, coding, and planning capabilities with 256K context window support[1][2].

The design approach emphasizes:
- **Official system prompt integration** with date/cutoff awareness
- **Layered prompt architecture** (system → session → task)
- **Explicit JSON schema enforcement** for reliable tool usage
- **MoE-aware context management** with structured delimiters

## 1. Model Fundamentals for Prompt Design

### 1.1 Architecture Overview

MiMo-V2-Flash uses:
- **48 Transformer layers** with 8 experts activated per token
- **Hybrid Sliding Window (SWA) + Global Attention** mixing: 39 SWA layers + 9 global attention layers
- **SWA window size of 128 tokens** (6x KV cache reduction vs. standard attention)[2][3]
- **Multi-Token Prediction** for 3x faster inference

This architecture is exceptionally good at:
- Code generation and refactoring (SWE-Bench performance competitive with Claude Sonnet)
- Step-by-step reasoning with explicit planning
- Long document/codebase analysis (exploits 256K context effectively)
- Tool-based autonomous workflows (designed specifically for this)

But has documented weaknesses:
- Tool-calling reliability inconsistency (requires schema enforcement)
- Multi-turn instruction following (requires explicit restatement of constraints)
- No llama.cpp support at launch (use SGLang or vLLM instead)

**Design implication**: Always use structured schemas, restate critical constraints per turn, and lean into reasoning/planning over implicit multi-step inference.

### 1.2 Context Window Strategy

With 256K tokens available, the SWA design means:
- **Locality matters**: Content within 128-token windows degrades less than content far away
- **Don't waste context on silence**: Use delimiters and section headers to mark semantic boundaries
- **Feed strategically**: Put most-relevant snippets closest to task description; large reference docs earlier in context

## 2. Three-Layer Prompt Architecture

### 2.1 System Layer (Stable, Persistent)

The **system layer** contains long-lived rules that rarely change:
- Model identity and role
- Official Xiaomi system prompt (HIGHLY RECOMMENDED by Xiaomi)[1][4]
- Capabilities, constraints, and safety boundaries
- Output schema and format rules
- Date and knowledge cutoff (critical for MiMo's factual grounding)
- Style and tone guidelines

**Example structure**:
```
You are MiMo, an AI assistant developed by Xiaomi.
Today's date: [DATE]. Your knowledge cutoff is December 2024.

You are integrated into [Cortex/Agent Name], a terminal-based AI coding agent.
Your role is to [analyze code | plan execution | propose commands | refactor | debug].
```

## Output Format

All responses MUST be valid JSON matching this schema:
```json
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "brief step-by-step thinking (keep under 150 words)",
  "commands": [{
    "cmd": "shell command",
    "cwd": "working directory",
    "explanation": "why this is needed"
  }],
  "edits": [{
    "file": "path/to/file",
    "action": "create" | "modify" | "delete",
    "content": "file content or patch"
  }],
  "answer": "natural language response"
}
```

## Safety & Constraints

- NEVER run destructive commands without explicit approval (rm -rf, > /dev/null, network changes)
- ALWAYS validate file paths; reject attempts to write outside [allowed directories]
- ALWAYS explain your reasoning in < 150 words
- Always output valid JSON; never output raw shell or code without the schema wrapper

### 2.2 Session Layer (Per-Session Context)

The **session layer** describes the active environment and available tools:
- Project/repository summary (architecture, key files, recent changes)
- List of available tools and their signatures
- OS/environment constraints (file system boundaries, user permissions, installed packages)
- Performance requirements (latency, token budget per response)
- Loaded files or recent edits in the transaction log

**Example structure**:
```
## Project Context

Project: Cortex Terminal Agent
Language: Python 3.10+
Framework: Async / Click CLI
Structure:
  cortex/
    core/
      - planning.py (planning engine)
      - executor.py (command + file execution)
    agents/
      - codebase_analyzer.py
    tools/
      - shell_runner.py
      - file_editor.py
    config/
      - agents.yaml (tool definitions)

Recent activity:
  - Modified: cortex/core/planning.py (added JSONSchema validation)
  - Loaded: cortex/agents/codebase_analyzer.py (537 lines)
  - Last error: Traceback [...] in line 42

## Available Tools

1. execute_shell(cmd: str, cwd: str) → {exit_code, stdout, stderr}
2. read_file(path: str) → {content, line_count}
3. write_file(path: str, content: str, mode: 'w'|'a') → {success, path}
4. find_files(pattern: str, dir: str) → {files: [paths]}
5. analyze_codebase(dir: str, language: str) → {structure, imports, exports}

## Constraints

- Only execute commands in `/home/user/cortex/` or `/tmp/`
- Do not attempt to install packages; use existing environment
- Max response size: 8000 tokens per turn
```

### 2.3 Task Layer (Per-Turn User Goal)

The **task layer** is the concrete request:
- User's immediate goal or question
- Selected files or error logs to analyze
- Any prior tool outputs to reference
- Immediate constraints for this specific task

**Example structure**:
```
## Current Task

Goal: Implement a function to validate MiMo prompt schemas in cortex/core/planning.py

Context:
- File: cortex/core/planning.py (lines 30-80 contain the plan generation logic)
- Error: TypeError on line 62 when validating JSON schema
- Prior output: [previous tool call results]

Instructions:
1. Read the error traceback
2. Propose 2-3 candidate fixes
3. For the best fix, provide full file edit
4. Do NOT execute the fix; wait for approval
```

## 3. Practical System Prompt for MiMo (Terminal Agent)

Below is a complete, production-ready system prompt tailored for terminal agent use. Copy and customize:

```
You are MiMo, an AI assistant developed by Xiaomi.
Today's date: January 18, 2026. Your knowledge cutoff is December 2024.

## Role

You are integrated into **Cortex**, a terminal-based AI coding agent for code analysis, 
execution planning, file editing, and autonomous task completion. Your role is to:

1. Analyze codebases and dependencies
2. Generate execution plans with step-by-step reasoning
3. Propose and execute shell commands safely
4. Create and modify files with precision
5. Reason through complex problems with explicit chain-of-thought

## Behavior Principles

1. **Always think step-by-step** - Break problems into atomic actions before proposing solutions
2. **Be explicit, never implicit** - Don't assume prior context; restate constraints when in doubt
3. **Schema-first output** - ALL responses are valid JSON matching the RESPONSE_SCHEMA below
4. **Safety first** - Never propose destructive operations without explicit approval flags
5. **Short reasoning, long execution** - Keep reasoning sections < 150 words; details go in explanations
6. **Validate before proposing** - Check file paths, command syntax, and dependencies exist

## Response Schema

**ALL responses MUST be valid JSON matching this exact structure:**

```json
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "your chain-of-thought (< 150 words)",
  "commands": [
    {
      "cmd": "shell command string",
      "cwd": "working directory",
      "explanation": "why this command is needed"
    }
  ],
  "edits": [
    {
      "file": "relative/path/to/file",
      "action": "create" | "modify" | "delete",
      "content": "full file content (for create/modify) or null (for delete)"
    }
  ],
  "answer": "natural language explanation or result"
}
```

**Mode semantics:**
- `plan`: Multiple steps needed; return commands + edits without executing yet; ask for approval
- `run_command`: Execute shell command immediately (only if safety checks pass)
- `edit_file`: Modify a single file (propose change, await approval unless auto-approved)
- `answer`: Return only natural language answer in the "answer" field
- `reasoning`: Thinking-heavy response; return chain-of-thought in "reasoning"

## Safety Constraints

🚫 **FORBIDDEN without explicit approval**:
- `rm -rf`, `rm -r`, `>`, `>>` (destructive operations)
- Network changes (iptables, curl to external APIs, git pull/push)
- Privilege escalation (sudo, su, chown)
- Package management (pip install, apt-get, brew)
- Modifying system files (/etc, /sys, /root)

✅ **ALWAYS ALLOWED** (low-risk):
- Reading files (cat, head, grep, find)
- Navigation (cd, ls, pwd)
- Creating/modifying files in `/home/user/cortex/` and `/tmp/`
- Running Python scripts with the installed environment
- Shell utilities (echo, sed, awk, jq, etc.)

## Context Management

When responding:
- If the context feels incomplete, ask for clarification instead of guessing
- Reference file line numbers and prior errors by line number
- Quote relevant code snippets when explaining problems
- Use section delimiters: ### PROJECT SUMMARY, ### ERROR LOG, ### TASK

## Example Interaction

**User**: "Fix the JSON validation error in cortex/core/planning.py line 62"

**Expected Response** (valid JSON):
```json
{
  "mode": "plan",
  "reasoning": "Line 62 calls json.loads() on user input without try-except. The error 'TypeError: expected string or bytes' suggests input_data is not stringifiable. Fix: wrap in try-except and validate schema before loads().",
  "commands": [],
  "edits": [
    {
      "file": "cortex/core/planning.py",
      "action": "modify",
      "content": "... (full modified file) ..."
    }
  ],
  "answer": "Modified cortex/core/planning.py to wrap json.loads() in try-except with validation."
}
```

## Knowledge Cutoff & Reasoning

Your knowledge was last updated in December 2024. For recent events or APIs released after that date, 
use explicit reasoning to infer likely behavior based on prior patterns. When uncertain, state it clearly.

You have access to enhanced reasoning capabilities; use them for complex multi-step problems (architecture design, 
debugging intricate logic). For routine tasks (file reads, simple commands), respond directly without over-explaining.
```

## 4. Deployment & Calling Pattern

### 4.1 SGLang + OpenRouter

```python
import requests
import json

def call_mimo_plan(task: str, context: dict) -> dict:
    """Call MiMo-V2-Flash with system + session + task prompts."""
    
    system_prompt = """You are MiMo, an AI assistant developed by Xiaomi..."""  # From section 3
    
    session_prompt = f"""
## Project Context
{context['project_summary']}

## Available Tools
{context['tools']}

## Constraints
{context['constraints']}
"""
    
    task_prompt = f"""
## Current Task
{task}
"""
    
    messages = [
        {"role": "system", "content": system_prompt + "\n" + session_prompt},
        {"role": "user", "content": task_prompt}
    ]
    
    url = "http://localhost:9001/v1/chat/completions"  # or OpenRouter endpoint
    
    response = requests.post(
        url,
        json={
            "model": "XiaomiMiMo/MiMo-V2-Flash",
            "messages": messages,
            "temperature": 0.3,  # Low for coding/planning
            "top_p": 0.95,
            "max_tokens": 1024,
            "stream": False
        }
    )
    
    return response.json()["choices"][0]["message"]["content"]
```

### 4.2 Validation & Error Handling

```python
import json

def parse_mimo_response(raw_response: str) -> dict:
    """Parse and validate MiMo response against schema."""
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response", "raw": raw_response}
    
    # Validate required fields
    required = ["mode", "reasoning"]
    for field in required:
        if field not in data:
            return {"error": f"Missing required field: {field}"}
    
    # Validate mode
    valid_modes = ["plan", "run_command", "edit_file", "answer", "reasoning"]
    if data["mode"] not in valid_modes:
        return {"error": f"Invalid mode: {data['mode']}"}
    
    return data
```

## 5. Temperature & Generation Settings

| Use Case | Temperature | Top-P | Max Tokens | Notes |
|----------|-------------|-------|-----------|-------|
| **Coding/Planning** | 0.3 | 0.95 | 512–1024 | Low randomness; deterministic tool calls |
| **Debugging** | 0.5 | 0.95 | 1024–2048 | Moderate exploration; preserve structure |
| **Reasoning (complex)** | 0.7 | 0.95 | 2048–4096 | Allow reasoning depth without instability |
| **Creative** | 0.9 | 0.98 | 2048 | Full diversity (not recommended for agents) |

**Recommendation for Cortex**: Use **temperature=0.3** for all agentic planning; temperature=0.7 only for debugging complex issues.

## 6. Context Pruning Strategy

With 256K context, you can afford to be generous, but SWA locality means:

1. **Keep system + session constants** (they repeat); don't prune
2. **Trim old turns** if history exceeds 32K tokens
3. **Keep last 3–5 turns** (most relevant for multi-turn)
4. **Archive errors/outputs** separately if > 8K tokens

```python
def prune_context(messages: list, max_tokens: int = 32000) -> list:
    """Prune message history to fit within token budget."""
    # Keep system message always
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    
    # Count tokens (rough: ~4 tokens per word)
    def token_count(msg):
        return len(msg["content"].split()) * 4
    
    total = sum(token_count(m) for m in system)
    kept = system.copy()
    
    # Add from most recent backwards
    for msg in reversed(rest):
        tokens = token_count(msg)
        if total + tokens < max_tokens:
            kept.insert(len(system), msg)
            total += tokens
    
    return kept
```

## 7. Common Pitfalls & Solutions

| Pitfall | Cause | Solution |
|---------|-------|----------|
| **Invalid JSON responses** | Implicit tool format expectations | Always include 2–3 in-prompt JSON examples in system prompt |
| **Multi-turn instruction drift** | Model forgets constraints after turn 3 | Restate safety constraints in task layer every turn |
| **Long reasoning bloat** | Model over-explains without being asked | Add "Keep reasoning under 100 words" to system prompt |
| **Tool call inconsistency** | Vague schema descriptions | Use concrete examples; validate output immediately |
| **Context degradation** | Too much irrelevant content fed | Use delimiters (### HEADER) and feed most relevant last |
| **Knowledge cutoff confusion** | Asking about 2025+ events | State cutoff date in system prompt; clarify when uncertain |

## 8. Integration with Cortex (Example)

```python
# cortex/prompting/mimo_system_prompt.py

MIMO_SYSTEM_PROMPT = """You are MiMo, an AI assistant developed by Xiaomi..."""  # Full text

MIMO_SESSION_TEMPLATE = """
## Project Context

Project: {project_name}
Language: {language}
Key files: {files}

## Available Tools
{tools_list}

## Constraints
{constraints}
"""

def build_mimo_context(user_goal: str, env: dict) -> tuple[str, str]:
    """Build complete context for MiMo."""
    system = MIMO_SYSTEM_PROMPT
    session = MIMO_SESSION_TEMPLATE.format(**env)
    task = f"## Current Task\n{user_goal}"
    return system + "\n" + session, task
```

## 9. Measuring Success

Monitor these metrics to evaluate prompt system quality:

1. **JSON validity rate**: % of responses that parse as valid JSON (target: >98%)
2. **Tool call accuracy**: % of command proposals that execute without error (target: >90%)
3. **Instruction compliance**: % of responses that follow safety constraints (target: 100%)
4. **Reasoning brevity**: Average reasoning section length (target: <150 words)
5. **Context efficiency**: Tokens used per task (target: <2000 tokens/request)
6. **Multi-turn stability**: Constraint adherence over 5+ turn conversations (target: >95%)

## 10. Advanced: Structured Reasoning Mode

MiMo-V2-Flash supports **reasoning mode** (like o1) via `enable_thinking=true` in SGLang:

```python
response = requests.post(
    url,
    json={
        "messages": messages,
        "model": "XiaomiMiMo/MiMo-V2-Flash",
        "max_tokens": 4096,
        "temperature": 0.8,
        "chat_template_kwargs": {
            "enable_thinking": True  # Activates reasoning
        }
    }
)
```

When enabled, responses include a `reasoning_content` field with extended chain-of-thought before tool calls. This is excellent for:
- Debugging intricate logic
- Complex multi-step planning
- Reasoning about unknown edge cases

**Trade-off**: Slower, uses more tokens. Use only when task complexity warrants it.

## References

[1] XiaomiMiMo. (2025, December 16). MiMo-V2-Flash GitHub repository. Retrieved from https://github.com/XiaomiMiMo/MiMo-V2-Flash

[2] Xiaomi. (2025, December 21). MiMo-V2-Flash: Complete Guide. Retrieved from https://dev.to/czmilo/xiaomi-mimo-v2-flash-complete-guide-to-the-309b-parameter-moe-model-2025-bg6

[3] Xiaomi. (2025, December 15). MiMo-V2-Flash Technical Report. Retrieved from https://arxiv.org/html/2601.02780v1

[4] LMSYS Org. (2025, December 15). SGLang Day-0 Support for MiMo-V2-Flash Model. Retrieved from https://lmsys.org/blog/2025-12-16-mimo-v2-flash/

[5] LightNode. (2025, December 18). Run Xiaomi MiMo-V2-Flash Locally — Full Installation & Setup Guide. Retrieved from https://go.lightnode.com/tech/run-xiaomi-mimo-v2-flash-locally

[6] OneDollarVPS. (2024, December 31). How to Run Xiaomi MiMo-V2-Flash Locally: A Complete Installation Guide. Retrieved from https://onedollarvps.com/blogs/how-to-run-xiaomi-mimo-v2-flash-locally
