# LocalAgent - Complete Architecture & Technical Specification

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Technical Specifications](#technical-specifications)
6. [Design Patterns](#design-patterns)
7. [Function Calling Protocol](#function-calling-protocol)
8. [Security & Safety](#security-safety)
9. [Performance Considerations](#performance-considerations)
10. [Extensibility](#extensibility)

---

## 1. Project Overview

### What is LocalAgent?

LocalAgent is a **terminal-based autonomous coding agent** that replicates Claude Code's functionality using local LLM models (via Ollama). It enables developers to interact with their codebase through natural language, allowing the AI to read files, write code, execute commands, and search through projects autonomously.

### Key Objectives

1. **Privacy-First**: All processing happens locally - no data sent to external APIs
2. **Cost-Effective**: Free to use (only requires local compute)
3. **Offline-Capable**: Works without internet connection
4. **Extensible**: Easy to add new tools and capabilities
5. **Safe**: Built-in permission system and dangerous operation blocking

### Use Cases

- Code refactoring and modernization
- Adding features to existing codebases
- Debugging and error investigation
- Project documentation generation
- Test writing and validation
- Code review and analysis
- Learning and exploring unfamiliar codebases

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER TERMINAL                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Interactive REPL Interface (cli.py)         │  │
│  │  (prompt_toolkit + rich for display)                     │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        │ User Commands
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOCAL AGENT CORE (agent.py)                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Conversation Manager (core/conversation.py) │  │
│  │  • Maintains message history                             │  │
│  │  • Manages system prompts                                │  │
│  │  • Handles context window (core/context.py)              │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       │ Orchestrates                            │
│                       │                                         │
│  ┌────────────────────▼─────────────────────────────────────┐  │
│  │              Agent Loop Controller                        │  │
│  │  • Iterative reasoning cycle                             │  │
│  │  • Tool call routing (via tool classes)                   │  │
│  │  • Termination detection                                 │  │
│  │  • Streaming support (core/streaming.py)                 │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        │ API Calls
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OLLAMA SERVICE                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Local LLM Server                             │  │
│  │  • Model inference (Llama 3.3, Qwen, etc.)              │  │
│  │  • Function calling support                              │  │
│  │  • Streaming responses                                   │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        │ Tool Calls
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TOOL EXECUTION LAYER (tools/)              │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐  │
│  │  File I/O    │   Command    │   Search     │   Git       │  │
│  │   Tools      │   Executor   │   Engine     │   Tools     │  │
│  │              │              │              │             │  │
│  │ • read_file  │ • execute_   │ • list_      │ • git_      │  │
│  │ • write_file │   command    │   files      │   status    │  │
│  │              │ • Safety     │ • search_    │ • git_diff  │  │
│  │              │   checks     │   files      │ • git_      │  │
│  │              │   (security) │              │   commit    │  │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬──────┘  │
│         │              │              │              │         │
│         │              │              │              │         │
│  ┌──────▼──────┬───────▼──────┬───────▼──────┬───────▼──────┐ │
│  │   Test      │   Config     │   Storage    │   UI         │ │
│  │   Tools     │   System    │   (sessions)  │   (display)  │ │
│  │             │              │              │              │ │
│  │ • run_tests │ • YAML      │ • save/load  │ • diffs      │ │
│  │             │   config     │   sessions   │ • progress   │ │
│  └─────────────┴──────────────┴──────────────┴──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │              │              │              │
          │              │              │              │
          ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FILE SYSTEM                                │
│  • Read/Write files in project directory                       │
│  • Execute shell commands                                       │
│  • Search through codebase                                      │
│  • Git operations                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User Input → REPL → Conversation Manager → Agent Loop
                                               ↓
                                          Ollama API
                                               ↓
                                    ┌──────────┴──────────┐
                                    │                     │
                              Text Response      Tool Calls
                                    │                     │
                                    ▼                     ▼
                              Display to User    Tool Execution Layer
                                                          ↓
                                                   Execute & Return
                                                          ↓
                                                   Add to History
                                                          ↓
                                                  ← Back to Agent Loop
```

---

## 3. Component Design

### 3.1 LocalAgent Class (Core Orchestrator)

**Responsibilities:**
- Initialize and configure the agent
- Manage conversation state
- Orchestrate the request-response loop
- Route tool calls to appropriate executors
- Handle permission checking

**Key Attributes:**
```python
class LocalAgent:
    model: str                    # Ollama model name
    project_dir: Path             # Working directory
    permission_mode: str          # normal/auto/plan
    config: AgentConfig           # Configuration settings
    conversation: ConversationManager  # Conversation history manager
    session_start: datetime       # Session tracking
    project_context: str          # Content from AGENT.md
    history_dir: Path             # Session storage directory
```

**Key Methods:**
```python
__init__()                        # Initialize agent
_load_project_context()           # Load AGENT.md
_get_system_prompt()              # Generate system prompt
execute_tool()                    # Route tool execution (uses tool classes)
_process_message()                # Main agent loop
get_conversation_history()        # Get current conversation
clear_conversation()               # Clear conversation history
```

**Note**: `run_interactive()` and `run_oneshot()` are now in `cli.py`, and `_handle_command()` is also in the CLI module.

### 3.2 Tool Execution Layer

Tools are now implemented as separate classes inheriting from a base `Tool` class, located in `localagent/tools/`:

**Tool Base Class:**
```python
class Tool(ABC):
    def __init__(self, project_dir: Path, permission_mode: str, console):
        self.project_dir = project_dir
        self.permission_mode = permission_mode
        self.console = console
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool with given arguments"""
        pass
```

**Available Tools (in `localagent/tools/`):**

1. **File I/O Tools** (`file_tools.py`)
   ```python
   ReadFileTool.execute(path: str) -> Dict
   WriteFileTool.execute(path: str, content: str) -> Dict
   ```
   - Handles file reading/writing with path validation
   - Shows syntax-highlighted previews
   - Requests permission for writes
   - Creates directories if needed

2. **Command Execution** (`command_tools.py`)
   ```python
   ExecuteCommandTool.execute(command: str, reason: str) -> Dict
   ```
   - Runs shell commands
   - Safety checks for dangerous operations
   - Captures stdout/stderr
   - Timeout protection (30s)

3. **File Discovery** (`search_tools.py`)
   ```python
   ListFilesTool.execute(path: str, pattern: str) -> Dict
   SearchFilesTool.execute(query: str, file_pattern: str) -> Dict
   ```
   - Directory listing with glob patterns
   - Full-text search via ripgrep/grep
   - Result limiting and formatting

4. **Git Integration** (`git_tools.py`) - NEW
   ```python
   GitStatusTool.execute() -> Dict
   GitDiffTool.execute(path: str) -> Dict
   GitCommitTool.execute(message: str) -> Dict
   GitLogTool.execute(limit: int) -> Dict
   ```
   - Git status, diff, commit, and log operations
   - Permission checking for commits

5. **Test Execution** (`test_tools.py`) - NEW
   ```python
   RunTestsTool.execute(pattern: str, verbose: bool) -> Dict
   ```
   - Auto-detects pytest or unittest
   - Runs test suite with results parsing

### 3.3 Permission System

**Three Permission Modes:**

```python
class PermissionMode:
    NORMAL = "normal"      # Ask before every action
    AUTO_APPROVE = "auto"  # Skip permission prompts
    PLAN = "plan"          # Read-only, no modifications
```

**Permission Flow:**
```
Tool Execution Request
        ↓
Is mode == PLAN?
  Yes → Block write/execute operations
  No ↓
Is mode == AUTO_APPROVE?
  Yes → Execute immediately
  No ↓
Is mode == NORMAL?
  Yes → Prompt user for approval
        ↓
    User approves?
      Yes → Execute
      No → Return cancellation error
```

### 3.4 REPL Interface

**Built with:**
- `prompt_toolkit`: Advanced terminal input with history
- `rich`: Beautiful terminal output with formatting

**Features:**
- Command history (saved between sessions)
- Multi-line input support
- Syntax highlighting
- Markdown rendering
- Progress indicators
- Interrupt handling (Ctrl+C)

**REPL Loop:**
```python
while True:
    user_input = session.prompt("> ")
    
    if user_input.startswith('/'):
        handle_command(user_input)
    else:
        process_message(user_input)
```

### 3.5 Display Layer (Rich Components)

**Console Output Types:**

1. **Panels** - Boxed content for important information
   ```python
   Panel(content, title="Title", border_style="cyan")
   ```

2. **Syntax** - Code with highlighting
   ```python
   Syntax(code, "python", theme="monokai", line_numbers=True)
   ```

3. **Markdown** - Formatted text
   ```python
   Markdown("## Heading\n\nText")
   ```

4. **Tables** - Structured data
   ```python
   Table(title="Files")
   table.add_column("Name")
   table.add_row("file.py")
   ```

5. **Status** - Loading indicators
   ```python
   with console.status("Loading...", spinner="dots"):
       # do work
   ```

---

## 4. Data Flow

### 4.1 Message Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONVERSATION HISTORY                         │
│  [                                                              │
│    {"role": "system", "content": "System prompt..."},          │
│    {"role": "user", "content": "User request..."},             │
│    {"role": "assistant", "content": "...", "tool_calls": [...]}│
│    {"role": "tool", "content": "Tool result..."},              │
│    {"role": "assistant", "content": "Final answer..."}         │
│  ]                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Complete Request-Response Cycle

```
Step 1: User Input
  User: "add logging to api.py"
    ↓
    
Step 2: Add to History
  history.append({
    "role": "user",
    "content": "add logging to api.py"
  })
    ↓
    
Step 3: Send to Ollama
  response = ollama.chat(
    model="llama3.2",
    messages=history,
    tools=TOOLS
  )
    ↓
    
Step 4: Ollama Returns Response
  {
    "message": {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "function": {
            "name": "read_file",
            "arguments": {"path": "api.py"}
          }
        }
      ]
    }
  }
    ↓
    
Step 5: Add to History
  history.append(response["message"])
    ↓
    
Step 6: Execute Tool
  result = agent.execute_tool("read_file", {"path": "api.py"})
  # Returns: {"success": true, "content": "...", "lines": 45}
    ↓
    
Step 7: Add Tool Result to History
  history.append({
    "role": "tool",
    "content": json.dumps(result)
  })
    ↓
    
Step 8: Loop Back to Step 3
  (Agent now has file content, decides next action)
    ↓
    
Step 9: Agent Decides to Write
  {
    "tool_calls": [
      {
        "function": {
          "name": "write_file",
          "arguments": {
            "path": "api.py",
            "content": "import logging\n..."
          }
        }
      }
    ]
  }
    ↓
    
Step 10: Execute Write (with permission)
  Display preview → Ask user → Execute → Return result
    ↓
    
Step 11: Agent Provides Final Answer
  {
    "message": {
      "role": "assistant",
      "content": "I've added logging to api.py with INFO level..."
    }
  }
    ↓
    
Step 12: Display to User & Complete
```

### 4.3 Tool Execution Flow

```
Tool Call Received
        ↓
Extract tool_name and arguments
        ↓
Route to appropriate handler
        ↓
    ┌───┴───────────────────────┐
    │                           │
Read/List        Write/Execute  │
    │                           │
    ▼                           ▼
Display      Check Permission Mode
Preview           │
    │         ────┼────
    │         │       │
    │       PLAN    OTHER
    │         │       │
    │       Block     ▼
    │               Display
    │               Preview
    │                 ↓
    │          Ask for Approval
    │          (if NORMAL mode)
    │                 │
    │           ┌─────┴─────┐
    │           │           │
    │         Yes          No
    │           │           │
    ▼           ▼           ▼
Execute     Execute     Cancel
Operation   Operation   Operation
    │           │           │
    └───────────┴───────────┘
                │
        Return Result Dict
                │
        Display to User
                │
        Add to History
```

---

## 5. Technical Specifications

### 5.1 System Requirements

**Minimum:**
- Python 3.8+
- 8GB RAM
- 4GB disk space for models
- CPU-only (slow but works)

**Recommended:**
- Python 3.10+
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM (for 70B models)
- 20GB disk space

**Optimal:**
- Python 3.11+
- 32GB+ RAM
- NVIDIA GPU with 24GB+ VRAM
- 50GB disk space

### 5.2 Dependencies

**Core Dependencies:**
```
ollama >= 0.1.0          # Local LLM server interface
rich >= 13.0.0           # Terminal formatting
prompt_toolkit >= 3.0.0  # Advanced input handling
pyyaml >= 6.0            # Configuration file support
```

**Project Structure:**
```
localagent/
├── agent.py             # Main agent class
├── cli.py               # Command-line interface
├── config.py            # Configuration management
├── models.py            # Data models (PermissionMode)
├── tools/               # Tool implementations
│   ├── base.py         # Base tool class
│   ├── file_tools.py
│   ├── command_tools.py
│   ├── search_tools.py
│   ├── git_tools.py    # NEW
│   └── test_tools.py   # NEW
├── core/                # Core functionality
│   ├── security.py     # Path validation, safety
│   ├── context.py      # Context window management
│   ├── conversation.py # Conversation manager
│   └── streaming.py    # Streaming responses
├── ui/                  # User interface
│   ├── console.py      # Console utilities
│   ├── display.py      # Display helpers
│   └── repl.py         # REPL interface
├── storage/             # Data persistence
│   ├── history.py      # Command history
│   └── sessions.py     # Session management
└── utils/               # Utilities
    └── errors.py       # Error handling & retry
```

**System Dependencies:**
```
ollama                   # LLM inference server
ripgrep (optional)       # Fast file search
git (optional)           # Version control operations
```

### 5.3 Model Support

**Tested Models:**
| Model | Size | RAM | Quality | Speed | Best For |
|-------|------|-----|---------|-------|----------|
| llama3.2 | 3B | 4GB | ⭐⭐⭐ | ⚡⚡⚡ | Testing/Learning |
| llama3.3 | 70B | 48GB | ⭐⭐⭐⭐⭐ | ⚡ | Production |
| qwen2.5 | 32B | 24GB | ⭐⭐⭐⭐ | ⚡⚡ | Balanced |
| qwen2.5-coder | 32B | 24GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | Coding-specific |
| deepseek-r1 | 70B | 48GB | ⭐⭐⭐⭐⭐ | ⚡ | Reasoning-heavy |

**Function Calling Support:**
All models must support Ollama's function calling format. Models trained on tool use (Hermes, Functionary) perform better.

### 5.4 Tool Schema Format

**Follows OpenAI/Anthropic Standard:**
```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What the tool does",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {
          "type": "string",
          "description": "Parameter description"
        }
      },
      "required": ["param_name"]
    }
  }
}
```

### 5.5 API Interfaces

**Ollama API:**
```python
ollama.chat(
    model: str,              # Model name
    messages: List[Dict],    # Conversation history
    tools: List[Dict],       # Tool definitions
    stream: bool = False     # Streaming response
) -> Dict
```

**Tool Result Format:**
```python
{
    "success": bool,         # Operation succeeded?
    "error": str,           # Error message (if failed)
    "data": Any,            # Tool-specific return data
    # Tool-specific fields
}
```

### 5.6 File Formats

**Conversation History:**
```json
[
  {
    "role": "system|user|assistant|tool",
    "content": "message text",
    "tool_calls": [...],  // Optional for assistant
    "name": "tool_name"   // Optional for tool role
  }
]
```

**Project Context File (AGENT.md):**
```markdown
# Project Name

## Tech Stack
- Technology list

## Architecture
- Component descriptions

## Code Style
- Style guidelines

## Common Tasks
- Frequent operations
```

---

## 6. Design Patterns

### 6.1 Command Pattern

**Tool Execution:**
```python
class ToolExecutor:
    def execute(self, tool_name: str, args: Dict) -> Dict:
        handler = self._get_handler(tool_name)
        return handler(args)
```

Each tool is encapsulated as a command with consistent interface.

### 6.2 Strategy Pattern

**Permission Modes:**
```python
class PermissionStrategy:
    def check_permission(self, action: str) -> bool:
        pass

class NormalMode(PermissionStrategy):
    def check_permission(self, action: str) -> bool:
        return Confirm.ask(f"Execute {action}?")

class AutoMode(PermissionStrategy):
    def check_permission(self, action: str) -> bool:
        return True
```

Different permission behaviors without changing execution logic.

### 6.3 Chain of Responsibility

**Agent Loop:**
```
User Input → Parse → Execute Tool → Check Result → 
  ↑                                                │
  └────────── Loop if tools needed ───────────────┘
```

Each iteration adds to context and influences next decision.

### 6.4 Template Method

**Tool Execution Template:**
```python
def execute_tool(self, name, args):
    # 1. Validate (hook)
    self._validate(name, args)
    
    # 2. Check permissions (hook)
    if not self._check_permission(name):
        return {"error": "Permission denied"}
    
    # 3. Execute (hook - implemented by subclass)
    result = self._execute(name, args)
    
    # 4. Display (hook)
    self._display_result(result)
    
    # 5. Return
    return result
```

### 6.5 Singleton (Optional Enhancement)

**Ollama Connection:**
```python
class OllamaConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
```

Reuse connection across multiple agent instances.

---

## 7. Function Calling Protocol

### 7.1 How Function Calling Works

**The Protocol:**
```
1. Agent receives user request
2. Agent analyzes what tools are needed
3. Agent returns tool_calls in response
4. System executes tools
5. System adds tool results to history
6. Loop back to step 1 until complete
```

### 7.2 Tool Call Format

**Agent's Tool Call:**
```json
{
  "tool_calls": [
    {
      "id": "call_abc123",
      "function": {
        "name": "read_file",
        "arguments": {
          "path": "api.py"
        }
      }
    }
  ]
}
```

**Tool Result:**
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"success\": true, \"content\": \"...\"}"
}
```

### 7.3 Multi-Tool Execution

**Sequential vs Parallel:**

Current implementation: Sequential (safer)
```python
for tool_call in tool_calls:
    result = execute(tool_call)
    add_to_history(result)
```

Future enhancement: Parallel (faster)
```python
results = await asyncio.gather(*[
    execute_async(tc) for tc in tool_calls
])
```

### 7.4 Tool Selection Logic

**How the model decides which tools to use:**

1. **Task Analysis**: Model analyzes user request
2. **Tool Matching**: Compares task needs vs tool descriptions
3. **Argument Extraction**: Extracts relevant parameters
4. **Dependency Resolution**: Orders tools logically (read before write)

**Example:**
```
User: "add logging to api.py"

Model thinks:
1. Need to see current content → read_file(api.py)
2. Need to modify it → write_file(api.py, new_content)
3. Maybe test it → execute_command("python api.py")
```

---

## 8. Security & Safety

### 8.1 Threat Model

**Potential Threats:**
1. **Malicious User Input**: Tricks agent into dangerous operations
2. **Command Injection**: User embeds harmful commands
3. **File System Access**: Unauthorized file access
4. **Resource Exhaustion**: Infinite loops, large file operations
5. **Data Exfiltration**: Agent leaking sensitive information

### 8.2 Security Measures

**1. Command Blacklist:**
```python
DANGEROUS_PATTERNS = [
    r'rm -rf /',           # Delete root
    r'rm -rf ~',           # Delete home
    r':(){ :|:& };:',     # Fork bomb
    r'mkfs',               # Format disk
    r'dd if=',             # Disk operations
    r'sudo rm',            # Elevated delete
]
```

**2. Sandboxing Recommendations:**
```bash
# Run in Docker container
docker run --rm -it \
  -v $(pwd):/workspace \
  -w /workspace \
  python:3.11 python localagent.py

# Or use firejail
firejail --private --net=none python localagent.py
```

**3. File Access Control:**
```python
def _read_file(self, path):
    full_path = self.project_dir / path
    
    # Prevent directory traversal
    if not full_path.resolve().is_relative_to(self.project_dir):
        return {"error": "Access denied: outside project"}
```

**4. Timeout Protection:**
```python
subprocess.run(
    command,
    timeout=30  # Kill after 30 seconds
)
```

**5. Permission System:**
- Default: Ask before everything
- User must explicitly enable auto-approve
- Plan mode blocks all modifications

### 8.3 Privacy Considerations

**100% Local Processing:**
- No data sent to external APIs
- All inference happens on local machine
- Conversation history stored locally
- No telemetry or tracking

**Data Storage:** ✅ IMPLEMENTED in `storage/` module
```
~/.localagent/
  ├── sessions/          # Conversation history (storage/sessions.py)
  │   └── session_name.json
  └── history.txt        # Command history (storage/history.py)
```

**Session Management:**
- Save/load conversations via `SessionManager`
- CLI commands: `--save-session`, `--load-session`, `--list-sessions`
- In-session commands: `/save`, `/load`, `/sessions`

---

## 9. Performance Considerations

### 9.1 Performance Characteristics

**Latency Breakdown (Llama 3.3 70B on RTX 4090):**
```
User input → Display:           ~5-15 seconds
  ├─ Ollama processing:          4-12s
  ├─ Tool execution:             0.1-2s
  ├─ Display rendering:          0.1s
  └─ Network overhead:           0.1s
```

**Context Window:**
```
Llama 3.3:     128K tokens
Qwen 2.5:      32K tokens
Typical usage: 5-20K tokens per session
```

### 9.2 Optimization Strategies

**1. Model Selection:**
```python
# Fast iteration: Use small model
agent = LocalAgent(model="llama3.2")  # 3B

# Production: Use large model
agent = LocalAgent(model="llama3.3:70b")  # 70B

# Balanced: Medium model
agent = LocalAgent(model="qwen2.5:32b")  # 32B
```

**2. Quantization:**
```bash
# Q4 quantization (4-bit) - 4x smaller, slight quality loss
ollama pull llama3.3:70b-q4_K_M

# Q8 quantization (8-bit) - 2x smaller, minimal quality loss
ollama pull llama3.3:70b-q8_0
```

**3. Context Management:**
```python
# Now handled by ConversationManager in core/conversation.py
# Automatically truncates when max_tokens exceeded
# Keeps system prompt + recent N messages
manager = ConversationManager(
    system_prompt="...",
    max_tokens=100000,
    keep_recent=20
)
manager._optimize()  # Called automatically after each message
```

**4. Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def read_file_cached(path: str, mtime: float):
    return read_file(path)

# Cache based on modification time
mtime = os.path.getmtime(path)
content = read_file_cached(path, mtime)
```

### 9.3 Scalability Limits

**Single Project:**
- Works well up to 10K files
- Context limited by model (32K-128K tokens)
- File operations are sequential (not parallelized)

**Concurrent Sessions:**
- One agent instance per terminal
- Ollama can serve multiple models simultaneously
- Memory scales linearly with active sessions

---

## 10. Extensibility

### 10.1 Adding New Tools

**Template for New Tool:**
```python
# 1. Define tool schema
{
    "type": "function",
    "function": {
        "name": "new_tool",
        "description": "What it does",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "..."}
            },
            "required": ["param"]
        }
    }
}

# 2. Add to TOOLS list

# 3. Implement handler
def _new_tool(self, param: str) -> Dict[str, Any]:
    try:
        # Do something
        result = process(param)
        return {"success": True, "result": result}
    except Exception as e:
        return {"error": str(e)}

# 4. Route in execute_tool()
elif tool_name == "new_tool":
    return self._new_tool(arguments["param"])
```

### 10.2 Extension Ideas

**Database Tools:**
```python
def _query_database(self, sql: str) -> Dict:
    """Execute SQL query on project database"""
    
def _list_tables(self) -> Dict:
    """List all database tables"""
```

**API Tools:**
```python
def _http_request(self, url: str, method: str) -> Dict:
    """Make HTTP request to test APIs"""
    
def _start_server(self, command: str) -> Dict:
    """Start development server"""
```

**Git Tools:** ✅ IMPLEMENTED in `tools/git_tools.py`
```python
GitStatusTool.execute() -> Dict
GitDiffTool.execute(path: str) -> Dict
GitCommitTool.execute(message: str) -> Dict
GitLogTool.execute(limit: int) -> Dict
```

**Testing Tools:** ✅ IMPLEMENTED in `tools/test_tools.py`
```python
RunTestsTool.execute(pattern: str, verbose: bool) -> Dict
# Auto-detects pytest or unittest
# Parses and displays test results
```

### 10.3 Plugin Architecture (Future)

**Concept:**
```python
class Plugin:
    def register_tools(self) -> List[Dict]:
        """Return tool definitions"""
        
    def execute(self, tool_name: str, args: Dict) -> Dict:
        """Execute tool"""

# Usage
agent.register_plugin(GitPlugin())
agent.register_plugin(DatabasePlugin())
agent.register_plugin(DockerPlugin())
```

### 10.4 Multi-Agent System (Advanced)

**Concept:**
```python
class MainAgent(LocalAgent):
    def __init__(self):
        self.subagents = {
            "coder": CodingAgent(),
            "tester": TestingAgent(),
            "reviewer": ReviewAgent()
        }
    
    def delegate(self, task: str, agent_type: str):
        return self.subagents[agent_type].execute(task)
```

**Use Case:**
```
User: "Add feature X with full testing"

MainAgent:
  1. Delegates to CodingAgent → Writes feature
  2. Delegates to TestingAgent → Writes tests
  3. Delegates to ReviewAgent → Reviews code
  4. Synthesizes results
```

---

## 11. Comparison Matrix

### LocalAgent vs Claude Code vs Alternatives

| Feature | LocalAgent | Claude Code | Cursor | Aider |
|---------|-----------|-------------|--------|-------|
| **Cost** | Free | $20-100/mo | $20/mo | Free |
| **Privacy** | 100% Local | Cloud | Cloud | Cloud/Local |
| **Model** | Any Ollama | Claude 4 | GPT-4/Claude | GPT/Claude/Local |
| **Offline** | ✅ Yes | ❌ No | ❌ No | ⚠️ Partial |
| **Function Calling** | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **Permission System** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **IDE Integration** | ❌ Standalone | ⚠️ Optional | ✅ VSCode | ❌ Standalone |
| **Quality** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Speed** | Varies | Fast | Fast | Fast |
| **Extensible** | ✅ Fully | ❌ No | ⚠️ Limited | ✅ Yes |

---

## 12. Future Enhancements

### Short-term (1-2 months)
- [x] Better context window management ✅
- [x] Improved error recovery ✅
- [x] Session management (save/load conversations) ✅
- [x] Git integration tools ✅
- [x] Test execution tools ✅
- [x] Configuration system ✅
- [x] Streaming responses (experimental) ✅
- [ ] Parallel tool execution
- [ ] File caching system

### Medium-term (3-6 months)
- [ ] Plugin architecture
- [ ] VSCode extension wrapper
- [ ] Web UI (optional)
- [ ] Multi-model support (switch models mid-conversation)
- [ ] Voice input integration

### Long-term (6-12 months)
- [ ] Multi-agent orchestration
- [ ] RAG integration for codebase understanding
- [ ] Fine-tuned models for specific tasks
- [ ] Distributed execution (remote models)
- [ ] Collaborative features (multi-user)

---

## 13. Conclusion

LocalAgent demonstrates that a **Claude Code-like experience is achievable with local models** and relatively simple architecture. The key insights:

### Architecture Principles
✅ **Simplicity wins**: Single main loop, clear tool boundaries
✅ **Safety first**: Permission system, dangerous operation blocking
✅ **User experience**: Rich terminal UI, clear feedback
✅ **Extensibility**: Easy to add tools and capabilities

### Technical Decisions
✅ **Python**: Rapid development, rich ecosystem
✅ **Ollama**: Simple local model serving
✅ **Function calling**: Industry-standard tool protocol
✅ **Rich/prompt_toolkit**: Professional terminal UI

### Trade-offs
⚠️ **Quality vs Cost**: Local models < Claude 4, but free
⚠️ **Speed vs Privacy**: Local = slower but private
⚠️ **Simplicity vs Features**: Focused on core functionality

The architecture is designed to be:
- **Understandable**: Clear component boundaries
- **Maintainable**: Simple patterns, minimal dependencies
- **Extensible**: Easy to add new tools and features
- **Safe**: Multiple layers of protection
- **Practical**: Solves real development tasks

This serves as both a **functional tool** and a **learning platform** for understanding how modern AI coding assistants work.