# Cortex Deployment Guide

This guide covers production deployment, security hardening, and operational considerations for running Cortex in production environments.

## Table of Contents

1. [Production Requirements](#1-production-requirements)
2. [Security Hardening](#2-security-hardening)
3. [Configuration](#3-configuration)
4. [Monitoring & Observability](#4-monitoring--observability)
5. [Scaling Considerations](#5-scaling-considerations)
6. [Backup & Recovery](#6-backup--recovery)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Production Requirements

### System Requirements

**Minimum:**
- Python 3.8+
- 4GB RAM
- 10GB disk space
- Linux/Windows/macOS

**Recommended:**
- Python 3.9+
- 8GB RAM
- 20GB SSD storage
- Linux (Ubuntu 20.04+ or CentOS 7+)

### Network Requirements

**Inbound:**
- None (Cortex is a client, not a server)

**Outbound:**
- HTTPS to LLM providers (OpenAI, Anthropic, etc.)
- HTTPS to external APIs (if using web tools)
- SSH to git repositories

### Dependencies

**Core:**
```bash
pip install cortex-ai
```

**Optional (for full functionality):**
```bash
pip install requests beautifulsoup4 html2text duckduckgo-search tree-sitter
```

---

## 2. Security Hardening

### API Key Management

**Environment Variables:**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
```

**Key Management Best Practices:**
- Use dedicated API keys with restricted permissions
- Rotate keys regularly (90 days)
- Store keys in secure vaults (AWS Secrets Manager, HashiCorp Vault)
- Never commit keys to version control

### Permission Modes

**Available Modes:**
- `NORMAL` - Ask for approval on destructive operations
- `AUTO_APPROVE` - Allow all operations (dangerous!)
- `PLAN` - Read-only mode

**Production Recommendation:**
```yaml
# config/production.yaml
permission_mode: normal
```

### Sandboxing

**Tool Restrictions:**
- File operations limited to project directory
- Command execution validated for safety
- Network requests restricted to safe domains

**Container Security:**
```dockerfile
# Use non-root user
USER cortex
# Read-only filesystem
READONLY
# No privileged access
securityContext:
  privileged: false
  allowPrivilegeEscalation: false
```

### Audit Logging

**Enable Comprehensive Logging:**
```yaml
logging:
  level: INFO
  handlers:
    - file: /var/log/cortex/cortex.log
      max_size: 100MB
      backups: 5
    - syslog: true
```

**Log Analysis:**
- Monitor for suspicious tool usage
- Track API key usage patterns
- Alert on configuration changes

---

## 3. Configuration

### Production Configuration

**config/production.yaml:**
```yaml
# Core settings
model: gpt-4  # Use stable production model
permission_mode: normal
max_iterations: 50
max_tokens: 100000

# Performance tuning
parallel_execution:
  enabled: true
  max_workers: 4
  batch_size: 5

# Rate limiting
rate_limit:
  enabled: true
  requests_per_minute: 50
  tokens_per_minute: 80000

# Session management
session_retention:
  warn_on_truncation: true
  compression_enabled: true

# Recovery
recovery:
  max_checkpoints: 20
  auto_checkpoint_interval: 100
  compression_enabled: true

# Tool configuration
tools:
  disabled:
    - web_search  # Disable for security
    - execute_command  # Restrict to approved commands
  enabled: []
  plugins: []

# Memory management
memory:
  max_file_size: 10485760  # 10MB
  streaming_threshold: 1048576  # 1MB
```

### Environment-Specific Configs

**Development:**
```yaml
model: llama3.2:3b
permission_mode: auto_approve
max_iterations: 10
```

**Staging:**
```yaml
model: gpt-3.5-turbo
permission_mode: normal
max_iterations: 25
```

**Production:**
```yaml
model: gpt-4
permission_mode: normal
max_iterations: 50
rate_limit:
  enabled: true
```

### Configuration Validation

**Validate config on startup:**
```bash
cortex --config config/production.yaml --validate
```

---

## 4. Monitoring & Observability

### Health Checks

**Built-in Health Monitoring:**
```python
from cortex.agent import Cortex

agent = Cortex(config_path="config/production.yaml")
health = agent.validate_session_health()

if not health["healthy"]:
    print(f"Issues: {health['issues']}")
    print(f"Recommendations: {health['recommendations']}")
```

**HTTP Health Endpoint (if using web interface):**
```python
@app.get("/health")
def health_check():
    agent = get_agent()
    health = agent.validate_session_health()
    return {"status": "healthy" if health["healthy"] else "unhealthy", **health}
```

### Metrics Collection

**Key Metrics to Monitor:**
- Request latency (P50, P95, P99)
- Token usage per request
- Tool execution success rate
- Memory usage
- Error rate by type

**Prometheus Metrics:**
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('cortex_requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('cortex_request_latency_seconds', 'Request latency')
TOKEN_USAGE = Counter('cortex_tokens_total', 'Total tokens used')
TOOL_EXECUTIONS = Counter('cortex_tool_executions_total', 'Tool executions', ['tool', 'success'])
```

### Logging

**Structured Logging:**
```python
import logging
import json

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "request_id": getattr(record, 'request_id', None)
        }
        return json.dumps(log_entry)
```

**Log Aggregation:**
- Use ELK stack (Elasticsearch, Logstash, Kibana)
- Or CloudWatch Logs, Stackdriver
- Set up alerts for ERROR/WARNING levels

### Performance Monitoring

**APM Integration:**
```python
# DataDog APM
import ddtrace
ddtrace.patch_all()

# New Relic
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')
```

---

## 5. Scaling Considerations

### Horizontal Scaling

**Stateless Design:**
- Each Cortex instance is independent
- Session state stored externally (Redis, database)
- Shared file storage for persistent data

**Load Balancing:**
```nginx
upstream cortex_backends {
    server cortex-01:8000;
    server cortex-02:8000;
    server cortex-03:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://cortex_backends;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Vertical Scaling

**Resource Allocation:**
- CPU: 2-4 cores per instance
- Memory: 4-8GB per instance
- Storage: 20-50GB SSD per instance

**Performance Tuning:**
```yaml
# config/high_performance.yaml
parallel_execution:
  max_workers: 8
  batch_size: 10

memory:
  max_file_size: 104857600  # 100MB
  streaming_threshold: 5242880  # 5MB
```

### Database Integration

**Session Persistence:**
```python
# Use external database for sessions
import redis

redis_client = redis.Redis(host='redis-server', port=6379)

def save_session(session_id, data):
    redis_client.setex(f"session:{session_id}", 3600, json.dumps(data))

def load_session(session_id):
    data = redis_client.get(f"session:{session_id}")
    return json.loads(data) if data else None
```

### Caching Strategy

**Multi-Level Caching:**
1. **Memory Cache**: Fast in-process cache (LRU)
2. **Redis Cache**: Shared distributed cache
3. **Disk Cache**: Persistent file-based cache

```yaml
cache:
  memory:
    enabled: true
    max_size: 1000
  redis:
    enabled: true
    host: redis-server
    ttl: 3600
  disk:
    enabled: true
    path: /var/cache/cortex
```

---

## 6. Backup & Recovery

### Data Backup

**What to Backup:**
- Configuration files
- Session checkpoints
- Tool cache data
- User data (if any)

**Automated Backup Script:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/cortex"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
tar -czf "$BACKUP_DIR/cortex_$DATE.tar.gz" \
    /etc/cortex/config/ \
    /var/lib/cortex/sessions/ \
    /var/cache/cortex/

# Clean old backups (keep last 7 days)
find "$BACKUP_DIR" -name "cortex_*.tar.gz" -mtime +7 -delete
```

### Disaster Recovery

**Recovery Procedure:**
1. Restore from backup
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Restore configuration
4. Validate functionality
5. Resume operations

**Recovery Time Objective (RTO):** 4 hours
**Recovery Point Objective (RPO):** 1 hour

### Session Recovery

**Built-in Recovery Features:**
- Automatic checkpointing
- Session health monitoring
- Corruption detection and repair

**Manual Recovery:**
```python
from cortex.agent import Cortex

# Load from checkpoint
agent = Cortex()
latest_checkpoint = agent.checkpoint_manager.get_latest_checkpoint(session_id)
if latest_checkpoint:
    conversation_data = agent.checkpoint_manager.restore_checkpoint(latest_checkpoint)
    # Restore conversation state
```

---

## 7. Troubleshooting

### Common Issues

**High Memory Usage:**
```
Symptoms: OOM errors, slow performance
Solutions:
- Reduce max_file_size in config
- Enable streaming for large files
- Monitor memory usage with ps/top
```

**Rate Limiting:**
```
Symptoms: API errors, slow responses
Solutions:
- Increase rate limits in config
- Use multiple API keys
- Implement request queuing
```

**Tool Failures:**
```
Symptoms: Tools return errors
Solutions:
- Check tool permissions
- Validate tool dependencies
- Review tool logs
```

### Debug Mode

**Enable Debug Logging:**
```bash
export CORTEX_LOG_LEVEL=DEBUG
cortex --debug
```

**Verbose Tool Execution:**
```yaml
debug:
  tool_execution: true
  api_calls: true
  memory_usage: true
```

### Performance Profiling

**CPU Profiling:**
```python
import cProfile
import pstats

with cProfile.Profile() as pr:
    # Run your code
    agent.process_message("Analyze this codebase")

stats = pstats.Stats(pr)
stats.sort_stats('cumulative').print_stats(20)
```

**Memory Profiling:**
```python
from memory_profiler import profile

@profile
def process_large_file():
    # Your code here
    pass
```

### Support Resources

**Community Support:**
- GitHub Issues: https://github.com/your-org/cortex/issues
- Documentation: https://your-org.github.io/cortex/
- Slack/Teams channel

**Enterprise Support:**
- 24/7 monitoring alerts
- Dedicated support engineer
- Custom deployment assistance

---

## Deployment Checklist

### Pre-Deployment
- [ ] Security review completed
- [ ] Configuration validated
- [ ] Dependencies installed
- [ ] API keys configured
- [ ] Backup strategy implemented

### Deployment
- [ ] Application deployed
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Logs aggregated
- [ ] Access controls set

### Post-Deployment
- [ ] Load testing completed
- [ ] Performance baselines established
- [ ] Runbooks documented
- [ ] Team trained on operations

### Maintenance
- [ ] Regular security updates
- [ ] Performance monitoring
- [ ] Backup verification
- [ ] Log rotation configured

---

*Last updated: 2026-01-18*
