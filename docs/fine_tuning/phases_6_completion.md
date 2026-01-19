# Phase 6: Production Deployment (Weeks 7-8)

## 6.1 Inference Cost & Performance

```
SECURITY MODEL (14B):
- Input cost: $0.14/M tokens
- Output cost: $0.56/M tokens
- Avg request: 300 input + 400 output tokens
- Cost/request: $0.00036
- Requests/month (50/day): $0.54
- Typical latency: 0.9s

CODING MODEL (32B):
- Input cost: $0.28/M tokens
- Output cost: $1.12/M tokens
- Avg request: 1000 input + 2000 output tokens
- Cost/request: $0.00280
- Requests/month (20/day): $1.68
- Typical latency: 2.5s

TOTAL MONTHLY (50 security + 20 coding):
- Together AI inference: ~$2.22/month
- Fine-tuning (one-time): $41
- Total setup cost: ~$43
```

## 6.2 Monitoring Both Models

```python
# scripts/production_monitor.py
import json
from datetime import datetime

class DualModelMonitor:
    """Monitor both models in production"""
    
    def __init__(self):
        self.security_log = "logs/security_inference.jsonl"
        self.coding_log = "logs/coding_inference.jsonl"
    
    def log_security_inference(self, prompt_len, response_len, latency, cost):
        """Log security model inference"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": "deepseek-coder-14b",
            "prompt_tokens": prompt_len,
            "response_tokens": response_len,
            "latency_ms": latency * 1000,
            "cost": cost,
        }
        with open(self.security_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def log_coding_inference(self, prompt_len, response_len, latency, cost):
        """Log coding model inference"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": "deepseek-coder-32b",
            "prompt_tokens": prompt_len,
            "response_tokens": response_len,
            "latency_ms": latency * 1000,
            "cost": cost,
        }
        with open(self.coding_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def generate_report(self):
        """Generate monthly usage report"""
        
        def parse_logs(log_file):
            entries = []
            try:
                with open(log_file) as f:
                    for line in f:
                        entries.append(json.loads(line))
            except:
                pass
            return entries
        
        security_entries = parse_logs(self.security_log)
        coding_entries = parse_logs(self.coding_log)
        
        print("\n" + "=" * 70)
        print("CORTEX DUAL MODEL PRODUCTION REPORT")
        print("=" * 70)
        
        print("\nSECURITY MODEL (14B):")
        if security_entries:
            total_requests = len(security_entries)
            avg_latency = sum(e["latency_ms"] for e in security_entries) / total_requests
            total_cost = sum(e["cost"] for e in security_entries)
            print(f"  Requests: {total_requests}")
            print(f"  Avg latency: {avg_latency:.0f}ms")
            print(f"  Total cost: ${total_cost:.2f}")
        
        print("\nCODING MODEL (32B):")
        if coding_entries:
            total_requests = len(coding_entries)
            avg_latency = sum(e["latency_ms"] for e in coding_entries) / total_requests
            total_cost = sum(e["cost"] for e in coding_entries)
            print(f"  Requests: {total_requests}")
            print(f"  Avg latency: {avg_latency:.0f}ms")
            print(f"  Total cost: ${total_cost:.2f}")
        
        if security_entries or coding_entries:
            total_cost = sum(e.get("cost", 0) for e in security_entries + coding_entries)
            print(f"\nTOTAL MONTHLY COST: ${total_cost:.2f}")
```

---

## Timeline & Milestones

| Week | Phase | Milestone | Deliverable |
|------|-------|-----------|-------------|
| 1-2 | Dataset Prep | Both datasets collected & validated | 600 security + 800 coding examples |
| 2-3 | Data Split | Train/val/test splits created | 3 JSONL files per model |
| 3-4 | Fine-Tuning | Both models training | 14B + 32B jobs running in parallel |
| 4-5 | Evaluation | Both models evaluated | Accuracy metrics for each |
| 5-6 | Integration | Framework integrated | Dual providers in CORTEX |
| 6-7 | Testing | End-to-end testing | Real security & coding scenarios |
| 7-8 | Production | Live monitoring | Cost tracking, performance metrics |

---

## Cost Breakdown

| Item | Cost | Timeline |
|------|------|----------|
| **Security 14B Fine-tuning** | $20 | Week 3-4 |
| **Coding 32B Fine-tuning** | $21 | Week 3-4 |
| **Evaluation & Testing** | $5-10 | Week 4-5 |
| **First Month Inference** | $2-5 | Week 6-8 |
| **Total to Production** | **$50-60** | **8 weeks** |
| **Monthly Ongoing** | **$2-5** | Recurring |

---

## Success Metrics

### Security Model (14B)

1. **Tool Accuracy**: >95% correct tool calls
2. **Response Time**: <1.5s avg latency
3. **False Positives**: <5% on vulnerability scanning
4. **Safety**: >98% dangerous command detection

### Coding Model (32B)

1. **Code Quality**: >90% of generated code is syntactically valid
2. **Response Time**: <3s avg latency
3. **Reasoning Chains**: >85% of 5+ step plans executed correctly
4. **Test Coverage**: >80% of generated tests pass

### Overall

1. **Cost Efficiency**: <$5/month for typical usage
2. **Task Accuracy**: >85% overall task success
3. **User Satisfaction**: <1.5s for security, <3s for coding tasks

---

## Quick Start Commands

```bash
# Setup
export TOGETHER_API_KEY="your_key_here"
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create datasets (Week 1-2)
python scripts/create_datasets.py
python scripts/prepare_datasets.py
python scripts/validate_datasets.py

# Launch fine-tuning (Week 3)
python scripts/finetune_14b.py &  # Background
python scripts/finetune_32b.py &  # Background
python scripts/monitor_all.py     # Monitor both

# Evaluate (Week 4-5)
python scripts/evaluate_14b.py
python scripts/evaluate_32b.py
python scripts/compare_models.py

# Integrate (Week 5-6)
python scripts/test_cortex_framework.py

# Monitor production (Week 7+)
python scripts/production_monitor.py
```

---

## Environment Variables Required

```bash
# API Keys
export TOGETHER_API_KEY="sk-..."

# Model IDs (after fine-tuning)
export DEEPSEEK_CODER_14B_FT_MODEL_ID="together-api/..."
export DEEPSEEK_CODER_32B_FT_MODEL_ID="together-api/..."

# Optional
export CORTEX_LOG_LEVEL="INFO"
export CORTEX_INFERENCE_TIMEOUT="30"
```

---

## Resources & References

- **Together AI Docs**: https://docs.together.ai/docs/fine-tuning-quickstart
- **DeepSeek Coder 14B**: https://huggingface.co/deepseek-ai/deepseek-coder-14b-base
- **DeepSeek Coder 32B**: https://huggingface.co/deepseek-ai/deepseek-coder-32b-base
- **LoRA Paper**: https://arxiv.org/abs/2106.09685
- **CORTEX Technical Spec**: CORTEX_TECHNICAL_SPEC.md

---

**Document Version**: 2.1 (Dual Model - Framework Only)  
**Last Updated**: 2026-01-15  
**Status**: Ready for implementation  
**Next Steps**: Implement your own router logic for task classification
