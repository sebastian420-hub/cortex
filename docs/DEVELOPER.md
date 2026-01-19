# Cortex Developer Guide

This guide is for developers who want to contribute to Cortex or understand its internals.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [Core Components](#core-components)
5. [Adding Features](#adding-features)
6. [Testing](#testing)
7. [Code Style](#code-style)
8. [Contributing](#contributing)

---

## Architecture Overview

Cortex follows a layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Layer                          │
│   (main.py, cli/, argument parsing, user interaction)   │
├─────────────────────────────────────────────────────────┤
│                     Agent Layer                         │
│   (agent.py - conversation loop, tool orchestration)    │
├─────────────────────────────────────────────────────────┤
│                     Core Layer                          │
│   ┌─────────────┬──────────────┬────────────────────┐  │
│   │  Providers  │ Conversation │     Routing        │  │
│   │  (LLM APIs) │  (history)   │ (model selection)  │  │
│   ├─────────────┼──────────────┼────────────────────┤  │
│   │   Memory    │   Planning   │   Orchestration    │  │
│   │  (context)  │  (multi-step)│ (model delegation) │  │
│   └─────────────┴──────────────┴────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     Tools Layer                         │
│   (file_tools, command_tools, git_tools, ast/, etc.)   │
├─────────────────────────────────────────────────────────┤
│                   Utilities Layer                       │
│   (errors, timeouts, security, cache, config)          │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Input → CLI → Agent._process_message()
                        ↓
              Route Request (optional)
                        ↓
              Build Messages + System Prompt
                        ↓
              Call LLM Provider
                        ↓
              Parse Response (text or tool calls)
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
   Text Response               Tool Call(s)
        ↓                               ↓
   Display to User            Execute Tool(s)
                                        ↓
                              Add Result to History
                                        ↓
                              Loop (call LLM again)
```

---

## Project Structure

```
cortex/
├── __init__.py           # Package exports
├── agent.py              # Main Cortex agent class (1400+ lines)
├── models.py             # Data models (PermissionMode, etc.)
├── config.py             # Configuration management
│
├── core/                 # Core functionality
│   ├── providers.py      # LLM provider abstraction (Anthropic, OpenRouter, etc.)
│   ├── conversation.py   # Conversation history management
│   ├── memory.py         # Memory bank for session context
│   ├── planning.py       # Multi-step planning system
│   ├── orchestration.py  # Model delegation/orchestration
│   ├── security.py       # Path validation, security checks
│   ├── transaction.py    # File backup/recovery
│   │
│   ├── routing/          # Model routing system
│   │   ├── orchestrator.py   # Main routing logic
│   │   ├── task_analysis.py  # Task complexity analysis
│   │   └── decision.py       # Routing decision types
│   │
│   ├── prompts/          # Prompt generation
│   │   ├── system.py     # Base system prompts
│   │   ├── builder.py    # Dynamic prompt builder
│   │   └── profiles.py   # Model capability profiles
│   │
│   ├── recovery/         # Error recovery system
│   │   ├── checkpoint.py # State checkpointing
│   │   └── health.py     # Health monitoring
│   │
│   └── models/           # Model management
│       └── registry.py   # Model registry
│
├── tools/                # Tool implementations
│   ├── __init__.py       # Tool exports, TOOLS constant
│   ├── base.py           # Tool base class
│   ├── registry.py       # Tool registry (1000 lines)
│   ├── file_tools.py     # Read/write files
│   ├── edit_tool.py      # Edit files
│   ├── command_tools.py  # Execute commands
│   ├── grep_tool.py      # Search content
│   ├── glob_tool.py      # Find files
│   ├── git_tools.py      # Git operations
│   ├── web_tools.py      # Web fetch/search
│   ├── skill_tools.py    # Skill management
│   ├── planning_tools.py # Planning tools
│   ├── delegation_tools.py # Model delegation
│   │
│   └── ast/              # AST-based code analysis
│       ├── ast_search_tool.py
│       ├── ast_extract_tool.py
│       ├── ast_analyze_tool.py
│       └── integration.py
│
├── ui/                   # User interface
│   ├── __init__.py
│   └── plan_progress.py  # Planning progress display
│
├── cache/                # Caching system
│   ├── __init__.py
│   └── file_cache.py     # File content cache
│
├── utils/                # Utilities
│   ├── errors.py         # Error types and responses
│   ├── timeouts.py       # Timeout configuration
│   └── formatting.py     # Output formatting
│
└── cli/                  # CLI components
    └── main.py           # Entry point
```

---

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- An API key (Anthropic, OpenAI, or OpenRouter)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/cortex.git
cd cortex

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode
pip install -e .

# Install dev dependencies
pip install -r requirements-dev.txt
pip install -r requirements-test.txt
```

### Environment Setup

```bash
# Copy example env file
cp .env.example .env

# Edit with your API keys
# ANTHROPIC_API_KEY=your-key-here
# OPENROUTER_API_KEY=your-key-here  # optional
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cortex --cov-report=html

# Run specific test file
pytest tests/test_tools.py -v

# Run tests matching pattern
pytest tests/ -k "test_read" -v
```

### Code Quality

```bash
# Format code
black cortex tests

# Lint
flake8 cortex tests --max-line-length=100

# Type check
mypy cortex --ignore-missing-imports
```

---

## Core Components

### 1. Agent (`agent.py`)

The main `Cortex` class orchestrates everything:

```python
class Cortex:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str = None,
        provider: str = "anthropic",
        project_dir: Path = None,
        permission_mode: str = "normal",
        ...
    ):
        # Initialize provider, tools, conversation, etc.

    def chat(self, user_message: str) -> str:
        """Main entry point for user messages."""
        return self._process_message(user_message)

    def _process_message(self, user_message: str) -> str:
        """
        Core message processing loop:
        1. Route request (if enabled)
        2. Add message to history
        3. Call LLM
        4. Handle response (text or tool calls)
        5. Loop if tool calls
        """
```

**Key methods:**
- `chat()` - Public API for sending messages
- `_process_message()` - Main conversation loop
- `_execute_tool()` - Execute a single tool
- `_build_messages()` - Prepare messages for API
- `route_request()` - Route to optimal model
- `switch_model()` - Change active model

### 2. Providers (`core/providers.py`)

Abstract interface for LLM providers:

```python
class ModelProvider(ABC):
    @abstractmethod
    def chat(self, model, messages, tools=None) -> Dict[str, Any]:
        """Send chat request."""
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models."""
        pass

class AnthropicProvider(ModelProvider):
    """Anthropic Claude API."""

class OpenRouterProvider(ModelProvider):
    """OpenRouter API (multiple models)."""

class OpenAIProvider(ModelProvider):
    """OpenAI API."""
```

### 3. Tools (`tools/`)

All tools inherit from `Tool` base class:

```python
class Tool(ABC):
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        pass
```

Tools are registered in `tools/registry.py` and exported via `tools/__init__.py`.

**Adding a new tool:**
1. Create tool class in `tools/`
2. Add schema to registry
3. Register in `register_builtins()`
4. Update `TOOLS` list in `__init__.py`

### 4. Conversation (`core/conversation.py`)

Manages conversation history:

```python
class ConversationManager:
    def add_user_message(self, content: str)
    def add_assistant_message(self, content: str, tool_calls=None)
    def add_tool_result(self, tool_use_id: str, result: Dict)
    def get_messages(self) -> List[Dict]
    def summarize_if_needed(self)  # Compress old messages
```

### 5. Routing (`core/routing/`)

Pre-conversation model selection:

```python
class RoutingOrchestrator:
    def route_request(
        self,
        request: str,
        context: Optional[RoutingContext] = None
    ) -> RoutingDecision:
        """
        Analyze task and select optimal model.
        Returns model name and reasoning.
        """
```

---

## Adding Features

### Adding a New Tool

1. **Create tool file:**

```python
# cortex/tools/my_tool.py
from .base import Tool
from typing import Dict, Any

class MyTool(Tool):
    def execute(self, param: str) -> Dict[str, Any]:
        # Implementation
        return self._create_success(result="done")

MY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Does something useful",
        "parameters": {...}
    }
}
```

2. **Register in registry:**

```python
# cortex/tools/registry.py, in register_builtins()
from .my_tool import MyTool

self.register(
    name="my_tool",
    tool_class=MyTool,
    schema=MY_TOOL_SCHEMA
)
```

3. **Export in `__init__.py`:**

```python
# cortex/tools/__init__.py
from .my_tool import MyTool, MY_TOOL_SCHEMA

TOOLS.append(MY_TOOL_SCHEMA)
```

4. **Add tests:**

```python
# tests/test_my_tool.py
def test_my_tool_basic():
    tool = MyTool(project_dir=Path("."), permission_mode="auto")
    result = tool.execute(param="test")
    assert result["success"] is True
```

### Adding a New Provider

1. **Create provider class:**

```python
# cortex/core/providers.py
class NewProvider(ModelProvider):
    def __init__(self, api_key: str):
        self.client = SomeClient(api_key)

    def chat(self, model, messages, tools=None):
        # Convert to provider format
        # Call API
        # Convert response back
        pass

    def list_models(self):
        return ["model-1", "model-2"]
```

2. **Register in factory:**

```python
# cortex/core/providers.py
class ProviderFactory:
    @staticmethod
    def create(provider_name: str, api_key: str) -> ModelProvider:
        if provider_name == "new_provider":
            return NewProvider(api_key)
        # ...
```

### Adding a CLI Command

1. **Add to argument parser:**

```python
# cortex/cli/main.py
parser.add_argument(
    "--my-option",
    action="store_true",
    help="Enable my feature"
)
```

2. **Handle in main:**

```python
def main():
    args = parse_args()
    if args.my_option:
        # Handle option
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_agent.py         # Agent tests
├── test_tools.py         # Tool tests
├── test_providers.py     # Provider tests
├── test_conversation.py  # Conversation tests
├── test_registry.py      # Registry tests
└── performance/          # Performance benchmarks
    └── test_benchmarks.py
```

### Writing Tests

```python
import pytest
from pathlib import Path
from cortex.tools.file_tools import ReadFileTool

@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project with test files."""
    (tmp_path / "test.py").write_text("print('hello')")
    return tmp_path

def test_read_file(temp_project):
    tool = ReadFileTool(
        project_dir=temp_project,
        permission_mode="auto"
    )
    result = tool.execute(path="test.py")
    assert result["success"] is True
    assert "hello" in result["content"]
```

### Mocking LLM Calls

```python
from unittest.mock import patch, MagicMock

@patch('cortex.core.providers.AnthropicProvider.chat')
def test_agent_chat(mock_chat, temp_project):
    mock_chat.return_value = {
        "message": {"content": "Hello!"},
        "stop_reason": "end_turn"
    }

    agent = Cortex(project_dir=temp_project)
    response = agent.chat("Hi")

    assert "Hello" in response
    mock_chat.assert_called_once()
```

---

## Code Style

### Formatting

- Use **Black** for formatting (line length 100)
- Use **isort** for import sorting
- Follow **PEP 8** guidelines

### Type Hints

```python
# Good
def process_file(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    ...

# Better (use TypedDict for complex returns)
class FileResult(TypedDict):
    content: str
    lines: int
    size: int

def process_file(path: str) -> FileResult:
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def complex_function(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    Brief description of function.

    Longer description if needed. Explain what the function does,
    any side effects, and important details.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Dictionary containing:
        - success: Whether operation succeeded
        - result: The computed result

    Raises:
        ValueError: If param1 is empty
        SecurityError: If path is outside project

    Example:
        >>> result = complex_function("test", param2=20)
        >>> print(result["success"])
        True
    """
```

### Error Handling

```python
# Use standardized error responses
from cortex.utils.errors import create_error_response, ErrorType

def my_function():
    try:
        # Operation
        pass
    except FileNotFoundError:
        return create_error_response(
            "File not found",
            ErrorType.NOT_FOUND,
            {"path": path}
        )
    except PermissionError:
        return create_error_response(
            "Permission denied",
            ErrorType.SECURITY,
            {"path": path}
        )
```

---

## Contributing

### Workflow

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/my-feature`
3. **Make changes** with tests
4. **Run checks**: `black . && flake8 && pytest`
5. **Commit**: `git commit -m "feat: add my feature"`
6. **Push**: `git push origin feature/my-feature`
7. **Open PR** against `main`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new weather tool
fix: handle empty file in read_file
docs: update plugin development guide
refactor: simplify conversation manager
test: add tests for routing system
chore: update dependencies
```

### PR Checklist

- [ ] Tests pass (`pytest tests/`)
- [ ] Code formatted (`black --check .`)
- [ ] No lint errors (`flake8`)
- [ ] Type hints added for new code
- [ ] Docstrings for public functions
- [ ] CHANGELOG updated (if applicable)

### Areas for Contribution

- **Tools**: New tools for common tasks
- **Providers**: Support for more LLM providers
- **Documentation**: Improve guides and API docs
- **Tests**: Increase coverage
- **Performance**: Optimize slow paths
- **Bug fixes**: Check issues for bugs

---

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or for specific module
logging.getLogger("cortex.core.providers").setLevel(logging.DEBUG)
```

### Common Issues

**Tool not found:**
```python
from cortex.tools import TOOLS
print([t["function"]["name"] for t in TOOLS])  # Check registered tools
```

**API errors:**
```python
# Enable request logging
import httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)
```

**Permission issues:**
```python
# Check permission mode
print(agent.permission_mode)  # Should be "normal", "auto", or "plan"
```

---

## Resources

- [Plugin Development Guide](PLUGIN_DEVELOPMENT.md)
- [API Documentation](api/) (coming soon)
- [Architecture Diagrams](design/)
- [Roadmap](ROADMAP.md)

---

*Last updated: 2026-01-17*
