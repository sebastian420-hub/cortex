# Cortex Hybrid Architecture - Implementation Plan (Phases 1-3)

## Codebase Assessment Summary

**Current State:**
- Python 3.10 on Windows, no Rust/Go toolchains yet
- Well-structured codebase: 43+ core modules, 23+ tools, 58 test files
- Existing performance patterns: LRU file cache, parallel tool execution, ripgrep subprocess, tree-sitter AST
- No benchmarks or feature flags exist yet
- Provider abstraction (Ollama/DeepSeek/Anthropic/OpenRouter), Tool base class, Config hierarchy

**Key files that will be modified or extended:**
- `cortex/core/context.py` (302 lines) - Token counting
- `cortex/tools/grep_tool.py` (545 lines) - Search via ripgrep subprocess
- `cortex/code_ast/parser.py` (230 lines) - Tree-sitter Python bindings
- `cortex/cache/file_cache.py` (545 lines) - LRU cache
- `cortex/cache/redis_backend.py` (563 lines) - Redis distributed cache
- `cortex/core/parallel.py` (396 lines) - Parallel tool execution
- `cortex/config.py` (477 lines) - Configuration system
- `cortex/tools/base.py` (219 lines) - Tool base class

---

## Phase 1: Foundation (Profiling, Benchmarks, Feature Flags)

### 1.1 Performance Profiler Module

**New file: `cortex/core/profiler.py` (~250 lines)**

Purpose: Instrument critical code paths with timing and memory tracking.

```
Components:
- PerformanceProfiler class (singleton)
  - start_operation(name) / end_operation(name) context manager
  - @profile decorator for functions
  - tracemalloc integration for memory tracking
  - Results storage: operation → [duration_ms, memory_delta_kb, timestamp]
  - generate_report() → dict with stats (min/max/avg/p50/p95/p99)
  - export_report(path) → JSON file

- Instrumentation targets:
  - grep_tool.execute() → "search"
  - glob_tool.execute() → "glob"
  - ASTParser.parse() → "ast_parse"
  - ASTParser.parse_file() → "ast_parse_file"
  - estimate_tokens() → "token_count"
  - count_message_tokens() → "message_token_count"
  - OllamaProvider.chat() → "model_inference"
  - OllamaProvider.stream_chat() → "model_stream"
  - FileCache.get() → "cache_get"
  - FileCache.set() → "cache_set"
  - ParallelToolExecutor.execute_batch() → "tool_batch"
  - truncate_history() → "context_truncation"
```

**Modify: `cortex/config.py`**
- Add `profiling` config section: `enabled: false, output_dir: ".cortex/profiles", auto_report: false`

### 1.2 Benchmark Suite

**New file: `tests/benchmarks/bench_search.py` (~150 lines)**
- Benchmark grep_tool with 1K/5K/10K file directories
- Benchmark glob_tool with various patterns
- Uses pytest-benchmark (already in requirements-test.txt)

**New file: `tests/benchmarks/bench_ast.py` (~120 lines)**
- Benchmark AST parsing for Python/JS/TS files of varying sizes
- Benchmark AST cache hit/miss scenarios
- Benchmark code_ast.service queries (function extraction, class extraction)

**New file: `tests/benchmarks/bench_tokens.py` (~100 lines)**
- Benchmark estimate_tokens() with varying text sizes (1K-100K chars)
- Benchmark count_message_tokens() with conversation histories
- Benchmark tiktoken vs fallback approximation

**New file: `tests/benchmarks/bench_cache.py` (~100 lines)**
- Benchmark FileCache get/set with various file sizes
- Benchmark LRU eviction under load
- Benchmark pre-cache performance

**New file: `tests/benchmarks/bench_e2e.py` (~120 lines)**
- End-to-end workflow benchmarks (simulated):
  - "code search" workflow: glob → grep → read → respond
  - "file edit" workflow: read → edit → write
  - "code analysis" workflow: glob → AST parse → extract functions
- Measures total pipeline time

**New file: `tests/benchmarks/conftest.py` (~80 lines)**
- Shared fixtures: temp directories with generated test files
- Baseline result storage and comparison
- `generate_test_codebase(num_files, avg_lines)` fixture

**Modify: `pytest.ini`**
- Add benchmark configuration section
- Add `benchmarks` test path

### 1.3 Feature Flag System

**New file: `cortex/core/feature_flags.py` (~200 lines)**

Purpose: Enable gradual rollout of hybrid components with safe fallback.

```
Components:
- FeatureFlag enum:
  - RUST_SEARCH (search via Rust native binding)
  - RUST_AST (AST parsing via Rust tree-sitter)
  - RUST_TOKENIZER (token counting via Rust)
  - GO_CACHE (Go-based caching service)
  - GO_MODEL_MANAGER (Go background model management)
  - PROFILING (performance profiling)

- FeatureManager class (singleton):
  - __init__(config: dict)
  - is_enabled(flag: FeatureFlag) → bool
  - enable(flag) / disable(flag)
  - get_all_flags() → dict[FeatureFlag, bool]
  - check_capability(flag) → bool
    (checks if native extension is actually importable)
  - with_fallback(flag, native_fn, fallback_fn, *args) → result
    (try native, fall back to Python on ImportError/RuntimeError)
  - get_stats() → dict (how often each flag was used, fallback rate)

- Platform capability detection:
  - _check_rust_available() → bool (try import cortex_native)
  - _check_go_available() → bool (check gRPC service health)
  - _check_ripgrep_available() → bool (existing check)
```

**Modify: `cortex/config.py`**
- Add `feature_flags` config section with defaults (all hybrid features off)
- Add `CORTEX_FEATURE_*` environment variable support

**Modify: `cortex/core/agent_init.py`**
- Initialize FeatureManager during agent setup
- Pass to tools that have hybrid implementations

### 1.4 Build System Setup

**New file: `Makefile` (~100 lines)**
```
Targets:
- make install        → pip install -e ".[dev]"
- make test          → pytest tests/ -v
- make benchmark     → pytest tests/benchmarks/ --benchmark-only
- make profile       → python -m cortex.core.profiler
- make rust-build    → cd rust/ && maturin develop
- make go-build      → cd go/ && go build ./...
- make build-all     → install + rust-build + go-build
- make lint          → black + flake8 + mypy
- make clean         → remove build artifacts
```

**New file: `scripts/setup_toolchains.ps1` (~60 lines)**
- PowerShell script to install Rust (rustup) and Go on Windows
- Verify installations
- Install maturin (pip install maturin)
- Install protoc for gRPC

**New file: `scripts/setup_toolchains.sh` (~50 lines)**
- Bash equivalent for Linux/macOS

**Modify: `pyproject.toml`**
- Add `[project.optional-dependencies]` for `hybrid` extras
- Add maturin build configuration

### Phase 1 Deliverables
- [ ] Performance profiler with decorator and context manager API
- [ ] 5 benchmark files covering all critical paths
- [ ] Feature flag system with fallback mechanism
- [ ] Build system with Makefile and toolchain setup scripts
- [ ] All existing tests still pass

---

## Phase 2: Rust Integration (Search, AST, Tokenization)

### 2.0 Toolchain Setup
- Install Rust via rustup (Windows: rustup-init.exe)
- Install maturin: `pip install maturin`
- Verify: `cargo --version`, `rustc --version`

### 2.1 Rust Project Structure

**New directory: `rust/cortex-native/`**

```
rust/cortex-native/
├── Cargo.toml              # Workspace root
├── src/
│   ├── lib.rs             # PyO3 module entry point
│   ├── search/
│   │   ├── mod.rs         # Search engine module
│   │   ├── engine.rs      # Core search implementation (grep crate)
│   │   └── filters.rs     # File filtering (ignore patterns)
│   ├── ast/
│   │   ├── mod.rs         # AST module
│   │   ├── parser.rs      # Tree-sitter parsing
│   │   ├── queries.rs     # Code queries (functions, classes)
│   │   └── languages.rs   # Language support
│   └── tokenizer/
│       ├── mod.rs         # Tokenizer module
│       └── counter.rs     # Token counting (tiktoken-rs)
├── benches/
│   └── benchmarks.rs      # Rust-side benchmarks (criterion)
└── tests/
    └── integration.rs     # Rust integration tests
```

**Cargo.toml dependencies:**
```toml
[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
grep = "0.3"                    # ripgrep core library
ignore = "0.4"                  # .gitignore-aware file walking
tree-sitter = "0.24"
tree-sitter-python = "0.23"
tree-sitter-javascript = "0.23"
tree-sitter-typescript = "0.23"
tree-sitter-java = "0.23"
tree-sitter-go = "0.23"
tree-sitter-rust = "0.23"
tiktoken-rs = "0.6"             # Rust tiktoken port
rayon = "1.10"                  # Parallel iteration
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[lib]
name = "cortex_native"
crate-type = ["cdylib"]         # For Python extension

[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"
```

### 2.2 Rust Search Engine

**`rust/cortex-native/src/search/engine.rs`**

PyO3-exposed functions:
```
#[pyfunction]
fn search(
    pattern: &str,
    path: &str,
    glob_filter: Option<&str>,
    file_type: Option<&str>,
    case_insensitive: bool,
    multiline: bool,
    context_before: usize,
    context_after: usize,
    output_mode: &str,       // "files_with_matches" | "content" | "count"
    head_limit: usize,
    offset: usize,
) -> PyResult<SearchResult>

#[pyclass]
struct SearchResult {
    matches: Vec<SearchMatch>,
    total_matches: usize,
    files_searched: usize,
    duration_ms: f64,
}
```

Implementation:
- Uses `grep` crate (same core as ripgrep) for regex matching
- Uses `ignore` crate for .gitignore-aware file walking
- `rayon` for parallel file processing
- Returns structured results (not raw text like subprocess)
- Expected: **10x faster** than subprocess ripgrep calls

### 2.3 Rust AST Parser

**`rust/cortex-native/src/ast/parser.rs`**

PyO3-exposed functions:
```
#[pyfunction]
fn parse_file(path: &str, language: Option<&str>) -> PyResult<ParseResult>

#[pyfunction]
fn parse_code(code: &str, language: &str) -> PyResult<ParseResult>

#[pyfunction]
fn extract_functions(code: &str, language: &str) -> PyResult<Vec<FunctionInfo>>

#[pyfunction]
fn extract_classes(code: &str, language: &str) -> PyResult<Vec<ClassInfo>>

#[pyfunction]
fn extract_imports(code: &str, language: &str) -> PyResult<Vec<ImportInfo>>

#[pyclass]
struct ParseResult {
    tree_json: String,       // Serialized AST
    has_errors: bool,
    language: String,
    parse_time_ms: f64,
}
```

Implementation:
- Uses tree-sitter Rust crate (native, no Python overhead)
- Pre-compiled language parsers (no dynamic loading)
- Returns structured data via PyO3
- Expected: **50x faster** than Python tree-sitter bindings

### 2.4 Rust Token Counter

**`rust/cortex-native/src/tokenizer/counter.rs`**

PyO3-exposed functions:
```
#[pyfunction]
fn count_tokens(text: &str, model: &str) -> PyResult<usize>

#[pyfunction]
fn count_message_tokens(message_json: &str, model: &str) -> PyResult<usize>

#[pyfunction]
fn count_messages_tokens(messages_json: &str, model: &str) -> PyResult<Vec<usize>>
```

Implementation:
- Uses tiktoken-rs for exact token counting
- Model-to-encoding mapping (cl100k_base, o200k_base, etc.)
- Batch counting for message arrays
- Expected: **10x faster** than Python tiktoken

### 2.5 Python Integration Layer

**New file: `cortex/native/__init__.py` (~30 lines)**
- Try to import `cortex_native` (the Rust extension)
- Set `NATIVE_AVAILABLE = True/False`
- Re-export all functions

**Modify: `cortex/tools/grep_tool.py`**
- Add hybrid execution path in `execute()`:
  ```python
  if feature_manager.is_enabled(FeatureFlag.RUST_SEARCH):
      return feature_manager.with_fallback(
          FeatureFlag.RUST_SEARCH,
          self._search_with_rust,
          self._search_with_ripgrep,  # existing fallback
          pattern, path, ...
      )
  ```
- New method `_search_with_rust()` that calls `cortex_native.search()`
- Convert SearchResult to existing tool result format

**Modify: `cortex/code_ast/parser.py`**
- Add hybrid path in `parse()` and `parse_file()`:
  ```python
  if feature_manager.is_enabled(FeatureFlag.RUST_AST):
      return feature_manager.with_fallback(
          FeatureFlag.RUST_AST,
          self._parse_with_rust,
          self._parse_with_python,
          source_code, language
      )
  ```

**Modify: `cortex/core/context.py`**
- Add hybrid path in `estimate_tokens()`:
  ```python
  if feature_manager.is_enabled(FeatureFlag.RUST_TOKENIZER):
      try:
          from cortex.native import count_tokens
          return count_tokens(text, model)
      except (ImportError, RuntimeError):
          pass  # fall through to Python implementation
  ```

### 2.6 Rust Tests and Benchmarks

**Rust-side tests:** `rust/cortex-native/tests/integration.rs`
- Test search with known patterns
- Test AST parsing for all supported languages
- Test token counting accuracy vs tiktoken

**Python-side tests:**
**New file: `tests/unit/test_native_search.py` (~150 lines)**
- Test cortex_native.search() results match grep_tool results
- Test edge cases: regex, multiline, unicode, large files
- Skip if native not available

**New file: `tests/unit/test_native_ast.py` (~120 lines)**
- Test cortex_native.parse_file() results match Python parser
- Test all supported languages
- Skip if native not available

**New file: `tests/unit/test_native_tokens.py` (~100 lines)**
- Test cortex_native.count_tokens() accuracy
- Compare with tiktoken Python results
- Skip if native not available

**New file: `tests/benchmarks/bench_native_vs_python.py` (~150 lines)**
- Side-by-side benchmarks: native vs Python for search/AST/tokens
- Report speedup ratios

### Phase 2 Deliverables
- [ ] Rust project compiles and produces `cortex_native` Python extension
- [ ] Native search: 10x faster than subprocess ripgrep
- [ ] Native AST: 50x faster than Python tree-sitter
- [ ] Native tokens: 10x faster than Python tiktoken
- [ ] Feature flag integration with automatic fallback
- [ ] All existing Python tests still pass
- [ ] New tests for native components
- [ ] Benchmark comparison (native vs Python)

---

## Phase 3: Go Services (Caching, gRPC, Model Management)

### 3.0 Toolchain Setup
- Install Go (go.dev/dl for Windows)
- Install protoc: `choco install protobuf` or manual download
- Install Go gRPC plugins: `go install google.golang.org/protobuf/cmd/protoc-gen-go`
- Verify: `go version`, `protoc --version`

### 3.1 Go Project Structure

**New directory: `go/`**

```
go/
├── go.mod                      # Go module definition
├── go.sum
├── cmd/
│   └── cortex-services/
│       └── main.go            # Service entry point
├── internal/
│   ├── cache/
│   │   ├── service.go         # Cache service implementation
│   │   ├── lru.go             # LRU cache with TTL
│   │   ├── store.go           # Persistent storage backend
│   │   └── metrics.go         # Cache metrics
│   ├── modelmanager/
│   │   ├── service.go         # Model management service
│   │   ├── health.go          # Model health checks
│   │   ├── preloader.go       # Background model preloading
│   │   └── pool.go            # Connection pooling
│   └── config/
│       └── config.go          # Service configuration
├── api/
│   └── proto/
│       ├── cache.proto        # Cache service protobuf
│       └── model.proto        # Model management protobuf
├── pkg/
│   └── client/
│       └── client.go          # Go client library (for testing)
└── tests/
    ├── cache_test.go
    └── model_test.go
```

### 3.2 gRPC Service Definitions

**`go/api/proto/cache.proto`**
```protobuf
syntax = "proto3";
package cortex.cache.v1;

service CacheService {
  rpc Get(GetRequest) returns (GetResponse);
  rpc Set(SetRequest) returns (SetResponse);
  rpc Invalidate(InvalidateRequest) returns (InvalidateResponse);
  rpc BatchGet(BatchGetRequest) returns (BatchGetResponse);
  rpc BatchSet(BatchSetRequest) returns (BatchSetResponse);
  rpc GetStats(StatsRequest) returns (StatsResponse);
  rpc PreCache(PreCacheRequest) returns (PreCacheResponse);
  rpc Clear(ClearRequest) returns (ClearResponse);
  rpc WatchInvalidations(WatchRequest) returns (stream InvalidationEvent);
}

message CacheEntry {
  string path = 1;
  bytes content = 2;
  int64 mtime = 3;
  int64 size = 4;
  string content_hash = 5;
}
```

**`go/api/proto/model.proto`**
```protobuf
syntax = "proto3";
package cortex.model.v1;

service ModelService {
  rpc GetHealth(HealthRequest) returns (HealthResponse);
  rpc ListModels(ListModelsRequest) returns (ListModelsResponse);
  rpc PreloadModel(PreloadRequest) returns (PreloadResponse);
  rpc GetModelStatus(StatusRequest) returns (StatusResponse);
  rpc WatchStatus(WatchRequest) returns (stream StatusEvent);
}
```

### 3.3 Go Cache Service Implementation

**`go/internal/cache/service.go`**

Features:
- **High-performance LRU** with O(1) get/set using Go's sync.Map + doubly-linked list
- **TTL support** with lazy expiration + background sweeper goroutine
- **mtime validation** on get (same as Python FileCache)
- **Batch operations** (BatchGet/BatchSet) for reduced gRPC round-trips
- **Watch invalidations** via server-side streaming for cache coherence
- **Persistent storage** option: write-behind to disk for crash recovery
- **Metrics**: hits, misses, evictions, memory usage, latency percentiles

Expected improvement over Python FileCache:
- **10x lower latency** (Go's goroutine model vs Python's threading + GIL)
- **Better memory efficiency** (no Python object overhead per entry)
- **True concurrency** (no GIL)

### 3.4 Go Model Manager Service

**`go/internal/modelmanager/service.go`**

Features:
- **Health monitoring**: Periodic ping to Ollama API (`/api/tags`)
- **Background preloading**: Pre-warm models based on usage patterns
- **Connection pooling**: Reuse HTTP connections to Ollama
- **Status streaming**: Real-time model status updates to Python client
- **Metrics**: model load times, inference latency, memory usage

### 3.5 Python gRPC Client

**New file: `cortex/services/__init__.py`**
**New file: `cortex/services/client.py` (~200 lines)**

```python
class CortexServiceClient:
    """gRPC client for Go services."""

    def __init__(self, host="localhost", cache_port=50051, model_port=50052):
        self.cache_channel = grpc.insecure_channel(f"{host}:{cache_port}")
        self.model_channel = grpc.insecure_channel(f"{host}:{model_port}")
        self.cache_stub = CacheServiceStub(self.cache_channel)
        self.model_stub = ModelServiceStub(self.model_channel)

    # Cache operations
    def cache_get(self, path: str) -> Optional[str]: ...
    def cache_set(self, path: str, content: str) -> bool: ...
    def cache_invalidate(self, path: str) -> bool: ...
    def cache_batch_get(self, paths: List[str]) -> Dict[str, str]: ...
    def cache_batch_set(self, entries: Dict[str, str]) -> bool: ...
    def cache_stats(self) -> dict: ...
    def cache_pre_cache(self, patterns: List[str]) -> dict: ...

    # Model operations
    def model_health(self) -> dict: ...
    def model_list(self) -> List[dict]: ...
    def model_preload(self, model_name: str) -> bool: ...
    def model_status(self, model_name: str) -> dict: ...
```

**New file: `cortex/services/generated/` (auto-generated)**
- Python protobuf generated code from `protoc`
- `cache_pb2.py`, `cache_pb2_grpc.py`
- `model_pb2.py`, `model_pb2_grpc.py`

### 3.6 Python Integration

**Modify: `cortex/cache/file_cache.py`**
- Add `GrpcFileCache` class that implements same interface as `FileCache`
- Delegates to Go cache service via gRPC client
- Falls back to local LRU cache if service unavailable

```python
class GrpcFileCache(FileCache):
    """File cache backed by Go gRPC service."""

    def __init__(self, service_client, **kwargs):
        super().__init__(**kwargs)
        self.client = service_client

    def get(self, path):
        if feature_manager.is_enabled(FeatureFlag.GO_CACHE):
            try:
                result = self.client.cache_get(str(path))
                if result is not None:
                    self._stats['grpc_hits'] += 1
                    return result
                self._stats['grpc_misses'] += 1
            except grpc.RpcError:
                self._stats['grpc_errors'] += 1
        return super().get(path)  # fallback to local
```

**Modify: `cortex/core/agent_init.py`**
- Optionally start Go services as subprocess if feature flags enabled
- Initialize gRPC client
- Pass to components that use caching

**New file: `cortex/services/manager.py` (~150 lines)**
```python
class ServiceManager:
    """Manages lifecycle of Go background services."""

    def start_services(self) -> None:
        """Start Go services as background processes."""

    def stop_services(self) -> None:
        """Gracefully stop Go services."""

    def health_check(self) -> dict:
        """Check health of all services."""

    def ensure_running(self) -> bool:
        """Ensure services are running, restart if needed."""
```

### 3.7 Go Service Tests

**Go tests:** `go/tests/cache_test.go`, `go/tests/model_test.go`
- Test cache operations (get/set/invalidate/eviction)
- Test TTL expiration
- Test batch operations
- Test concurrent access
- Test model health checking

**Python integration tests:**
**New file: `tests/integration/test_grpc_cache.py` (~150 lines)**
- Test GrpcFileCache matches FileCache behavior
- Test fallback when service is down
- Test batch operations
- Skip if Go service not running

**New file: `tests/benchmarks/bench_grpc_vs_local.py` (~100 lines)**
- Benchmark gRPC cache vs local LRU cache
- Benchmark batch get/set vs individual operations
- Measure latency distribution (p50/p95/p99)

### 3.8 Modify Config

**Modify: `cortex/config.py`**
- Add `services` config section:
  ```yaml
  services:
    enabled: false
    cache:
      host: localhost
      port: 50051
      auto_start: true
    model_manager:
      host: localhost
      port: 50052
      auto_start: true
      health_interval: 30
  ```

### Phase 3 Deliverables
- [ ] Go cache service running as background process
- [ ] Go model manager service with health monitoring
- [ ] gRPC protobuf definitions and generated code
- [ ] Python gRPC client with full cache + model API
- [ ] GrpcFileCache class with fallback to local
- [ ] ServiceManager for lifecycle management
- [ ] Feature flag integration
- [ ] All existing tests still pass
- [ ] Go unit tests and Python integration tests
- [ ] Benchmark: gRPC cache vs local cache

---

## Implementation Order

```
PHASE 1 (do first - no toolchain dependencies)
  1.1  Performance Profiler         [~250 lines Python]
  1.2  Benchmark Suite              [~650 lines Python]
  1.3  Feature Flag System          [~200 lines Python]
  1.4  Build System                 [~210 lines scripts]

PHASE 2 (requires Rust install)
  2.0  Install Rust + maturin
  2.1  Rust project scaffold        [Cargo.toml, module structure]
  2.2  Rust search engine           [~400 lines Rust]
  2.3  Rust AST parser              [~500 lines Rust]
  2.4  Rust token counter           [~200 lines Rust]
  2.5  Python integration layer     [~200 lines Python, ~100 lines mods]
  2.6  Tests and benchmarks         [~520 lines Python, ~200 lines Rust]

PHASE 3 (requires Go install)
  3.0  Install Go + protoc
  3.1  Go project scaffold          [go.mod, module structure]
  3.2  gRPC proto definitions       [~100 lines protobuf]
  3.3  Go cache service             [~600 lines Go]
  3.4  Go model manager             [~400 lines Go]
  3.5  Python gRPC client           [~200 lines Python]
  3.6  Python integration           [~300 lines Python modifications]
  3.7  Tests                        [~400 lines Go + Python]
  3.8  Config updates               [~30 lines Python]
```

## New Files Summary

| File | Language | Lines | Phase |
|------|----------|-------|-------|
| `cortex/core/profiler.py` | Python | ~250 | 1.1 |
| `tests/benchmarks/conftest.py` | Python | ~80 | 1.2 |
| `tests/benchmarks/bench_search.py` | Python | ~150 | 1.2 |
| `tests/benchmarks/bench_ast.py` | Python | ~120 | 1.2 |
| `tests/benchmarks/bench_tokens.py` | Python | ~100 | 1.2 |
| `tests/benchmarks/bench_cache.py` | Python | ~100 | 1.2 |
| `tests/benchmarks/bench_e2e.py` | Python | ~120 | 1.2 |
| `cortex/core/feature_flags.py` | Python | ~200 | 1.3 |
| `Makefile` | Make | ~100 | 1.4 |
| `scripts/setup_toolchains.ps1` | PowerShell | ~60 | 1.4 |
| `scripts/setup_toolchains.sh` | Bash | ~50 | 1.4 |
| `rust/cortex-native/Cargo.toml` | TOML | ~40 | 2.1 |
| `rust/cortex-native/src/lib.rs` | Rust | ~50 | 2.1 |
| `rust/cortex-native/src/search/*.rs` | Rust | ~400 | 2.2 |
| `rust/cortex-native/src/ast/*.rs` | Rust | ~500 | 2.3 |
| `rust/cortex-native/src/tokenizer/*.rs` | Rust | ~200 | 2.4 |
| `cortex/native/__init__.py` | Python | ~30 | 2.5 |
| `tests/unit/test_native_*.py` | Python | ~370 | 2.6 |
| `tests/benchmarks/bench_native_vs_python.py` | Python | ~150 | 2.6 |
| `go/go.mod` | Go | ~15 | 3.1 |
| `go/cmd/cortex-services/main.go` | Go | ~80 | 3.1 |
| `go/api/proto/*.proto` | Protobuf | ~100 | 3.2 |
| `go/internal/cache/*.go` | Go | ~600 | 3.3 |
| `go/internal/modelmanager/*.go` | Go | ~400 | 3.4 |
| `cortex/services/client.py` | Python | ~200 | 3.5 |
| `cortex/services/manager.py` | Python | ~150 | 3.6 |
| `go/tests/*.go` | Go | ~200 | 3.7 |
| `tests/integration/test_grpc_cache.py` | Python | ~150 | 3.7 |
| `tests/benchmarks/bench_grpc_vs_local.py` | Python | ~100 | 3.7 |

## Modified Files Summary

| File | Phase | Changes |
|------|-------|---------|
| `cortex/config.py` | 1.1, 1.3, 3.8 | Add profiling, feature_flags, services config sections |
| `cortex/core/agent_init.py` | 1.3, 3.6 | Initialize FeatureManager and ServiceManager |
| `pytest.ini` | 1.2 | Add benchmark configuration |
| `pyproject.toml` | 1.4 | Add hybrid optional deps, maturin config |
| `requirements.txt` | 3.5 | Add grpcio, grpcio-tools |
| `cortex/tools/grep_tool.py` | 2.5 | Add `_search_with_rust()` hybrid path |
| `cortex/code_ast/parser.py` | 2.5 | Add `_parse_with_rust()` hybrid path |
| `cortex/core/context.py` | 2.5 | Add native token counting path |
| `cortex/cache/file_cache.py` | 3.6 | Add GrpcFileCache class |

## Risk Mitigation

1. **Feature flags ensure zero-risk rollout** - Every hybrid component defaults to OFF
2. **Fallback chain**: Rust native → subprocess (ripgrep) → pure Python
3. **All existing tests must pass** at each phase boundary
4. **Benchmarks validate** that native implementations are actually faster
5. **Go services are optional** - Cortex works fully without them running
6. **Platform detection** - Skip native features on unsupported platforms

## Success Criteria

| Metric | Current | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|---------|----------------|----------------|----------------|
| Search (10K files) | 500-1000ms | Baselined | 50-100ms | 50-100ms |
| AST parse (10K LOC) | 100-200ms | Baselined | 2-5ms | 2-5ms |
| Token count (50K) | 50-100ms | Baselined | 5-10ms | 5-10ms |
| Cache latency | 1-5ms local | Baselined | 1-5ms | <1ms (Go) |
| E2E P95 response | ~15s | Baselined | ~8s | ~5s |
| Benchmark suite | None | Established | Native vs Python | gRPC vs local |
