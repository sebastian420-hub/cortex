# LocalAgent

A Claude Code-like terminal agent supporting both local LLM models (via Ollama) and cloud APIs (DeepSeek, Anthropic). Work with your codebase through natural language with flexible model options.

## Features

- **Flexible Models**: Use local models (Ollama) or cloud APIs (DeepSeek, Anthropic Claude)
- **Cost-Effective**: Choose between free local models or affordable cloud APIs
- **Privacy Options**: Use local models for complete privacy, or cloud APIs for better performance
- **Offline-Capable**: Works without internet when using local models
- **Extensible**: Easy to add new tools and capabilities
- **Safe**: Built-in permission system and dangerous operation blocking
- **Rich Terminal UI**: Beautiful syntax highlighting, markdown rendering, and progress indicators

## Installation

### Prerequisites

- Python 3.8+
- For local models: [Ollama](https://ollama.ai/) installed and running
- For cloud APIs: API keys (see [Cloud API Setup](#cloud-api-setup))

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

#### Local Models (Ollama)

```bash
# Use Llama 3.3 70B (much smarter)
localagent --model llama3.3:70b

# Use Qwen 2.5 (good at coding)
localagent --model qwen2.5:32b

# Use DeepSeek R1 (local via Ollama)
localagent --model deepseek-r1:8b
```

#### Cloud APIs

```bash
# Use DeepSeek Chat (cheapest cloud option, excellent for coding)
localagent --model deepseek-chat

# Use DeepSeek Coder (specialized for coding)
localagent --model deepseek-coder

# Use Claude 3 Haiku (fast and affordable)
localagent --model claude-3-haiku-20240307

# Use Claude 3.5 Sonnet (best quality, similar to Claude Code)
localagent --model claude-3-5-sonnet-20241022
```

### Cloud API Setup

#### DeepSeek API

1. Get your API key from [DeepSeek Platform](https://platform.deepseek.com/)
2. Set environment variable:
   ```bash
   export DEEPSEEK_API_KEY=your_key_here
   ```
3. Use DeepSeek models:
   ```bash
   localagent --model deepseek-chat
   ```

#### Anthropic Claude API

1. Get your API key from [Anthropic Console](https://console.anthropic.com/)
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY=your_key_here
   ```
3. Use Claude models:
   ```bash
   localagent --model claude-3-haiku-20240307
   ```

#### List Available Providers

```bash
localagent --list-providers
```

Shows all available providers, models, and API key status.

### Provider Auto-Detection

LocalAgent automatically detects the provider from the model name:

- Models starting with `deepseek-` → DeepSeek API
- Models starting with `claude-` → Anthropic API
- All others → Ollama (local)

You can also explicitly specify the provider:

```bash
localagent --provider deepseek --model deepseek-chat
```

### Cost Comparison

| Model | Provider | Input/1M | Output/1M | Best For |
|-------|----------|----------|-----------|----------|
| **DeepSeek-V3.2** | DeepSeek | $0.28 | $0.42 | Coding (cheapest) |
| **Claude 3 Haiku** | Anthropic | $0.25 | $1.25 | General coding |
| **Claude 3.5 Sonnet** | Anthropic | $3.00 | $15.00 | Best quality (Claude Code) |
| **Local Models** | Ollama | Free | Free | Privacy, offline use |

*Note: Pricing as of 2024. Check provider websites for current rates.*

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

