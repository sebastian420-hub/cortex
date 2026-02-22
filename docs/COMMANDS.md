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
localagent
```

Starts an interactive REPL session where you can chat with the agent and give it tasks.

### One-Shot Mode

```bash
localagent -p "your task here"
# or
localagent --prompt "your task here"
```

Executes a single task and exits. Useful for automation and scripting.

**Example:**
```bash
localagent -p "list all Python files in the project"
```

---

## Command-Line Options

### Model Selection

```bash
--model <model_name>
-m <model_name>
```

Specify which model to use. Provider is auto-detected from model name. Default is `llama3.2` (Ollama).

**Local Models (Ollama):**
```bash
localagent --model llama3.3:70b
localagent -m qwen2.5:32b
localagent --model deepseek-r1:8b
```

**Cloud Models:**
```bash
# DeepSeek (requires DEEPSEEK_API_KEY)
localagent --model deepseek-chat
localagent --model deepseek-coder

# Anthropic Claude (requires ANTHROPIC_API_KEY)
localagent --model claude-3-haiku-20240307
localagent --model claude-3-5-sonnet-20241022
```

### Provider Selection

```bash
--provider <provider_name>
```

Override provider auto-detection. Options: `ollama`, `deepseek`, `anthropic`.

**Examples:**
```bash
localagent --provider deepseek --model deepseek-chat
localagent --provider anthropic --model claude-3-haiku-20240307
```

### List Providers

```bash
--list-providers
```

Display all available providers, models, and API key status.

**Example:**
```bash
localagent --list-providers
```

### Permission Modes

#### Normal Mode (Default)
```bash
localagent
```
Asks for approval before making changes. Safest option.

#### Auto-Approve Mode
```bash
localagent --auto-approve
```
Automatically approves all actions. **Use with caution!** Recommended only in isolated environments.

#### Plan Mode
```bash
localagent --plan-mode
```
Read-only mode. Agent will analyze and create plans but won't make any changes.

### Configuration File

```bash
--config <path>
-c <path>
```

Load settings from a YAML configuration file.

**Example:**
```bash
localagent --config config.yaml
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
localagent --save-session mywork
localagent -p "add logging" --save-session logging-task
```

#### Load Session
```bash
--load-session <session_name>
```

Resume a previously saved session.

**Example:**
```bash
localagent --load-session mywork
```

#### List Sessions
```bash
--list-sessions
```

Show all saved sessions.

**Example:**
```bash
localagent --list-sessions
```

### Project Directory

```bash
--project-dir <path>
```

Specify the project directory. Defaults to current working directory.

**Example:**
```bash
localagent --project-dir ~/my-project
```

### Output Format

```bash
--output-format <format>
-o <format>
```

Control output format. Options: `text` (default), `json`, `stream-json`.

**Examples:**
```bash
localagent -o json -p "list files"
localagent --output-format stream-json
```

### Streaming

```bash
--streaming
```

Enable streaming responses (experimental). Shows responses as they're generated.

**Example:**
```bash
localagent --streaming
```

### Hooks Configuration

#### Disable Hooks
```bash
--no-hooks
```

Disable the hook system entirely.

**Example:**
```bash
localagent --no-hooks
```

#### Custom Hooks Config
```bash
--hooks-config <path>
```

Load hooks from a separate configuration file.

**Example:**
```bash
localagent --hooks-config hooks.yaml
```

### Version

```bash
--version
```

Display version information and exit.

**Example:**
```bash
localagent --version
```

---

## Interactive Session Commands

While in an interactive session, you can use these commands (prefixed with `/`):

### `/help`

Display help information for available commands.

```bash
> /help
```

### `/memory [search|clear]`

Manage the semantic memory (Vector Database).

**Subcommands:**
- `search <query>`: Search for semantically similar memories in the **current session**.
- `search --global <query>`: Search across **all past sessions** in this project.
- `clear`: Permanently delete the entire semantic database for this project.

**Examples:**
```bash
> /memory search "database port"
> /memory search --global "reason for choosing fastapi"
> /memory clear
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
localagent

# One-shot task
localagent -p "add logging to api.py"

# Use different model
localagent --model llama3.3:70b -p "refactor user service"

# Plan mode (read-only)
localagent --plan-mode -p "analyze code structure"

# With configuration file
localagent --config my-config.yaml
```

### Session Management Examples

```bash
# Save session
localagent --save-session feature-work

# Load and continue
localagent --load-session feature-work

# List all sessions
localagent --list-sessions
```

### Cloud API Examples

```bash
# Use DeepSeek Chat (cheapest cloud option)
export DEEPSEEK_API_KEY=your_key_here
localagent --model deepseek-chat -p "refactor authentication module"

# Use Claude 3 Haiku (fast and affordable)
export ANTHROPIC_API_KEY=your_key_here
localagent --model claude-3-haiku-20240307 -p "write tests for user service"

# Use Claude 3.5 Sonnet (best quality, similar to Claude Code)
localagent --model claude-3-5-sonnet-20241022 -p "optimize database queries"

# List available providers and check API key status
localagent --list-providers
```

### Automation Examples

```bash
# JSON output for scripting
localagent -o json -p "list all Python files" | jq

# One-shot with auto-approve (use carefully!)
localagent --auto-approve -p "format all Python files"

# With custom project directory
localagent --project-dir ~/projects/myapp -p "run tests"
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

### Task Delegation

- **`task`** - Delegate complex tasks to sub-agents
  - Parameters: `description` (required), `context` (optional)
  - Example: "create a complete authentication system"

---

## Quick Reference

### Common Command Patterns

```bash
# Basic usage
localagent

# One-shot with model
localagent -m llama3.3:70b -p "task"

# With config
localagent -c config.yaml

# Save session
localagent --save-session name

# Load session
localagent --load-session name

# JSON output
localagent -o json -p "task"

# Plan mode
localagent --plan-mode

# Auto-approve (dangerous!)
localagent --auto-approve
```

### Interactive Commands

```
/help              # Show help
/clear             # Clear history
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
