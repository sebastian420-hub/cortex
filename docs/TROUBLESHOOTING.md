# Troubleshooting Guide

This guide covers common issues and their solutions.

## Table of Contents
1. [Installation Issues](#installation-issues)
2. [API Key Issues](#api-key-issues)
3. [Tool Errors](#tool-errors)
4. [Performance Issues](#performance-issues)
5. [Debug Techniques](#debug-techniques)

---

## Installation Issues

### `ModuleNotFoundError: No module named 'cortex'`

**Cause:** Package not installed or wrong environment.

**Solutions:**
```bash
# Install the package
pip install cortex-terminal

# Or install in development mode
pip install -e .

# Check you're in the right environment
which python
pip list | grep cortex
```

### Tree-sitter not working

**Cause:** Optional dependencies not installed.

**Solutions:**
```bash
# Install tree-sitter dependencies
pip install tree-sitter tree-sitter-python tree-sitter-javascript

# Check if available
python -c "from cortex.tools.ast import is_ast_available; print(is_ast_available())"
```

### Ripgrep not found

**Cause:** Ripgrep not installed system-wide.

**Note:** Cortex will fall back to Python-based search, which is slower but functional.

**Solutions:**
```bash
# macOS
brew install ripgrep

# Ubuntu/Debian
sudo apt install ripgrep

# Windows (with Chocolatey)
choco install ripgrep

# Windows (with Scoop)
scoop install ripgrep
```

---

## API Key Issues

### `API key not set`

**Cause:** Environment variable not configured.

**Solutions:**
```bash
# Set for Anthropic
export ANTHROPIC_API_KEY=your-key-here

# Set for OpenRouter
export OPENROUTER_API_KEY=your-key-here

# Set for DeepSeek
export DEEPSEEK_API_KEY=your-key-here

# Verify it's set
echo $ANTHROPIC_API_KEY
```

**For Windows:**
```cmd
set ANTHROPIC_API_KEY=your-key-here
```

**Persistent (add to shell profile):**
```bash
# ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY=your-key-here
```

### `Invalid API key`

**Cause:** API key is incorrect or expired.

**Solutions:**
1. Verify the key at your provider's dashboard
2. Check for extra whitespace or quotes
3. Ensure the key has the required permissions

```python
# Test the key
from cortex.core.providers import ProviderFactory

provider = ProviderFactory.get_provider("claude-sonnet-4-20250514")
print(f"Valid: {provider.validate_api_key()}")
```

### `Rate limit exceeded`

**Cause:** Too many API calls.

**Solutions:**
1. Wait and retry
2. Upgrade your API plan
3. Enable rate limiting in config:
```yaml
# config/default.yaml
rate_limiting:
  enabled: true
  requests_per_minute: 30
```

---

## Tool Errors

### `SecurityError: Path outside project directory`

**Cause:** Attempting to access files outside the project root.

**Solutions:**
1. Use relative paths from project root
2. Start Cortex in the correct directory
3. Use `--dir` flag to specify project root

```bash
# Specify project directory
cortex --dir /path/to/project

# In code
agent = Cortex(project_dir=Path("/path/to/project"))
```

### `File not found: <path>`

**Cause:** File doesn't exist or path is incorrect.

**Solutions:**
1. Check the file exists: `ls -la <path>`
2. Use tab completion for paths
3. Check for typos in filename

### `Permission denied`

**Cause:** File permissions or permission mode.

**Solutions:**
```bash
# Check file permissions
ls -la <file>

# Fix permissions if needed
chmod 644 <file>
```

If in plan mode:
```bash
# Switch to normal mode for write operations
cortex --permission normal
```

### `Tool execution timeout`

**Cause:** Operation took too long.

**Solutions:**
1. Configure longer timeout in config:
```yaml
timeouts:
  default: 60
  long: 600
```

2. For specific tools:
```python
class MyTool(Tool):
    default_timeout = 120  # 2 minutes
```

---

## Performance Issues

### Slow startup

**Cause:** Loading large caches or many plugins.

**Solutions:**
```bash
# Disable file cache
cortex --no-cache

# Check startup time
time cortex --help
```

### High memory usage

**Cause:** Large files in context or cache.

**Solutions:**
1. Read files with limits:
```
read_file path="large.txt" limit=500
```

2. Clear cache:
```python
from cortex.cache import clear_cache
clear_cache()
```

3. Reduce context window:
```yaml
max_tokens: 50000  # Instead of 100000
```

### Slow tool execution

**Cause:** Network issues, large files, or complex operations.

**Solutions:**
1. Enable parallel execution:
```yaml
parallel_execution:
  enabled: true
  max_workers: 4
```

2. Check network connectivity for web tools
3. Use more specific file patterns in search

---

## Debug Techniques

### Enable Debug Logging

```python
import logging

# Enable all debug logs
logging.basicConfig(level=logging.DEBUG)

# Or for specific modules
logging.getLogger("cortex.core.providers").setLevel(logging.DEBUG)
logging.getLogger("cortex.tools").setLevel(logging.DEBUG)
```

### Check Tool Registry

```python
from cortex.tools import TOOLS
from cortex.tools.registry import get_registry

# List all tools
print(f"Total tools: {len(TOOLS)}")
for tool in TOOLS:
    print(f"  - {tool['function']['name']}")

# Check specific tool
registry = get_registry()
schema = registry.get_schema("read_file")
print(schema)
```

### Inspect Conversation

```python
agent = Cortex(...)

# After some conversation
messages = agent.conversation.get_messages()
for msg in messages:
    print(f"{msg['role']}: {msg.get('content', '')[:100]}...")

# Get stats
stats = agent.conversation.get_stats()
print(f"Messages: {stats['message_count']}")
print(f"Tokens: {stats['estimated_tokens']}")
```

### Test Tool Execution

```python
from pathlib import Path
from cortex.tools.file_tools import ReadFileTool

# Create tool directly
tool = ReadFileTool(
    project_dir=Path.cwd(),
    permission_mode="auto",
)

# Execute and inspect result
result = tool.execute(path="test.py")
print(f"Success: {result.get('success')}")
print(f"Error: {result.get('error')}")
print(f"Content: {result.get('content', '')[:200]}")
```

### Check Provider Connection

```python
from cortex.core.providers import ProviderFactory

# Get provider
provider = ProviderFactory.get_provider("claude-sonnet-4-20250514")

# Test connection
try:
    response = provider.chat(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(f"Response: {response}")
except Exception as e:
    print(f"Error: {e}")
```

### Profile Performance

```python
import cProfile
import pstats

# Profile a session
profiler = cProfile.Profile()
profiler.enable()

agent.chat("Do something")

profiler.disable()
stats = pstats.Stats(profiler).sort_stats("cumtime")
stats.print_stats(20)
```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ProviderError: API key not set` | Missing API key | Set environment variable |
| `SecurityError: Path outside project` | Invalid path | Use relative path |
| `ValidationError: Invalid parameter` | Bad tool input | Check parameter format |
| `TimeoutError: Operation timed out` | Slow operation | Increase timeout |
| `ConnectionError: Failed to connect` | Network issue | Check internet connection |
| `RateLimitError: Too many requests` | API rate limit | Wait or upgrade plan |

---

## Getting Help

If you're still stuck:

1. **Search Issues:** Check [GitHub Issues](https://github.com/yourusername/cortex/issues)
2. **Ask a Question:** Open a new issue with:
   - Cortex version (`cortex --version`)
   - Python version (`python --version`)
   - OS and version
   - Full error message
   - Steps to reproduce
3. **Community:** Join discussions on GitHub Discussions

---

*Last updated: 2026-01-17*
