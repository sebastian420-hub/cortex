# Cortex Comprehensive Improvement Plan v2

> Deep research-based improvement plan covering Performance, Memory, CI/CD, Plugin System, and Documentation.

## Table of Contents
1. [Performance Optimization](#1-performance-optimization)
2. [Memory Management](#2-memory-management)
3. [CI/CD Pipeline](#3-cicd-pipeline)
4. [Plugin System](#4-plugin-system)
5. [Documentation](#5-documentation)
6. [Implementation Priority](#6-implementation-priority)

---

## 1. Performance Optimization

### Current State Analysis

**Parallel Execution System:** `cortex/core/parallel.py`
- ThreadPoolExecutor with 4 workers (hardcoded)
- Hybrid parallel/serial batching based on tool safety
- No rate limiting for API calls
- Main conversation loop is synchronous

**Caching System:**
- LRU caches in `cortex/cache/` with 100-500 item limits
- Tool result caching with TTL
- Model response caching available but underutilized
- File content cache exists but not integrated with large file handling

### Issues Identified

| Issue | Location | Impact |
|-------|----------|--------|
| Hardcoded 4 workers | `parallel.py:45` | Suboptimal for different hardware |
| `batch_size` config unused | `parallel.py` | Config has no effect |
| No rate limiting | `parallel.py` | API throttling issues |
| Synchronous main loop | `agent.py:_process_message` | Blocks UI updates |
| Ripgrep check on every grep | `grep_tool.py` | Repeated subprocess calls |

### Improvement Tasks

#### Sprint P1: Parallel Execution Refinement
- [ ] **P1.1** Make worker count configurable
  - Add `parallel_workers` to `config/default.yaml`
  - Default to `min(4, cpu_count())`
  - File: `cortex/core/parallel.py:45`

- [ ] **P1.2** Implement batch_size functionality
  - Actually use the config value in `_batch_execute()`
  - Add dynamic batching based on tool type
  - File: `cortex/core/parallel.py`

- [ ] **P1.3** Add rate limiting for API calls
  - Create `RateLimiter` class with token bucket algorithm
  - Integrate with provider calls
  - File: New `cortex/core/rate_limiter.py`

- [ ] **P1.4** Async main loop option
  - Add `--async` flag for non-blocking execution
  - Use asyncio for I/O-bound operations
  - Keep backward compatibility
  - File: `cortex/agent.py`

#### Sprint P2: Caching Improvements
- [ ] **P2.1** Add ripgrep availability caching
  - Cache result of `shutil.which('rg')` at startup
  - File: `cortex/tools/grep_tool.py`

- [ ] **P2.2** Implement intelligent cache warming
  - Pre-cache frequently accessed files on startup
  - Based on git history or config
  - File: `cortex/cache/file_cache.py`

- [ ] **P2.3** Add cache statistics and monitoring
  - Track hit/miss rates
  - Log cache performance metrics
  - File: `cortex/cache/__init__.py`

- [ ] **P2.4** Implement distributed cache option
  - Redis backend for multi-instance scenarios
  - File: New `cortex/cache/redis_backend.py`

### Checklist Summary
```
Performance Optimization Progress:
[x] P1.1 - Configurable workers (implemented: cortex/agent.py:196-207, cortex/config.py:60-64)
[x] P1.2 - Batch size implementation (implemented: cortex/agent.py:206, cortex/config.py:63)
[x] P1.3 - Rate limiting (implemented: cortex/core/rate_limiter.py, cortex/agent.py:209-221)
[ ] P1.4 - Async main loop (pending - synchronous main loop still in use)
[x] P2.1 - Ripgrep caching (implemented: cortex/tools/grep_tool.py:36, 143-152)
[ ] P2.2 - Cache warming (pending - feature request for pre-caching)
[x] P2.3 - Cache monitoring (implemented: cortex/cache/file_cache.py:205-221)
[ ] P2.4 - Distributed cache (pending - Redis backend not implemented)
```

---

## 2. Memory Management

### Current State Analysis

**File Handling:** `cortex/tools/file_tools.py`
- Read limit: 2000 lines default
- Line truncation: 2000 characters
- Full file loaded for edits (no streaming)
- Binary file detection exists

**Context Window Management:** `cortex/core/conversation.py`
- Max tokens: 100,000 default
- Token estimation: ~4 chars per token
- Summarization when context full
- No partial file injection

**Memory Layers:**
- Working memory: Current conversation
- Session memory: `MemoryBank` class
- File cache: LRU with limits

### Issues Identified

| Issue | Location | Impact |
|-------|----------|--------|
| Full file load for edits | `file_tools.py:WriteFileTool` | OOM on large files |
| Simple token estimation | `conversation.py:_estimate_tokens` | Inaccurate for code |
| No streaming for large reads | `file_tools.py:ReadFileTool` | Memory spikes |
| Context wasted on unchanged content | `conversation.py` | Reduced effective context |

### Improvement Tasks

#### Sprint M1: Large File Handling
- [ ] **M1.1** Implement streaming file reads
  - Yield chunks instead of loading full file
  - Add `stream_file()` method
  - File: `cortex/tools/file_tools.py`

- [ ] **M1.2** Add chunked edit support
  - Edit files in place without full load
  - Use memory-mapped files for large edits
  - File: `cortex/tools/file_tools.py`

- [ ] **M1.3** Binary file handling improvements
  - Better detection (magic numbers)
  - Truncation with warning for binaries
  - File: `cortex/tools/file_tools.py`

- [ ] **M1.4** Add file size warnings
  - Warn user before loading files > 1MB
  - Suggest range reads for large files
  - File: `cortex/tools/file_tools.py`

#### Sprint M2: Context Window Optimization
- [ ] **M2.1** Improve token estimation
  - Use tiktoken for accurate counts
  - Cache token counts per message
  - File: `cortex/core/conversation.py`

- [ ] **M2.2** Implement smart context compression
  - Summarize old tool results
  - Keep only diffs for repeated file reads
  - File: `cortex/core/conversation.py`

- [ ] **M2.3** Add context budget visualization
  - Show context usage in status bar
  - Warn when approaching limit
  - File: `cortex/ui/status.py`

- [ ] **M2.4** Implement selective context injection
  - Only inject relevant file portions
  - Based on current task focus
  - File: `cortex/core/context.py`

### Checklist Summary
```
Memory Management Progress:
[x] M1.1 - Streaming file reads (implemented via offset/limit in ReadFileTool)
[ ] M1.2 - Chunked edit support (pending - full file load for edits)
[x] M1.3 - Binary file handling (implemented: cortex/tools/file_tools.py:64-89, 154-165)
[x] M1.4 - File size warnings (implemented: cortex/tools/file_tools.py:132-152)
[ ] M2.1 - Accurate token estimation (pending - uses simple ~4 chars/token estimate)
[ ] M2.2 - Smart context compression (pending - uses full summarization only)
[ ] M2.3 - Context budget visualization (pending - no UI status bar integration)
[ ] M2.4 - Selective context injection (pending - always loads full files)
```

---

## 3. CI/CD Pipeline

### Current State Analysis

**GitHub Actions Workflows:**
- `ci.yml` - Main CI (pytest, coverage, lint)
- `tests.yml` - Duplicate test workflow (redundant)

**Current Checks:**
- pytest with coverage (100+ tests)
- MyPy type checking (non-blocking)
- Flake8 linting
- Security scan with bandit (non-blocking)
- Black formatting check

**Missing:**
- No deployment pipeline
- No release automation
- No performance benchmarks
- No integration tests in CI

### Issues Identified

| Issue | Location | Impact |
|-------|----------|--------|
| Duplicate workflows | `.github/workflows/` | Maintenance burden |
| Non-blocking security | `ci.yml` | Vulnerabilities may merge |
| No deployment | N/A | Manual releases |
| No integration tests | `tests/` | E2E coverage gap |

### Improvement Tasks

#### Sprint C1: CI Consolidation
- [ ] **C1.1** Merge duplicate workflows
  - Combine `ci.yml` and `tests.yml`
  - Single workflow with matrix strategy
  - File: `.github/workflows/ci.yml`

- [ ] **C1.2** Make security checks blocking
  - Fail on high/critical vulnerabilities
  - Allow medium with review
  - File: `.github/workflows/ci.yml`

- [ ] **C1.3** Add MyPy strict mode
  - Gradually enable strict checking
  - Start with core modules
  - File: `pyproject.toml`

- [ ] **C1.4** Add test coverage threshold
  - Fail if coverage drops below 80%
  - Generate coverage badge
  - File: `.github/workflows/ci.yml`

#### Sprint C2: CD Pipeline
- [ ] **C2.1** Create release workflow
  - Trigger on version tags
  - Build and publish to PyPI
  - File: `.github/workflows/release.yml`

- [ ] **C2.2** Add changelog automation
  - Generate from conventional commits
  - Include in releases
  - File: `.github/workflows/release.yml`

- [ ] **C2.3** Create Docker build workflow
  - Build and push to ghcr.io
  - Multi-arch support
  - File: `.github/workflows/docker.yml`

- [ ] **C2.4** Add integration test job
  - Run E2E tests with mock LLM
  - Test tool execution pipeline
  - File: `.github/workflows/ci.yml`

#### Sprint C3: Quality Gates
- [ ] **C3.1** Add performance benchmarks
  - Benchmark tool execution times
  - Track regressions
  - File: `.github/workflows/benchmark.yml`

- [ ] **C3.2** Add documentation build check
  - Verify docs build without errors
  - Check for broken links
  - File: `.github/workflows/ci.yml`

- [ ] **C3.3** Add dependency audit
  - Check for vulnerable dependencies
  - Run weekly scheduled check
  - File: `.github/workflows/audit.yml`

### Checklist Summary
```
CI/CD Pipeline Progress:
[x] C1.1 - Merge duplicate workflows
[x] C1.2 - Blocking security checks
[x] C1.3 - MyPy strict mode
[x] C1.4 - Coverage threshold
[x] C2.1 - Release workflow
[x] C2.2 - Changelog automation
[x] C2.3 - Docker build
[ ] C2.4 - Integration tests
[ ] C3.1 - Performance benchmarks
[x] C3.2 - Documentation build check
[x] C3.3 - Dependency audit
```

---

## 4. Plugin System

### Current State Analysis

**Architecture:**
- Base class: `cortex/tools/base.py` (Tool ABC)
- Registry: `cortex/tools/registry.py` (1000 lines)
- Plugin loading: `load_plugin()` method exists

**Extension Points:**
- `PLUGIN_TOOLS` export convention
- Namespace support for tools
- Conditional tool registration (AST pattern)

**What Works:**
- Clean Tool base class with standardized responses
- Registry with enable/disable functionality
- Dynamic plugin loading from module paths

### Issues Identified

| Issue | Location | Impact |
|-------|----------|--------|
| No plugin documentation | `docs/` | Users can't create plugins |
| No example plugins | `examples/` | No learning resources |
| No plugin config support | `config/` | Manual loading required |
| No plugin discovery | `registry.py` | Plugins must be explicit |
| No security sandboxing | `registry.py` | Plugins have full access |

### Improvement Tasks

#### Sprint PL1: Plugin Documentation
- [x] **PL1.1** Create plugin development guide
  - Step-by-step tutorial
  - Tool interface explanation
  - Schema format reference
  - File: `docs/PLUGIN_DEVELOPMENT.md`

- [x] **PL1.2** Document registry API
  - Public methods documentation
  - Usage examples
  - File: `docs/api/REGISTRY.md`

- [x] **PL1.3** Create best practices guide
  - Error handling patterns
  - Permission modes
  - Testing strategies
  - File: `docs/PLUGIN_BEST_PRACTICES.md`

#### Sprint PL2: Example Plugins
- [ ] **PL2.1** Create simple plugin example
  - Single tool, minimal code (~50 lines)
  - "Hello World" of plugins
  - File: `examples/plugins/simple_tool/`

- [ ] **PL2.2** Create complex plugin example
  - Multiple tools with shared state
  - External API integration
  - File: `examples/plugins/api_integration/`

- [ ] **PL2.3** Create async plugin example
  - Async tool execution pattern
  - Progress reporting
  - File: `examples/plugins/async_tool/`

- [ ] **PL2.4** Create plugin template
  - Cookiecutter or copier template
  - Includes tests and docs
  - File: `examples/plugin-template/`

#### Sprint PL3: Plugin Infrastructure
- [ ] **PL3.1** Add plugin config support
  - `plugins:` section in config
  - Auto-load from config
  - File: `cortex/tools/registry.py`

- [ ] **PL3.2** Implement plugin discovery
  - Scan `~/.cortex/plugins/` directory
  - Entry points support
  - File: `cortex/tools/registry.py`

- [ ] **PL3.3** Add plugin metadata
  - Version, author, description
  - Dependency declarations
  - File: New `cortex/tools/plugin_meta.py`

- [ ] **PL3.4** Create plugin CLI commands
  - `cortex plugin list/install/remove`
  - Local and remote plugin support
  - File: `cortex/cli/plugin_commands.py`

### Checklist Summary
```
Plugin System Progress:
[x] PL1.1 - Plugin development guide
[ ] PL1.2 - Registry API docs
[x] PL1.3 - Best practices guide
[x] PL2.1 - Simple plugin example
[ ] PL2.2 - Complex plugin example
[ ] PL2.3 - Async plugin example
[ ] PL2.4 - Plugin template
[x] PL3.1 - Plugin config support
[ ] PL3.2 - Plugin discovery
[ ] PL3.3 - Plugin metadata
[ ] PL3.4 - Plugin CLI commands
```

---

## 5. Documentation

### Current State Analysis

**Existing Documentation:**
- User docs: README, COMMANDS.md (good quality)
- Design docs: docs/design/ (comprehensive)
- Research docs: docs/research/ (thorough)

**Code Documentation:**
- Module docstrings: 100% coverage
- Method docstrings: ~50% coverage
- Type hints: ~47% with return types

**Missing:**
- No API reference site
- No Sphinx/MkDocs build system
- No developer guide
- No type stubs (.pyi)

### Issues Identified

| Issue | Location | Impact |
|-------|----------|--------|
| No API docs | `docs/api/` empty | Can't browse API |
| No doc build system | N/A | No auto-generation |
| Sparse method docstrings | Various | IDE support limited |
| Generic type hints | `Dict[str, Any]` everywhere | Poor type checking |

### Improvement Tasks

#### Sprint D1: API Documentation
- [ ] **D1.1** Set up Sphinx with autodoc
  - Install sphinx, sphinx-autodoc-typehints
  - Configure in `docs/sphinx/`
  - File: `docs/sphinx/conf.py`

- [ ] **D1.2** Generate API reference
  - Auto-generate from docstrings
  - Organize by module
  - File: `docs/sphinx/api/`

- [ ] **D1.3** Add to CI pipeline
  - Build docs on PR
  - Fail on warnings
  - File: `.github/workflows/ci.yml`

- [ ] **D1.4** Deploy to GitHub Pages
  - Auto-publish on main merge
  - Configure custom domain
  - File: `.github/workflows/docs.yml`

#### Sprint D2: Developer Documentation
- [ ] **D2.1** Create developer guide
  - Architecture overview
  - Setup instructions
  - File: `docs/DEVELOPER.md`

- [ ] **D2.2** Create integration guide
  - Using Cortex as library
  - Embedding examples
  - File: `docs/INTEGRATION.md`

- [ ] **D2.3** Create troubleshooting guide
  - Common issues
  - Debug techniques
  - File: `docs/TROUBLESHOOTING.md`

- [ ] **D2.4** Create deployment guide
  - Production setup
  - Security hardening
  - File: `docs/DEPLOYMENT.md`

#### Sprint D3: Code Documentation Quality
- [ ] **D3.1** Add missing docstrings
  - Focus on public methods
  - Priority: planning.py, orchestration.py, routing/
  - Use consistent format (Google style)

- [ ] **D3.2** Improve type hints
  - Replace `Dict[str, Any]` with TypedDicts
  - Add return type hints to all public methods
  - File: Various core modules

- [ ] **D3.3** Create type stubs
  - Add `py.typed` marker
  - Create .pyi files for complex modules
  - File: `cortex/py.typed`, `cortex/*.pyi`

- [ ] **D3.4** Enable strict MyPy
  - Enable `disallow_untyped_defs`
  - Fix type errors incrementally
  - File: `pyproject.toml`

### Checklist Summary
```
Documentation Progress:
[x] D1.1 - Sphinx setup
[ ] D1.2 - API reference generation
[x] D1.3 - Docs in CI
[ ] D1.4 - GitHub Pages deployment
[x] D2.1 - Developer guide
[x] D2.2 - Integration guide
[x] D2.3 - Troubleshooting guide
[ ] D2.4 - Deployment guide
[ ] D3.1 - Missing docstrings
[ ] D3.2 - Improved type hints
[x] D3.3 - Type stubs
[ ] D3.4 - Strict MyPy
```

---

## 6. Implementation Priority

### Phase 1: Foundation (High Impact, Quick Wins)
**Timeline: First**

| Task | Area | Effort | Impact |
|------|------|--------|--------|
| C1.1 Merge workflows | CI/CD | Low | Med |
| PL1.1 Plugin dev guide | Plugin | Med | High |
| D2.1 Developer guide | Docs | Med | High |
| M1.4 File size warnings | Memory | Low | Med |
| P2.1 Ripgrep caching | Perf | Low | Med |

### Phase 2: Core Improvements (High Value)
**Timeline: Second**

| Task | Area | Effort | Impact |
|------|------|--------|--------|
| D1.1-D1.4 Sphinx setup | Docs | Med | High |
| PL2.1-PL2.4 Examples | Plugin | Med | High |
| C2.1-C2.2 Release workflow | CI/CD | Med | High |
| M2.1 Token estimation | Memory | Med | Med |
| P1.1-P1.2 Workers & batch | Perf | Med | Med |

### Phase 3: Advanced Features (Enhancement)
**Timeline: Third**

| Task | Area | Effort | Impact |
|------|------|--------|--------|
| M1.1-M1.2 Streaming files | Memory | High | High |
| PL3.1-PL3.4 Plugin infra | Plugin | High | High |
| P1.3-P1.4 Rate limit & async | Perf | High | Med |
| C2.3-C2.4 Docker & E2E | CI/CD | Med | Med |
| D3.1-D3.4 Code docs | Docs | High | Med |

---

## Master Checklist

### Performance Optimization (8 tasks)
```
[x] P1.1 - Configurable workers (cortex/agent.py:203, config.py:62)
[x] P1.2 - Batch size implementation (cortex/agent.py:205, config.py:63)
[x] P1.3 - Rate limiting (cortex/core/rate_limiter.py, agent.py:862-867)
[ ] P1.4 - Async main loop (agent.py needs async _process_message)
[x] P2.1 - Ripgrep caching (cortex/tools/grep_tool.py:36, 143-152)
[ ] P2.2 - Cache warming (cortex/cache/file_cache.py needs pre_cache method)
[x] P2.3 - Cache monitoring (cortex/cache/file_cache.py:205-221)
[ ] P2.4 - Distributed cache (cortex/cache/redis_backend.py - not created)
```

### Memory Management (8 tasks)
```
[ ] M1.1 - Streaming file reads
[ ] M1.2 - Chunked edit support
[x] M1.3 - Binary file handling
[x] M1.4 - File size warnings
[ ] M2.1 - Accurate token estimation
[ ] M2.2 - Smart context compression
[ ] M2.3 - Context budget visualization
[ ] M2.4 - Selective context injection
```

### CI/CD Pipeline (11 tasks)
```
[x] C1.1 - Merge duplicate workflows
[x] C1.2 - Blocking security checks
[x] C1.3 - MyPy strict mode
[x] C1.4 - Coverage threshold
[x] C2.1 - Release workflow
[x] C2.2 - Changelog automation
[x] C2.3 - Docker build
[ ] C2.4 - Integration tests
[ ] C3.1 - Performance benchmarks
[x] C3.2 - Documentation build check
[x] C3.3 - Dependency audit
```

### Plugin System (11 tasks)
```
[x] PL1.1 - Plugin development guide
[ ] PL1.2 - Registry API docs
[x] PL1.3 - Best practices guide
[x] PL2.1 - Simple plugin example
[ ] PL2.2 - Complex plugin example
[ ] PL2.3 - Async plugin example
[ ] PL2.4 - Plugin template
[x] PL3.1 - Plugin config support
[ ] PL3.2 - Plugin discovery
[ ] PL3.3 - Plugin metadata
[ ] PL3.4 - Plugin CLI commands
```

### Documentation (12 tasks)
```
[x] D1.1 - Sphinx setup
[ ] D1.2 - API reference generation
[x] D1.3 - Docs in CI
[ ] D1.4 - GitHub Pages deployment
[x] D2.1 - Developer guide
[x] D2.2 - Integration guide
[x] D2.3 - Troubleshooting guide
[ ] D2.4 - Deployment guide
[ ] D3.1 - Missing docstrings
[ ] D3.2 - Improved type hints
[x] D3.3 - Type stubs
[ ] D3.4 - Strict MyPy
```

---

## Total: 50 Tasks

| Category | Tasks | Priority Items |
|----------|-------|----------------|
| Performance | 8 | P1.1, P2.1 |
| Memory | 8 | M1.4, M2.1 |
| CI/CD | 11 | C1.1, C2.1 |
| Plugin | 11 | PL1.1, PL2.1 |
| Documentation | 12 | D1.1, D2.1 |

---

*Generated: 2026-01-17*
*Based on deep codebase research*
