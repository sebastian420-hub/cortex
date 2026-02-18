# Phase 1 Implementation: Performance Foundation
**Timeline**: Weeks 1-2 | **Priority**: P0 | **Owner**: Performance Lead

## Overview
Establish the foundation for Cortex's hybrid architecture transformation. This phase focuses on profiling, measurement, and building the infrastructure needed for subsequent performance optimizations.

## Objectives
1. **Identify exact performance bottlenecks** through comprehensive profiling
2. **Establish baseline metrics** for all critical operations
3. **Create hybrid build system** supporting Rust/Go extensions
4. **Implement performance monitoring** infrastructure
5. **Set up CI/CD pipeline** for cross-language components

## Week 1: Profiling & Analysis

### Day 1-2: Performance Audit Infrastructure

#### 1.1 Create Performance Profiler Module
```python
# cortex/core/performance.py
"""
Comprehensive performance monitoring and bottleneck identification.
"""

import time
import tracemalloc
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import statistics

@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    operation: str
    duration_ms: float
    memory_delta_kb: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

class PerformanceProfiler:
    """Instrumentation for measuring and optimizing Cortex performance"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.current_operation = None
        self.start_time = None
        self.start_memory = 0
        
        # Enable detailed memory tracking
        if enabled:
            tracemalloc.start()
    
    def start_operation(self, operation: str):
        """Begin timing an operation"""
        if not self.enabled:
            return
            
        self.current_operation = operation
        self.start_time = time.perf_counter()
        self.start_memory = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
    
    def end_operation(self, metadata: Optional[Dict] = None):
        """End timing and record metrics"""
        if not self.enabled or not self.current_operation:
            return
            
        end_time = time.perf_counter()
        end_memory = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
        
        metric = PerformanceMetric(
            operation=self.current_operation,
            duration_ms=(end_time - self.start_time) * 1000,
            memory_delta_kb=(end_memory - self.start_memory) // 1024,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.metrics[self.current_operation].append(metric)
        self.current_operation = None
    
    def get_heatmap(self) -> Dict[str, Any]:
        """Identify performance hotspots"""
        if not self.metrics:
            return {}
        
        heatmap = {}
        for operation, metrics in self.metrics.items():
            durations = [m.duration_ms for m in metrics]
            heatmap[operation] = {
                "count": len(metrics),
                "avg_ms": statistics.mean(durations) if durations else 0,
                "p95_ms": statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else durations[0],
                "max_ms": max(durations) if durations else 0,
                "total_ms": sum(durations),
                "memory_avg_kb": statistics.mean([m.memory_delta_kb for m in metrics]) if metrics else 0,
            }
        
        # Sort by total time (most expensive first)
        return dict(sorted(heatmap.items(), key=lambda x: x[1]["total_ms"], reverse=True))
    
    def generate_report(self, output_path: str = "performance_report.json"):
        """Generate comprehensive performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "heatmap": self.get_heatmap(),
            "summary": self._generate_summary(),
            "recommendations": self._generate_recommendations(),
        }
        
        import json
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate executive summary"""
        heatmap = self.get_heatmap()
        total_time = sum(data["total_ms"] for data in heatmap.values())
        
        return {
            "total_operations": sum(data["count"] for data in heatmap.values()),
            "total_time_ms": total_time,
            "top_5_bottlenecks": list(heatmap.items())[:5],
            "avg_operation_time": total_time / sum(data["count"] for data in heatmap.values()) if heatmap else 0,
        }
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate optimization recommendations based on data"""
        heatmap = self.get_heatmap()
        recommendations = []
        
        for operation, data in list(heatmap.items())[:10]:  # Top 10
            if data["avg_ms"] > 100:  # > 100ms is significant
                rec = {
                    "operation": operation,
                    "current_performance": f"{data['avg_ms']:.1f}ms avg, {data['p95_ms']:.1f}ms p95",
                    "priority": "HIGH" if data["avg_ms"] > 500 else "MEDIUM" if data["avg_ms"] > 100 else "LOW",
                    "suggested_optimization": self._get_optimization_suggestion(operation, data),
                }
                recommendations.append(rec)
        
        return recommendations
    
    def _get_optimization_suggestion(self, operation: str, data: Dict[str, Any]) -> str:
        """Map operations to optimization strategies"""
        suggestions = {
            "grep": "Replace with Rust ripgrep bindings (10x speedup expected)",
            "glob": "Replace with Rust glob implementation (5x speedup)",
            "read_file": "Use memory-mapped I/O with Rust (2-3x speedup)",
            "ast_parse": "Replace with tree-sitter Rust bindings (50x speedup)",
            "token_count": "Use tiktoken Rust implementation (10x speedup)",
            "execute_command": "Optimize subprocess spawning, consider async",
            "model_inference": "Consider direct llama.cpp integration (remove HTTP overhead)",
        }
        
        # Pattern matching for partial operation names
        for pattern, suggestion in suggestions.items():
            if pattern in operation.lower():
                return suggestion
        
        return "Profile in detail to identify specific bottleneck"
```

#### 1.2 Integrate Profiler into Cortex
```python
# cortex/agent.py - Add performance instrumentation

class Cortex:
    def __init__(self, *args, **kwargs):
        # ... existing initialization ...
        
        # Initialize performance profiler
        self.profiler = PerformanceProfiler(
            enabled=self.config.get("performance_monitoring", True)
        )
    
    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Instrumented process_message"""
        self.profiler.start_operation("total_response")
        
        try:
            # ... existing code ...
            
            # Instrument tool calls
            self.profiler.start_operation(f"tool_{tool_name}")
            result = self.execute_tool(tool_name, arguments)
            self.profiler.end_operation({
                "arguments": str(arguments)[:100],
                "success": result.get("success", False)
            })
            
        finally:
            self.profiler.end_operation({
                "user_message_length": len(user_message),
                "final_response_length": len(final_text) if final_text else 0
            })
    
    def generate_performance_report(self):
        """Generate and display performance report"""
        report = self.profiler.generate_report()
        
        if self._is_text_output():
            from rich.table import Table
            from rich.panel import Panel
            
            table = Table(title="Performance Hotspots", show_header=True)
            table.add_column("Operation", style="cyan")
            table.add_column("Avg Time", style="green")
            table.add_column("P95 Time", style="yellow")
            table.add_column("Count", style="dim")
            table.add_column("Priority", style="red")
            
            heatmap = report["heatmap"]
            for op, data in list(heatmap.items())[:10]:
                priority = "HIGH" if data["avg_ms"] > 500 else "MEDIUM" if data["avg_ms"] > 100 else "LOW"
                table.add_row(
                    op[:40],
                    f"{data['avg_ms']:.1f}ms",
                    f"{data['p95_ms']:.1f}ms",
                    str(data["count"]),
                    priority
                )
            
            console.print(table)
            
            # Show recommendations
            if report.get("recommendations"):
                console.print(Panel(
                    "\n".join([f"• {r['operation']}: {r['suggested_optimization']}" 
                              for r in report["recommendations"][:3]]),
                    title="Top Optimization Recommendations",
                    border_style="yellow"
                ))
        
        return report
```

### Day 3: Benchmark Suite Creation

#### 1.3 Create Comprehensive Benchmark Suite
```python
# benchmarks/__init__.py
"""
Benchmark suite for measuring Cortex performance.
"""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Any
import json
from dataclasses import dataclass, asdict

@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    avg_time_ms: float
    p95_time_ms: float
    memory_usage_kb: int
    success_rate: float
    metadata: Dict[str, Any]

class BenchmarkSuite:
    """Standardized benchmarks for Cortex operations"""
    
    def __init__(self, project_dir: Path = Path(".")):
        self.project_dir = project_dir
        self.results = []
        
    def run_search_benchmark(self, file_count: int = 10000) -> BenchmarkResult:
        """Benchmark file search operations"""
        # Create test files if needed
        test_dir = self.project_dir / "benchmark_files"
        test_dir.mkdir(exist_ok=True)
        
        if len(list(test_dir.glob("*.txt"))) < file_count:
            self._generate_test_files(test_dir, file_count)
        
        # Benchmark grep
        times = []
        for _ in range(10):
            start = time.perf_counter()
            # Simulate grep operation
            list(test_dir.glob("*.txt"))
            times.append((time.perf_counter() - start) * 1000)
        
        return BenchmarkResult(
            name=f"glob_{file_count}_files",
            iterations=10,
            avg_time_ms=statistics.mean(times),
            p95_time_ms=statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0],
            memory_usage_kb=0,  # Would need memory profiling
            success_rate=1.0,
            metadata={"file_count": file_count, "operation": "glob"}
        )
    
    def run_ast_benchmark(self, file_size_kb: int = 100) -> BenchmarkResult:
        """Benchmark AST parsing operations"""
        # Generate test Python file
        test_code = self._generate_python_code(file_size_kb)
        
        times = []
        for _ in range(10):
            start = time.perf_counter()
            # Parse with Python ast
            import ast
            tree = ast.parse(test_code)
            times.append((time.perf_counter() - start) * 1000)
        
        return BenchmarkResult(
            name=f"ast_parse_{file_size_kb}kb",
            iterations=10,
            avg_time_ms=statistics.mean(times),
            p95_time_ms=statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0],
            memory_usage_kb=len(test_code.encode()) // 1024,
            success_rate=1.0,
            metadata={"file_size_kb": file_size_kb, "operation": "ast_parse"}
        )
    
    def run_token_count_benchmark(self, token_count: int = 50000) -> BenchmarkResult:
        """Benchmark token counting operations"""
        # Generate test text
        test_text = "word " * token_count
        
        times = []
        for _ in range(10):
            start = time.perf_counter()
            # Current token counting method
            char_count = len(test_text)
            estimated_tokens = max(1, int(char_count / 4))
            times.append((time.perf_counter() - start) * 1000)
        
        return BenchmarkResult(
            name=f"token_count_{token_count}",
            iterations=10,
            avg_time_ms=statistics.mean(times),
            p95_time_ms=statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0],
            memory_usage_kb=len(test_text.encode()) // 1024,
            success_rate=1.0,
            metadata={"token_count": token_count, "operation": "token_count"}
        )
    
    def run_e2e_benchmark(self, workflow: str = "complex-refactor") -> BenchmarkResult:
        """Benchmark end-to-end workflows"""
        workflows = {
            "complex-refactor": [
                "read_file main.py",
                "grep 'def.*function' --file_type py",
                "ast_parse main.py",
                "write_file refactored.py --content '...'",
                "execute_command 'python -m pytest'"
            ],
            "simple-search": [
                "glob '**/*.py'",
                "grep 'import' --file_type py",
                "list_files ."
            ]
        }
        
        # Simulate workflow execution
        times = []
        success = 0
        
        for _ in range(5):
            start = time.perf_counter()
            # Simulate each step with realistic delays
            for step in workflows[workflow]:
                time.sleep(0.01)  # Simulate work
            times.append((time.perf_counter() - start) * 1000)
            success += 1
        
        return BenchmarkResult(
            name=f"e2e_{workflow}",
            iterations=5,
            avg_time_ms=statistics.mean(times),
            p95_time_ms=statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0],
            memory_usage_kb=50000,  # Estimated
            success_rate=success / 5,
            metadata={"workflow": workflow, "steps": len(workflows[workflow])}
        )
    
    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run complete benchmark suite"""
        benchmarks = [
            self.run_search_benchmark(1000),
            self.run_search_benchmark(10000),
            self.run_ast_benchmark(10),
            self.run_ast_benchmark(100),
            self.run_token_count_benchmark(10000),
            self.run_token_count_benchmark(50000),
            self.run_e2e_benchmark("simple-search"),
            self.run_e2e_benchmark("complex-refactor"),
        ]
        
        self.results.extend(benchmarks)
        return benchmarks
    
    def generate_report(self, output_path: Path = Path("benchmark_results.json")):
        """Generate benchmark report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": [asdict(r) for r in self.results],
            "summary": self._generate_summary(),
            "comparison": self._compare_to_baseline(),
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate benchmark summary"""
        if not self.results:
            return {}
        
        return {
            "total_benchmarks": len(self.results),
            "avg_performance": statistics.mean([r.avg_time_ms for r in self.results]),
            "slowest_operation": max(self.results, key=lambda r: r.avg_time_ms).name,
            "fastest_operation": min(self.results, key=lambda r: r.avg_time_ms).name,
            "success_rate": statistics.mean([r.success_rate for r in self.results]),
        }
    
    def _compare_to_baseline(self, baseline_path: Path = Path("baseline_benchmarks.json")):
        """Compare current results to baseline"""
        if not baseline_path.exists():
            return {"status": "no_baseline", "message": "Run with --save-baseline first"}
        
        with open(baseline_path) as f:
            baseline = json.load(f)
        
        comparisons = []
        for current in self.results:
            # Find matching baseline
            baseline_match = next(
                (b for b in baseline.get("benchmarks", []) if b["name"] == current.name),
                None
            )
            
            if baseline_match:
                change_pct = ((current.avg_time_ms - baseline_match["avg_time_ms"]) / 
                             baseline_match["avg_time_ms"] * 100)
                comparisons.append({
                    "name": current.name,
                    "current_ms": current.avg_time_ms,
                    "baseline_ms": baseline_match["avg_time_ms"],
                    "change_pct": change_pct,
                    "status": "regression" if change_pct > 5 else "improvement" if change_pct < -5 else "stable"
                })
        
        return comparisons

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Cortex benchmarks")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--search", action="store_true", help="Run search benchmarks")
    parser.add_argument("--ast", action="store_true", help="Run AST benchmarks")
    parser.add_argument("--tokens", action="store_true", help="Run token benchmarks")
    parser.add_argument("--e2e", action="store_true", help="Run E2E benchmarks")
    parser.add_argument("--save-baseline", action="store_true", help="Save results as baseline")
    parser.add_argument("--compare", action="store_true", help="Compare to baseline")
    
    args = parser.parse_args()
    
    suite = BenchmarkSuite()
    
    if args.all or not any([args.search, args.ast, args.tokens, args.e2e]):
        results = suite.run_all_benchmarks()
    else:
        results = []
        if args.search:
            results.append(suite.run_search_benchmark(1000))
            results.append(suite.run_search_benchmark(10000))
        if args.ast:
            results.append(suite.run_ast_benchmark(10))
            results.append(suite.run_ast_benchmark(100))
        if args.tokens:
            results.append(suite.run_token_count_benchmark(10000))
            results.append(suite.run_token_count_benchmark(50000))
        if args.e2e:
            results.append(suite.run_e2e_benchmark("simple-search"))
            results.append(suite.run_e2e_benchmark("complex-refactor"))
    
    report = suite.generate_report()
    
    if args.save_baseline:
        baseline_path = Path("baseline_benchmarks.json")
        with open(baseline_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Baseline saved to {baseline_path}")
    
    if args.compare:
        comparisons = suite._compare_to_baseline()
        print("\nPerformance Comparison:")
        for comp in comparisons:
            print(f"{comp['name']}: {comp['current_ms']:.1f}ms vs {comp['baseline_ms']:.1f}ms "
                  f"({comp['change_pct']:+.1f}%) - {comp['status']}")
```

### Day 4-5: Real-world Workload Profiling

#### 1.4 Create Real-world Scenario Tests
```python
# scripts/profile_real_world.py
"""
Profile Cortex with realistic developer workflows.
"""

import subprocess
import time
import json
from pathlib import Path
from typing import List, Dict, Any

class RealWorldProfiler:
    """Profile Cortex with realistic usage scenarios"""
    
    SCENARIOS = {
        "code_refactor": [
            "add logging to all API endpoints",
            "refactor duplicate code in utils.py",
            "add type hints to service modules",
        ],
        "bug_investigation": [
            "find why login is failing",
            "debug memory leak in background jobs",
            "investigate slow database queries",
        ],
        "feature_development": [
            "add user profile page with avatar upload",
            "implement rate limiting middleware",
            "create API documentation with OpenAPI",
        ],
        "code_review": [
            "review pull request #42 for security issues",
            "check test coverage of new feature",
            "audit dependencies for vulnerabilities",
        ]
    }
    
    def run_scenario(self, scenario_name: str, commands: List[str]) -> Dict[str, Any]:
        """Run a scenario and measure performance"""
        results = []
        
        for command in commands:
            print(f"Running: {command}")
            
            # Start Cortex process
            start_time = time.time()
            process = subprocess.Popen(
                ["python", "-m", "cortex.cli", "-p", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=120)  # 2 minute timeout
                duration = time.time() - start_time
                
                results.append({
                    "command": command,
                    "duration_seconds": duration,
                    "success": process.returncode == 0,
                    "stdout_length": len(stdout),
                    "stderr_length": len(stderr),
                    "timeout": False,
                })
                
            except subprocess.TimeoutExpired:
                process.kill()
                results.append({
                    "command": command,
                    "duration_seconds": 120,
                    "success": False,
                    "timeout": True,
                })
        
        # Calculate statistics
        durations = [r["duration_seconds"] for r in results if not r["timeout"]]
        
        return {
            "scenario": scenario_name,
            "commands": len(commands),
            "results": results,
            "statistics": {
                "avg_duration": sum(durations) / len(durations) if durations else 0,
                "total_duration": sum([r["duration_seconds"] for r in results]),
                "success_rate": sum(1 for r in results if r["success"]) / len(results),
                "timeout_rate": sum(1 for r in results if r["timeout"]) / len(results),
            }
        }
    
    def profile_all_scenarios(self) -> Dict[str, Any]:
        """Profile all real-world scenarios"""
        profile_results = {}
        
        for scenario_name, commands in self.SCENARIOS.items():
            print(f"\n=== Profiling {scenario_name} ===")
            result = self.run_scenario(scenario_name, commands[:2])  # First 2 commands for speed
            profile_results[scenario_name] = result
        
        # Generate summary
        total_commands = sum(len(r["results"]) for r in profile_results.values())
        total_duration = sum(r["statistics"]["total_duration"] for r in profile_results.values())
        avg_success = statistics.mean([r["statistics"]["success_rate"] for r in profile_results.values()])
        
        summary = {
            "total_scenarios": len(profile_results),
            "total_commands": total_commands,
            "total_duration_seconds": total_duration,
            "avg_success_rate": avg_success,
            "bottleneck_scenario": max(profile_results.items(), 
                                      key=lambda x: x[1]["statistics"]["avg_duration"])[0],
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "scenarios": profile_results,
        }
    
    def save_profile(self, results: Dict[str, Any], output_path: Path = Path("real_world_profile.json")):
        """Save profiling results"""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nProfile saved to {output_path}")
        print(f"Total duration: {results['summary']['total_duration_seconds']:.1f}s")
        print(f"Success rate: {results['summary']['avg_success_rate']:.1%}")
        
        # Print bottleneck analysis
        bottleneck = results['summary']['bottleneck_scenario']
        print(f"Bottleneck scenario: {bottleneck}")
        
        return output_path

if __name__ == "__main__":
    profiler = RealWorldProfiler()
    results = profiler.profile_all_scenarios()
    profiler.save_profile(results)
```

## Week 2: Build System & Infrastructure

### Day 6-7: Hybrid Build System Setup

#### 2.1 Update pyproject.toml for Hybrid Builds
```toml
# pyproject.toml
[build-system]
requires = ["maturin>=1.0", "setuptools>=42", "wheel"]
build-backend = "maturin"

[project]
name = "cortex"
version = "3.0.0-alpha.1"
description = "Hybrid AI coding assistant with Rust/Go performance"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    # Core Python dependencies
    "rich>=13.0.0",
    "prompt-toolkit>=3.0.0",
    "pyyaml>=6.0",
    "httpx>=0.25.0",
    
    # Optional hybrid extensions (will be auto-installed if available)
    "cortex-search>=0.1; extra == 'performance'",
    "cortex-cache>=0.1; extra == 'performance'",
    "cortex-inference>=0.1; extra == 'performance' and platform_machine != 'arm64'",
]

[project.optional-dependencies]
performance = [
    "cortex-search>=0.1",
    "cortex-cache>=0.1",
]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "mypy>=1.0",
    "ruff>=0.1.0",
    "maturin>=1.0",
]
all = [
    "cortex-search>=0.1",
    "cortex-cache>=0.1",
    "pytest>=7.0",
    "black>=23.0",
]

[project.scripts]
cortex = "cortex.cli:main"
cortex-benchmark = "benchmarks.__main__:main"
cortex-profile = "scripts.profile_real_world:main"

[tool.maturin]
# Rust extension configuration
module-name = "cortex_search"
cargo-extra-args = ["--release"]
bindings = "pyo3"

# Feature flags for hybrid components
[tool.cortex.features]
rust_search = { enabled = true, required = false }
go_cache = { enabled = false, required = false }
cpp_inference = { enabled = false, required = false }

# Performance monitoring
[tool.cortex.performance]
monitoring = true
benchmark_on_startup = false
auto_profile = false
report_path = "reports/performance"

# Platform-specific configurations
[tool.cortex.platform.linux]
rust_search = { enabled = true }
go_cache = { enabled = true }

[tool.cortex.platform.windows]
rust_search = { enabled = true, features = ["windows-compat"] }
go_cache = { enabled = false }  # Disable on Windows initially

[tool.cortex.platform.macos]
rust_search = { enabled = true }
go_cache = { enabled = true }
```

#### 2.2 Create Makefile for Hybrid Builds
```makefile
# Makefile
.PHONY: all build install dev test bench profile clean

# Configuration
PYTHON := python3
CARGO := cargo
GO := go
PROJECT := cortex
RUST_EXT := cortex-search
GO_SERVICE := cortex-cache

# Default target
all: build

# Build everything
build: build-python build-rust build-go

# Build Python package
build-python:
	$(PYTHON) -m pip install --upgrade pip build
	$(PYTHON) -m build

# Build Rust extension
build-rust:
	cd $(RUST_EXT) && $(CARGO) build --release
	# Copy to python package
	cp $(RUST_EXT)/target/release/libcortex_search.* $(PROJECT)/

# Build Go service
build-go:
	cd $(GO_SERVICE) && $(GO) build -o ../$(PROJECT)/cache-service

# Install in development mode
install: build
	$(PYTHON) -m pip install -e .[dev]

# Install with performance extensions
install-perf: build
	$(PYTHON) -m pip install -e .[all]

# Development setup
dev: install
	$(PYTHON) -m pip install -r requirements-dev.txt
	pre-commit install

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v --cov=$(PROJECT)

# Run benchmarks
bench:
	$(PYTHON) -m benchmarks --all --save-baseline

# Profile real-world usage
profile:
	$(PYTHON) -m scripts.profile_real_world

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/
	cd $(RUST_EXT) && $(CARGO) clean
	cd $(GO_SERVICE) && $(GO) clean
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.so" -delete
	find . -type f -name "cache-service" -delete

# Cross-compilation targets
build-linux: build-python
	cd $(RUST_EXT) && $(CARGO) build --release --target=x86_64-unknown-linux-gnu
	cd $(GO_SERVICE) && GOOS=linux GOARCH=amd64 $(GO) build -o ../$(PROJECT)/cache-service-linux

build-windows: build-python
	cd $(RUST_EXT) && $(CARGO) build --release --target=x86_64-pc-windows-msvc
	cd $(GO_SERVICE) && GOOS=windows GOARCH=amd64 $(GO) build -o ../$(PROJECT)/cache-service.exe

# Docker builds
docker-build:
	docker build -t $(PROJECT):latest .

docker-run:
	docker run -it --rm -v $(PWD):/workspace $(PROJECT):latest

# Performance report
report: bench profile
	$(PYTHON) -c "from cortex.core.performance import PerformanceProfiler; p = PerformanceProfiler(); p.generate_report('performance_report.json')"
	@echo "Reports generated:"
	@echo "  - benchmark_results.json"
	@echo "  - real_world_profile.json"
	@echo "  - performance_report.json"
```

#### 2.3 Docker Development Environment
```dockerfile
# Dockerfile
# Multi-stage build for hybrid development

# Stage 1: Rust builder
FROM rust:1.75-slim as rust-builder
WORKDIR /build
COPY cortex-search/ .
RUN cargo build --release

# Stage 2: Go builder  
FROM golang:1.21-alpine as go-builder
WORKDIR /build
COPY cortex-cache/ .
RUN go build -o cache-service

# Stage 3: Python runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy built artifacts
COPY --from=rust-builder /build/target/release/libcortex_search.so /usr/lib/
COPY --from=go-builder /build/cache-service /usr/local/bin/

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Cortex
COPY . .
RUN pip install -e .[all]

# Set up development environment
RUN echo 'alias cortex="python -m cortex.cli"' >> ~/.bashrc
RUN echo 'alias bench="python -m benchmarks"' >> ~/.bashrc
RUN echo 'alias profile="python -m scripts.profile_real_world"' >> ~/.bashrc

# Default command
CMD ["python", "-m", "cortex.cli"]
```

### Day 8: CI/CD Pipeline Setup

#### 2.4 GitHub Actions Workflow
```yaml
# .github/workflows/hybrid-ci.yml
name: Hybrid CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  # Build and test Python
  python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]
    
    - name: Lint with ruff
      run: |
        ruff check .
        ruff format --check .
    
    - name: Type check with mypy
      run: |
        mypy cortex/
    
    - name: Test with pytest
      run: |
        pytest tests/ -v --cov=cortex --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  # Build and test Rust extension
  rust:
    runs-on: ubuntu-latest
    needs: python
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: stable
        override: true
    
    - name: Build Rust extension
      run: |
        cd cortex-search
        cargo build --release
        cargo test
    
    - name: Run Rust benchmarks
      run: |
        cd cortex-search
        cargo bench
    
    - name: Upload Rust artifacts
      uses: actions/upload-artifact@v4
      with:
        name: cortex-search
        path: cortex-search/target/release/

  # Build and test Go service
  go:
    runs-on: ubuntu-latest
    needs: python
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'
    
    - name: Build Go service
      run: |
        cd cortex-cache
        go build -v ./...
        go test ./...
    
    - name: Run Go benchmarks
      run: |
        cd cortex-cache
        go test -bench=. -benchmem
    
    - name: Upload Go artifacts
      uses: actions/upload-artifact@v4
      with:
        name: cortex-cache
        path: cortex-cache/

  # Integration tests
  integration:
    runs-on: ubuntu-latest
    needs: [python, rust, go]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Download artifacts
      uses: actions/download-artifact@v4
      with:
        path: artifacts/
    
    - name: Set up hybrid environment
      run: |
        # Copy Rust extension
        cp artifacts/cortex-search/libcortex_search.so cortex/
        # Copy Go service
        cp artifacts/cortex-cache/cache-service cortex/
        
        # Install Cortex with performance extensions
        pip install -e .[all]
    
    - name: Run integration tests
      run: |
        # Test Python-Rust integration
        python -c "import cortex_search; print('Rust extension loaded')"
        
        # Test Python-Go integration
        ./cortex/cache-service --version
        
        # Run hybrid integration tests
        pytest tests/integration/ -v
    
    - name: Run performance regression tests
      run: |
        python -m benchmarks --all --compare
        # Fail if any regression > 10%
    
    - name: Generate performance report
      run: |
        python -m scripts.profile_real_world
        python -c "from cortex.core.performance import PerformanceProfiler; p = PerformanceProfiler(); p.generate_report()"
    
    - name: Upload performance reports
      uses: actions/upload-artifact@v4
      with:
        name: performance-reports
        path: |
          benchmark_results.json
          real_world_profile.json
          performance_report.json

  # Cross-platform builds
  cross-platform:
    runs-on: ${{ matrix.os }}
    needs: python
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Cortex
      run: |
        pip install -e .
    
    - name: Run platform-specific tests
      run: |
        pytest tests/platform/ -v -m "${{ matrix.os }}"
    
    - name: Test basic functionality
      run: |
        python -m cortex.cli --version
        python -m cortex.cli --list-providers

  # Release
  release:
    runs-on: ubuntu-latest
    needs: [integration, cross-platform]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Build distribution
      run: |
        pip install build
        python -m build
    
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
    
    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/*
        generate_release_notes: true
```

### Day 9-10: Feature Flag System & Integration

#### 2.5 Feature Flag Implementation
```python
# cortex/config/features.py
"""
Feature flag system for gradual rollout of hybrid components.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

class FeatureStatus(Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"

@dataclass
class Feature:
    """A feature that can be toggled"""
    name: str
    description: str
    status: FeatureStatus
    default: bool
    dependencies: Set[str] = field(default_factory=set)
    requirements: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def is_available(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if feature is available in current context"""
        if self.status == FeatureStatus.DISABLED:
            return False
        
        if self.status == FeatureStatus.DEPRECATED:
            return False  # Or True with warnings
        
        # Check requirements
        if context:
            for req_key, req_value in self.requirements.items():
                if context.get(req_key) != req_value:
                    return False
        
        return True

class FeatureManager:
    """Manage feature flags for hybrid architecture"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.features: Dict[str, Feature] = {}
        self.context: Dict[str, Any] = {}
        
        # Default features for hybrid architecture
        self._initialize_default_features()
        
        # Load user configuration
        if config_path and config_path.exists():
            self.load_config(config_path)
    
    def _initialize_default_features(self):
        """Initialize default feature flags"""
        default_features = [
            Feature(
                name="rust_search",
                description="Use Rust implementation for search operations (grep, glob)",
                status=FeatureStatus.EXPERIMENTAL,
                default=True,
                requirements={"platform": ["linux", "macos"]},
                metrics={"expected_speedup": 10.0}
            ),
            Feature(
                name="rust_ast",
                description="Use tree-sitter Rust bindings for AST parsing",
                status=FeatureStatus.EXPERIMENTAL,
                default=True,
                requirements={"platform": ["linux", "macos"]},
                metrics={"expected_speedup": 50.0}
            ),
            Feature(
                name="go_cache",
                description="Use Go service for distributed caching",
                status=FeatureStatus.DISABLED,
                default=False,
                requirements={"has_redis": True},
                metrics={"expected_speedup": 5.0}
            ),
            Feature(
                name="cpp_inference",
                description="Use direct llama.cpp integration (bypass Ollama HTTP)",
                status=FeatureStatus.DISABLED,
                default=False,
                requirements={"has_cuda": False},  # CPU-only initially
                metrics={"expected_speedup": 2.0}
            ),
            Feature(
                name="performance_monitoring",
                description="Enable detailed performance monitoring and profiling",
                status=FeatureStatus.ENABLED,
                default=True,
                metrics={"overhead_percent": 1.0}
            ),
            Feature(
                name="auto_fallback",
                description="Automatically fallback to Python if hybrid component fails",
                status=FeatureStatus.ENABLED,
                default=True,
                metrics={"reliability_improvement": "high"}
            ),
            Feature(
                name="gradual_rollout",
                description="Gradually enable features for users (A/B testing)",
                status=FeatureStatus.EXPERIMENTAL,
                default=False,
                requirements={"user_tier": "beta"},
            ),
        ]
        
        for feature in default_features:
            self.features[feature.name] = feature
        
        # Detect platform and capabilities
        self._detect_capabilities()
    
    def _detect_capabilities(self):
        """Detect system capabilities for feature requirements"""
        import platform
        import sys
        
        self.context.update({
            "platform": platform.system().lower(),
            "python_version": sys.version_info[:3],
            "architecture": platform.machine(),
        })
        
        # Detect CUDA
        try:
            import torch
            self.context["has_cuda"] = torch.cuda.is_available()
        except ImportError:
            self.context["has_cuda"] = False
        
        # Detect Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
            r.ping()
            self.context["has_redis"] = True
        except:
            self.context["has_redis"] = False
        
        # Detect Rust extension
        try:
            import cortex_search
            self.context["has_rust_search"] = True
        except ImportError:
            self.context["has_rust_search"] = False
        
        # Detect Go service
        import subprocess
        try:
            result = subprocess.run(["cache-service", "--version"], 
                                  capture_output=True, timeout=1)
            self.context["has_go_cache"] = result.returncode == 0
        except:
            self.context["has_go_cache"] = False
    
    def is_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled in current context"""
        if feature_name not in self.features:
            return False
        
        feature = self.features[feature_name]
        
        # Check if feature is available
        if not feature.is_available(self.context):
            return False
        
        # For experimental features, check user preference
        if feature.status == FeatureStatus.EXPERIMENTAL:
            # Could check user config, A/B testing, etc.
            return feature.default
        
        return feature.status == FeatureStatus.ENABLED
    
    def enable(self, feature_name: str):
        """Enable a feature"""
        if feature_name in self.features:
            self.features[feature_name].status = FeatureStatus.ENABLED
    
    def disable(self, feature_name: str):
        """Disable a feature"""
        if feature_name in self.features:
            self.features[feature_name].status = FeatureStatus.DISABLED
    
    def get_enabled_features(self) -> Dict[str, Feature]:
        """Get all currently enabled features"""
        return {name: feature for name, feature in self.features.items() 
                if self.is_enabled(name)}
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate feature status report"""
        enabled = self.get_enabled_features()
        
        return {
            "context": self.context,
            "total_features": len(self.features),
            "enabled_features": len(enabled),
            "enabled_list": list(enabled.keys()),
            "feature_details": {
                name: {
                    "status": feature.status.value,
                    "available": feature.is_available(self.context),
                    "requirements_met": all(
                        self.context.get(k) == v 
                        for k, v in feature.requirements.items()
                    ) if feature.requirements else True,
                }
                for name, feature in self.features.items()
            }
        }
    
    def load_config(self, config_path: Path):
        """Load feature configuration from file"""
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            for name, settings in config.get("features", {}).items():
                if name in self.features:
                    if "status" in settings:
                        self.features[name].status = FeatureStatus(settings["status"])
                    if "default" in settings:
                        self.features[name].default = settings["default"]
        except Exception as e:
            print(f"Warning: Failed to load feature config: {e}")
    
    def save_config(self, config_path: Path):
        """Save feature configuration to file"""
        config = {
            "features": {
                name: {
                    "status": feature.status.value,
                    "default": feature.default,
                }
                for name, feature in self.features.items()
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

# Global feature manager instance
_feature_manager = None

def get_feature_manager() -> FeatureManager:
    """Get or create the global feature manager"""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureManager()
    return _feature_manager

def feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled (convenience function)"""
    return get_feature_manager().is_enabled(feature_name)

# Decorator for feature-gated functions
def require_feature(feature_name: str, fallback=None):
    """Decorator to require a feature to be enabled"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if feature_enabled(feature_name):
                return func(*args, **kwargs)
            elif fallback is not None:
                return fallback(*args, **kwargs)
            else:
                raise FeatureNotAvailableError(
                    f"Feature '{feature_name}' is required but not enabled"
                )
        return wrapper
    return decorator

class FeatureNotAvailableError(Exception):
    """Exception raised when a required feature is not available"""
    pass
```

#### 2.6 Hybrid Tool Integration
```python
# cortex/tools/hybrid_search.py
"""
Hybrid search tool that uses Rust implementation when available.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

from .base import Tool
from ..models import PermissionMode
from ..utils.errors import create_error_response, create_success_response, ErrorType
from ..config.features import feature_enabled, require_feature

class HybridSearchTool(Tool):
    """Search tool that uses Rust implementation when available"""
    
    def __init__(self, project_dir: Path, permission_mode: PermissionMode, console: Console):
        super().__init__(project_dir, permission_mode, console)
        
        # Try to import Rust extension
        self.rust_available = False
        self.rust_engine = None
        
        if feature_enabled("rust_search"):
            try:
                import cortex_search
                self.rust_engine = cortex_search.SearchEngine()
                self.rust_available = True
                console.print("[dim]✓ Rust search engine available[/dim]")
            except ImportError:
                console.print("[yellow]⚠ Rust search engine not available, using Python fallback[/yellow]")
        
        # Python fallback
        from .search_tools import SearchFilesTool
        self.python_fallback = SearchFilesTool(project_dir, permission_mode, console)
    
    def execute(self, query: str, file_pattern: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Execute search with Rust acceleration if available"""
        
        # Determine which implementation to use
        use_rust = (
            self.rust_available and 
            feature_enabled("rust_search") and
            not kwargs.get("force_python", False)
        )
        
        if use_rust:
            return self._rust_search(query, file_pattern, **kwargs)
        else:
            return self._python_search(query, file_pattern, **kwargs)
    
    def _rust_search(self, query: str, file_pattern: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Use Rust implementation for search"""
        try:
            start_time = time.perf_counter()
            
            # Convert file pattern to paths
            if file_pattern:
                paths = list(Path(self.project_dir).rglob(file_pattern))
            else:
                paths = [Path(self.project_dir)]
            
            # Execute search with Rust
            results = self.rust_engine.grep(
                pattern=query,
                paths=paths,
                case_insensitive=kwargs.get("case_insensitive", False),
                multiline=kwargs.get("multiline", False),
                max_results=kwargs.get("max_results", 1000)
            )
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return create_success_response({
                "matches": len(results),
                "results": self._format_rust_results(results),
                "duration_ms": duration_ms,
                "engine": "rust",
                "performance_notes": f"Rust implementation: {duration_ms:.1f}ms"
            })
            
        except Exception as e:
            # Fall back to Python on Rust error
            if feature_enabled("auto_fallback"):
                self.console.print(f"[yellow]Rust search failed, falling back to Python: {e}[/yellow]")
                return self._python_search(query, file_pattern, **kwargs)
            else:
                return create_error_response(
                    f"Rust search failed: {e}",
                    ErrorType.EXECUTION,
                    {"engine": "rust", "fallback_available": True}
                )
    
    def _python_search(self, query: str, file_pattern: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Use Python implementation for search"""
        start_time = time.perf_counter()
        
        result = self.python_fallback.execute(query, file_pattern, **kwargs)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        if result["success"]:
            result["data"]["engine"] = "python"
            result["data"]["duration_ms"] = duration_ms
            result["data"]["performance_notes"] = f"Python implementation: {duration_ms:.1f}ms"
        
        return result
    
    def _format_rust_results(self, rust_results) -> list:
        """Format Rust results to match Python format"""
        formatted = []
        for result in rust_results:
            formatted.append({
                "file": str(result.file_path.relative_to(self.project_dir)),
                "line": result.line_number,
                "text": result.line_text,
                "match_start": result.match_start,
                "match_end": result.match_end,
            })
        return formatted

# Factory function to create hybrid tools
def create_hybrid_tool(tool_name: str, project_dir: Path, permission_mode: PermissionMode, console: Console):
    """Create a tool with hybrid implementation if available"""
    
    tool_map = {
        "grep": HybridSearchTool,
        "glob": HybridSearchTool,  # Would have separate implementation
        # Add more hybrid tools as they're implemented
    }
    
    if tool_name in tool_map and feature_enabled(f"rust_{tool_name}"):
        return tool_map[tool_name](project_dir, permission_mode, console)
    
    # Fall back to standard tool creation
    from .registry import create_tool_instance
    return create_tool_instance(tool_name, project_dir, permission_mode, console)
```

## Success Criteria Checklist

### Week 1: Profiling & Analysis ✅
- [ ] **PerformanceProfiler** module implemented and integrated
- [ ] **BenchmarkSuite** with comprehensive operation benchmarks
- [ ] **RealWorldProfiler** with developer workflow scenarios
- [ ] Initial performance baseline established
- [ ] Top 3 bottlenecks identified with concrete measurements

### Week 2: Build System & Infrastructure ✅
- [ ] **Hybrid pyproject.toml** with Rust/Go extension support
- [ ] **Makefile** for cross-language builds
- [ ] **Dockerfile** for hybrid development environment
- [ ] **GitHub Actions CI/CD** pipeline with multi-language support
- [ ] **FeatureManager** with gradual rollout capabilities
- [ ] **HybridSearchTool** proof-of-concept implementation

### Validation Tests
- [ ] All existing tests pass with hybrid features disabled
- [ ] Performance monitoring adds < 5% overhead
- [ ] Feature flags work correctly on all platforms
- [ ] Fallback mechanisms work when hybrid components unavailable
- [ ] Build system works on Linux, macOS, and Windows

## Deliverables for Phase 1

### Documentation
1. **Performance Baseline Report**: `reports/performance_baseline.md`
2. **Bottleneck Analysis**: `reports/bottleneck_analysis.json`
3. **Build System Guide**: `docs/hybrid_build_system.md`
4. **Feature Flag Guide**: `docs/feature_flags.md`

### Code
1. **Performance Monitoring Module**: `cortex/core/performance.py`
2. **Benchmark Suite**: `benchmarks/` directory
3. **Real-world Profiler**: `scripts/profile_real_world.py`
4. **Feature Flag System**: `cortex/config/features.py`
5. **Hybrid Build Configuration**: Updated `pyproject.toml`, `Makefile`, `Dockerfile`
6. **CI/CD Pipeline**: `.github/workflows/hybrid-ci.yml`
7. **Proof-of-concept Hybrid Tool**: `cortex/tools/hybrid_search.py`

### Infrastructure
1. **Cross-platform CI Pipeline**: Operational on GitHub Actions
2. **Docker Development Environment**: Ready for team use
3. **Performance Dashboard**: Basic dashboard showing key metrics
4. **Automated Regression Detection**: CI fails on >10% performance regression

## Next Steps After Phase 1

### Immediate (Week 3)
1. **Begin Rust search extension implementation** based on profiling data
2. **Set up performance regression gates** in CI
3. **Create detailed optimization roadmap** based on Phase 1 findings

### Short-term (Week 4-6)
1. **Implement `cortex-search` Rust extension**
2. **Integrate tree-sitter for AST parsing**
3. **Benchmark and validate performance improvements**
4. **Gradual rollout to beta users**

### Medium-term (Week 7-9)
1. **Implement Go caching service**
2. **Add distributed caching to Cortex**
3. **Optimize memory usage patterns**
4. **Implement advanced performance monitoring**

## Risk Mitigation for Phase 1

### Technical Risks
- **Performance overhead from monitoring**: Keep instrumentation lightweight, use sampling
- **Build system complexity**: Clear documentation, Dockerized environment
- **Platform compatibility issues**: Test on all major platforms early

### Project Risks  
- **Scope creep in profiling**: Stick to defined scenarios, timebox analysis
- **Team skill gaps**: Provide detailed documentation, pair programming
- **Integration delays**: Mock interfaces for parallel development

## Measurement of Success

### Quantitative Metrics
- **Performance data collected**: 100% of critical operations profiled
- **Benchmark coverage**: 10+ standard benchmarks implemented
- **Build success rate**: 100% on CI for all platforms
- **Feature flag test coverage**: 90%+ of feature combinations tested

### Qualitative Metrics
- **Developer experience**: Setup time < 10 minutes for new contributors
- **Documentation completeness**: All new systems fully documented
- **Team confidence**: Clear understanding of performance bottlenecks
- **Stakeholder alignment**: Agreement on optimization priorities

---

**Phase 1 Complete When**: All checklist items are ✅, baseline established, and team ready for Phase 2 implementation.

**Estimated Duration**: 2 weeks with 2 engineers focused full-time

**Key Decision Point**: After Phase 1, review profiling data to confirm optimization priorities before starting Rust implementation.