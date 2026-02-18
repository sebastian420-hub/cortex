#!/bin/bash
# Cortex Hybrid Architecture - Toolchain Setup (Linux/macOS)
# Usage: bash scripts/setup_toolchains.sh [--rust] [--go] [--all]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

install_rust() {
    echo -e "\n${CYAN}=== Installing Rust ===${NC}"

    if command -v cargo &> /dev/null; then
        echo -e "${GREEN}Rust is already installed: $(cargo --version)${NC}"
    else
        echo "Installing Rust via rustup..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
        echo -e "${GREEN}Rust installed: $(cargo --version)${NC}"
    fi

    echo "Installing maturin (Python-Rust bridge)..."
    pip install maturin
    echo -e "${GREEN}maturin installed: $(maturin --version)${NC}"
}

install_go() {
    echo -e "\n${CYAN}=== Installing Go ===${NC}"

    if command -v go &> /dev/null; then
        echo -e "${GREEN}Go is already installed: $(go version)${NC}"
    else
        echo -e "${YELLOW}Please install Go from: https://go.dev/dl/${NC}"
        echo "After installation, re-run this script."
        return 1
    fi

    echo "Installing Go gRPC tools..."
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
    echo -e "${GREEN}Go gRPC tools installed${NC}"

    echo "Installing Python gRPC dependencies..."
    pip install grpcio grpcio-tools
    echo -e "${GREEN}Python gRPC dependencies installed${NC}"
}

show_status() {
    echo -e "\n${CYAN}=== Toolchain Status ===${NC}"

    if command -v python3 &> /dev/null; then
        echo -e "${GREEN}[OK] Python: $(python3 --version)${NC}"
    else
        echo -e "${RED}[MISSING] Python${NC}"
    fi

    if command -v cargo &> /dev/null; then
        echo -e "${GREEN}[OK] Rust: $(cargo --version)${NC}"
    else
        echo -e "${YELLOW}[MISSING] Rust (install with --rust)${NC}"
    fi

    if command -v go &> /dev/null; then
        echo -e "${GREEN}[OK] Go: $(go version)${NC}"
    else
        echo -e "${YELLOW}[MISSING] Go (install from go.dev/dl)${NC}"
    fi

    if command -v maturin &> /dev/null; then
        echo -e "${GREEN}[OK] Maturin: $(maturin --version)${NC}"
    else
        echo -e "${YELLOW}[MISSING] Maturin${NC}"
    fi

    if command -v protoc &> /dev/null; then
        echo -e "${GREEN}[OK] Protoc: $(protoc --version)${NC}"
    else
        echo -e "${YELLOW}[MISSING] Protoc${NC}"
    fi
}

case "${1:-}" in
    --all)
        install_rust
        install_go
        ;;
    --rust)
        install_rust
        ;;
    --go)
        install_go
        ;;
    *)
        echo "Cortex Toolchain Setup"
        echo "Usage: $0 [--rust] [--go] [--all]"
        ;;
esac

show_status
