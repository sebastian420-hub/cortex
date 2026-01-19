# CORTEX Dual Model Project - Complete Structure

## Project Organization

```
cortex-finetuning/
├── data/
│   ├── security/
│   │   ├── raw/
│   │   │   └── security_examples.jsonl (600 examples)
│   │   └── processed/
│   │       ├── security_train.jsonl
│   │       ├── security_val.jsonl
│   │       └── security_test.jsonl
│   │
│   └── coding/
│       ├── raw/
│       │   └── coding_examples.jsonl (800 examples)
│       └── processed/
│           ├── coding_train.jsonl
│           ├── coding_val.jsonl
│           └── coding_test.jsonl
│
├── models/
│   ├── 14b/
│   │   ├── checkpoints/
│   │   └── results/
│   │
│   └── 32b/
│       ├── checkpoints/
│       └── results/
│
├── cortex/
│   └── core/
│       └── providers.py (Your provider implementations)
│
├── config/
│   ├── cortex.yaml (Simplified provider config)
│   ├── 14b_config.json (Training config)
│   ├── 32b_config.json (Training config)
│   ├── 14b_model.json (Model ID after training)
│   └── 32b_model.json (Model ID after training)
│
├── scripts/
│   ├── create_datasets.py (Generate 600 + 800 examples)
│   ├── prepare_datasets.py (Create train/val/test splits)
│   ├── validate_datasets.py (Quality checks)
│   ├── finetune_14b.py (Launch 14B training)
│   ├── finetune_32b.py (Launch 32B training)
│   ├── monitor_all.py (Monitor both jobs in parallel)
│   ├── evaluate_14b.py (Test security model)
│   ├── evaluate_32b.py (Test coding model)
│   ├── compare_models.py (Side-by-side comparison)
│   ├── test_cortex_framework.py (Integration tests)
│   └── production_monitor.py (Cost & performance tracking)
│
├── logs/
│   ├── security_inference.jsonl (Production logs)
│   └── coding_inference.jsonl (Production logs)
│
├── results/
│   ├── evaluation_14b.json
│   ├── evaluation_32b.json
│   └── production_report.json
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## requirements.txt

```
together-ai>=0.2.0
huggingface-hub>=0.16.0
datasets>=2.14.0
transformers>=4.30.0
torch>=2.0.0
jsonlines>=3.1.0
pandas>=2.0.0
tqdm>=4.65.0
pyyaml>=6.0
```

---

## .env.example

```bash
# Together AI API
TOGETHER_API_KEY=sk_your_key_here

# Model IDs (filled in after fine-tuning)
DEEPSEEK_CODER_14B_FT_MODEL_ID=together-api/model_id_here
DEEPSEEK_CODER_32B_FT_MODEL_ID=together-api/model_id_here

# CORTEX Settings
CORTEX_LOG_LEVEL=INFO
CORTEX_INFERENCE_TIMEOUT=30
```

---

## Implementation Checklist

### Week 1-2: Data Collection
- [ ] Generate 600 security examples (credential detection, vulnerability scanning, git security, etc.)
- [ ] Generate 800 coding examples (async conversion, design patterns, refactoring, etc.)
- [ ] Validate all examples have proper prompt/completion format
- [ ] Store in `data/security/raw/` and `data/coding/raw/`

### Week 2-3: Data Preparation
- [ ] Run `python scripts/prepare_datasets.py`
- [ ] Verify train/val/test splits created
- [ ] Run `python scripts/validate_datasets.py`
- [ ] Check dataset quality metrics (examples, avg length, no empty rows)

### Week 3-4: Fine-Tuning
- [ ] Set `TOGETHER_API_KEY` in environment
- [ ] Run `python scripts/finetune_14b.py` (background)
- [ ] Run `python scripts/finetune_32b.py` (background)
- [ ] Run `python scripts/monitor_all.py` to watch progress
- [ ] Save model IDs from Together AI to config files

### Week 4-5: Evaluation
- [ ] Run `python scripts/evaluate_14b.py`
- [ ] Run `python scripts/evaluate_32b.py`
- [ ] Run `python scripts/compare_models.py` for comparison
- [ ] Review evaluation results in `results/` directory
- [ ] Verify >85% accuracy on test sets

### Week 5-6: Integration
- [ ] Implement `DeepSeekCoder14BSecurityProvider` in `cortex/core/providers.py`
- [ ] Implement `DeepSeekCoder32BCodegenProvider` in `cortex/core/providers.py`
- [ ] Create simplified `config/cortex.yaml` with provider definitions
- [ ] Write initialization tests for both providers
- [ ] Verify API keys validate correctly

### Week 6-7: Testing
- [ ] Run `python scripts/test_cortex_framework.py`
- [ ] Test security provider with real security scenarios
- [ ] Test coding provider with real coding tasks
- [ ] Verify tool context is properly passed
- [ ] Check response quality and latency

### Week 7-8: Production
- [ ] Deploy providers to production environment
- [ ] Initialize `DualModelMonitor` for cost tracking
- [ ] Run `python scripts/production_monitor.py`
- [ ] Monitor inference logs in `logs/` directory
- [ ] Generate monthly reports
- [ ] Track cost and latency metrics

---

## Implementation Strategy

### Step 1: Build the Framework
1. Create two clean provider classes (no router)
2. Each provider handles: initialization, chat, tool context, API validation
3. Return consistent response format

### Step 2: Build the Data
1. Create 600 security examples covering all security categories
2. Create 800 coding examples covering all coding categories
3. Validate and split into train/val/test sets

### Step 3: Train the Models
1. Upload datasets to Together AI
2. Launch parallel fine-tuning jobs
3. Monitor progress, save model IDs
4. Evaluate both models independently

### Step 4: Integrate with CORTEX
1. Plug providers into CORTEX initialization
2. Keep configuration minimal (just provider definitions)
3. Leave router logic as user responsibility

### Step 5: Monitor Production
1. Log all inferences to JSONL files
2. Track tokens, latency, and cost
3. Generate monthly usage reports
4. Use data to optimize routing strategy

---

## Your Router Logic (You'll Build This)

The framework provides two providers. You decide:

```python
# Your responsibility:
# 1. Classify incoming tasks (security vs coding)
# 2. Route to appropriate provider
# 3. Log results for monitoring

# Examples of classification approaches:
# - Keyword matching (simple, fast)
# - ML classification model (accurate, slower)
# - User explicit hints (reliable, requires user input)
# - Hybrid approach (best of all)
```

---

## Key Files You'll Modify

### `cortex/core/providers.py`
- Add `DeepSeekCoder14BSecurityProvider` class
- Add `DeepSeekCoder32BCodegenProvider` class
- Both providers already in document, just copy/paste

### `config/cortex.yaml`
- Define both provider configurations
- Simplified YAML, no orchestrator config
- Just provider type, model_id, API key, default settings

### Your Application Code
- Initialize both providers at startup
- Implement your own task router
- Call appropriate provider based on classification
- Log results for monitoring

---

## Expected Timeline

| Week | Effort | Milestone |
|------|--------|-----------|
| 1-2 | High | Datasets created & validated |
| 2-3 | Medium | Data splits prepared |
| 3-4 | Low | Fine-tuning (automated) |
| 4-5 | Medium | Models evaluated |
| 5-6 | Medium | Framework integrated |
| 6-7 | Medium | Testing complete |
| 7-8 | Low | Production live |

**Total Active Effort**: ~30-40 hours across 8 weeks  
**Automated Waiting**: ~15 hours (fine-tuning jobs)

---

## Success Indicators

✅ **After Week 2**: 600 + 800 examples created and validated  
✅ **After Week 3**: Data splits ready for fine-tuning  
✅ **After Week 4**: Both models training in parallel  
✅ **After Week 5**: Both models evaluated with >85% accuracy  
✅ **After Week 6**: Providers integrated into CORTEX  
✅ **After Week 7**: End-to-end testing complete  
✅ **After Week 8**: Live in production with monitoring  

---

## Cost Summary

```
One-time Setup: $50-60
├── 14B Fine-tuning: $20
├── 32B Fine-tuning: $21
├── Evaluation & Testing: $5-10
└── First month inference: $2-5

Monthly Recurring: $2-5
├── Security inference (50 requests/day): $0.54
└── Coding inference (20 requests/day): $1.68
```

---

## Next Actions

1. **Copy provider code** from sections 5.2 into `cortex/core/providers.py`
2. **Copy config** from section 5.3 into `config/cortex.yaml`
3. **Generate datasets** using scripts in section 1.3
4. **Launch fine-tuning** using scripts in section 3
5. **Build your router** based on your needs (keyword matching, ML classifier, etc.)

---

**Document Version**: 2.1  
**Status**: Framework Ready - Awaiting Your Router Logic Implementation  
**Last Updated**: 2026-01-15
