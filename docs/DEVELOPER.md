# Cortex Developer Guide

This guide is for developers who want to contribute to Cortex or understand its internals.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [Cognitive Core (Limbic System)](#cognitive-core-limbic-system)
5. [Multi-Layered Memory](#multi-layered-memory)
6. [Testing & Research](#testing--research)
7. [Code Style](#code-style)

---

## Architecture Overview

Cortex follows a bio-inspired layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Layer                          │
│   (cli.py, cli_commands/, argument parsing)             │
├─────────────────────────────────────────────────────────┤
│                     Agent Layer                         │
│   (agent.py - unified loop, tool orchestration)         │
├─────────────────────────────────────────────────────────┤
│                   Cognitive Core Layer                  │
│   ┌─────────────┬──────────────┬────────────────────┐  │
│   │ Metacognition│   Planning   │   Routing          │  │
│   │  (Limbic)   │   (Atomic)   │ (model selection)  │  │
│   ├─────────────┼──────────────┼────────────────────┤  │
│   │ Memory Stack│  Orchestration│   Recovery         │  │
│   │ (Layered)   │ (multi-model) │ (transactions)     │  │
│   └─────────────┴──────────────┴────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     Tools Layer                         │
│   (file, git, web, ast/, metacognition/, etc.)          │
├─────────────────────────────────────────────────────────┤
│                   Native/Service Layer                  │
│   (Rust: AST/Regex, Go: Cache, ChromaDB)                │
└─────────────────────────────────────────────────────────┘
```

### Data Flow (The Reasoning Loop)

1. **Recall**: Prompt is embedded to query **Semantic Memory** for relevant "Synthetic Experiences".
2. **Assemble**: `PromptBuilder` combines goal, retrieved context, and **Limbic State** (Confidence/Tone).
3. **Inference**: LLM generates a plan or tool call.
4. **Execute**: Surgical tools (AST, File, Git) interact with the codebase.
5. **Appraise**: `StateManager` updates confidence based on tool success/failure.
6. **Consolidate**: `metacognitive_reflect` summarizes the session into long-term memory.

---

## Project Structure

```
cortex/
├── agent.py              # Unified Agent Orchestrator
├── core/                 # Core Cognitive Logic
│   ├── memory_layers/    # Metacognitive State & Layered Memory
│   ├── planning.py       # Atomic Planning Engine
│   ├── prompts/          # Dynamic Prompt Building (Limbic Injection)
│   ├── routing/          # Intelligent Model Router
│   └── security.py       # Surgical path validation
├── tools/                # Surgical Tooling
│   ├── ast/              # Rust-powered AST refactoring
│   ├── search_tools.py   # Robust multi-OS search
│   └── metacognition.py  # Reflection & Experience generation
├── native/               # High-performance Rust bindings
└── cache/                # Go-based caching services

research/                 # Scientific Benchmarking Framework
├── challenges.py         # Standardized engineering benchmarks
└── orchestrator.py       # Sandbox-isolated experiment runner
```

---

## Cognitive Core (Limbic System)

The Limbic System (`cortex/core/memory_layers/state.py`) regulates the agent's behavior through internal metrics:

- **Confidence Score (0.0-1.0)**: Certainty in the current path. Dropping confidence triggers strategy pivots.
- **Urgency Score (0.0-1.0)**: Drive to escalate or conclude a task.
- **Internal Monologue**: Persistent self-reflection injected into every prompt.

---

## Multi-Layered Memory

Cortex implements a hierarchical memory stack:

1. **Working Memory**: Immediate context (active files, recent tool outputs).
2. **Session Memory**: Records **Failed Approaches** and **Successful Patterns**.
3. **Semantic Memory**: Persistent vector storage (ChromaDB) with:
    - **Belief Verification**: Reinforcing memories confirmed by tools.
    - **Memory Decay**: Natural forgetting of unverified information over time.

---

## Testing & Research

### Running the Test Suite
Cortex maintains a 100% pass rate across 950+ tests.
```bash
pytest tests/ -v
```

### Running Research Experiments
Use the Research Framework to benchmark agent intelligence:
```bash
python run_research.py
```
This clones the project into a **Sandbox**, injects a challenge (e.g., corrupted config), and measures **Correction Latency**.

---

## Code Style

- **Strict Path Validation**: Always use `validate_path` from `cortex.core.security` for file operations.
- **Atomic Tooling**: Prefer one-shot tools like `create_and_execute_plan` for complex operations.
- **Metacognitive Logging**: Ensure tool results provide enough context for the Limbic appraisal system.

---

*Last updated: February 25, 2026 (v1.2.0)*
