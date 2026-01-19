# CORTEX Dual Model - Implementation Checklist

## Pre-Start

- [ ] Read full project plan (Sections 1-6)
- [ ] Understand dual-model architecture (14B for security, 32B for coding)
- [ ] Create Together AI account and generate API key
- [ ] Have ~$50-60 budget for fine-tuning setup
- [ ] Allocate 8 weeks for full implementation
- [ ] Clone/setup CORTEX codebase

---

## Week 1-2: Data Collection ⏱️

### Generate Examples
- [ ] Create 600 security examples
  - [ ] 80 credential detection examples
  - [ ] 80 vulnerability scanning examples
  - [ ] 70 git security examples
  - [ ] 60 permission validation examples
  - [ ] 70 dangerous command prevention examples
  - [ ] 60 code pattern detection examples
  - [ ] 50 dependency analysis examples
  - [ ] 60 multi-tool chains examples
  - [ ] 50 error recovery examples
  - [ ] 40 context preservation examples

- [ ] Create 800 coding examples
  - [ ] 100 async conversion examples
  - [ ] 90 design pattern application examples
  - [ ] 80 multi-file refactoring examples
  - [ ] 80 test generation examples
  - [ ] 70 documentation generation examples
  - [ ] 80 code quality improvement examples
  - [ ] 70 architecture analysis examples
  - [ ] 60 performance optimization examples
  - [ ] 70 library migration examples
  - [ ] 70 complex reasoning chain examples

### Validation
- [ ] All examples have "prompt" and "completion" fields
- [ ] All completions are 100+ words (likely tokens)
- [ ] Format is valid JSONL (one JSON per line)
- [ ] Store in `data/security/raw/security_examples.jsonl`
- [ ] Store in `data/coding/raw/coding_examples.jsonl`
- [ ] Review 10 random examples for quality

**Deliverable**: `data/security/raw/` and `data/coding/raw/` with JSONL files

---

## Week 2-3: Data Preparation ⏱️

### Split Datasets
- [ ] Run `python scripts/prepare_datasets.py`
- [ ] Verify 3 JSONL files created for security:
  - [ ] `data/security/processed/security_train.jsonl`
  - [ ] `data/security/processed/security_val.jsonl`
  - [ ] `data/security/processed/security_test.jsonl`
- [ ] Verify 3 JSONL files created for coding:
  - [ ] `data/coding/processed/coding_train.jsonl`
  - [ ] `data/coding/processed/coding_val.jsonl`
  - [ ] `data/coding/processed/coding_test.jsonl`

### Quality Validation
- [ ] Run `python scripts/validate_datasets.py`
- [ ] Security dataset:
  - [ ] Total examples: 600+
  - [ ] Avg text length: 100+ tokens
  - [ ] Empty examples: 0
  - [ ] Quality checks: PASSED
- [ ] Coding dataset:
  - [ ] Total examples: 800+
  - [ ] Avg text length: 100+ tokens
  - [ ] Empty examples: 0
  - [ ] Quality checks: PASSED

**Deliverable**: Train/val/test splits validated and ready for fine-tuning

---

## Week 3-4: Fine-Tuning 🔥

### Environment Setup
- [ ] Set `TOGETHER_API_KEY` environment variable
- [ ] Verify API key works: `python scripts/test_api_key.py`

### Launch 14B Fine-Tuning
- [ ] Run `python scripts/finetune_14b.py`
- [ ] Check output for job ID
- [ ] Save job ID to `config/14b_config.json`
- [ ] Verify training file uploaded successfully

### Launch 32B Fine-Tuning
- [ ] Run `python scripts/finetune_32b.py`
- [ ] Check output for job ID
- [ ] Save job ID to `config/32b_config.json`
- [ ] Verify training file uploaded successfully

### Monitor Progress
- [ ] Run `python scripts/monitor_all.py`
- [ ] Watch both jobs in parallel
- [ ] Check status every 30 minutes
- [ ] Note any errors or warnings
- [ ] Expected training time: 3-6 hours each

### Post-Training
- [ ] 14B job status: COMPLETED
- [ ] 32B job status: COMPLETED
- [ ] Save 14B model ID to `config/14b_model.json`
- [ ] Save 32B model ID to `config/32b_model.json`
- [ ] Update environment variables:
  - [ ] `DEEPSEEK_CODER_14B_FT_MODEL_ID`
  - [ ] `DEEPSEEK_CODER_32B_FT_MODEL_ID`

**Deliverable**: Two fine-tuned models ready for inference

---

## Week 4-5: Evaluation 📊

### Evaluate Security Model (14B)
- [ ] Run `python scripts/evaluate_14b.py`
- [ ] Check results in `results/evaluation_14b.json`
- [ ] Verify metrics:
  - [ ] Total tests: 100+
  - [ ] Tool call accuracy: >95% ✓
  - [ ] False positives: <5% ✓
- [ ] Save evaluation report

### Evaluate Coding Model (32B)
- [ ] Run `python scripts/evaluate_32b.py`
- [ ] Check results in `results/evaluation_32b.json`
- [ ] Verify metrics:
  - [ ] Total tests: 100+
  - [ ] Code quality: >90% ✓
  - [ ] Reasoning success: >85% ✓
- [ ] Save evaluation report

### Side-by-Side Comparison
- [ ] Run `python scripts/compare_models.py`
- [ ] Review comparison output
- [ ] Note strengths/weaknesses of each model
- [ ] Verify both models are production-ready

**Deliverable**: Evaluation metrics showing both models ready for production

---

## Week 5-6: Integration 🔗

### Setup Providers
- [ ] Create `cortex/core/providers.py`
- [ ] Copy `DeepSeekCoder14BSecurityProvider` from Section 5.2
- [ ] Copy `DeepSeekCoder32BCodegenProvider` from Section 5.2
- [ ] Verify both providers:
  - [ ] Have `__init__` method
  - [ ] Have `chat()` method
  - [ ] Have `validate_api_key()` method
  - [ ] Return consistent response format

### Setup Configuration
- [ ] Create `config/cortex.yaml`
- [ ] Add provider definitions from Section 5.3
- [ ] Update model IDs in config:
  - [ ] `DEEPSEEK_CODER_14B_FT_MODEL_ID`
  - [ ] `DEEPSEEK_CODER_32B_FT_MODEL_ID`
- [ ] Verify YAML syntax is valid

### Verify API Keys
- [ ] Run provider initialization code
- [ ] Call `security_provider.validate_api_key()`
- [ ] Call `coding_provider.validate_api_key()`
- [ ] Both should return `True`

**Deliverable**: Providers integrated and API keys validated

---

## Week 6-7: Testing 🧪

### Provider Tests
- [ ] Create test file: `scripts/test_cortex_framework.py`
- [ ] Test security provider with security prompt
- [ ] Test coding provider with coding prompt
- [ ] Verify responses include model ID and specialization
- [ ] Check response latency:
  - [ ] Security: <2s ✓
  - [ ] Coding: <4s ✓

### Tool Context Tests
- [ ] Test security provider with security tools list
- [ ] Test coding provider with coding tools list
- [ ] Verify tools appear in system prompt
- [ ] Verify tool calls in response

### Error Handling
- [ ] Test invalid API key handling
- [ ] Test network timeout handling
- [ ] Test malformed message handling
- [ ] Verify graceful error responses

### Quality Spot Checks
- [ ] Security model on 5 security scenarios ✓
- [ ] Coding model on 5 coding scenarios ✓
- [ ] Real-world example: find hardcoded keys ✓
- [ ] Real-world example: convert to async ✓

**Deliverable**: All tests passing, providers working correctly

---

## Week 7-8: Production 🚀

### Deploy Providers
- [ ] Integrate providers into main CORTEX agent
- [ ] Initialize both providers at startup
- [ ] Configure environment variables
- [ ] Verify providers load without errors

### Implement Router Logic (Your Responsibility)
- [ ] Design task classification approach:
  - [ ] Keyword matching? OR
  - [ ] ML classifier? OR
  - [ ] User hints? OR
  - [ ] Hybrid approach?
- [ ] Implement `classify_task()` function
- [ ] Test classification accuracy on 20 examples
- [ ] Verify routing to correct provider

### Setup Monitoring
- [ ] Create `logs/` directory
- [ ] Initialize `DualModelMonitor`
- [ ] Start logging security inferences
- [ ] Start logging coding inferences
- [ ] Verify logs are being written to JSONL files

### Initial Monitoring (First Week)
- [ ] Run `python scripts/production_monitor.py`
- [ ] Monitor first 10 security requests
- [ ] Monitor first 10 coding requests
- [ ] Verify latency is within expectations
- [ ] Verify costs are as estimated
- [ ] Check for any errors or issues

### Generate Report
- [ ] Run monthly report generation
- [ ] Review cost metrics
- [ ] Review latency metrics
- [ ] Review accuracy metrics
- [ ] Use data to optimize routing

**Deliverable**: System live in production with monitoring active

---

## Ongoing: Monitoring & Optimization 📈

### Weekly Tasks
- [ ] Monitor inference logs
- [ ] Check for error patterns
- [ ] Review latency trends
- [ ] Monitor cost tracking

### Monthly Tasks
- [ ] Generate full production report
- [ ] Analyze router accuracy
- [ ] Identify misclassified tasks
- [ ] Evaluate model performance
- [ ] Plan optimizations

### Quarterly Tasks
- [ ] Review total cost vs budget
- [ ] Evaluate success metrics
- [ ] Plan next iteration (RLVR training, fine-tuning, etc.)
- [ ] Document learnings

---

## Critical Success Factors

✅ **Data Quality**: 600 + 800 high-quality examples  
✅ **Parallel Training**: Both models train simultaneously  
✅ **Provider Framework**: Correct implementation with both models  
✅ **Router Logic**: Accurate task classification  
✅ **Monitoring**: Active cost and performance tracking  

---

## Troubleshooting

### Fine-tuning takes too long
- Check job status on Together AI dashboard
- Verify data was uploaded correctly
- Check for API errors in job logs

### Model accuracy is low
- Review training data quality
- Increase training epochs
- Add more diverse examples

### Latency is higher than expected
- Check network connectivity
- Verify model IDs are correct
- Monitor Together AI API status

### Router accuracy is low
- Collect misclassified examples
- Refine classification logic
- Add more keywords or features

---

## When Complete

- [ ] Both models fine-tuned and evaluated
- [ ] Providers integrated and tested
- [ ] Router logic implemented
- [ ] System live in production
- [ ] Monitoring active
- [ ] Monthly reports generated
- [ ] Learnings documented

**Congratulations! CORTEX Dual Model System is operational.** 🎉

---

**Last Updated**: 2026-01-15  
**Status**: Ready to Start Implementation
