# Cortex Testing Plan

## Overview

This document outlines a comprehensive testing strategy for the Cortex AI coding assistant. The plan covers unit tests, integration tests, functional tests, security tests, and performance tests to ensure reliability, security, and performance across all features.

## Implementation Status (March 2024)

**Phase 1: Foundation - COMPLETED ✅**

### ✅ Test Infrastructure Setup
- **Configuration**: `pytest.ini`, `.coveragerc`, `requirements-test.txt`
- **Shared Fixtures**: `tests/conftest.py` with comprehensive mocking system
- **CI/CD Pipeline**: Multi-platform GitHub Actions workflow (`tests.yml`)
- **Security Scanning**: Integrated bandit and safety checks

### ✅ Enhanced Agent Testing
- **File**: `tests/unit/agent/test_enhanced_agent.py`
- **Tests**: 17 tests covering planning system, layered memory, backward compatibility

### ✅ Core Module Unit Tests (166 tests total)
- **Context Management** (`test_context.py`): 17 tests - Token estimation, history truncation
- **Parallel Execution** (`test_parallel.py`): 28 tests - Tool batching, execution modes
- **Planning System** (`test_planning.py`): 20 tests - Plan/PlanStep operations, engine functionality
- **Streaming Responses** (`test_streaming.py`): 13 tests - Chunk aggregation, display logic
- **Conversation Summarization** (`test_summarization.py`): 33 tests - Simple/LLM/hybrid strategies
- **Transaction Management** (`test_transaction.py`): 38 tests - Backup/restore, rollback capability

### 📊 Current Test Statistics
- **New Tests Added**: 166 unit tests
- **Total Test Files**: 36+ test files (including existing)
- **Total Test Functions**: 325+ test functions (159 existing + 166 new)
- **Coverage Goal**: 80% minimum (configured in `.coveragerc`)

### 📊 Phase 1 Test Results (March 2024)
**Test Execution**: 642 tests run, 642 passed, 2 skipped (100% pass rate for non-skipped tests)

**All previously failing categories are now passing.**

**Next Steps**:
- Proceed with Phase 2: Integration & Functional Testing

### 🔄 Next Phase: Integration & Functional Testing
- End-to-end workflow validation
- Provider integration with real services
- Functional CLI testing
- Permission mode behavior verification

## Current Test Coverage Analysis

### Current Test Suites
- **35+ test files** with approximately **325+ test functions** (166 new unit tests added)
- **Covered areas**:
  - Basic agent initialization and configuration (`test_agent.py`)
  - Cloud provider integration (DeepSeek, Anthropic) (`test_agent_cloud.py`)
  - CLI command handling (`test_cli_commands.py`)
  - Conversation management (`test_conversation.py`)
  - Error handling and recovery (`test_error_handling.py`)
  - Loop guard mechanisms (`test_loop_guards.py`)
  - Security features (`test_security.py`)
  - Session storage and management (`test_storage_sessions.py`)
  - Tool registry and execution (`test_tools.py`)
  - AST-based code analysis tools (`tests/ast/`)
  - Integration tests for agent loops (`tests/integration/`)
  - Phase-specific feature tests (`test_phase1_features.py`, etc.)

### Test Statistics by Module
- **Agent Core (Basic)**: 30+ tests across 4 files
- **Enhanced Agent**: 17 tests (`test_enhanced_agent.py`) ✅ NEW
- **Core Modules**: 166 tests across 7 files ✅ NEW
  - Context Management: 17 tests (`test_context.py`)
  - Parallel Execution: 28 tests (`test_parallel.py`)
  - Planning System: 20 tests (`test_planning.py`)
  - Streaming Responses: 13 tests (`test_streaming.py`)
  - Conversation Summarization: 33 tests (`test_summarization.py`)
  - Transaction Management: 38 tests (`test_transaction.py`)
- **CLI & Commands**: 4 tests
- **Providers**: 12 tests
- **Security**: 16 tests
- **Tools**: 20+ tests
- **AST System**: 8+ tests
- **Integration**: 13+ tests

## Identified Testing Gaps

Based on analysis of the codebase structure, the following critical areas need additional test coverage:

### 1. Enhanced Agent System ✅ IMPLEMENTED
- **File**: `cortex/agent_enhanced.py` - **17 TESTS CREATED** (`tests/unit/agent/test_enhanced_agent.py`)
- Features: Planning system, layered memory, enhanced processing
- Critical for advanced functionality
- **Status**: ✅ Comprehensive test suite covering initialization, planning integration, layered memory, backward compatibility, and processing workflows

### 2. Core Components ✅ IMPLEMENTED
- **Context Management** (`core/context.py`): ✅ **17 tests** - Token estimation, history truncation (`tests/unit/core/test_context.py`)
- **Parallel Execution** (`core/parallel.py`): ✅ **28 tests** - Tool batching, execution modes (`tests/unit/core/test_parallel.py`)
- **Planning System** (`core/planning.py`): ✅ **20 tests** - Plan/PlanStep operations, engine functionality (`tests/unit/core/test_planning.py`)
- **Streaming Responses** (`core/streaming.py`): ✅ **13 tests** - Chunk aggregation, display logic (`tests/unit/core/test_streaming.py`)
- **Summarization** (`core/summarization.py`): ✅ **33 tests** - Simple/LLM/hybrid strategies (`tests/unit/core/test_summarization.py`)
- **Transaction Management** (`core/transaction.py`): ✅ **38 tests** - Backup/restore, rollback capability (`tests/unit/core/test_transaction.py`)

### 3. UI Components (`ui/` directory)
- **Console Interface** (`ui/console.py`): Output formatting and display
- **REPL Interface** (`ui/repl.py`): Interactive command processing
- **Progress Indicators** (`ui/progress.py`): Status updates
- **Display Utilities** (`ui/display.py`): Content presentation

### 4. MCP Integration (`mcp/` directory)
- **MCP Client** (`mcp/client.py`): Model Context Protocol integration
- **MCP Protocol** (`mcp/protocol.py`): Message handling
- **MCP Tools** (`mcp/tools.py`): Tool integration
- **MCP Transport** (`mcp/transport.py`): Network communication

### 5. Hook System (`hooks/` directory)
- **Hook Manager** (`hooks/manager.py`): Event system management
- **Built-in Hooks** (`hooks/builtin.py`): Default hook implementations
- **Event System** (`hooks/events.py`): Event definitions and handling

### 6. Subagent System (`subagent/`)
- **Task Delegation** (`subagent/task_tool.py`): Complex task handling
- **Context Management** (`subagent/context.py`): Subagent context

### 7. Cache System (`cache/`)
- **File Cache** (`cache/file_cache.py`): Caching mechanism
- **Cache Management**: Invalidation and cleanup

### 8. Recovery System (`core/recovery/`)
- **Checkpoint Manager**: Session checkpointing
- **Health Monitor**: Session health assessment
- **Recovery Orchestrator**: Automatic recovery strategies

### 9. Memory Layers (`core/memory_layers/`)
- **Session Memory**: Short-term context
- **Working Memory**: Active task memory
- **State Memory**: Long-term state preservation

## Comprehensive Testing Strategy

### 1. Unit Testing

#### 1.1 Agent Layer Testing
**Basic Agent** (`cortex/agent.py`):
```python
# Existing tests cover:
- test_agent_initialization()
- test_agent_load_project_context()
- test_agent_execute_tool_string_args()

# Missing tests needed:
- test_agent_model_switching() - Model switching with validation
- test_agent_permission_mode_transitions() - Mode switching behavior
- test_agent_memory_bank_operations() - Memory CRUD operations
- test_agent_session_recovery() - Recovery system integration
- test_agent_tool_validation() - Tool permission validation
- test_agent_conversation_summarization() - Auto-summarization
- test_agent_streaming_responses() - Streaming mode handling
```

**Enhanced Agent** (`cortex/agent_enhanced.py`):
```python
# CRITICAL: No existing tests
- test_enhanced_agent_initialization() - Enhanced features setup
- test_planning_system_integration() - Planning workflow
- test_layered_memory_functionality() - Memory layer interactions
- test_enhanced_processing_workflows() - Complex task handling
- test_backward_compatibility() - Compatibility with basic agent
- test_plan_execution_monitoring() - Plan progress tracking
```

#### 1.2 Core Module Testing
**Context Management** (`core/context.py`):
- Context initialization and validation
- Project context loading from AGENT.md
- Context persistence and restoration
- Context update and merge operations

**Parallel Execution** (`core/parallel.py`):
- Concurrent tool execution safety
- Tool call serialization/deserialization
- Error handling in parallel operations
- Resource limiting and throttling

**Planning System** (`core/planning.py`):
- Plan generation from user requests
- Plan validation and optimization
- Plan execution monitoring
- Plan adaptation based on results

**Streaming Responses** (`core/streaming.py`):
- Stream parsing and chunk handling
- Real-time display updates
- Stream interruption handling
- Error recovery during streaming

**Summarization** (`core/summarization.py`):
- Conversation summarization algorithms
- Summary quality assessment
- Summary injection into context
- Different summarization strategies

**Transaction Management** (`core/transaction.py`):
- Transaction creation and management
- Rollback functionality
- Transaction isolation
- Backup and restore operations

#### 1.3 Tool System Testing
**Tool Registry** (`tools/registry.py`):
- Tool registration and discovery
- Tool validation and security checks
- Tool execution lifecycle
- Tool permission checking

**Individual Tools** (comprehensive coverage needed):
- **File Tools**: `read_file`, `write_file`, `edit`, `list_files`, `glob`, `grep`
- **Git Tools**: All git operations with proper mocking
- **Web Tools**: `web_fetch`, `web_search` with HTTP mocking
- **AST Tools**: `ast_search_tool`, `ast_analyze_tool`, `ast_extract_tool`
- **User Interaction**: `ask_user_tool`, `todo_tool`
- **Skill Tools**: `skill_loader` for development workflows
- **Task Tools**: `task` delegation to subagents

#### 1.4 UI Component Testing
**Console Interface** (`ui/console.py`):
- Output formatting for different content types
- Markdown rendering and syntax highlighting
- Progress indicator display
- Error message presentation

**REPL Interface** (`ui/repl.py`):
- Command history management
- Input validation and parsing
- Tab completion functionality
- Multi-line input handling

#### 1.5 MCP Integration Testing
**MCP Client** (`mcp/client.py`):
- Connection establishment and maintenance
- Protocol message serialization/deserialization
- Tool discovery and execution
- Error handling and reconnection logic

### 2. Integration Testing

#### 2.1 End-to-End Workflows
**Coding Assistant Workflow**:
1. User requests code modification
2. Agent analyzes codebase using AST tools
3. Agent generates execution plan
4. Agent executes tools with user approval
5. Results presented and validated

**Session Management Workflow**:
1. Start new session with specific model
2. Perform complex operations (read, write, git)
3. Save session state
4. Load session and verify state restoration
5. Continue operations seamlessly

**Model Switching Workflow**:
1. Start with local Ollama model
2. Switch to cloud provider (DeepSeek/Anthropic)
3. Continue conversation with context preservation
4. Switch back to local model
5. Verify conversation continuity

#### 2.2 Provider Integration Testing
**Multi-Provider Scenarios**:
- Ollama local models with various model sizes
- DeepSeek API with different endpoints
- Anthropic Claude API variants
- Provider fallback on failure
- API key validation and error handling

**Error Scenarios**:
- Network timeouts and retries
- Rate limiting handling
- Invalid API key responses
- Provider-specific error formats

#### 2.3 Tool Chain Integration
**Complex Sequences**:
- File reading → AST analysis → Code generation → Testing
- Web search → Content extraction → File creation → Git commit
- Error detection → Recovery planning → Automatic repair
- Multiple tool execution with dependency resolution

### 3. Functional Testing

#### 3.1 CLI Interface Testing
**Command-Line Arguments**:
- Model selection (`--model`, `-m`)
- Provider override (`--provider`)
- Permission modes (`--auto-approve`, `--plan-mode`)
- Session management (`--save-session`, `--load-session`)
- Configuration file loading (`--config`, `-c`)
- Output formats (`--output-format`, `-o`)

**Interactive Commands**:
- `/help` command with topic-based help
- `/model` switching with validation
- `/mode` permission mode changes
- `/save` and `/load` session operations
- `/clear` conversation reset
- `/project` information display
- Recovery commands (`/session validate`, `/session repair`, `/session rollback`)

#### 3.2 Permission Mode Testing
**Normal Mode**:
- Tool execution requiring user approval
- Permission escalation for dangerous operations
- User confirmation flow
- Cancel operation handling

**Auto-Approve Mode**:
- Automated tool execution without prompts
- Safety boundary verification
- Dangerous operation blocking
- Audit logging of auto-approved actions

**Plan Mode**:
- Read-only analysis without modifications
- Plan generation without execution
- Resource usage limitations
- Analysis result presentation

### 4. Security Testing

#### 4.1 Input Validation
- Path traversal prevention
- Command injection protection
- Malicious file path handling
- Environment variable sanitization
- JSON/XML injection prevention

#### 4.2 Permission System Security
- Unauthorized tool execution attempts
- Permission bypass detection
- Secure session handling
- API key protection and masking
- Credential storage security

#### 4.3 Tool Safety
- Dangerous command prevention (`rm -rf /`, etc.)
- File system boundary enforcement
- Network access restrictions
- Resource usage limits (CPU, memory, disk)
- Timeout enforcement for long operations

#### 4.4 Data Protection
- Session data encryption at rest
- Secure communication channels
- Memory sanitization between sessions
- Cache isolation and cleanup
- Sensitive data masking in logs

### 5. Performance Testing

#### 5.1 Response Time Benchmarks
- Tool execution latency (read_file, write_file, etc.)
- Model response time across providers
- File system operation performance
- Network request latency
- Large file handling performance

#### 5.2 Memory Usage Profiling
- Conversation history memory management
- Memory bank growth and cleanup
- Cache efficiency and hit rates
- Resource cleanup after operations
- Memory leak detection

#### 5.3 Scalability Testing
- Large codebase analysis performance
- Concurrent tool execution limits
- Long-running session stability
- Multiple file operation handling
- High-frequency user interaction

#### 5.4 Stress Testing
- Maximum iteration limit handling
- Token limit enforcement and recovery
- Large file size limitations
- Concurrent operation stress
- Network failure scenarios

### 6. Cross-Platform Testing

#### 6.1 Operating System Compatibility
- **Windows** (current development environment)
- **Linux** (common server environment)
- **macOS** (common developer environment)

#### 6.2 Python Version Compatibility
- Python 3.8 (minimum supported)
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

#### 6.3 Environment Variations
- Virtual environments (venv, conda)
- Docker container environments
- Different shell environments (cmd, PowerShell, bash, zsh)
- Network configurations (proxy, VPN, firewalls)

## Test Implementation Plan

### Phase 1: Foundation ✅ COMPLETED (March 2024)
**Objective**: ✅ **Established comprehensive test infrastructure and critical coverage**

1. **Test Infrastructure Setup** ✅
   - ✅ Configured pytest with coverage reporting (`pytest-cov`, `.coveragerc`)
   - ✅ Set up GitHub Actions CI/CD workflow (`.github/workflows/tests.yml`)
   - ✅ Created shared test utilities and fixtures (`tests/conftest.py`)
   - ✅ Established mocking patterns for external services (Ollama, DeepSeek, Anthropic)
   - ✅ Added security scanning (bandit, safety) to CI pipeline
   - ✅ Added test requirements (`requirements-test.txt`)

2. **Enhanced Agent Testing** ✅ **HIGH PRIORITY COMPLETED**
   - ✅ Created test suite for `agent_enhanced.py` (`tests/unit/agent/test_enhanced_agent.py`) - **17 tests**
   - ✅ Test planning system integration with layered memory
   - ✅ Test layered memory functionality and state persistence
   - ✅ Verified backward compatibility with basic agent

3. **Core Module Unit Tests** ✅ **166 TESTS IMPLEMENTED**
   - ✅ Context management tests (`test_context.py`) - **17 tests**
   - ✅ Parallel execution tests (`test_parallel.py`) - **28 tests**
   - ✅ Planning system tests (`test_planning.py`) - **20 tests**
   - ✅ Streaming response tests (`test_streaming.py`) - **13 tests**
   - ✅ Conversation summarization tests (`test_summarization.py`) - **33 tests**
   - ✅ Transaction management tests (`test_transaction.py`) - **38 tests**

### Phase 2: Integration & Functional (Weeks 3-4)
**Objective**: Ensure end-to-end functionality and workflow reliability

1. **End-to-End Workflow Tests**
   - Complete coding assistant scenarios
   - Session management flows
   - Model switching workflows
   - Complex tool sequences

2. **Provider Integration Tests**
   - Mock provider testing suite
   - Real provider testing (staged, with rate limits)
   - Error scenario and recovery testing
   - Fallback mechanism validation

3. **Functional CLI Testing**
   - Command-line argument validation
   - Interactive command processing
   - Permission mode behavior
   - Session operation flows

### Phase 3: Security & Performance (Weeks 5-6)
**Objective**: Ensure security and performance requirements are met

1. **Security Testing Suite**
   - Input validation and sanitization
   - Permission system security
   - Tool safety mechanisms
   - Data protection measures

2. **Performance Benchmarking**
   - Response time measurements
   - Memory usage profiling
   - Stress test scenarios
   - Scalability testing

3. **Edge Case Coverage**
   - Error recovery scenarios
   - Boundary condition testing
   - Unusual user interaction patterns
   - Resource exhaustion handling

### Phase 4: Cross-Platform & Maintenance (Weeks 7-8)
**Objective**: Ensure broad compatibility and maintainable test suite

1. **Cross-Platform Validation**
   - OS-specific testing matrix
   - Python version compatibility matrix
   - Environment variation testing
   - Installation and setup testing

2. **Test Suite Maintenance**
   - Test documentation and examples
   - Flaky test identification and fixing
   - Performance optimization of test suite
   - Regular test review and updates

### Continuous Improvement
- **Quarterly Reviews**: Test effectiveness and coverage analysis
- **New Technologies**: Evaluate and adopt new testing tools annually
- **Industry Practices**: Regular review and adoption of best practices
- **Feedback Incorporation**: Monthly review of developer and user feedback

### Knowledge Sharing
- **Documentation**: Living documentation updated with changes
- **Training**: Quarterly workshops on test patterns and tools
- **Community**: Encourage open source contributions to test suite
- **Knowledge Base**: Curated collection of test patterns and solutions

## Appendix

### Test Directory Structure
```
tests/
├── unit/
│   ├── agent/
│   │   ├── test_basic_agent.py
│   │   ├── test_enhanced_agent.py
│   │   └── test_agent_security.py
│   ├── core/
│   │   ├── test_context.py
│   │   ├── test_parallel.py
│   │   ├── test_planning.py
│   │   ├── test_streaming.py
│   │   ├── test_summarization.py
│   │   └── test_transaction.py
│   ├── tools/
│   │   ├── test_file_tools.py
│   │   ├── test_git_tools.py
│   │   ├── test_web_tools.py
│   │   ├── test_ast_tools.py
│   │   └── test_tool_registry.py
│   ├── ui/
│   │   ├── test_console.py
│   │   ├── test_repl.py
│   │   └── test_display.py
│   ├── mcp/
│   │   ├── test_client.py
│   │   ├── test_protocol.py
│   │   └── test_tools.py
│   └── utils/
│       ├── test_errors.py
│       ├── test_timeouts.py
│       └── test_encoding.py
├── integration/
│   ├── workflows/
│   │   ├── test_coding_workflow.py
│   │   ├── test_session_workflow.py
│   │   └── test_model_switching.py
│   ├── providers/
│   │   ├── test_ollama_integration.py
│   │   ├── test_deepseek_integration.py
│   │   └── test_anthropic_integration.py
│   └── toolchains/
│       ├── test_file_analysis_chain.py
│       ├── test_web_research_chain.py
│       └── test_error_recovery_chain.py
├── functional/
│   ├── cli/
│   │   ├── test_cli_arguments.py
│   │   ├── test_interactive_commands.py
│   │   └── test_permission_modes.py
│   └── commands/
│       ├── test_help_system.py
│       ├── test_session_commands.py
│       └── test_recovery_commands.py
├── security/
│   ├── test_input_validation.py
│   ├── test_permission_security.py
│   ├── test_tool_safety.py
│   └── test_data_protection.py
├── performance/
│   ├── benchmarks/
│   │   ├── test_response_times.py
│   │   └── test_memory_usage.py
│   ├── stress/
│   │   ├── test_iteration_limits.py
│   │   └── test_resource_limits.py
│   └── scalability/
│       ├── test_large_codebases.py
│       └── test_concurrent_operations.py
├── fixtures/
│   ├── code_samples/
│   │   ├── python/
│   │   ├── javascript/
│   │   ├── typescript/
│   │   └── java/
│   ├── sessions/
│   │   ├── simple_session.json
│   │   ├── complex_session.json
│   │   └── recovery_session.json
│   └── configs/
│       ├── default_config.yaml
│       ├── secure_config.yaml
│       └── custom_hooks.yaml
└── conftest.py
```

### Required Test Dependencies
```txt
# requirements-test.txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
pytest-asyncio>=0.21.0
pytest-xdist>=3.0.0
pytest-benchmark>=4.0.0
hypothesis>=6.0.0
freezegun>=1.2.0
responses>=0.23.0
docker>=6.0.0
bandit>=1.7.0
safety>=2.0.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0
```

### Configuration Files
**`pytest.ini`**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --strict-config
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    security: marks tests as security tests
    performance: marks tests as performance benchmarks
```

**`.coveragerc`**:
```ini
[run]
source = cortex
omit = 
    */tests/*
    */__pycache__/*
    */migrations/*
    setup.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if self.debug:
    if settings.DEBUG
    raise AssertionError
    raise NotImplementedError
    if 0:
    if __name__ == .__main__.:
    class .*Mock.:
    @abc.abstractmethod

fail_under = 80
```

### Key Performance Indicators
- **Test Execution Frequency**: Daily automated runs
- **Flaky Test Rate**: <1% of total tests
- **Test Addition Rate**: 1:1 tests to new features
- **Bug Detection Rate**: >95% bugs caught by tests
- **Test Maintenance Effort**: <10% of development time
- **Test Suite Growth**: Controlled, optimized growth

---

*This testing plan provides a comprehensive framework for ensuring the quality, reliability, and security of the Cortex AI coding assistant. Regular review and updates will ensure it remains effective as the codebase evolves and new requirements emerge.*
