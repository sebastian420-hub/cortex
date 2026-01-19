# CORTEX Dual Model Fine-Tuning Project Plan

## Project Overview

**Objective**: Fine-tune TWO specialized DeepSeek Coder models for CORTEX:
1. **14B Model** (Terminal Security Agent) - Fast tool calling, security analysis
2. **32B Model** (Coding Agent) - Complex refactoring, multi-step code generation

**Timeline**: 6-8 weeks  
**Total Cost**: $70-120 (both fine-tuning + inference)  
**Cloud Service**: Together AI (managed fine-tuning + inference)  
**Training Method**: LoRA (Low-Rank Adaptation) SFT → RLVR (Reinforcement Learning)  

**Architecture**:
```
User Input
    ↓
CORTEX Orchestrator (Planning Layer)
    ├─→ Security Analysis Task → DeepSeek Coder 14B FT (fast, tool-precise)
    ├─→ Code Generation Task → DeepSeek Coder 32B FT (deep reasoning, refactoring)
    └─→ Complex Multi-step → Route to 32B with planning context
```

---

## Model Specialization Strategy

### DeepSeek Coder 14B (Terminal Security Agent)

**Optimized for**:
- ✅ Fast terminal command execution (0.8-1.2s latency)
- ✅ Precise tool calling (grep, ast_analyze, git operations)
- ✅ Security scanning with low hallucination (<3%)
- ✅ Real-time interactive security checks
- ✅ Quick vulnerability detection

**Training Data Focus** (~600 examples):
- Credential detection (AWS keys, DB passwords, tokens)
- Vulnerability scanning (SQL injection, XSS, RCE patterns)
- Git security (commit analysis, branch protection, leaks)
- Permission checks (file access, sensitive operations)
- Dangerous command validation (preventing harmful execution)
- Multi-tool chains (2-3 sequential tool calls)
- Error handling & recovery

**Inference Profile**:
- Latency: 0.8-1.2 seconds
- Token window: 2,000 max (typical: 500-1,000)
- Cost/request: $0.0004 (light usage)
- Memory: 16GB (fits on most GPUs)

### DeepSeek Coder 32B (Coding Agent)

**Optimized for**:
- ✅ Complex code refactoring (async/await, patterns, architecture)
- ✅ Multi-file understanding (imports, dependencies, cross-file context)
- ✅ Advanced reasoning (10+ step chains)
- ✅ Test generation & verification
- ✅ Documentation generation
- ✅ Design pattern application

**Training Data Focus** (~800 examples):
- Multi-file refactoring (converting sync → async, applying design patterns)
- Architecture understanding (reading complex systems, suggesting improvements)
- Test generation (unit tests, edge cases, mocking)
- Code quality improvements (linting, type hints, error handling)
- Documentation generation (docstrings, README updates, API docs)
- Complex code analysis (finding bottlenecks, security issues at scale)
- Planning-aware code generation (understands previous planning context)

**Inference Profile**:
- Latency: 2-3 seconds (acceptable for heavy lifting)
- Token window: 8,000+ (for large file context)
- Cost/request: $0.0012 (heavier token usage)
- Memory: 40GB (A40/H100 tier)

---

## Phase 1: Preparation & Dataset Collection (Weeks 1-2)

### 1.1 Environment Setup (Single Setup for Both Models)

```bash
# Create project directory
mkdir cortex-finetuning
cd cortex-finetuning

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install together-ai huggingface-hub datasets transformers torch
pip install jsonlines pandas tqdm

# Directory structure for dual models
mkdir -p data/{security,coding}/{raw,processed}
mkdir -p models/{14b,32b}/{checkpoints,results}
mkdir -p config scripts logs
```

### 1.2 Dataset Collection Strategy

#### Security Model Dataset (600 examples)

**Data Format** (JSONL):

```json
{"prompt": "Find hardcoded API keys in src/", "completion": "I'll systematically search for exposed API keys.\n\n1. grep -r \"AKIA[0-9A-Z]{16}\" . // AWS Access Key\n2. grep -r \"api_key|API_KEY|secret\" . // Generic patterns\n3. ast_analyze(file_path=\".\", query_type=\"secrets\") // Deep analysis\n4. read_file(path=\".env\") // Config files\n\nResult: Found 3 potential exposures in config.py and .env"}
```

**Categories** (600 total):

```python
# scripts/create_security_dataset.py
security_categories = {
    "credential_detection": 80,          # AWS keys, DB passwords, tokens
    "vulnerability_scanning": 80,        # SQL injection, XSS, RCE
    "git_security": 70,                  # Commit analysis, leaks, branches
    "permission_validation": 60,         # File access, sensitive ops
    "dangerous_command_prevention": 70,  # Block harmful commands
    "code_pattern_detection": 60,        # Security antipatterns
    "dependency_analysis": 50,           # Vulnerable packages
    "multi_tool_chains": 60,             # 2-3 tool sequences
    "error_recovery": 50,                # Graceful failure handling
    "context_preservation": 40,          # Maintaining state across calls
}
# Total: 620 examples
```

#### Coding Model Dataset (800 examples)

**Data Format** (JSONL):

```json
{"prompt": "Convert this synchronous database code to async/await pattern", "context": "File path: src/db.py, 200 lines", "completion": "I'll analyze the current code structure and apply async patterns.\n\n1. read_file(path=\"src/db.py\") // Get full context\n2. ast_analyze(file_path=\"src/db.py\", query_type=\"sync_calls\") // Find sync ops\n3. Plan: Replace db.query() with await db.query_async()\n\nRefactoring:\n- Change function signatures: async def\n- Replace all blocking calls with await\n- Update imports for async library\n\nResult: Converted 12 functions to async, added type hints"}
```

**Categories** (800 total):

```python
# scripts/create_coding_dataset.py
coding_categories = {
    "async_conversion": 100,             # Sync → Async refactoring
    "design_pattern_application": 90,    # Factory, Observer, etc.
    "multi_file_refactoring": 80,        # Cross-file changes
    "test_generation": 80,               # Unit tests, edge cases
    "documentation_generation": 70,      # Docstrings, README
    "code_quality_improvement": 80,      # Type hints, error handling
    "architecture_analysis": 70,         # System-level understanding
    "performance_optimization": 60,      # Bottleneck detection
    "library_migration": 70,             # Upgrade dependencies
    "complex_reasoning_chains": 70,      # 5+ step logic
}
# Total: 770 examples
```

### 1.3 Data Collection Scripts

```python
# scripts/create_datasets.py
import json
from pathlib import Path

def create_security_examples():
    """Generate security-focused training examples"""
    examples = []
    
    # Credential Detection Examples
    cred_examples = [
        {
            "prompt": "Find all hardcoded AWS credentials",
            "completion": "I need to search systematically for AWS key patterns.\n\n1. grep -r \"AKIA[0-9A-Z]{16}\" . // AWS Access Keys\n2. grep -r \"ASIA[0-9A-Z]{16}\" . // Temporary keys\n3. grep -r \"aws_secret|AWS_SECRET\" . // Secret patterns\n4. ast_analyze(file_path=\".\", query_type=\"aws_keys\") // Code analysis\n5. git_log --oneline // Check commits for accidental uploads\n\nFound 2 potential exposures: config.py line 45, .env.example"
        },
        # ... 79 more examples
    ]
    
    examples.extend(cred_examples)
    
    # Vulnerability Scanning Examples
    vuln_examples = [
        {
            "prompt": "Scan for SQL injection vulnerabilities in user input handling",
            "completion": "I'll analyze code that processes user input.\n\n1. grep -r \"execute\\|query\" src/ // Find DB calls\n2. grep -r \"user\\|input\\|request\\.args\" src/ // User input points\n3. ast_analyze(file_path=\".\", query_type=\"sql_patterns\") // Pattern matching\n4. read_file(path=\"src/db.py\") // Review implementation\n\nIdentified: 3 potential SQL injection points in forms.py, recommend parameterized queries"
        },
        # ... 79 more examples
    ]
    
    examples.extend(vuln_examples)
    
    # Save examples
    with open("data/security/raw/security_examples.jsonl", "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    
    return len(examples)

def create_coding_examples():
    """Generate coding-focused training examples"""
    examples = []
    
    # Async Conversion Examples
    async_examples = [
        {
            "prompt": "Convert synchronous database queries to async/await in user service",
            "context": "The service makes 5 blocking DB calls that need to be parallelized",
            "completion": "I'll refactor the UserService to use async patterns.\n\n1. read_file(path=\"src/services/user_service.py\") // Current implementation\n2. ast_analyze(file_path=\"src/services/user_service.py\", query_type=\"blocking_calls\") // Find issues\n3. Plan refactoring:\n   - Add 'async' keyword to function signatures\n   - Replace db.query() with await db.query_async()\n   - Update import statements\n   - Add asyncio.gather() for parallel queries\n\n4. Apply changes:\n   - Modified 5 methods to be async\n   - Added type hints for await returns\n   - Created async context manager for DB connections\n\n5. Test implications: Update unit tests with async/await syntax"
        },
        # ... 99 more examples
    ]
    
    examples.extend(async_examples)
    
    # Complex Reasoning Examples
    reasoning_examples = [
        {
            "prompt": "Refactor this codebase to follow SOLID principles, specifically Dependency Injection",
            "context": "Large monolithic service with tight coupling between components",
            "completion": "I'll systematically refactor to introduce dependency injection.\n\n1. read_file(path=\"src/app.py\") // Main entry point\n2. ast_analyze(file_path=\"src/\", query_type=\"class_dependencies\") // Map dependencies\n3. Planning phase:\n   - Identify tightly coupled components (3 layers: data, service, api)\n   - Design DI container structure\n   - Plan migration strategy (least dependent → most dependent)\n\n4. Implementation:\n   - Create DI container class\n   - Refactor data layer to accept dependencies\n   - Update service layer constructors\n   - Inject dependencies in API layer\n\n5. Verification:\n   - write_file(path=\"tests/test_di_container.py\") // Add DI tests\n   - Execute tests to verify decoupling\n   - Document new architecture"
        },
        # ... 69 more examples
    ]
    
    examples.extend(reasoning_examples)
    
    # Save examples
    with open("data/coding/raw/coding_examples.jsonl", "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    
    return len(examples)

# Run both
print(f"✓ Created {create_security_examples()} security examples")
print(f"✓ Created {create_coding_examples()} coding examples")
```

---

## Phase 2: Data Preparation for Together AI (Weeks 2-3)

### 2.1 Split & Validate Datasets

```python
# scripts/prepare_datasets.py
import json
from pathlib import Path
from sklearn.model_selection import train_test_split

def prepare_for_model(model_type: str, split_ratio=0.85):
    """Prepare dataset for specific model (security or coding)"""
    
    # Load raw examples
    raw_file = f"data/{model_type}/raw/{model_type}_examples.jsonl"
    examples = []
    
    with open(raw_file) as f:
        for line in f:
            examples.append(json.loads(line))
    
    print(f"Loaded {len(examples)} {model_type} examples")
    
    # Train/test split
    train_examples, test_examples = train_test_split(
        examples, 
        test_size=1-split_ratio,
        random_state=42
    )
    
    # Further split train into train/validation
    train_examples, val_examples = train_test_split(
        train_examples,
        test_size=0.15,
        random_state=42
    )
    
    # Save splits
    splits = {
        "train": (train_examples, f"data/{model_type}/processed/{model_type}_train.jsonl"),
        "val": (val_examples, f"data/{model_type}/processed/{model_type}_val.jsonl"),
        "test": (test_examples, f"data/{model_type}/processed/{model_type}_test.jsonl"),
    }
    
    for split_name, (data, path) in splits.items():
        with open(path, "w") as f:
            for ex in data:
                formatted = {
                    "text": f"{ex['prompt']}\n\n{ex['completion']}"
                }
                f.write(json.dumps(formatted) + "\n")
        
        print(f"  ✓ {split_name}: {len(data)} examples → {path}")
    
    return splits

# Prepare both datasets
print("=" * 60)
print("SECURITY MODEL DATASET")
print("=" * 60)
prepare_for_model("security", split_ratio=0.85)

print("\n" + "=" * 60)
print("CODING MODEL DATASET")
print("=" * 60)
prepare_for_model("coding", split_ratio=0.85)
```

### 2.2 Data Quality Validation

```python
# scripts/validate_datasets.py
import json
from collections import defaultdict

def validate_dataset(model_type: str):
    """Validate dataset quality and statistics"""
    
    train_file = f"data/{model_type}/processed/{model_type}_train.jsonl"
    
    stats = {
        "total_examples": 0,
        "avg_text_length": 0,
        "min_length": float('inf'),
        "max_length": 0,
        "empty_count": 0,
        "category_distribution": defaultdict(int),
    }
    
    text_lengths = []
    
    with open(train_file) as f:
        for i, line in enumerate(f):
            ex = json.loads(line)
            text = ex.get("text", "")
            length = len(text.split())
            
            text_lengths.append(length)
            stats["total_examples"] += 1
            stats["min_length"] = min(stats["min_length"], length)
            stats["max_length"] = max(stats["max_length"], length)
            
            if length == 0:
                stats["empty_count"] += 1
    
    stats["avg_text_length"] = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    
    print(f"\n{model_type.upper()} Dataset Validation")
    print("=" * 60)
    print(f"Total examples: {stats['total_examples']}")
    print(f"Average length: {stats['avg_text_length']:.0f} tokens")
    print(f"Min length: {stats['min_length']} tokens")
    print(f"Max length: {stats['max_length']} tokens")
    print(f"Empty examples: {stats['empty_count']}")
    
    # Quality checks
    quality_pass = True
    
    if stats["total_examples"] < 500:
        print(f"\n⚠️  WARNING: {stats['total_examples']} examples (recommend 500+)")
        quality_pass = False
    
    if stats["avg_text_length"] < 100:
        print(f"\n⚠️  WARNING: Average length {stats['avg_text_length']:.0f} (recommend 100+)")
        quality_pass = False
    
    if stats["empty_count"] > 0:
        print(f"\n⚠️  WARNING: {stats['empty_count']} empty examples")
        quality_pass = False
    
    if quality_pass:
        print(f"\n✓ Dataset quality PASSED")
    
    return stats

# Validate both
validate_dataset("security")
validate_dataset("coding")
```

---

## Phase 3: Cloud Fine-Tuning on Together AI (Weeks 3-5)

### 3.1 Security Model (14B) - Fine-Tuning

```python
# scripts/finetune_14b.py
import os
from together import Together
import json
import time

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

print("=" * 70)
print("FINE-TUNING: DeepSeek Coder 14B (Security Agent)")
print("=" * 70)

# Step 1: Upload training data
print("\n[1/4] Uploading training dataset...")
with open("data/security/processed/security_train.jsonl", "rb") as f:
    train_response = client.files.upload(
        file=f,
        purpose="fine-tune"
    )
train_file_id = train_response.id
print(f"✓ Training file: {train_file_id}")

# Step 2: Upload validation data
print("\n[2/4] Uploading validation dataset...")
with open("data/security/processed/security_val.jsonl", "rb") as f:
    val_response = client.files.upload(
        file=f,
        purpose="fine-tune"
    )
val_file_id = val_response.id
print(f"✓ Validation file: {val_file_id}")

# Step 3: Launch fine-tuning job
print("\n[3/4] Launching fine-tuning job...")

job_14b = client.fine_tuning.create(
    model="deepseek-ai/deepseek-coder-14b-base",
    training_file=train_file_id,
    validation_file=val_file_id,
    
    # LoRA Configuration
    lora=True,
    lora_rank=32,              # Slightly higher rank for 14B
    lora_alpha=64,
    lora_dropout=0.05,
    
    # Training Parameters
    learning_rate=1.5e-4,      # Slightly lower for larger model
    num_train_epochs=3,
    batch_size=8,              # Can use larger batch for 14B
    
    # Optimization
    warmup_ratio=0.1,
    weight_decay=0.01,
    
    # Output
    output_name="cortex-security-agent-14b-v1",
    max_steps=1000,
)

job_id_14b = job_14b.id
print(f"✓ Job ID: {job_id_14b}")

# Save config
with open("config/14b_config.json", "w") as f:
    json.dump({
        "model": "deepseek-coder-14b",
        "purpose": "security_terminal_agent",
        "job_id": job_id_14b,
        "training_file_id": train_file_id,
        "status": "launched",
        "timestamp": str(time.time())
    }, f, indent=2)

print(f"\n[4/4] Monitoring progress...")
print("Run: python scripts/monitor_14b.py")
```

### 3.2 Coding Model (32B) - Fine-Tuning

```python
# scripts/finetune_32b.py
import os
from together import Together
import json
import time

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

print("=" * 70)
print("FINE-TUNING: DeepSeek Coder 32B (Code Generation Agent)")
print("=" * 70)

# Step 1: Upload training data
print("\n[1/4] Uploading training dataset...")
with open("data/coding/processed/coding_train.jsonl", "rb") as f:
    train_response = client.files.upload(
        file=f,
        purpose="fine-tune"
    )
train_file_id = train_response.id
print(f"✓ Training file: {train_file_id}")

# Step 2: Upload validation data
print("\n[2/4] Uploading validation dataset...")
with open("data/coding/processed/coding_val.jsonl", "rb") as f:
    val_response = client.files.upload(
        file=f,
        purpose="fine-tune"
    )
val_file_id = val_response.id
print(f"✓ Validation file: {val_file_id}")

# Step 3: Launch fine-tuning job
print("\n[3/4] Launching fine-tuning job...")

job_32b = client.fine_tuning.create(
    model="deepseek-ai/deepseek-coder-32b-base",
    training_file=train_file_id,
    validation_file=val_file_id,
    
    # LoRA Configuration (larger model = higher rank)
    lora=True,
    lora_rank=64,              # Higher rank for 32B complexity
    lora_alpha=128,
    lora_dropout=0.05,
    
    # Training Parameters
    learning_rate=1e-4,        # Lower LR for larger, more stable model
    num_train_epochs=3,
    batch_size=4,              # Smaller batch due to model size
    
    # Optimization
    warmup_ratio=0.1,
    weight_decay=0.01,
    
    # Output
    output_name="cortex-coding-agent-32b-v1",
    max_steps=1000,
)

job_id_32b = job_32b.id
print(f"✓ Job ID: {job_id_32b}")

# Save config
with open("config/32b_config.json", "w") as f:
    json.dump({
        "model": "deepseek-coder-32b",
        "purpose": "code_generation_refactoring",
        "job_id": job_id_32b,
        "training_file_id": train_file_id,
        "status": "launched",
        "timestamp": str(time.time())
    }, f, indent=2)

print(f"\n[4/4] Monitoring progress...")
print("Run: python scripts/monitor_32b.py")
```

### 3.3 Monitor Both Models (Parallel)

```python
# scripts/monitor_all.py
import os
from together import Together
import json
import time
from datetime import datetime

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

# Load job IDs
with open("config/14b_config.json") as f:
    config_14b = json.load(f)
job_id_14b = config_14b["job_id"]

with open("config/32b_config.json") as f:
    config_32b = json.load(f)
job_id_32b = config_32b["job_id"]

print("Monitoring both models...")
print(f"  14B Security Agent: {job_id_14b}")
print(f"  32B Coding Agent: {job_id_32b}\n")

jobs_completed = {"14b": False, "32b": False}
last_status = {"14b": None, "32b": None}

while not all(jobs_completed.values()):
    # Check 14B
    if not jobs_completed["14b"]:
        job_14b = client.fine_tuning.retrieve(job_id_14b)
        
        if job_14b.status != last_status["14b"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 14B Security Agent: {job_14b.status}")
            if hasattr(job_14b, 'progress'):
                print(f"         Progress: {job_14b.progress}%")
            last_status["14b"] = job_14b.status
        
        if job_14b.status == "completed":
            print(f"  ✓ Model ID: {job_14b.model_id}")
            jobs_completed["14b"] = True
            with open("config/14b_model.json", "w") as f:
                json.dump({"model_id": job_14b.model_id}, f)
        elif job_14b.status == "failed":
            print(f"  ✗ Error: {job_14b.error}")
            jobs_completed["14b"] = True
    
    # Check 32B
    if not jobs_completed["32b"]:
        job_32b = client.fine_tuning.retrieve(job_id_32b)
        
        if job_32b.status != last_status["32b"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 32B Coding Agent: {job_32b.status}")
            if hasattr(job_32b, 'progress'):
                print(f"         Progress: {job_32b.progress}%")
            last_status["32b"] = job_32b.status
        
        if job_32b.status == "completed":
            print(f"  ✓ Model ID: {job_32b.model_id}")
            jobs_completed["32b"] = True
            with open("config/32b_model.json", "w") as f:
                json.dump({"model_id": job_32b.model_id}, f)
        elif job_32b.status == "failed":
            print(f"  ✗ Error: {job_32b.error}")
            jobs_completed["32b"] = True
    
    if not all(jobs_completed.values()):
        time.sleep(60)  # Check every minute

print("\n✓ Both models completed!")
```

### 3.4 Cost Estimation

```
SECURITY MODEL (14B):
- Dataset: 520 examples × 200 tokens = 104K tokens/epoch
- 3 epochs: 312K tokens
- Cost: 312K × $0.60/M = $0.19 + $20 minimum = ~$20

CODING MODEL (32B):
- Dataset: 680 examples × 250 tokens = 170K tokens/epoch
- 3 epochs: 510K tokens
- Cost: 510K × $1.20/M = $0.61 + $20 minimum = ~$21

TOTAL TRAINING: ~$41
```

---

## Phase 4: Testing & Evaluation (Weeks 5-6)

### 4.1 Evaluate Security Model (14B)

```python
# scripts/evaluate_14b.py
import os
from together import Together
import json
from tqdm import tqdm

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

with open("config/14b_model.json") as f:
    model_config = json.load(f)
model_id_14b = model_config["model_id"]

# Load test set
with open("data/security/processed/security_test.jsonl") as f:
    test_examples = [json.loads(line) for line in f]

print(f"Evaluating 14B Security Model on {len(test_examples)} examples\n")

results = {
    "model": "deepseek-coder-14b",
    "purpose": "security_terminal_agent",
    "total_tests": len(test_examples),
    "passed": 0,
    "failed": 0,
    "examples": []
}

for i, example in enumerate(tqdm(test_examples)):
    # Extract original prompt/completion
    text = example["text"]
    prompt, completion = text.split("\n\n", 1)
    
    # Generate with fine-tuned model
    response = client.chat.completions.create(
        model=model_id_14b,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.2,
    )
    
    generated = response.choices[0].message.content
    
    # Simple evaluation: check for tool calls
    import re
    expected_tools = set(re.findall(r'(\w+)\(', completion))
    generated_tools = set(re.findall(r'(\w+)\(', generated))
    
    match = len(expected_tools) == len(generated_tools)
    
    results["examples"].append({
        "prompt": prompt[:80] + "...",
        "expected_tools": list(expected_tools),
        "generated_tools": list(generated_tools),
        "match": match
    })
    
    if match:
        results["passed"] += 1
    else:
        results["failed"] += 1

# Save results
with open("results/evaluation_14b.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✓ 14B Security Model Evaluation")
print(f"  Passed: {results['passed']}/{results['total_tests']}")
print(f"  Failed: {results['failed']}/{results['total_tests']}")
print(f"  Accuracy: {results['passed']/results['total_tests']*100:.1f}%")
```

### 4.2 Evaluate Coding Model (32B)

```python
# scripts/evaluate_32b.py
import os
from together import Together
import json
from tqdm import tqdm

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

with open("config/32b_model.json") as f:
    model_config = json.load(f)
model_id_32b = model_config["model_id"]

# Load test set
with open("data/coding/processed/coding_test.jsonl") as f:
    test_examples = [json.loads(line) for line in f]

print(f"Evaluating 32B Coding Model on {len(test_examples)} examples\n")

results = {
    "model": "deepseek-coder-32b",
    "purpose": "code_generation_refactoring",
    "total_tests": len(test_examples),
    "passed": 0,
    "failed": 0,
    "examples": []
}

# More sophisticated evaluation for coding
for i, example in enumerate(tqdm(test_examples)):
    text = example["text"]
    prompt, expected_completion = text.split("\n\n", 1)
    
    response = client.chat.completions.create(
        model=model_id_32b,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.3,  # Slightly higher for creativity
    )
    
    generated = response.choices[0].message.content
    
    # For coding: check for planning + implementation pattern
    has_planning = "plan" in generated.lower() or "step" in generated.lower()
    has_code_changes = "def " in generated or "async " in generated or "class " in generated
    
    match = has_planning and has_code_changes
    
    results["examples"].append({
        "prompt": prompt[:100] + "...",
        "has_planning": has_planning,
        "has_code_changes": has_code_changes,
        "match": match
    })
    
    if match:
        results["passed"] += 1
    else:
        results["failed"] += 1

with open("results/evaluation_32b.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✓ 32B Coding Model Evaluation")
print(f"  Passed: {results['passed']}/{results['total_tests']}")
print(f"  Failed: {results['failed']}/{results['total_tests']}")
print(f"  Accuracy: {results['passed']/results['total_tests']*100:.1f}%")
```

### 4.3 Side-by-Side Comparison

```python
# scripts/compare_models.py
import os
from together import Together
import json

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
client = Together(api_key=TOGETHER_API_KEY)

with open("config/14b_model.json") as f:
    model_id_14b = json.load(f)["model_id"]

with open("config/32b_model.json") as f:
    model_id_32b = json.load(f)["model_id"]

# Test scenarios
test_cases = {
    "security": [
        "Find all hardcoded API keys in src/ directory",
        "Scan for SQL injection vulnerabilities in database layer",
    ],
    "coding": [
        "Convert this synchronous database code to async/await",
        "Refactor this module to follow SOLID principles",
    ]
}

print("=" * 70)
print("MODEL COMPARISON: 14B vs 32B")
print("=" * 70)

for category, prompts in test_cases.items():
    print(f"\n{category.upper()} TASKS")
    print("-" * 70)
    
    for prompt in prompts:
        print(f"\nPrompt: {prompt}\n")
        
        if category == "security":
            # 14B for security
            response = client.chat.completions.create(
                model=model_id_14b,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2,
            )
            print("14B Response (specialized for security):")
            print(response.choices[0].message.content[:400])
        
        else:
            # 32B for coding
            response = client.chat.completions.create(
                model=model_id_32b,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            print("32B Response (specialized for coding):")
            print(response.choices[0].message.content[:500])
        
        print()
```

---

## Phase 5: Integration with CORTEX (Weeks 6-7)

### 5.1 Dual Model Provider

```python
# cortex/core/providers.py (add to existing)

from together import Together
from typing import List, Dict, Optional, Any, Iterator

class DeepSeekCoder14BSecurityProvider(ModelProvider):
    """14B specialized for terminal security tasks"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        self.client = Together(api_key=self.api_key)
        self.model_id = os.environ.get(
            "DEEPSEEK_CODER_14B_FT_MODEL_ID",
            "deepseek-ai/deepseek-coder-14b-base"
        )
        self.specialization = "security_terminal_agent"
    
    def chat(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """14B optimized for fast, precise tool calling"""
        
        tool_context = ""
        if tools:
            tool_context = "SECURITY TOOLS (use for threat analysis):\n"
            for tool in tools:
                tool_context += f"- {tool['name']}({', '.join(tool['parameters'].keys())}): {tool['description']}\n"
            
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n\n{tool_context}"
            else:
                messages.insert(0, {"role": "system", "content": tool_context})
        
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            temperature=0.15,  # Very low for consistency
            max_tokens=1500,
            top_p=0.9,
        )
        
        return {
            "choices": [{"message": {"role": "assistant", "content": response.choices[0].message.content}}],
            "model": self.model_id,
            "specialization": self.specialization,
        }

class DeepSeekCoder32BCodegenProvider(ModelProvider):
    """32B specialized for complex code generation and refactoring"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        self.client = Together(api_key=self.api_key)
        self.model_id = os.environ.get(
            "DEEPSEEK_CODER_32B_FT_MODEL_ID",
            "deepseek-ai/deepseek-coder-32b-base"
        )
        self.specialization = "code_generation_refactoring"
    
    def chat(self, model: str, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """32B optimized for deep reasoning and code generation"""
        
        tool_context = ""
        if tools:
            tool_context = "CODE TOOLS (use for refactoring/generation):\n"
            for tool in tools:
                tool_context += f"- {tool['name']}({', '.join(tool['parameters'].keys())}): {tool['description']}\n"
            
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n\n{tool_context}"
            else:
                messages.insert(0, {"role": "system", "content": tool_context})
        
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            temperature=0.25,  # Higher for reasoning flexibility
            max_tokens=4000,
            top_p=0.95,
        )
        
        return {
            "choices": [{"message": {"role": "assistant", "content": response.choices[0].message.content}}],
            "model": self.model_id,
            "specialization": self.specialization,
        }
```

### 5.2 CORTEX Orchestrator (Route to Correct Model)

```python
# cortex/agent.py (add router)

class CortexOrchestrator:
    """Route tasks to appropriate specialized model"""
    
    def __init__(self):
        self.security_provider = DeepSeekCoder14BSecurityProvider()
        self.coding_provider = DeepSeekCoder32BCodegenProvider()
    
    def classify_task(self, prompt: str) -> str:
        """Determine if task is security or coding"""
        
        security_keywords = [
            "security", "vulnerability", "scan", "credential", 
            "api key", "password", "leak", "exposure", "threat",
            "dangerous", "command", "git", "danger"
        ]
        
        coding_keywords = [
            "refactor", "implement", "generate", "convert", "async",
            "design pattern", "architecture", "test", "optimize",
            "rewrite", "multi-file", "migration", "library"
        ]
        
        prompt_lower = prompt.lower()
        
        security_score = sum(1 for kw in security_keywords if kw in prompt_lower)
        coding_score = sum(1 for kw in coding_keywords if kw in prompt_lower)
        
        if security_score > coding_score:
            return "security"
        elif coding_score > security_score:
            return "coding"
        else:
            return "security"  # Default to security (faster, more conservative)
    
    def execute(self, prompt: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Route to appropriate model and execute"""
        
        task_type = self.classify_task(prompt)
        
        if task_type == "security":
            provider = self.security_provider
            model_name = "DeepSeek Coder 14B (Security)"
            tools = self.get_security_tools()
        else:
            provider = self.coding_provider
            model_name = "DeepSeek Coder 32B (Coding)"
            tools = self.get_coding_tools()
        
        messages = [
            {"role": "system", "content": f"You are a specialized {model_name}. {context or ''}"},
            {"role": "user", "content": prompt}
        ]
        
        response = provider.chat(
            model=model_name,
            messages=messages,
            tools=tools
        )
        
        return {
            "response": response,
            "task_type": task_type,
            "model": model_name,
        }
    
    def get_security_tools(self) -> List[Dict]:
        """Security-focused tool set"""
        return [
            {"name": "grep", "parameters": {"pattern", "path", "output_mode"}},
            {"name": "ast_analyze", "parameters": {"file_path", "query_type"}},
            {"name": "git_diff", "parameters": {"path"}},
            {"name": "read_file", "parameters": {"path", "offset", "limit"}},
            {"name": "execute_command", "parameters": {"command", "reason"}},
        ]
    
    def get_coding_tools(self) -> List[Dict]:
        """Coding-focused tool set"""
        return [
            {"name": "read_file", "parameters": {"path", "offset", "limit"}},
            {"name": "write_file", "parameters": {"path", "content"}},
            {"name": "edit", "parameters": {"file_path", "old_string", "new_string"}},
            {"name": "ast_analyze", "parameters": {"file_path", "query_type"}},
            {"name": "execute_command", "parameters": {"command", "reason"}},
            {"name": "run_tests", "parameters": {"pattern", "verbose"}},
        ]
```

### 5.3 Updated CORTEX Configuration

```yaml
# config/cortex.yaml

# Dual Model Configuration
models:
  security:
    name: "deepseek-coder-14b"
    provider: "deepseek-coder-14b-security"
    purpose: "terminal_security_analysis"
    latency_target: 1.2s
    
  coding:
    name: "deepseek-coder-32b"
    provider: "deepseek-coder-32b-coding"
    purpose: "code_generation_refactoring"
    latency_target: 3s

providers:
  deepseek-coder-14b-security:
    type: "deepseek-coder-14b"
    model_id: "${DEEPSEEK_CODER_14B_FT_MODEL_ID}"
    api_key: "${TOGETHER_API_KEY}"
    config:
      temperature: 0.15
      max_tokens: 1500
      top_p: 0.9
      
  deepseek-coder-32b-coding:
    type: "deepseek-coder-32b"
    model_id: "${DEEPSEEK_CODER_32B_FT_MODEL_ID}"
    api_key: "${TOGETHER_API_KEY}"
    config:
      temperature: 0.25
      max_tokens: 4000
      top_p: 0.95

# Orchestrator configuration
orchestrator:
  enabled: true
  auto_classify: true
  timeout_security: 5s
  timeout_coding: 30s
  fallback: "security"  # If classification unclear, use 14B
```

---

## Phase 6: Production Deployment (Weeks 7-8)

### 6.1 Inference Cost & Performance

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

### 6.2 Monitoring Both Models

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
| 5-6 | Integration | Orchestrator integrated | Dual provider in CORTEX |
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
3. **User Satisfaction**: <2s for security, <3s for coding tasks

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
python scripts/test_cortex_orchestrator.py

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

**Document Version**: 2.0 (Dual Model)  
**Last Updated**: 2026-01-15  
**Status**: Ready for implementation
