# Architecture

This document provides an overview of Cortex's internal architecture.

## High-Level Architecture

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
│   └─────────────┴──────────────┴────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     Tools Layer                         │
│   (file_tools, command_tools, git_tools, ast/, etc.)   │
├─────────────────────────────────────────────────────────┤
│                   Utilities Layer                       │
│   (errors, timeouts, security, cache, config)          │
└─────────────────────────────────────────────────────────┘
```

## Components

### Agent

The `Cortex` class in `agent.py` is the main orchestrator:

- Manages conversation history
- Coordinates tool execution
- Handles model switching
- Routes requests to optimal models

### Providers

Provider classes abstract different LLM APIs:

- `AnthropicProvider` - Claude models
- `OpenRouterProvider` - Multiple models via OpenRouter
- `OpenAIProvider` - GPT models
- `OllamaProvider` - Local models

### Tools

Tools are the actions Cortex can perform:

- **File tools**: read, write, edit files
- **Search tools**: grep, glob
- **Git tools**: status, diff, commit
- **AST tools**: code structure analysis
- **Web tools**: fetch, search

### Routing

The routing system selects optimal models based on task complexity:

- Task analysis
- Model capability matching
- Cost/performance optimization

## Data Flow

1. User input arrives at CLI
2. Agent processes message
3. LLM generates response (text or tool calls)
4. Tool calls are executed
5. Results are added to conversation
6. Loop continues until task complete

See {doc}`developer` for more implementation details.
