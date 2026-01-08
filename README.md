# LocalAgent

A Claude Code-like terminal agent using local LLM models via Ollama. Work with your codebase through natural language, all running locally on your machine.

## Features

- **Privacy-First**: All processing happens locally - no data sent to external APIs
- **Cost-Effective**: Free to use (only requires local compute)
- **Offline-Capable**: Works without internet connection
- **Extensible**: Easy to add new tools and capabilities
- **Safe**: Built-in permission system and dangerous operation blocking
- **Rich Terminal UI**: Beautiful syntax highlighting, markdown rendering, and progress indicators

## Installation

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- A local LLM model (e.g., `llama3.2`, `llama3.3:70b`)

### Install LocalAgent

```bash
# Clone the repository
git clone https://github.com/yourusername/localagent.git
cd localagent

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Pull a Model

```bash
# Start Ollama (if not already running)
ollama serve

# Pull a model (in a new terminal)
ollama pull llama3.2          # 3B - Fast, good for testing
# OR
ollama pull llama3.3:70b      # 70B - Much smarter, needs good GPU
# OR
ollama pull qwen2.5:32b       # 32B - Good balance
```

## Quick Start

```bash
# Navigate to your project
cd ~/my-project

# Start LocalAgent
localagent

# Or use one-shot mode
localagent -p "add logging to api.py"
```

## Usage

### Interactive Mode

```bash
localagent

> add logging to api.py
> create a README file
> fix the bug in line 45 of database.py
> explain how authentication works
> write tests for the user service
```

### One-Shot Mode

```bash
localagent -p "list all Python files"
localagent -p "add type hints to utils.py"
```

### Different Models

```bash
# Use Llama 3.3 70B (much smarter)
localagent --model llama3.3:70b

# Use Qwen 2.5 (good at coding)
localagent --model qwen2.5:32b
```

### Permission Modes

```bash
# Normal mode (asks for everything) - DEFAULT
localagent

# Auto-approve mode (dangerous! use in containers)
localagent --auto-approve

# Plan mode (read-only, no changes)
localagent --plan-mode
```

### Session Management

```bash
# Save current session
localagent --save-session mywork

# Load a saved session
localagent --load-session mywork

# List all sessions
localagent --list-sessions
```

### Configuration File

Create a `config.yaml`:

```yaml
model: llama3.3:70b
permission_mode: normal
max_iterations: 20
max_tokens: 100000
keep_recent_messages: 20
```

Then use it:

```bash
localagent --config config.yaml
```

## In-Session Commands

While in interactive mode, you can use these commands:

- `/help` - Show help
- `/clear` - Clear conversation history
- `/mode [normal|auto|plan]` - Change permission mode
- `/project` - Show project info
- `/save [name]` - Save current session
- `/load [name]` - Load a saved session
- `/sessions` - List saved sessions
- `/exit` - Exit LocalAgent

## Available Tools

LocalAgent comes with a comprehensive set of tools:

### File Operations
- `read_file` - Read file contents
- `write_file` - Write or overwrite files

### Command Execution
- `execute_command` - Run shell commands

### File Discovery
- `list_files` - List files in directory
- `search_files` - Search for text across files

### Git Integration
- `git_status` - Show git status
- `git_diff` - Show git diff
- `git_commit` - Commit changes
- `git_log` - Show recent commits

### Testing
- `run_tests` - Run test suite (auto-detects pytest/unittest)

## Project Configuration

Create an `AGENT.md` file in your project root to give the agent context:

```markdown
# My Project

## Tech Stack
- Python 3.11 + FastAPI
- PostgreSQL + SQLAlchemy
- Redis for caching

## Architecture
- `api/`: FastAPI routes and schemas
- `service/`: Business logic layer
- `repository/`: Database access

## Code Style
- Use type hints everywhere
- Follow PEP 8 strictly
- Write docstrings for all functions

## Testing
- Use pytest
- Write tests BEFORE implementation
- Aim for 80%+ coverage
```

The agent will automatically read this and follow your conventions!

## Architecture

LocalAgent is organized into clean, modular components:

```
localagent/
├── agent.py          # Main agent class
├── cli.py            # Command-line interface
├── config.py         # Configuration management
├── models.py         # Data models
├── tools/            # Tool implementations
├── core/             # Core functionality (security, context, streaming)
├── ui/               # User interface components
├── storage/          # Session and history management
└── utils/            # Utilities (errors, validation)
```

## Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Run Tests

```bash
pytest tests/ -v --cov=localagent
```

### Code Quality

```bash
# Format code
black localagent tests

# Lint
flake8 localagent tests

# Type check
mypy localagent
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by Claude Code and similar AI coding assistants
- Built with [Ollama](https://ollama.ai/) for local LLM inference
- Uses [Rich](https://github.com/Textualize/rich) for beautiful terminal UI

