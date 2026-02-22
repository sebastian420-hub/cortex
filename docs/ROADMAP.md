# Cortex Roadmap

**Vision:** High-performance multi-agent orchestration for autonomous software engineering.

---

## 1. Phase 1: Latency Reduction & Core Polish
**Status:** Current Focus

### Latency Optimizations
*   **Lazy Component Initialization**: Background load `SentenceTransformer` and `ChromaDB` clients. Target startup time: `< 0.5s`.
*   **Rust Logic Migration**: Port `ContextManager` token-budgeting and history truncation to `cortex-native` (Rust).
*   **LLM Response Caching**: Implement tiered caching (RAM/Redis) for model outputs to reduce redundant API latency and cost.
*   ✅ **Delivered**: `ParallelToolExecutor` for concurrent read-only operations.
*   ✅ **Delivered**: `FileCache` with Redis backend and git-history pre-warming.

### Execution Fluidity
*   **Asynchronous Tool Streaming**: Refactor `GrepTool` and `TestTool` to stream stdout/stderr directly to the CLI using `asyncio` instead of blocking subprocess calls.
*   **Optimistic State Updates**: Render reasoning blocks and plan transitions immediately during LLM generation.
*   ✅ **Delivered**: Provider-agnostic LLM response streaming.

---

## 2. Phase 2: Multi-Agent Swarms
**Status:** Next Milestone

### Orchestration
*   **Parallel Sub-tasking**: Update the `PlanningEngine` to execute independent plan branches using multiple concurrent agent threads.
*   **Specialized Agent Roles**:
    *   `@architect`: Goal decomposition and system-wide logic verification.
    *   `@coder`: Optimized for high-speed implementation and refactoring.
    *   `@security`: Dedicated logic for vulnerability scanning and permission auditing.
*   **Shared Knowledge Bus**: Use the Vector Database as a shared memory space for agents to exchange insights without increasing context window pressure.

---

## 3. Phase 3: Unsupervised Autonomy
**Status:** Long-term Research

### Autonomous Workflows
*   **Headless Mode**: "Night shift" execution for large-scale refactors with automated logging and rollback safety.
*   **Self-Healing Planning**: Algorithmic backtracking when plans encounter consistent regressions or environmental failures.

### Integration
*   **Language Server Protocol (LSP)**: Expose agent capabilities to IDEs (VS Code, Neovim) via standard LSP.
*   **CI/CD Integration**: Headless deployment for automated PR review and dependency remediation.

---

## 📊 Technical Targets

| Metric | v1.1 (Current) | v2.0 (Target) |
|:---|:---:|:---:|
| **Cold Startup** | ~9.0s | **< 0.5s** |
| **Core Overhead** | ~150ms | **< 10ms** |
| **Tool Execution** | Sequential/Parallel | **Parallel Swarm** |
| **Agent Topology** | Sequential Chain | **Concurrent Mesh** |

---
*Last Updated: February 21, 2026*
