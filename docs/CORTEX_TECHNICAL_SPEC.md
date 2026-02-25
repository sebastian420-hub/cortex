# Cortex: Technical Specification

## Version 1.2.0 (Bio-inspired Metacognition)

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Core Components](#2-core-components)
3. [Data Models](#3-data-models)
4. [Metacognitive Core (Limbic System)](#4-metacognitive-core-limbic-system)
5. [Tool System](#5-tool-system)
6. [Provider Interface](#6-provider-interface)
7. [Memory Architecture](#7-memory-architecture)
8. [Planning System](#8-planning-system)
9. [Research Framework](#9-research-framework)
10. [Security Model](#10-security-model)
11. [Configuration System](#11-configuration-system)
12. [Storage Layer](#12-storage-layer)
13. [UI/UX Specifications](#13-uiux-specifications)
14. [Testing Strategy](#14-testing-strategy)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
├─────────────────────────────────────────────────────────────┤
│  CLI │ REPL │ API Gateway │ Web UI (Future) │ MCP Server    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Agent Orchestration Layer                 │
├─────────────────────────────────────────────────────────────┤
│  Base Cortex Agent │ Enhanced Cortex Agent │ Subagents      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Cognitive Core Layer                      │
├─────────────────────────────────────────────────────────────┤
│  Metacognition (Limbic) │ Planning │ Memory │ Security      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Integration Layer                         │
├─────────────────────────────────────────────────────────────┤
│  Tool Registry │ Provider Factory │ Hook System │ AST       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    External Systems Layer                    │
├─────────────────────────────────────────────────────────────┤
│  Ollama │ DeepSeek │ Anthropic │ Git │ File System │ MCP    │
└─────────────────────────────────────────────────────────────┘
```

## 2. Core Components

### 2.1 Agent System

#### Enhanced Cortex Agent (`cortex/agent.py`)
In v1.2.0, the "Enhanced" and "Base" agents have been unified. The agent now supports:
- **Limbic Feedback**: Adjusts strategy based on Confidence and Urgency.
- **Atomic Planning**: 1-step creation and execution of task DAGs.
- **Layered Memory**: Multi-tier persistence from Working to Semantic memory.

## 3. Data Models

### 3.1 Metacognitive State (`cortex/core/memory_layers/state.py`)
```python
@dataclass
class MetacognitiveState:
    confidence_score: float = 0.8  # 0.0 - 1.0
    urgency_score: float = 0.1     # 0.0 - 1.0
    emotional_tone: str = "analytical" # analytical, confident, cautious, frustrated
    internal_monologue: str = ""   # Persistent self-reflection
```

## 4. Metacognitive Core (Limbic System)

The Limbic System acts as the agent's "Gut Feeling" and emotional regulator.

### 4.1 Appraisal Loop
1. **Action**: Agent executes a tool.
2. **Appraisal**: `StateManager` evaluates the result.
3. **Shift**: 
    - **Success** -> Confidence Spike (+0.1), Tone becomes "Confident".
    - **Failure** -> Confidence Drop (-0.15), Tone becomes "Cautious" or "Frustrated" (if failures >= 2).
4. **Injection**: The `Internal Monologue` is injected into the next prompt, forcing the LLM to reflect on the failure before acting again.

## 5. Tool System

### 5.1 Simplified Planning Tools
- `create_and_execute_plan`: The primary interface for complex tasks (4+ steps).
- `monitor_plan`: Tracks progress and completion percentage.
- `update_plan`: Dynamically modifies a running plan.

### 5.2 Surgical Tools (v1.2.0 Fixed)
- `search_files(query, path, file_pattern)`: Now features robust path resolution for all OS environments.

## 7. Memory Architecture

### 7.1 The Multi-Layered Memory Stack
1. **Working Memory**: Short-term context (max 20 items).
2. **Session Memory**: Tracks **Failed Approaches** and **Successful Patterns**.
3. **Semantic Memory**: Persistent vector storage (ChromaDB) with:
    - **Belief Verification**: Confidence reinforcement upon tool confirmation.
    - **Memory Decay**: Natural confidence reduction for unverified facts over time.

## 8. Planning System

### 8.1 Atomic Execution
Cortex v1.2.0 moves away from the "Plan then Execute" split. The `create_and_execute_plan` tool is an atomic operation that hands a validated DAG to the engine, reducing "context drift" where the agent forgets its plan during long runs.

## 9. Research Framework

The Research Framework (`research/`) is Cortex's "Laboratory" for systematic intelligence benchmarking.

### 9.1 Evaluation Tiers
- **Control**: Baseline without metacognition.
- **Architectural**: Enables the Limbic and Layered Memory systems.
- **Stress**: Injected environment failures (corrupted configs, tool instability).

### 9.2 Key KPIs
- **Correction Latency**: Steps taken to identify and fix an error.
- **Success Rate**: % of challenges passed in the sandbox.

## 14. Testing Strategy

### 14.1 Full-Stack Verification
The project maintains a **100% success rate** across 950+ tests.
- **Python**: Unit and Integration tests for agent logic.
- **Rust/Go**: Performance verification for native bindings and caching.

---

## Appendix C: Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.2.0 | 2026-02-25 | Metacognitive Core, Atomic Planning, Research Framework | Cortex Team |
| 1.1.0 | 2026-02-24 | Added AST-driven surgical refactoring and semantic memory | Cortex Team |
| 1.0.0 | 2024-01-15 | Initial technical specification | Cortex Team |
