# Cortex

A high-performance, hybrid AI agent for coding, cybersecurity, and personal assistance. Cortex combines the flexibility of Python with the speed of **Rust** and **Go** to provide a robust, production-ready engineering assistant.

Cortex supports local LLM models (via Ollama), cloud APIs (DeepSeek, Anthropic, OpenAI), and integrates seamlessly with **MCP (Model Context Protocol)** servers.

## Features

- **Hybrid Performance**: Offloads critical tasks (AST parsing, tokenization, search) to native Rust and Go extensions for maximum speed.
- **Smart Context Management**: Uses chunked memory and token budgeting to work with massive codebases without overflowing context limits.
- **Hierarchical Planning**: Breaks down complex requests into structured plans with self-reflection and auto-correction.
- **Transactional Safety**: Protects your codebase with a built-in transaction manager that supports `begin/commit/rollback` for all file operations.
- **Flexible Models**: Support for local models (Ollama) and high-performance cloud APIs (DeepSeek, Anthropic, OpenAI).
- **Rich Terminal UI**: Beautiful syntax highlighting, markdown rendering, and real-time plan progress visualization.
- **MCP Integrated**: Support for third-party services through the Model Context Protocol.

## Installation

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) (for local models)
- Rust toolchain (for native extensions)
- Go (for high-performance services)

### Install Cortex

```bash
# Clone the repository
git clone https://github.com/sebastian420-hub/cortex.git
cd cortex

# Install dependencies and build native extensions
pip install -r requirements.txt
pip install -e .[hybrid]
```

## Quick Start

```bash
# Navigate to your project
cd ~/my-project

# Start Cortex
cortex

# Or use one-shot mode
cortex -p "Refactor the authentication logic in auth.py to use JWT"
```

## Core Architecture

Cortex is built on a modular, multi-layered architecture:

- **UI Layer (`cortex.ui`)**: Handles terminal interaction and markdown rendering.
- **Agent Layer (`cortex.agent`)**: Orchestrates execution, planning, and tool selection.
- **Core Services (`cortex.core`)**:
    - **Planning Engine**: Manages task decomposition and execution state.
    - **Context Window Manager**: Handles dynamic code injection and token budgeting.
    - **Memory System**: Layered memory for short-term history and long-term chunked storage.
- **Native Layer (`cortex.native`)**:
    - **Rust Core**: Ultra-fast AST parsing (tree-sitter) and tokenization.
    - **Go Services**: High-concurrency search and gRPC service integrations.

## Available Tools

Cortex provides a powerful suite of engineering tools:

### Advanced Editing
- `read_file_chunked`: Efficiently read large files using paging.
- `chunked_edit`: Surgically modify large files with precision.
- `transactional_apply`: Apply changes within a safe transaction block.

### File Operations
- `read_file` / `write_file`: Standard I/O operations.
- `execute_command`: Secure shell command execution.

### Discovery & Search
- `list_files`: Intelligent file listing with gitignore awareness.
- `search_files`: High-speed regex search across the project.
- `ast_search`: Search for specific code symbols (classes, functions) using native AST parsing.

### Git & Testing
- Full Git suite (`status`, `diff`, `commit`, `log`).
- `run_tests`: Automatic test detection and execution (Pytest/Unittest).

## Configuration

Cortex can be customized via `config.yaml`:

```yaml
model: deepseek-chat
max_tokens: 128000
permission_mode: normal  # normal, auto, plan
features:
  rust_ast: true
  rust_tokenizer: true
  go_cache: true
```

## Project Context (`GEMINI.md` / `AGENT.md`)

Cortex automatically reads `GEMINI.md` or `AGENT.md` files in your project root to understand your specific tech stack, architecture, and coding standards.

## Development

### Running Tests

Cortex maintains a high bar for stability with a comprehensive test suite:

```bash
# Run all unit tests
pytest tests/unit

# Run benchmarks
pytest tests/benchmarks
```

Current test status: **453/455 tests passing (~99.5%)**.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by the evolution of AI coding assistants.
- Built with **Ollama**, **Tree-sitter**, and **Rich**.
- Performance powered by **Rust** and **Go**.
