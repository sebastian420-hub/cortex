# Cortex: System Requirements & Deployment Guide

## Version 1.0.0

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Software Prerequisites](#software-prerequisites)
3. [Installation Guide](#installation-guide)
4. [Configuration Management](#configuration-management)
5. [Deployment Options](#deployment-options)
6. [Operation & Maintenance](#operation--maintenance)
7. [Monitoring & Observability](#monitoring--observability)
8. [Security Hardening](#security-hardening)
9. [Performance Tuning](#performance-tuning)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Upgrade Procedures](#upgrade-procedures)

---

## 1. Hardware Requirements

### 1.1 Minimum Requirements (Local Models)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 4 cores (x86_64) | 8+ cores (x86_64/ARM) |
| **RAM** | 8 GB | 16+ GB |
| **Storage** | 10 GB free space | 50+ GB SSD |
| **GPU** | Optional | NVIDIA GPU (8+ GB VRAM) |
| **Network** | - | For cloud model access |

### 1.2 Recommended Requirements

#### For Local Development
- **CPU**: Intel i7/AMD Ryzen 7 or equivalent (8 cores)
- **RAM**: 32 GB (for larger models like llama3.3:70b)
- **Storage**: NVMe SSD with 100+ GB free space
- **GPU**: NVIDIA RTX 4070+ (12GB VRAM) or equivalent
- **OS**: Linux/macOS/Windows WSL2

#### For Production Usage
- **CPU**: 16+ cores with AVX2 support
- **RAM**: 64+ GB
- **Storage**: 500+ GB fast SSD
- **GPU**: Multiple GPUs for parallel processing
- **Network**: 1 Gbps+ connectivity for cloud models

### 1.3 Model-Specific Requirements

| Model | RAM (Minimum) | VRAM (Recommended) | Storage |
|-------|---------------|-------------------|---------|
| **llama3.2** (3B) | 4 GB | 4 GB | 2 GB |
| **llama3.3:70b** | 64 GB | 40 GB | 40 GB |
| **qwen2.5:32b** | 32 GB | 16 GB | 20 GB |
| **deepseek-r1:8b** | 8 GB | 8 GB | 5 GB |

## 2. Software Prerequisites

### 2.1 Operating Systems

#### Supported Platforms
- **Linux**: Ubuntu 20.04+, Debian 11+, CentOS 8+
- **macOS**: 11.0+ (Intel/Apple Silicon)
- **Windows**: Windows 10/11 with WSL2 (Ubuntu recommended)

#### Unsupported Platforms
- Windows native (without WSL2)
- 32-bit architectures
- ARM Linux (except macOS Apple Silicon)

### 2.2 Required Software

#### Python Environment
- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12
- **pip**: Latest version
- **virtualenv/venv**: Recommended for isolation
- **pipx**: Optional for global installation

#### System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-venv \
    git \
    curl \
    wget

# macOS
brew install python@3.11 git curl wget

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install python3-devel git curl wget
```

### 2.3 Optional Dependencies

#### GPU Acceleration (CUDA)
```bash
# For NVIDIA GPU support with Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve  # Starts with GPU acceleration
```

#### Docker (Containerized Deployment)
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker run hello-world
```

#### Model-Specific Requirements

**Ollama** (for local models):
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# Pull models (in separate terminal)
ollama pull llama3.2
ollama pull qwen2.5:32b
```

**Cloud API Keys** (for cloud models):
```bash
# DeepSeek API
export DEEPSEEK_API_KEY="your_key_here"

# Anthropic Claude API  
export ANTHROPIC_API_KEY="your_key_here"

# Make permanent in ~/.bashrc or ~/.zshrc
echo 'export DEEPSEEK_API_KEY="your_key_here"' >> ~/.bashrc
echo 'export ANTHROPIC_API_KEY="your_key_here"' >> ~/.bashrc
```

## 3. Installation Guide

### 3.1 Installation Methods

#### Method 1: From Source (Recommended)
```bash
# Clone repository
git clone https://github.com/yourusername/cortex.git
cd cortex

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
cortex --version
```

#### Method 2: PyPI Installation (Future)
```bash
# When available on PyPI
pip install cortex-agent

# Verify installation
cortex --help
```

#### Method 3: Docker
```bash
# Build from Dockerfile
docker build -t cortex .

# Or pull from registry (future)
docker pull yourregistry/cortex:latest

# Run container
docker run -it \
  -v $(pwd):/project \
  -v ~/.cortex:/root/.cortex \
  -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY \
  cortex
```

### 3.2 Post-Installation Setup

#### Configuration Directory
```bash
# Default configuration directory
ls ~/.cortex/
# config/          # Configuration files
# sessions/        # Session storage
# cache/           # Cache files
# logs/            # Log files (if enabled)
```

#### Initial Configuration
```bash
# Create minimal config file
mkdir -p ~/.cortex/config
cat > ~/.cortex/config/default.yaml << EOF
model: llama3.2
permission_mode: normal
max_iterations: 15
EOF
```

#### Test Installation
```bash
# Basic functionality test
cortex --list-providers

# Interactive test
cortex

# One-shot test
cortex -p "list files in current directory"
```

### 3.3 Development Installation

For contributing to Cortex:
```bash
# Clone with submodules
git clone --recursive https://github.com/yourusername/cortex.git
cd cortex

# Install development dependencies
pip install -r requirements-dev.txt
pip install -r requirements-test.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Run type checking
mypy cortex/

# Run code formatting
black cortex/ tests/
```

## 4. Configuration Management

### 4.1 Configuration Files

#### Default Configuration (`config/default.yaml`)
```yaml
# Core settings
model: deepseek-reasoner
permission_mode: normal
max_iterations: 15
max_tokens: 100000
keep_recent_messages: 20
auto_save: false

# Provider settings (auto-detected if null)
provider: null

# Session management
session_retention:
  max_age_days: 30
  max_count: 100
  max_total_size_mb: 500
  cleanup_on_startup: false

# Parallel execution
parallel_execution:
  enabled: true
  max_workers: 4
  batch_size: 10

# Error recovery
error_recovery:
  max_repeats: 3
  stuck_threshold: 5
  recovery_strategy: "suggest"
  max_recovery_attempts: 2

# File cache
file_cache:
  enabled: true
  max_entries: 100
  max_size_mb: 50.0
```

#### Custom Configuration
```bash
# Use custom config file
cortex --config /path/to/custom-config.yaml

# Environment variable override
export CORTEX_CONFIG_PATH="/path/to/config.yaml"
cortex
```

### 4.2 Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API access | `export DEEPSEEK_API_KEY="sk-..."` |
| `ANTHROPIC_API_KEY` | Claude API access | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `CORTEX_MODEL` | Override default model | `export CORTEX_MODEL="llama3.3:70b"` |
| `CORTEX_PERMISSION_MODE` | Security mode | `export CORTEX_PERMISSION_MODE="plan"` |
| `CORTEX_CONFIG_PATH` | Config file path | `export CORTEX_CONFIG_PATH="~/.cortex/config.yaml"` |
| `CORTEX_LOG_LEVEL` | Logging verbosity | `export CORTEX_LOG_LEVEL="DEBUG"` |
| `CORTEX_CACHE_DIR` | Cache location | `export CORTEX_CACHE_DIR="/tmp/cortex-cache"` |

### 4.3 Configuration Precedence

1. **CLI Arguments**: Highest priority (`--model llama3.3:70b`)
2. **Environment Variables**: Medium priority (`CORTEX_MODEL`)
3. **Config File**: Low priority (`config/default.yaml`)
4. **Defaults**: Lowest priority (hardcoded defaults)

### 4.4 Configuration Validation

```bash
# Validate configuration
cortex --config config.yaml --dry-run

# Check configuration schema
python -m cortex.config.validate config.yaml
```

## 5. Deployment Options

### 5.1 Local Development Deployment

#### Single User Setup
```bash
# Simple start
cd /path/to/project
cortex

# With specific model
cortex --model llama3.3:70b

# With auto-approve for testing
cortex --auto-approve

# One-shot tasks
cortex -p "analyze code structure"
```

#### Persistent Service (Systemd)
```bash
# Create systemd service file
sudo cat > /etc/systemd/system/cortex.service << EOF
[Unit]
Description=Cortex AI Assistant
After=network.target ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER
Environment="DEEPSEEK_API_KEY=your_key"
Environment="ANTHROPIC_API_KEY=your_key"
ExecStart=/usr/local/bin/cortex --model llama3.2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable cortex
sudo systemctl start cortex
sudo systemctl status cortex
```

### 5.2 Docker Deployment

#### Docker Compose Setup
```yaml
# docker-compose.yml
version: '3.8'

services:
  cortex:
    build: .
    image: cortex:latest
    container_name: cortex
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CORTEX_MODEL=deepseek-chat
    volumes:
      - ./projects:/projects
      - cortex-data:/root/.cortex
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8080:8080"  # For future web interface
    restart: unless-stopped

volumes:
  cortex-data:
```

#### Run with Docker Compose
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f cortex

# Execute commands
docker-compose exec cortex cortex --list-providers
```

### 5.3 Kubernetes Deployment

#### Deployment Manifest
```yaml
# cortex-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortex
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cortex
  template:
    metadata:
      labels:
        app: cortex
    spec:
      containers:
      - name: cortex
        image: cortex:latest
        env:
        - name: DEEPSEEK_API_KEY
          valueFrom:
            secretKeyRef:
              name: cortex-secrets
              key: deepseek-api-key
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: cortex-secrets
              key: anthropic-api-key
        volumeMounts:
        - name: cortex-storage
          mountPath: /root/.cortex
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: cortex-storage
        persistentVolumeClaim:
          claimName: cortex-pvc
```

#### Service Manifest
```yaml
# cortex-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: cortex-service
spec:
  selector:
    app: cortex
  ports:
  - port: 8080
    targetPort: 8080
  type: LoadBalancer
```

### 5.4 Cloud Deployment

#### AWS ECS/Fargate
```json
{
  "family": "cortex",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "cortex",
      "image": "cortex:latest",
      "essential": true,
      "environment": [
        {"name": "DEEPSEEK_API_KEY", "value": "your-key"},
        {"name": "ANTHROPIC_API_KEY", "value": "your-key"}
      ],
      "secrets": [
        {"name": "API_KEYS", "valueFrom": "arn:aws:secretsmanager:region:account:secret:name"}
      ]
    }
  ]
}
```

## 6. Operation & Maintenance

### 6.1 Daily Operations

#### Starting Cortex
```bash
# Interactive mode
cortex

# With project directory
cortex --project-dir /path/to/project

# With specific configuration
cortex --config production.yaml

# As background service
nohup cortex --model deepseek-chat > cortex.log 2>&1 &
```

#### Session Management
```bash
# List saved sessions
cortex --list-sessions

# Load specific session
cortex --load-session project-analysis

# Save current session
cortex --save-session api-refactoring

# Clean old sessions
cortex --cleanup-sessions
```

### 6.2 Monitoring Operations

#### Health Checks
```bash
# Check agent health
curl http://localhost:8080/health

# Check provider connectivity
cortex --list-providers

# Test model response
cortex -p "echo test" --model llama3.2
```

#### Performance Monitoring
```bash
# Monitor resource usage
top -p $(pgrep -f cortex)

# Check disk usage
du -sh ~/.cortex/

# Check cache efficiency
cortex --cache-stats
```

### 6.3 Backup Procedures

#### Configuration Backup
```bash
# Backup configuration
tar -czf cortex-config-backup-$(date +%Y%m%d).tar.gz ~/.cortex/config/

# Backup sessions
tar -czf cortex-sessions-backup-$(date +%Y%m%d).tar.gz ~/.cortex/sessions/
```

#### Database Backup (Future)
```bash
# Export conversation history
cortex --export-history history.json

# Backup vector database (if used)
cortex --export-knowledge knowledge.db
```

### 6.4 Maintenance Tasks

#### Regular Cleanup
```bash
# Clear cache
cortex --clear-cache

# Remove old sessions
find ~/.cortex/sessions/ -type f -mtime +30 -delete

# Rotate logs
logrotate /etc/logrotate.d/cortex
```

#### Update Procedures
```bash
# Update Cortex
git pull origin main
pip install --upgrade -r requirements.txt
pip install -e .

# Update models (Ollama)
ollama pull llama3.2:latest
ollama pull qwen2.5:32b:latest
```

## 7. Monitoring & Observability

### 7.1 Logging Configuration

#### Log Levels
```yaml
# config/logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: detailed
  
  file:
    class: logging.handlers.RotatingFileHandler
    filename: /var/log/cortex/cortex.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
    formatter: detailed

loggers:
  cortex:
    level: INFO
    handlers: [console, file]
```

#### Log Rotation
```bash
# /etc/logrotate.d/cortex
/var/log/cortex/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 cortex cortex
}
```

### 7.2 Metrics Collection

#### Prometheus Metrics (Future)
```python
# metrics.py (planned)
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('cortex_requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('cortex_request_latency_seconds', 'Request latency')
TOOL_USAGE = Counter('cortex_tool_usage', 'Tool usage by type', ['tool_name'])
```

#### Health Check Endpoints
```python
# health.py (planned)
@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': __version__
    }
```

### 7.3 Alerting Configuration

#### Alert Rules (Prometheus)
```yaml
# prometheus-rules.yaml
groups:
- name: cortex
  rules:
  - alert: HighErrorRate
    expr: rate(cortex_errors_total[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate in Cortex"
      
  - alert: ServiceDown
    expr: up{job="cortex"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Cortex service is down"
```

## 8. Security Hardening

### 8.1 Security Configuration

#### Permission Modes
```bash
# Development mode (interactive)
cortex --permission-mode normal

# Automated tasks
cortex --permission-mode auto-approve

# Safe exploration
cortex --permission-mode plan
```

#### Security Boundaries
```yaml
# security.yaml
security:
  # File system restrictions
  allowed_directories:
    - /home/user/projects
    - /tmp
  
  # Command restrictions
  blocked_commands:
    - "rm -rf"
    - "format"
    - "dd"
  
  # Network restrictions
  allowed_domains:
    - "api.deepseek.com"
    - "api.anthropic.com"
```

### 8.2 Authentication & Authorization (Future)

#### API Key Management
```bash
# Generate API key
cortex --generate-api-key

# Revoke API key
cortex --revoke-api-key KEY_ID

# List API keys
cortex --list-api-keys
```

#### Role-Based Access Control
```yaml
# roles.yaml
roles:
  developer:
    permissions:
      - read_file
      - write_file
      - execute_command
    restrictions:
      - no_git_push
      - no_system_commands
  
  admin:
    permissions:
      - all
    restrictions: []
```

### 8.3 Network Security

#### Firewall Configuration
```bash
# Allow only local access
sudo ufw allow from 127.0.0.1 to any port 8080

# Or allow specific IP range
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

#### TLS/SSL Configuration
```bash
# Generate certificates
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# Run with TLS
cortex --tls-cert cert.pem --tls-key key.pem --port 8443
```

## 9. Performance Tuning

### 9.1 Memory Optimization

#### Cache Configuration
```yaml
# config/performance.yaml
cache:
  ast_cache:
    enabled: true
    max_size_mb: 100
    ttl_minutes: 60
  
  file_cache:
    enabled: true
    max_entries: 500
    max_size_mb: 200
  
  model_cache:
    enabled: true
    max_entries: 50
    ttl_minutes: 30
```

#### Memory Limits
```bash
# Set memory limits
export CORTEX_MAX_MEMORY_MB=4096
export CORTEX_MAX_CACHE_MB=1024

# Or via configuration
cortex --max-memory 4096 --max-cache 1024
```

### 9.2 CPU Optimization

#### Parallel Processing
```yaml
# config/parallel.yaml
parallel:
  tool_execution:
    enabled: true
    max_workers: 8
    batch_size: 20
  
  model_requests:
    enabled: false  # Most providers don't support parallel requests
    max_concurrent: 1
```

#### Processor Affinity
```bash
# Pin to specific cores
taskset -c 0-3 cortex

# Or use Docker CPU limits
docker run --cpus=4 cortex
```

### 9.3 I/O Optimization

#### Disk I/O
```bash
# Use tmpfs for cache
sudo mount -t tmpfs -o size=1G tmpfs /tmp/cortex-cache
export CORTEX_CACHE_DIR=/tmp/cortex-cache

# Or use SSD with noatime
sudo mount -o noatime /dev/sdb1 /mnt/cortex
```

#### Network Optimization
```yaml
# config/network.yaml
network:
  timeouts:
    default: 30
    model_request: 120
    tool_execution: 60
  
  retries:
    max_attempts: 3
    backoff_factor: 1.5
  
  connection_pool:
    enabled: true
    max_size: 10
```

## 10. Troubleshooting Guide

### 10.1 Common Issues

#### Issue: Ollama Connection Failed
```bash
# Check if Ollama is running
systemctl status ollama

# Start Ollama if stopped
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

#### Issue: API Key Not Working
```bash
# Check environment variables
echo $DEEPSEEK_API_KEY
echo $ANTHROPIC_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  https://api.deepseek.com/v1/models
```

#### Issue: Permission Denied
```bash
# Check file permissions
ls -la ~/.cortex/

# Fix permissions
chmod 755 ~/.cortex
chmod 644 ~/.cortex/config/*

# Run with correct user
sudo -u $USER cortex
```

### 10.2 Diagnostic Commands

#### System Diagnostics
```bash
# Check Python environment
python --version
pip list | grep cortex

# Check configuration
cortex --config-test

# Check dependencies
cortex --check-dependencies

# Generate diagnostic report
cortex --diagnostics > diagnostics.log
```

#### Performance Diagnostics
```bash
# Profile execution
python -m cProfile -o profile.stats -m cortex.cli -p "test"

# Memory profiling
python -m memory_profiler cortex/cli.py -p "test"

# Generate flame graph
py-spy record -o profile.svg -- python -m cortex.cli -p "test"
```

### 10.3 Recovery Procedures

#### Session Recovery
```bash
# List available checkpoints
cortex --list-checkpoints

# Restore from checkpoint
cortex --restore-checkpoint checkpoint_id

# Repair corrupted session
cortex --repair-session session_id
```

#### Configuration Recovery
```bash
# Reset to defaults
cortex --reset-config

# Restore from backup
cp backup/config.yaml ~/.cortex/config/

# Validate configuration
cortex --validate-config
```

## 11. Upgrade Procedures

### 11.1 Version Compatibility

#### Backward Compatibility
- Configuration files: Backward compatible within major versions
- Session data: May require migration between major versions
- Tool definitions: Backward compatible within minor versions

#### Upgrade Matrix
| From Version | To Version | Migration Required |
|--------------|------------|-------------------|
| 0.9.x | 1.0.0 | Yes (configuration schema) |
| 1.0.0 | 1.1.0 | No |
| 1.x.x | 2.0.0 | Yes (major changes) |

### 11.2 Upgrade Steps

#### Minor Version Upgrade
```bash
# Backup current installation
tar -czf cortex-backup-$(date +%Y%m%d).tar.gz ~/.cortex/

# Update code
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Test upgrade
cortex --version
cortex --config-test
```

#### Major Version Upgrade
```bash
# 1. Backup everything
backup-cortex.sh

# 2. Read release notes
cat CHANGELOG.md

# 3. Run migration script
python -m cortex.migrations.v1_to_v2

# 4. Verify migration
cortex --validate-all

# 5. Test functionality
cortex -p "test upgrade"
```

### 11.3 Rollback Procedures

#### Quick Rollback
```bash
# Stop Cortex service
systemctl stop cortex

# Restore backup
tar -xzf cortex-backup-20240115.tar.gz -C ~/

# Restart service
systemctl start cortex
```

#### Configuration Rollback
```bash
# Revert configuration
git checkout -- config/

# Or restore from backup
cp backup/config.yaml config/

# Clear cache (optional)
cortex --clear-cache
```

---

## Appendix A: Quick Reference

### Installation Quick Start
```bash
# 1. Install prerequisites
sudo apt-get install python3-venv git curl

# 2. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull llama3.2

# 3. Install Cortex
git clone https://github.com/yourusername/cortex.git
cd cortex
python -m venv venv
source venv/bin/activate
pip install -e .

# 4. Run Cortex
cortex
```

### Common Commands
```bash
# Start interactive session
cortex

# One-shot task
cortex -p "list python files"

# With specific model
cortex --model llama3.3:70b

# Safe exploration mode
cortex --permission-mode plan

# Save session
cortex --save-session mywork

# List providers
cortex --list-providers
```

### Configuration Quick Reference
```yaml
# Minimal config
model: llama3.2
permission_mode: normal
max_iterations: 15

# Add API keys for cloud models
# export DEEPSEEK_API_KEY="your_key"
# export ANTHROPIC_API_KEY="your_key"
```

## Appendix B: Support Resources

### Documentation
- [User Guide](../docs/COMMANDS.md)
- [API Reference](../docs/api/)
- [Development Guide](../docs/development.md)

### Community Support
- GitHub Issues: https://github.com/yourusername/cortex/issues
- Discord/Slack: [Link to be added]
- Stack Overflow: Tag `cortex-agent`

### Professional Support
- Enterprise Support: support@cortex.example.com
- Consulting Services: consulting@cortex.example.com
- Training: training@cortex.example.com

## Appendix C: License Information

Cortex is released under the MIT License. See [LICENSE](../LICENSE) file for details.

Third-party dependencies have their own licenses. Run `cortex --licenses` to view all licenses.

---

*Last updated: January 15, 2024*  
*For the latest information, check: https://github.com/yourusername/cortex*