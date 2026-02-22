# Cortex: The Local-First, Long-Term Memory AI Engineer 🧠

## Your Autonomous Coding Partner, Engineered for Performance and Trust.

Cortex isn't just another AI agent; it's a meticulously crafted **AI engineer framework** designed to accelerate your development workflow without compromising speed, privacy, or reliability. By seamlessly blending Python's flexibility with the raw power of **Rust** and **Go**, Cortex brings truly intelligent, persistent, and trustworthy automation directly to your codebase.

---

## ✨ Why Cortex Stands Out

Current AI agents often struggle with context, speed, and reliability. Cortex is built from the ground up to overcome these limitations:

*   ⚡ **Hybrid Performance Engine**: Tired of slow AI? Cortex offloads critical tasks like AST parsing, code search, and tokenization to highly optimized **Rust** and **Go** native extensions. Experience unparalleled speed where it matters most.
*   🧠 **Long-Term Semantic Memory (v1.1.0)**: Cortex remembers. Forever. Powered by a local **Vector Database (ChromaDB)**, your agent retains every lesson, decision, and solution across sessions. It learns from past mistakes and builds upon successes, growing smarter with every interaction.
*   🛡️ **Transactional Safety & Control**: Your codebase is sacred. Cortex protects it with a built-in transaction manager, offering `begin/commit/rollback` for all file operations. Code with confidence, knowing your work is always recoverable.
*   🚀 **Intelligent Orchestration & Planning**: For complex challenges, Cortex breaks down tasks into structured, self-correcting plans. It anticipates issues, adapts to feedback, and executes with a clear, verifiable strategy.
*   🌐 **Local-First & Flexible Models**: Keep your code private. Cortex supports powerful local LLMs via Ollama, alongside seamless integration with cloud APIs like DeepSeek, Anthropic, and OpenAI. You choose your model, your way.

---

## 🚀 Quick Start (Get Coding in Minutes)

```bash
# 1. Clone the repository
git clone https://github.com/sebastian420-hub/cortex.git
cd cortex

# 2. Install dependencies & build native extensions
# This may take a few minutes as Rust and Go components are compiled.
pip install -r requirements.txt
pip install -e .[hybrid] 

# 3. Start your local LLM (e.g., Llama3 via Ollama)
# If you don't have Ollama, visit ollama.ai for setup.
ollama run llama3

# 4. Launch Cortex and let it handle the rest!
cortex

# Or use one-shot mode for quick tasks:
cortex -p "Refactor the authentication logic in auth.py to use JWT"
```

---

## 🛠️ Core Features

*   **⚡ Blazing Fast Codebase Analysis**: Leverages Rust for AST parsing (Tree-sitter) and advanced code search.
*   **🧠 Persistent Long-Term Memory**: Stores and retrieves semantic context, facts, and past solutions across sessions.
*   **🛡️ Robust Transaction Management**: Safe file modifications with rollback capabilities.
*   **🎯 Goal-Oriented Planning**: Hierarchical planning engine for complex multi-step tasks.
*   **🔄 Self-Correction & Recovery**: Learns from errors and adapts strategies to overcome obstacles.
*   **🔗 Extensive Tooling**: A rich suite of File, Git, Web, and Code Analysis (AST) tools.
*   **🗣️ Intuitive CLI**: Rich terminal UI with syntax highlighting and live progress updates.
*   **🧩 Extensible Architecture**: Modular design with a powerful plugin system and webhook integration.

---

## 📐 Core Architecture

Cortex is built on a robust, multi-layered architecture designed for modularity, performance, and scalability.

*   **UI Layer (`cortex.ui`)**: Handles all user interactions, providing a rich, responsive terminal experience.
*   **Agent Layer (`cortex.agent`)**: The brain of Cortex, orchestrating planning, tool execution, and decision-making.
*   **Core Services (`cortex.core`)**:
    *   **Planning Engine**: Decomposes complex goals into actionable steps.
    *   **Context Manager**: Dynamically manages LLM context windows, incorporating working memory, session memory, and semantic long-term memory.
    *   **Memory System**: A 4-layered memory architecture:
        1.  **Working Memory**: Instant, short-term context.
        2.  **Session Memory**: In-session learning (failed approaches, successful patterns).
        3.  **State Memory**: Tracks overall task progress and agent focus.
        4.  **Semantic Memory (New!)**: Project-wide, persistent vector database for long-term knowledge retention.
*   **Native Layer (`cortex.native`)**:
    *   **Rust Core**: High-performance bindings for Tree-sitter (AST), regex search, and Tiktoken tokenization.
    *   **Go Services**: High-concurrency caching and gRPC-based microservices.

For an in-depth dive, refer to the [Cortex Technical Specification](docs/CORTEX_TECHNICAL_SPEC.md).

---

## 🚀 Development & Contribution

Cortex is a rapidly evolving open-source project. We welcome contributions from developers of all skill levels!

*   **Project Status**: **v1.1.0 (Semantic AI Agent)**. All 966/966 tests are passing (100% success rate) across Python, Rust, and Go components.
*   **Roadmap**: Explore our exciting plans for multi-agent capabilities, IDE integrations, and more in the [Development Roadmap](docs/ROADMAP.md).
*   **Contribute**: Whether it's bug fixes, new features, or documentation, your contributions make Cortex stronger. See [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon) for details.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with passion and powered by the incredible open-source community, especially:
*   [Ollama](https://ollama.ai/)
*   [ChromaDB](https://www.trychroma.com/)
*   [Sentence-Transformers](https://www.sbert.net/)
*   [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)
*   [Rich](https://rich.readthedocs.io/en/stable/)
*   The entire Rust and Go ecosystems.

