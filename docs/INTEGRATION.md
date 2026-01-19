# Integration Guide

This guide explains how to use Cortex as a library in your own applications.

## Table of Contents
1. [Basic Usage](#basic-usage)
2. [Configuration](#configuration)
3. [Custom Providers](#custom-providers)
4. [Event Hooks](#event-hooks)
5. [Tool Integration](#tool-integration)
6. [Embedding Examples](#embedding-examples)

---

## Basic Usage

### Minimal Example

```python
from pathlib import Path
from cortex.agent import Cortex

# Create agent
agent = Cortex(
    model="claude-sonnet-4-20250514",
    project_dir=Path.cwd(),
    permission_mode="auto",  # No confirmations
)

# Send a message
response = agent.chat("What files are in this directory?")
print(response)

# Continue the conversation
response = agent.chat("Read the README file")
print(response)
```

### With Configuration

```python
from cortex.agent import Cortex
from cortex.config import AgentConfig

# Load config from file
config = AgentConfig.from_file(Path("config/custom.yaml"))

# Or create programmatically
config = AgentConfig(
    model="claude-sonnet-4-20250514",
    permission_mode="auto",
    max_iterations=20,
    max_tokens=150000,
)

# Create agent with config
agent = Cortex(config=config, project_dir=Path.cwd())
```

---

## Configuration

### AgentConfig Options

```python
from cortex.config import AgentConfig

config = AgentConfig(
    # Model settings
    model="claude-sonnet-4-20250514",  # Model name
    provider=None,  # Auto-detect from model name

    # Permission settings
    permission_mode="normal",  # "normal", "auto", "plan"

    # Conversation settings
    max_iterations=15,  # Max tool calls per message
    max_tokens=100000,  # Context window limit
    keep_recent_messages=20,  # Messages to keep before summarizing

    # Parallel execution
    parallel_execution={
        "enabled": True,
        "max_workers": 0,  # 0 = auto-detect
        "batch_size": 10,
    },

    # File cache
    file_cache={
        "enabled": True,
        "max_entries": 100,
        "max_size_mb": 50.0,
    },

    # Timeouts
    timeouts={
        "default": 30,
        "network": 60,
        "long": 300,
    },
)
```

### Environment Variables

```python
import os

# API keys
os.environ["ANTHROPIC_API_KEY"] = "your-key"
os.environ["OPENROUTER_API_KEY"] = "your-key"
os.environ["DEEPSEEK_API_KEY"] = "your-key"

# Optional: Override model
os.environ["CORTEX_MODEL"] = "claude-sonnet-4-20250514"
```

---

## Custom Providers

### Implementing a Provider

```python
from cortex.core.providers import ModelProvider
from typing import List, Dict, Any, Optional

class MyCustomProvider(ModelProvider):
    """Custom LLM provider."""

    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.myservice.com"

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send chat request."""
        # Convert messages to your API format
        # Make API call
        # Return response in standard format
        return {
            "message": {
                "role": "assistant",
                "content": "Response text",
            },
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        }

    def list_models(self) -> List[str]:
        """List available models."""
        return ["my-model-1", "my-model-2"]

    def validate_api_key(self) -> bool:
        """Validate API key is set."""
        return bool(self.api_key)
```

### Registering a Provider

```python
from cortex.core.providers import ProviderFactory

# Register custom provider
ProviderFactory.register_provider(
    name="myservice",
    provider_class=MyCustomProvider,
    model_patterns=["my-*"],  # Models matching this pattern
)

# Now use it
agent = Cortex(model="my-model-1", provider="myservice")
```

---

## Event Hooks

### Available Hooks

```python
from cortex.agent import Cortex

agent = Cortex(model="claude-sonnet-4-20250514")

# Before processing a message
@agent.on("before_message")
def on_before_message(message: str):
    print(f"Processing: {message}")

# After getting LLM response
@agent.on("after_response")
def on_after_response(response: dict):
    print(f"Got response with {len(response.get('content', ''))} chars")

# Before tool execution
@agent.on("before_tool")
def on_before_tool(tool_name: str, args: dict):
    print(f"Executing: {tool_name}")
    return True  # Return False to skip

# After tool execution
@agent.on("after_tool")
def on_after_tool(tool_name: str, result: dict):
    print(f"Tool {tool_name} returned: {result.get('success')}")

# On error
@agent.on("error")
def on_error(error: Exception):
    print(f"Error: {error}")
```

### Custom Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Get Cortex loggers
cortex_logger = logging.getLogger("cortex")
cortex_logger.setLevel(logging.DEBUG)

# Provider-specific logging
provider_logger = logging.getLogger("cortex.core.providers")
provider_logger.setLevel(logging.INFO)
```

---

## Tool Integration

### Adding Custom Tools

```python
from cortex.tools.base import Tool
from cortex.tools.registry import get_registry

# Create custom tool
class MyTool(Tool):
    def execute(self, param: str) -> dict:
        return self._create_success(result=f"Processed: {param}")

# Register tool
registry = get_registry()
registry.register(
    name="my_tool",
    tool_class=MyTool,
    schema={
        "type": "function",
        "function": {
            "name": "my_tool",
            "description": "My custom tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                },
                "required": ["param"],
            },
        },
    },
)

# Tool is now available to the agent
```

### Disabling Built-in Tools

```python
from cortex.tools.registry import get_registry

registry = get_registry()

# Disable specific tools
registry.disable("web_search")
registry.disable("web_fetch")

# Or filter tools by namespace
enabled_tools = registry.list_tools(namespace="builtin")
```

---

## Embedding Examples

### CLI Application

```python
#!/usr/bin/env python3
"""Simple CLI using Cortex."""

import argparse
from pathlib import Path
from cortex.agent import Cortex

def main():
    parser = argparse.ArgumentParser(description="AI Coding Assistant")
    parser.add_argument("message", nargs="?", help="Message to send")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    agent = Cortex(
        model=args.model,
        project_dir=args.dir,
        permission_mode="normal",
    )

    if args.message:
        # One-shot mode
        print(agent.chat(args.message))
    else:
        # Interactive mode
        while True:
            try:
                message = input("You: ")
                if message.lower() in ("exit", "quit"):
                    break
                print(f"Assistant: {agent.chat(message)}")
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
```

### Web API

```python
"""FastAPI integration example."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from cortex.agent import Cortex

app = FastAPI()

# Create agent (in production, use dependency injection)
agent = Cortex(
    model="claude-sonnet-4-20250514",
    project_dir=Path("/workspace"),
    permission_mode="plan",  # Read-only for safety
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response = agent.chat(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Jupyter Notebook

```python
# In a Jupyter notebook
from pathlib import Path
from cortex.agent import Cortex
from IPython.display import Markdown, display

# Create agent
agent = Cortex(
    model="claude-sonnet-4-20250514",
    project_dir=Path.cwd(),
    permission_mode="plan",
    console=None,  # Disable rich console in notebooks
)

def ask(question: str):
    """Helper to display formatted responses."""
    response = agent.chat(question)
    display(Markdown(response))

# Usage
ask("Explain the structure of this project")
ask("What are the main functions in src/main.py?")
```

### Background Worker

```python
"""Background task processing with Cortex."""

import threading
import queue
from pathlib import Path
from cortex.agent import Cortex

class CortexWorker:
    def __init__(self, project_dir: Path):
        self.agent = Cortex(
            model="claude-sonnet-4-20250514",
            project_dir=project_dir,
            permission_mode="auto",
        )
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self._running = False
        self._thread = None

    def start(self):
        """Start the worker thread."""
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop)
        self._thread.start()

    def stop(self):
        """Stop the worker thread."""
        self._running = False
        self.task_queue.put(None)  # Signal to stop
        if self._thread:
            self._thread.join()

    def _worker_loop(self):
        """Main worker loop."""
        while self._running:
            task = self.task_queue.get()
            if task is None:
                break

            task_id, message = task
            try:
                response = self.agent.chat(message)
                self.result_queue.put((task_id, response, None))
            except Exception as e:
                self.result_queue.put((task_id, None, str(e)))

    def submit(self, task_id: str, message: str):
        """Submit a task."""
        self.task_queue.put((task_id, message))

    def get_result(self, timeout: float = None):
        """Get a result (blocking)."""
        return self.result_queue.get(timeout=timeout)

# Usage
worker = CortexWorker(Path.cwd())
worker.start()

worker.submit("task-1", "Analyze this codebase")
task_id, response, error = worker.get_result()

worker.stop()
```

---

## Best Practices

### Resource Management

```python
# Use context manager for cleanup
from contextlib import contextmanager

@contextmanager
def create_agent(**kwargs):
    agent = Cortex(**kwargs)
    try:
        yield agent
    finally:
        # Cleanup resources
        agent.parallel_executor.shutdown()

# Usage
with create_agent(model="claude-sonnet-4-20250514") as agent:
    response = agent.chat("Hello")
```

### Error Handling

```python
from cortex.core.providers import ProviderError
from cortex.core.security import SecurityError

try:
    response = agent.chat("Do something")
except ProviderError as e:
    print(f"API error: {e}")
except SecurityError as e:
    print(f"Security violation: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Conversation Management

```python
# Reset conversation
agent.conversation.clear()

# Get conversation history
history = agent.conversation.get_messages()

# Save/restore conversation
import json

# Save
with open("conversation.json", "w") as f:
    json.dump(history, f)

# Restore (for new session, rebuild from messages)
```

---

*Last updated: 2026-01-17*
