# Cortex: Technical Architecture & System Status
**Date:** February 18, 2026
**Version:** 1.0.0-beta

## 1. Executive Summary
Cortex is a high-performance, hybrid AI agent framework designed for complex software engineering tasks. Unlike purely Python-based agents, Cortex utilizes a **hybrid architecture** where high-level orchestration is handled in Python, while performance-critical tasks (AST parsing, tokenization, high-speed search) are offloaded to **Rust** and **Go** native extensions.

The system emphasizes **safety** through transactional file operations and **intelligence** through a hierarchical planning system and dynamic context management.

---

## 2. Current System Status

### 2.1 Testing Health
*   **Total Tests:** 455
*   **Passing:** 453 (~99.5%)
*   **Failing:** 2 (Isolated to `TestEstimateTokens` mocking artifacts)
*   **Key Validations:**
    *   ✅ **Context Window Manager:** Fully validated token budgeting and chunk injection strategies.
    *   ✅ **Chunked Editing:** `ChunkedEditTool` validated for surgical file modifications on large codebases.
    *   ✅ **Planning Engine:** Validated plan generation, execution, and reflection loops.
    *   ✅ **Native Integration:** Rust-based AST parsing and token counting functional.

### 2.2 Known Issues
*   **Tiktoken Mocking:** The `cortex.core.context` module has complex import dependencies that make unit testing the fallback logic for `get_encoding_for_model` difficult without integration tests.
*   **Feature Flagging:** The interaction between Python-based token counting and Rust-native token counting requires explicit feature flag management in the testing environment.

---

## 3. System Architecture

### 3.1 High-Level Layers

```mermaid
graph TD
    User[User Input] --> CLI[CLI / UI Layer]
    CLI --> Agent[Enhanced Agent Core]
    
    subgraph "Core Services (Python)"
        Agent --> Planner[Planning Engine]
        Agent --> Context[Context Window Manager]
        Agent --> Memory[Layered Memory]
        Agent --> Tools[Tool Executor]
    end
    
    subgraph "Native Extensions (Hybrid)"
        Context --> RustCore[Cortex-Native (Rust)]
        Tools --> GoServices[Go Microservices]
    end
    
    Tools --> FS[FileSystem (Transactional)]
```

### 3.2 Core Subsystems

#### A. The Agent Core (`cortex.agent`)
The `EnhancedAgent` operates on a **Research -> Strategy -> Execution** loop.
*   **Delegation:** Capable of routing specialized sub-tasks to sub-agents.
*   **Reflection:** Evaluates the success of executed steps against expected outcomes before proceeding.

#### B. Context Management (`cortex.core.context`)
This is the system's differentiating engine. It manages the LLM's finite context window.
*   **Token Budgeting:** Enforces strict limits per operation (e.g., 10k tokens for "read", 50k for "analyze").
*   **Smart Injection:** Instead of dumping whole files, it uses `ChunkingStrategy` (Smart, Line-based, or AST-based) to inject only relevant code blocks.
*   **Strategies:** 
    *   `ContextInjectionStrategy.RELEVANT`: Uses vector similarity or keyword matching.
    *   `ContextInjectionStrategy.LRU`: Least Recently Used eviction.

#### C. Native Layer (`cortex.native`)
*   **Rust (PyO3):**
    *   **AST Parsing:** Uses `tree-sitter` bindings for rapid symbol extraction (functions, classes, imports) significantly faster than Python's `ast` module.
    *   **Tokenization:** High-speed BPE tokenization.
*   **Go:**
    *   Handles high-concurrency tasks and gRPC-based service calls.

#### D. Tooling & Safety (`cortex.tools`)
*   **ChunkedEditTool:** Allows the agent to read and edit files larger than the context window by paging through content.
*   **TransactionManager:** Wraps file operations in a `begin -> commit/rollback` block. If an agent generates bad code or a tool fails mid-operation, the filesystem state is rolled back to prevent corruption.

---

## 4. Key Workflows

### 4.1 The Planning Loop
1.  **Goal Analysis:** User input is analyzed for intent.
2.  **Plan Generation:** A hierarchical list of `PlanStep`s is created.
3.  **Step Execution:**
    *   The agent selects the next `PENDING` step.
    *   It retrieves necessary context (using the Context Manager).
    *   It selects tools via the `ParallelToolExecutor`.
    *   It executes the tools.
4.  **Reflection:** The output is analyzed. If successful, the step is marked `COMPLETED`. If failed, the plan is updated.

### 4.2 The "Smart Context" Pipeline
1.  **Request:** Agent needs to read `large_file.py`.
2.  **Chunking:** File is split into logical units (e.g., individual functions) using Rust-based AST parsing.
3.  **Selection:** Based on the current prompt, only the chunks containing relevant keywords or symbols are selected.
4.  **Budget Check:** Chunks are added to the context window until the `TokenBudget` is reached.
5.  **Injection:** The constructed prompt is sent to the model.

---

## 5. Directory Structure Map

| Directory | Description |
| :--- | :--- |
| `cortex/agent/` | Core agent logic, state machine, and loops. |
| `cortex/core/` | Essential services: `context`, `planning`, `memory`, `routing`. |
| `cortex/native/` | Python bindings for Rust extensions. |
| `cortex/tools/` | Tool implementations (`ChunkedEdit`, `Bash`, etc.). |
| `cortex/ui/` | Rich-text terminal UI and progress rendering. |
| `rust/` | Source code for the Rust extension (performance layer). |
| `go/` | Source code for Go-based microservices. |
| `tests/` | Comprehensive `pytest` suite (Unit, Integration, Benchmarks). |

---

## 6. Development Guidelines

*   **Testing:** Always run `pytest` after changes. Use `pytest tests/unit` for fast feedback.
*   **Mocking:** When testing `cortex.core.context`, prefer `patch.object` on modules rather than patching imports to avoid cache pollution.
*   **Native Code:** Changes to `rust/` require rebuilding the python bindings (typically handled via `maturin`).
