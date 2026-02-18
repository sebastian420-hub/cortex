# Cortex Hybrid Architecture Build System
# Supports Python, Rust (via maturin), and Go builds

.PHONY: install test benchmark profile lint clean rust-build go-build build-all help

# === Python ===
install:
	pip install -e ".[dev]"

install-all: install
	pip install maturin grpcio grpcio-tools pytest-benchmark

test:
	pytest tests/ -v --ignore=tests/benchmarks -m "not slow and not web and not cloud"

test-all:
	pytest tests/ -v

benchmark:
	pytest tests/benchmarks/ -v --benchmark-only --benchmark-sort=mean

benchmark-save:
	pytest tests/benchmarks/ -v --benchmark-only --benchmark-save=baseline

benchmark-compare:
	pytest tests/benchmarks/ -v --benchmark-only --benchmark-compare=0001

profile:
	python -c "from cortex.core.profiler import PerformanceProfiler; p = PerformanceProfiler(enabled=True); print('Profiler ready')"

lint:
	black cortex/ tests/ --check
	flake8 cortex/ tests/ --max-line-length=100
	mypy cortex/ --ignore-missing-imports

format:
	black cortex/ tests/ --line-length=100

# === Rust (Phase 2) ===
rust-build:
	cd rust/cortex-native && maturin develop --release

rust-test:
	cd rust/cortex-native && cargo test

rust-bench:
	cd rust/cortex-native && cargo bench

rust-clean:
	cd rust/cortex-native && cargo clean

# === Go (Phase 3) ===
go-build:
	cd go && go build ./...

go-test:
	cd go && go test ./... -v

go-run:
	cd go && go run cmd/cortex-services/main.go

go-proto:
	cd go && protoc --go_out=. --go-grpc_out=. api/proto/*.proto

go-clean:
	cd go && go clean ./...

# === Combined ===
build-all: install rust-build go-build
	@echo "All components built successfully"

test-hybrid: test rust-test go-test
	@echo "All tests passed"

clean: rust-clean go-clean
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache build dist *.egg-info

# === Help ===
help:
	@echo "Cortex Hybrid Architecture Build Targets:"
	@echo ""
	@echo "  Python:"
	@echo "    install         - Install Python package in dev mode"
	@echo "    install-all     - Install with all hybrid dependencies"
	@echo "    test            - Run Python unit tests"
	@echo "    test-all        - Run all Python tests"
	@echo "    benchmark       - Run performance benchmarks"
	@echo "    benchmark-save  - Run benchmarks and save baseline"
	@echo "    benchmark-compare - Compare against saved baseline"
	@echo "    profile         - Initialize profiler"
	@echo "    lint            - Run linters (black, flake8, mypy)"
	@echo "    format          - Auto-format code with black"
	@echo ""
	@echo "  Rust (Phase 2):"
	@echo "    rust-build      - Build Rust native extension"
	@echo "    rust-test       - Run Rust tests"
	@echo "    rust-bench      - Run Rust benchmarks"
	@echo ""
	@echo "  Go (Phase 3):"
	@echo "    go-build        - Build Go services"
	@echo "    go-test         - Run Go tests"
	@echo "    go-run          - Run Go services"
	@echo "    go-proto        - Generate Go protobuf code"
	@echo ""
	@echo "  Combined:"
	@echo "    build-all       - Build all components"
	@echo "    test-hybrid     - Run all tests (Python + Rust + Go)"
	@echo "    clean           - Clean all build artifacts"
