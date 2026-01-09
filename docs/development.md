# Development Guide

## Project Structure

```
LocalTerminalAgent/
├── cortex/          # Main package
│   ├── agent.py        # Core agent class
│   ├── cli.py          # CLI entry point
│   ├── config.py       # Configuration
│   ├── models.py       # Data models
│   ├── tools/          # Tool implementations
│   ├── core/           # Core functionality
│   ├── ui/             # UI components
│   ├── storage/        # Persistence
│   └── utils/          # Utilities
├── tests/              # Test suite
├── docs/               # Documentation
└── config/             # Configuration files
```

## Adding a New Tool

1. Create a tool class in `cortex/tools/`:

```python
from .base import Tool

class MyNewTool(Tool):
    def execute(self, param1: str, param2: int = 10) -> Dict[str, Any]:
        # Implementation
        return {"success": True, "result": ...}
```

2. Add tool definition to `cortex/tools/__init__.py`:

```python
TOOLS.append({
    "type": "function",
    "function": {
        "name": "my_new_tool",
        "description": "What it does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer", "default": 10}
            },
            "required": ["param1"]
        }
    }
})
```

3. Register in `create_tool_instance()`:

```python
tools_map = {
    # ...
    "my_new_tool": MyNewTool,
}
```

4. Write tests in `tests/test_tools.py`

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_tools.py -v

# With coverage
pytest tests/ --cov=cortex --cov-report=html
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions focused and small
- Use meaningful variable names

## Git Workflow

1. Create a feature branch
2. Make changes
3. Run tests and linting
4. Commit with clear messages
5. Push and create PR

## Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Profiling

```bash
python -m cProfile -o profile.stats cortex/cli.py
```

