# Cortex Hybrid Architecture - Toolchain Setup (Windows)
# Run: powershell -ExecutionPolicy Bypass -File scripts\setup_toolchains.ps1

param(
    [switch]$Rust,
    [switch]$Go,
    [switch]$All
)

$ErrorActionPreference = "Stop"

function Install-Rust {
    Write-Host "`n=== Installing Rust ===" -ForegroundColor Cyan

    if (Get-Command cargo -ErrorAction SilentlyContinue) {
        Write-Host "Rust is already installed: $(cargo --version)" -ForegroundColor Green
    } else {
        Write-Host "Downloading rustup installer..."
        $rustupUrl = "https://win.rustup.rs/x86_64"
        $rustupExe = "$env:TEMP\rustup-init.exe"
        Invoke-WebRequest -Uri $rustupUrl -OutFile $rustupExe
        Write-Host "Running rustup installer..."
        & $rustupExe -y --default-toolchain stable
        $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
        Write-Host "Rust installed: $(cargo --version)" -ForegroundColor Green
    }

    # Install maturin for PyO3 builds
    Write-Host "Installing maturin (Python-Rust bridge)..."
    pip install maturin
    Write-Host "maturin installed: $(maturin --version)" -ForegroundColor Green
}

function Install-Go {
    Write-Host "`n=== Installing Go ===" -ForegroundColor Cyan

    if (Get-Command go -ErrorAction SilentlyContinue) {
        Write-Host "Go is already installed: $(go version)" -ForegroundColor Green
    } else {
        Write-Host "Please install Go from: https://go.dev/dl/"
        Write-Host "After installation, restart this script." -ForegroundColor Yellow
        return
    }

    # Install protoc for gRPC
    Write-Host "Installing Go gRPC tools..."
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
    Write-Host "Go gRPC tools installed" -ForegroundColor Green

    # Install Python gRPC dependencies
    Write-Host "Installing Python gRPC dependencies..."
    pip install grpcio grpcio-tools
    Write-Host "Python gRPC dependencies installed" -ForegroundColor Green
}

function Show-Status {
    Write-Host "`n=== Toolchain Status ===" -ForegroundColor Cyan

    # Python
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Python: $(python --version)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Python" -ForegroundColor Red
    }

    # Rust
    if (Get-Command cargo -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Rust: $(cargo --version)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Rust (install with -Rust flag)" -ForegroundColor Yellow
    }

    # Go
    if (Get-Command go -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Go: $(go version)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Go (install from go.dev/dl)" -ForegroundColor Yellow
    }

    # Maturin
    if (Get-Command maturin -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Maturin: $(maturin --version)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Maturin (installed with Rust)" -ForegroundColor Yellow
    }

    # Protoc
    if (Get-Command protoc -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Protoc: $(protoc --version)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] Protoc (needed for gRPC)" -ForegroundColor Yellow
    }
}

# Main
if ($All) {
    Install-Rust
    Install-Go
} elseif ($Rust) {
    Install-Rust
} elseif ($Go) {
    Install-Go
} else {
    Write-Host "Cortex Toolchain Setup" -ForegroundColor Cyan
    Write-Host "Usage: setup_toolchains.ps1 [-Rust] [-Go] [-All]"
    Write-Host ""
}

Show-Status
