# Cortex: The AI Engineer with Persistent Memory

Cortex is a high-performance, hybrid AI agent framework for software development. It combines Python's flexibility with the speed of **Rust** and **Go** to provide a robust, production-ready engineering assistant. Cortex supports local LLM models (via Ollama) and integrates with cloud APIs (DeepSeek, Anthropic, OpenAI).

---

## Core Strengths

Cortex is engineered to overcome common limitations of traditional AI agents through its architectural design:

*   **Hybrid Native Performance**: Critical tasks like AST parsing, code search, and tokenization are offloaded to highly optimized **Rust** and **Go** native extensions. This ensures superior performance and efficiency, particularly in large codebases.
*   **Long-Term Semantic Memory (v1.1.0)**: Cortex features a persistent, local **Vector Database (ChromaDB)**. It automatically indexes all learned facts, decisions, and solutions across sessions, enabling intelligent recall of relevant historical context and continuous learning.
*   **Transactional Code Safety**: All file modifications are managed within a built-in transaction system, providing `begin/commit/rollback` capabilities. This ensures codebase integrity and allows developers to work with confidence.
*   **Advanced Planning & Orchestration**: Complex development tasks are managed through a hierarchical planning engine that includes goal decomposition, adaptive execution, and self-correction mechanisms.
*   **Local-First & Flexible Model Support**: Designed for privacy and flexibility, Cortex prioritizes local execution with Ollama-powered LLMs, while also supporting cloud-based models via OpenRouter (default), DeepSeek, and Anthropic (Claude 4.6+).

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/sebastian420-hub/cortex.git
cd cortex

# Install dependencies & build native extensions
# This may take a few minutes as Rust and Go components are compiled.
pip install -r requirements.txt
pip install -e .[hybrid] 
```

### 2. Configuration (Choose your path)

#### Option A: Cloud (Default - moonshotai/kimi-k2.5)
Cortex uses [OpenRouter](https://openrouter.ai/) by default. You will need an API key.

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY="your_key_here"

# Launch Cortex for an interactive session
cortex
```

#### Option B: Truly Local (Privacy-First)
Run completely offline using [Ollama](https://ollama.ai/).

```bash
# 1. Pull your preferred model
ollama pull llama3

# 2. Start Cortex specifying the local model
cortex --model llama3
```

---

## Key Capabilities

*   **Fast Codebase Analysis**: Leverages Rust for AST parsing (Tree-sitter) and efficient code search.
*   **AST-Driven Surgical Refactoring**: Precise, deterministic symbol renaming and code block replacement with automatic syntax verification and rollback.
*   **Persistent Context**: Stores and retrieves semantic information, facts, and past resolutions across multiple sessions.
*   **Recoverable File Operations**: Ensures safe modifications with transactional integrity.
*   **Goal-Driven Task Management**: Utilizes a hierarchical planning engine for complex tasks.
*   **Adaptive Strategy**: Incorporates self-correction and recovery mechanisms.
*   **Comprehensive Toolset**: Includes File, Git, Web, and Code Analysis (AST) tools.
*   **CLI Interface**: Provides a rich terminal experience with syntax highlighting and live updates.
*   **Extensible Design**: Modular architecture supporting plugin development and webhook integration.

---

## Environment Variables

For cloud-based models, set the following environment variables:

*   **OpenRouter (Default)**: `OPENROUTER_API_KEY`
*   **DeepSeek**: `DEEPSEEK_API_KEY`
*   **Anthropic**: `ANTHROPIC_API_KEY`
*   **OpenAI**: `OPENAI_API_KEY`

---

## Architecture Overview

Cortex employs a multi-layered architecture focused on performance, modularity, and extensibility.

*   **UI Layer (`cortex.ui`)**: Manages terminal-based user interactions.
*   **Agent Layer (`cortex.agent`)**: Orchestrates overall execution, planning, and tool selection.
*   **Core Services (`cortex.core`)**: Includes the Planning Engine, dynamic Context Manager, and a 4-layered Memory System:
    1.  **Working Memory**: Ephemeral, immediate task context.
    2.  **Session Memory**: In-session learning and transient patterns.
    3.  **State Memory**: Tracks overall agent focus and task progression.
    4.  **Semantic Memory**: Project-wide, persistent vector database for long-term knowledge retention.
*   **Native Layer (`cortex.native`)**: Integrates high-performance Rust bindings (Tree-sitter, regex search, Tiktoken) and Go-based services for caching and model management.

For a detailed architectural breakdown, consult the [Cortex Technical Specification](docs/CORTEX_TECHNICAL_SPEC.md).

### 🔬 Research & Benchmarking

Cortex includes a systematic **Research Framework** for evaluating agent intelligence and resilience through tiered engineering challenges in isolated sandboxes. 

See the [Research Framework Documentation](docs/RESEARCH_FRAMEWORK.md) for details on:
- **Sandbox Isolation**: Safe execution of complex tasks.
- **Evaluation Tiers**: Control, Architectural, and Stress testing.
- **KPI Tracking**: Success rate, turns taken, and "Correction Latency".
- **Challenge Bank**: Standardized benchmarks for continuous improvement.

---

## Development & Contribution

Cortex is an open-source project and welcomes contributions from developers.

*   **Project Status**: **v1.2.0 (Bio-inspired Metacognition)**. All 950/950 tests are passing (100% success rate) across Python, Rust, and Go components.
*   **Research**: We use a custom [Research Framework](docs/RESEARCH_FRAMEWORK.md) to benchmark agent performance under stress.
*   **Roadmap**: Our plans for multi-agent systems, IDE integrations, and further enhancements are detailed in the [Development Roadmap](docs/ROADMAP.md).
*   **Contribute**: Information on contributing will be available in [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with the support of the open-source community, notably:
*   [Ollama](https://ollama.ai/)
*   [ChromaDB](https://www.trychroma.com/)
*   [Sentence-Transformers](https://www.sbert.net/)
*   [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)
*   [Rich](https://rich.readthedocs.io/en/stable/)
