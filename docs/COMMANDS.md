# Cortex Commands Reference

Complete guide to using Cortex commands and options.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Command-Line Options](#command-line-options)
- [Interactive Session Commands](#interactive-session-commands)
- [Configuration](#configuration)
- [Examples](#examples)
- [Available Tools](#available-tools)

---

## Basic Usage

### Start Interactive Session

```bash
cortex
```

Starts an interactive REPL session where you can chat with the agent and give it tasks.

### One-Shot Mode

```bash
cortex -p "your task here"
# or
cortex --prompt "your task here"
```

Executes a single task and exits. Useful for automation and scripting. The exit code is 0 only if the
model finished its turn; it is 1 if the turn failed, hit the iteration limit or was stopped by the loop
guard. It does not say whether the work is correct: run your tests afterwards.

**Example:**
```bash
cortex -p "list all Python files in the project"
```

### Unattended Runs (`cortex run`)

```bash
cortex run --task "fix the failing test" --verify "python -m pytest -q" --json
```

Does one task with nobody watching, on its own git branch in a separate worktree, and checks it
with your command. The branch is kept only if the check passed. Your checkout is never touched.
The exit code is 0 when the run completed as asked (`passed`, or `unverified` because you said
`--no-verify`), 1 when it ran and did not succeed, 2 when it could not start. Full description,
the JSON result and the safety notes: [HEADLESS.md](HEADLESS.md).

| Option | Meaning |
|--------|---------|
| `--task TEXT` or `--task-file FILE` | what to do (one is required) |
| `--verify COMMAND` or `--no-verify` | how the work is checked (one is required) |
| `--retries N` (1), `--max-steps N` (40), `--max-tokens N` (1000000), `--timeout S` (3600), `--verify-timeout S` (600) | budgets; 0 = no limit |
| `--project-dir DIR`, `--base REF`, `--branch NAME` | where it runs and what it starts from |
| `--keep-failed` | keep the branch of a run that did not succeed |
| `--protect GLOB` | a path the run must not change (repeatable); changing one fails the run |
| `--require-sandbox` | refuse to run unless `command_sandbox` confines commands |
| `--model`, `--provider`, `--config` | as for `cortex` |
| `--price-in`, `--price-out` | dollars per million tokens, to report a cost |
| `--json`, `--output FILE`, `--quiet` | the result as JSON on stdout; also to a file; hide the agent's commentary |

---

## Command-Line Options

### Model Selection

```bash
--model <model_name>
-m <model_name>
```

Specify which model to use. Provider is auto-detected from model name. Default is `moonshotai/kimi-k2.5` (via OpenRouter).

**Cloud Models (OpenRouter):**
Cortex uses OpenRouter by default. Set the `OPENROUTER_API_KEY` environment variable.
```bash
cortex --model moonshotai/kimi-k2.5
cortex -m deepseek/deepseek-r1
```

**Local Models (Ollama):**
```bash
cortex --model llama3.3:70b
cortex -m qwen2.5:32b
cortex --model deepseek-r1:8b
```

**Specific Cloud Providers:**
```bash
# DeepSeek (requires DEEPSEEK_API_KEY)
cortex --model deepseek-chat

# Anthropic Claude (requires ANTHROPIC_API_KEY)
cortex --model claude-4-6-sonnet
cortex --model claude-4-6-opus
```

### Provider Selection

```bash
--provider <provider_name>
```

Override provider auto-detection. Options: `ollama`, `deepseek`, `anthropic`, `openrouter`, `openai`
(any OpenAI-compatible server such as vLLM or llama.cpp; set `OPENAI_BASE_URL`, see
[DEPLOYMENT.md](DEPLOYMENT.md)).

**Examples:**
```bash
cortex --provider deepseek --model deepseek-chat
cortex --provider anthropic --model claude-3-haiku-20240307
OPENAI_BASE_URL=http://gpu-box:8000/v1 cortex --provider openai --model <model>
```

### List Providers

```bash
--list-providers
```

Display all available providers, models, and API key status.

**Example:**
```bash
cortex --list-providers
```

### Permission Modes

#### Normal Mode (Default)
```bash
cortex
```
Asks for approval before making changes. Safest option.

#### Auto-Approve Mode
```bash
cortex --auto-approve
```
Automatically approves all actions. **Use with caution!** Recommended only in isolated environments.

#### Plan Mode
```bash
cortex --plan-mode
```
Read-only mode. Agent will analyze and create plans but won't make any changes.

### Optional Features

These are off until you ask for them.

```bash
cortex --planning        # the planning tools: the model writes steps, Cortex runs them in order
cortex --memory          # layered session memory (long-term memory also needs the memory extra
                         #   and semantic_memory.enabled in the config file)
cortex --metacognition   # experimental: a confidence/urgency/tone note in the prompt
```

`--enhanced` is a deprecated alias for `--planning --memory`.

### Configuration File

```bash
--config <path>
-c <path>
```

Load settings from a YAML configuration file.

**Example:**
```bash
cortex --config config.yaml
```

**Configuration file format:**
```yaml
model: llama3.3:70b
permission_mode: normal
max_iterations: 20
max_tokens: 100000
keep_recent_messages: 20
auto_save: false
# provider: null  # Auto-detected, or specify: "ollama", "deepseek", "anthropic"
```

**Note:** API keys are read from environment variables, not config files:
- `DEEPSEEK_API_KEY` for DeepSeek models
- `ANTHROPIC_API_KEY` for Anthropic/Claude models

### Session Management

#### Save Session
```bash
--save-session <session_name>
```

Save the current conversation and state for later use.

**Example:**
```bash
cortex --save-session mywork
cortex -p "add logging" --save-session logging-task
```

#### Load Session
```bash
--load-session <session_name>
```

Resume a previously saved session.

**Example:**
```bash
cortex --load-session mywork
```

#### List Sessions
```bash
--list-sessions
```

Show all saved sessions.

**Example:**
```bash
cortex --list-sessions
```

### Project Directory

```bash
--project-dir <path>
```

Specify the project directory. Defaults to current working directory.

**Example:**
```bash
cortex --project-dir ~/my-project
```

### Output Format

```bash
--output-format <format>
-o <format>
```

Control output format. Options: `text` (default), `json`, `stream-json`.

**Examples:**
```bash
cortex -o json -p "list files"
cortex --output-format stream-json
```

### Streaming

```bash
--streaming
```

Enable streaming responses (experimental). Shows responses as they're generated.

**Example:**
```bash
cortex --streaming
```

### Hooks Configuration

#### Disable Hooks
```bash
--no-hooks
```

Disable the hook system entirely.

**Example:**
```bash
cortex --no-hooks
```

#### Custom Hooks Config
```bash
--hooks-config <path>
```

Load hooks from a separate configuration file.

**Example:**
```bash
cortex --hooks-config hooks.yaml
```

### Version

```bash
--version
```

Display version information and exit.

**Example:**
```bash
cortex --version
```

---

## Interactive Session Commands

While in an interactive session, you can use these commands (prefixed with `/`):

### `/help`

Display help information for available commands.

```bash
> /help
```

### `/memory [list|add|edit|delete|search|clear]`

See and control what Cortex keeps for future sessions. Long-term memory needs the `memory` extra
(`pip install ".[memory]"`) and `semantic_memory.enabled: true`; without it these commands say
so. Only decisions, conventions, facts and summaries of solved problems are kept, not your
requests or error messages.

**Subcommands:**
- `list`: everything stored, with kind, source, confidence and when it was last confirmed.
- `add <text>`: remember something as your own instruction (it does not fade over time).
- `edit <id> <text>`: change a stored memory. An id prefix is enough.
- `delete <id>` (or `forget <id>`): remove one memory.
- `search <query>`: search the **current session**; `search --global <query>` searches **all past sessions** in this project.
- `clear`: permanently delete the entire long-term memory for this project.

**Examples:**
```bash
> /memory list
> /memory add Run the tests with pytest -x
> /memory edit mem_3fa9 Run the tests with pytest -x -q
> /memory delete mem_3fa9
> /memory search --global "reason for choosing fastapi"
```

The model can also store a memory itself with its `remember` tool.

### `/undo`, `/redo`

Restore the whole project to how it was before your last request, including changes made by
shell commands. Needs the project to be in a git repository. Cortex takes a snapshot before the
first change of each request, on a private git ref; your branch, index and stash are not touched.

- `/undo` restores the files that differ and removes files the request created. Run it again to
  step back one more request.
- `/redo` brings back what the last `/undo` removed.

Not covered: files git ignores (build output, virtual environments), and the branch position if a
command committed or reset (Cortex prints the `git reset --soft` that moves it back).

```bash
> /undo
> /redo
```

### `/rollback`

Restore the exact bytes of every file the last request created, edited or overwrote with Cortex's
file tools. Works without git, but does not see changes made by shell commands (use `/undo` for
those). `/transactions` shows the transaction statistics.

### `/gym`

A practice session in a scratch copy of the project.

```bash
> /gym --bench list                      # the benchmark tasks
> /gym --bench bug-sum-to-off-by-one     # a verified session: succeeds only if the task's tests pass
> /gym --task "Fix bug" --goal "..."     # free-form: reported as unchecked, not as success
```

### `/clear`

Clear the conversation history (keeps system prompt).

```bash
> /clear
```

### `/mode [normal|auto|plan]`

Change the permission mode during the session.

**Examples:**
```bash
> /mode normal      # Switch to normal mode
> /mode auto        # Switch to auto-approve mode
> /mode plan        # Switch to plan mode
> /mode             # Show current mode
```

### `/project`

Display project information including:
- Project path
- Current permission mode
- Model being used
- Session duration
- Token count

```bash
> /project
```

### `/save [session_name]`

Save the current session. If no name is provided, uses a timestamp-based name.

**Examples:**
```bash
> /save mywork
> /save              # Auto-generates name like "session_20240101_120000"
```

### `/load <session_name>`

Load a previously saved session.

**Example:**
```bash
> /load mywork
```

### `/sessions`

List all saved sessions.

```bash
> /sessions
```

### `/exit`

Exit the Cortex session.

```bash
> /exit
```

---

## Configuration

### Configuration File Location

You can create a configuration file (YAML format) to set default options:

**Example `config.yaml`:**
```yaml
model: llama3.3:70b
permission_mode: normal
max_iterations: 20
max_tokens: 100000
keep_recent_messages: 20
auto_save: false
output_format: text
hooks_enabled: true
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | `llama3.2` | Ollama model to use |
| `permission_mode` | string | `normal` | Permission mode: `normal`, `auto_approve`, or `plan` |
| `max_iterations` | integer | `15` | Maximum agent loop iterations |
| `max_tokens` | integer | `100000` | Maximum tokens in conversation |
| `keep_recent_messages` | integer | `20` | Number of recent messages to keep |
| `auto_save` | boolean | `false` | Automatically save sessions |
| `output_format` | string | `text` | Output format: `text`, `json`, or `stream-json` |
| `hooks_enabled` | boolean | `true` | Enable hook system |
| `semantic_memory` | object | N/A | Semantic memory configuration (see below) |

### Semantic Memory Configuration

You can tune the vector database behavior in your `config.yaml`:

```yaml
semantic_memory:
  enabled: true
  persist_directory: ".cortex/semantic_db"
  collection_name: "cortex_semantic_memory"
  clear_on_init: false
```

### Project Context Files

Cortex automatically reads project context from these files (in order of priority):

1. `AGENT.md` - Project-specific instructions for the agent
2. `CLAUDE.md` - Alternative project context file
3. `README.md` - Standard project readme

Create an `AGENT.md` file in your project root to provide context:

```markdown
# My Project

## Tech Stack
- Python 3.11 + FastAPI
- PostgreSQL + SQLAlchemy

## Code Style
- Use type hints everywhere
- Follow PEP 8 strictly
- Write docstrings for all functions

## Testing
- Use pytest
- Aim for 80%+ coverage
```

---

## Examples

### Basic Examples

```bash
# Start interactive session
cortex

# One-shot task
cortex -p "add logging to api.py"

# Use different model
cortex --model llama3.3:70b -p "refactor user service"

# Plan mode (read-only)
cortex --plan-mode -p "analyze code structure"

# With configuration file
cortex --config my-config.yaml
```

### Session Management Examples

```bash
# Save session
cortex --save-session feature-work

# Load and continue
cortex --load-session feature-work

# List all sessions
cortex --list-sessions
```

### Cloud API Examples

```bash
# Use OpenRouter (Default provider for moonshotai/kimi-k2.5)
export OPENROUTER_API_KEY=your_key_here
cortex

# Use DeepSeek Chat
export DEEPSEEK_API_KEY=your_key_here
cortex --model deepseek-chat -p "refactor authentication module"

# Use Claude 4.6 Sonnet
export ANTHROPIC_API_KEY=your_key_here
cortex --model claude-4-6-sonnet -p "optimize database queries"
```

### Automation Examples

```bash
# JSON output for scripting
cortex -o json -p "list all Python files" | jq

# One-shot with auto-approve (use carefully!)
cortex --auto-approve -p "format all Python files"

# With custom project directory
cortex --project-dir ~/projects/myapp -p "run tests"
```

### Interactive Session Examples

```
> add type hints to utils.py
> read the README file
> search for all uses of the User class
> run the test suite
> /mode plan
> explain how authentication works
> /save current-work
> /exit
```

---

## Available Tools

The agent has access to these tools (used automatically based on your requests):

### File Operations

- **`read_file`** - Read file contents
  - Parameters: `path` (required)
  - Example: "read api.py"

- **`write_file`** - Write or overwrite files
  - Parameters: `path` (required), `content` (required)
  - Example: "create a new file called config.py"

### Command Execution

- **`execute_command`** - Run shell commands
  - Parameters: `command` (required), `reason` (required)
  - Example: "install dependencies", "run tests"

### File Discovery

- **`list_files`** - List files in directory
  - Parameters: `path` (optional), `pattern` (optional)
  - Example: "list all Python files", "show files in src/"

- **`search_files`** - Search for text across files
  - Parameters: `query` (required), `file_pattern` (optional)
  - Example: "find where User class is defined", "search for 'authenticate'"

### Git Integration

- **`git_status`** - Show git status
  - Example: "show git status"

- **`git_diff`** - Show git diff
  - Parameters: `path` (optional)
  - Example: "show changes", "show diff for api.py"

- **`git_commit`** - Commit changes
  - Parameters: `message` (required)
  - Example: "commit with message 'Add logging'"

- **`git_log`** - Show recent commits
  - Parameters: `limit` (optional, default: 10)
  - Example: "show last 5 commits"

### Testing

- **`run_tests`** - Run test suite
  - Parameters: `pattern` (optional), `verbose` (optional)
  - Example: "run tests", "run tests in test_auth.py"

### Code Analysis (AST)

- **`ast_search`** - Enhanced structural search
  - Parameters: `pattern` (required), `search_type` (optional), `path` (optional)
  - Example: "search for function definitions matching 'parse_'", "find all classes"

- **`ast_extract`** - Extract semantic structures
  - Parameters: `path` (required), `extract_type` (optional: function, class, import)
  - Example: "extract all functions from models.py", "show imports in api.py"

- **`ast_analyze`** - Analyze code quality and complexity
  - Parameters: `path` (required), `analysis_type` (optional: complexity, dependencies)
  - Example: "analyze complexity of core.py", "show dependencies for main.py"

- **`ast_refactor`** - Surgical AST-driven refactoring
  - Parameters: `file_path` (required), `action` (required), `symbol_name` (required), `new_name` (optional), `new_content` (optional)
  - Example: "rename function 'old_name' to 'new_name'", "replace class body for 'User'"

### Task Delegation

- **`task`** - Delegate complex tasks to sub-agents
  - Parameters: `description` (required), `context` (optional)
  - Example: "create a complete authentication system"

---

## Quick Reference

### Common Command Patterns

```bash
# Basic usage
cortex

# One-shot with model
cortex -m llama3.3:70b -p "task"

# With config
cortex -c config.yaml

# Save session
cortex --save-session name

# Load session
cortex --load-session name

# JSON output
cortex -o json -p "task"

# Plan mode
cortex --plan-mode

# Auto-approve (dangerous!)
cortex --auto-approve
```

### Interactive Commands

```
/help              # Show help
/clear             # Clear history
/undo, /redo       # Restore the project to before the last request (git), or reverse that
/rollback          # Undo the last request's file edits (no git needed)
/memory [sub]      # list, add, edit, delete, search, clear
/gym --bench <id>  # A verified practice session on a benchmark task
/mode [mode]       # Change mode
/project           # Show project info
/save [name]       # Save session
/load <name>       # Load session
/sessions          # List sessions
/exit              # Exit
```

---

## Tips

1. **Start with plan mode** for complex tasks to see what the agent will do before making changes
2. **Use sessions** to save your work and resume later
3. **Create AGENT.md** in your project root to give the agent context about your codebase
4. **Use JSON output** when integrating with scripts or automation
5. **Be specific** in your requests - the more context you provide, the better the results

---

## Troubleshooting

### Ollama Not Found

If you see "Ollama Not Found" error:

1. Make sure Ollama is running:
   ```bash
   ollama serve
   ```

2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```

### Permission Denied

If you get permission errors:
- Check file permissions
- Use `--auto-approve` only in safe environments
- Verify you have write access to the project directory

### Model Not Found

If the specified model isn't available:
```bash
# List available models
ollama list

# Pull the model you need
ollama pull llama3.3:70b
```

---

For more information, see the main [README.md](../README.md) file.
