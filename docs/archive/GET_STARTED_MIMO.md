# Get Started with MiMo-V2-Flash

## 🚀 Quick Start (5 Minutes)

### Option 1: Automatic Implementation (Recommended)

```bash
# Run the implementation script
bash scripts/implement_mimo.sh

# Follow the prompts and watch it work!
```

**What it does:**
- ✅ Adds MiMo model profile
- ✅ Creates MiMo adapter with JSON schema enforcement
- ✅ Adds date/cutoff awareness
- ✅ Creates comprehensive tests
- ✅ Runs all tests
- ✅ Creates documentation and examples
- ✅ Updates README

### Option 2: Manual Quick Implementation

If you prefer to add files manually:

#### Step 1: Add Model Profile
Edit `cortex/core/model_capabilities.py` and add:

```python
# Add to MODEL_PROFILES dict
"mimo-v2-flash": ModelProfile(
    name="MiMo-V2-Flash",
    context_window=256000,
    tool_following=CapabilityLevel.EXCELLENT,
    reasoning=CapabilityLevel.EXCELLENT,
    prompt_style=PromptStyle.DETAILED,
    supports_json_mode=True,
    max_tools_per_prompt=64,
    recommended_temperature=0.3,
    exposes_thinking=True,
    thinking_field="reasoning_content",
)
```

#### Step 2: Add to ADAPTERS List
Edit `cortex/core/prompts/adapters.py` and add `MiMoAdapter` to `ADAPTERS` list.

#### Step 3: Run Tests
```bash
python -m pytest tests/unit/core/test_mimo_integration.py -v
```

## 📖 First Steps

### 1. Test Your Installation

```python
# test_mimo.py
from cortex.core.model_capabilities import get_model_profile
from cortex.core.prompts import PromptBuilder

# Get MiMo profile
profile = get_model_profile("mimo-v2-flash")
print(f"✅ Model: {profile.name}")
print(f"✅ Context: {profile.context_window} tokens")

# Build a prompt
builder = PromptBuilder("mimo-v2-flash")
prompt = builder.build_system_prompt(tools=[])
print(f"✅ Prompt built ({len(prompt)} chars)")
```

Run it:
```bash
python test_mimo.py
```

### 2. Try a Simple Task

```python
# example.py
from cortex.agent import Agent

agent = Agent(model="mimo-v2-flash")

# Ask a question
response = agent.query("Hello! What can you help me with?")
print(response)
```

### 3. Test JSON Schema Enforcement

```python
# test_json_schema.py
from cortex.core.prompts import PromptBuilder

builder = PromptBuilder("mimo-v2-flash")
prompt = builder.build_system_prompt(tools=[
    {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {"path": "string"}
    }
])

# Check if JSON schema is included
if "Output Format" in prompt and "JSON" in prompt:
    print("✅ JSON schema enforcement is working!")
else:
    print("❌ JSON schema not found in prompt")
```

## 🎯 Use Cases

### Code Analysis
```python
from cortex.agent import Agent

agent = Agent(model="mimo-v2-flash")
response = agent.query(
    "Analyze cortex/core/planning.py and identify any issues"
)
```

### Bug Fixing
```python
response = agent.query(
    "Fix the TypeError in cortex/core/planning.py line 62"
)
```

### File Editing
```python
response = agent.query(
    "Add logging to cortex/agent.py with timestamps"
)
```

### Planning
```python
response = agent.query(
    "Plan how to refactor cortex/core/prompt_builder.py"
)
```

## ⚙️ Configuration

### API Key Setup

**Option A: OpenRouter (Cloud)**
```bash
export OPENROUTER_API_KEY="your_key_here"
```

**Option B: SGLang (Local)**
```bash
# Install SGLang
pip install sglang[srt]

# Deploy MiMo locally
bash scripts/deploy_mimo.sh
```

### Temperature Settings

Choose the right temperature for your task:

```python
from cortex.core.model_capabilities import get_temperature_for_task

# For coding and planning (most common)
temp = get_temperature_for_task("mimo-v2-flash", "coding_planning")  # 0.3

# For debugging complex issues
temp = get_temperature_for_task("mimo-v2-flash", "debugging")  # 0.5

# For complex reasoning
temp = get_temperature_for_task("mimo-v2-flash", "reasoning")  # 0.7
```

### Reasoning Mode

For complex tasks, enable reasoning mode:

```python
from cortex.core.model_capabilities import get_reasoning_mode_config

config = get_reasoning_mode_config("mimo-v2-flash")
# Returns: {"enable_thinking": True, "max_tokens": 4096, "temperature": 0.7}

# Use this config when calling the API
```

## 🧪 Testing

### Run Unit Tests
```bash
# Test MiMo-specific functionality
python -m pytest tests/unit/core/test_mimo_integration.py -v

# Test all prompt system functionality
python -m pytest tests/unit/core/test_prompt_system.py -v
```

### Run Integration Tests
```bash
# Test with actual agent (requires MiMo deployment)
python -m pytest tests/integration/test_mimo_integration.py -v
```

### Manual Testing
```bash
# Deploy MiMo (if using local)
bash scripts/deploy_mimo.sh

# Run usage examples
python examples/mimo_usage.py
```

## 📚 Learn More

### Documentation
- **Model Guide**: `docs/models/mimo-v2-flash.md`
- **Implementation Plan**: `IMPLEMENTATION_PLAN_MIMO.md`
- **Summary**: `MIMO_IMPLEMENTATION_SUMMARY.md`

### Examples
- **Usage Examples**: `examples/mimo_usage.py`
- **Deployment Script**: `scripts/deploy_mimo.sh`
- **Implementation Script**: `scripts/implement_mimo.sh`

### Reference
- [MiMo-V2-Flash GitHub](https://github.com/XiaomiMiMo/MiMo-V2-Flash)
- [MiMo Complete Guide](https://dev.to/czmilo/xiaomi-mimo-v2-flash-complete-guide-to-the-309b-parameter-moe-model-2025-bg6)
- [MiMo Technical Report](https://arxiv.org/html/2601.02780v1)

## 🔧 Troubleshooting

### Issue: Model not found
**Solution**: Check that model profile is added to `MODEL_PROFILES` in `model_capabilities.py`

```python
# Test it
from cortex.core.model_capabilities import get_model_profile
profile = get_model_profile("mimo-v2-flash")
print(profile)
```

### Issue: Adapter not found
**Solution**: Verify `MiMoAdapter` is added to `ADAPTERS` list in `adapters.py`

```python
# Test it
from cortex.core.prompts import get_adapter
adapter = get_adapter("mimo-v2-flash")
print(adapter)
```

### Issue: JSON schema not in prompt
**Solution**: Check that `supports_json_mode=True` in model profile

```python
# Test it
from cortex.core.model_capabilities import get_model_profile
profile = get_model_profile("mimo-v2-flash")
print(f"JSON mode: {profile.supports_json_mode}")
```

### Issue: Tests failing
**Solution**: Run tests with verbose output to see details

```bash
python -m pytest tests/unit/core/test_mimo_integration.py -v --tb=short
```

## 🎯 Success Checklist

- [ ] Model profile loads correctly
- [ ] Adapter is registered
- [ ] JSON schema appears in prompts
- [ ] Date/cutoff awareness works
- [ ] Tests pass
- [ ] Example runs without errors
- [ ] Can query the model
- [ ] Tool calls work correctly
- [ ] Documentation is clear

## 🚀 Next Steps

### After Basic Setup
1. **Run the example**: `python examples/mimo_usage.py`
2. **Test with your own tasks**: Try fixing a bug or analyzing code
3. **Monitor metrics**: Track JSON validity, tool accuracy
4. **Optimize temperature**: Test different values for your use case
5. **Try reasoning mode**: Use it for complex problems

### Production Deployment
1. **Deploy MiMo**: Use `scripts/deploy_mimo.sh` or OpenRouter
2. **Configure API keys**: Set `OPENROUTER_API_KEY`
3. **Test end-to-end**: Run through typical workflows
4. **Monitor performance**: Check metrics and logs
5. **Gather feedback**: User acceptance testing

### Advanced Features
1. **A/B testing**: Try different prompt variants
2. **Dynamic learning**: Let the system learn from usage
3. **Context optimization**: Tune pruning for your workflows
4. **Cost optimization**: Track token usage and costs

## 💡 Tips

### Best Practices
1. **Always use JSON schema** - MiMo requires it
2. **Restate constraints** - Every 3-4 turns in multi-turn
3. **Use low temperature** - 0.3 for coding (most reliable)
4. **Enable reasoning mode** - For complex problems
5. **Keep reasoning short** - Under 150 words
6. **Reference line numbers** - Helps with code analysis

### Performance Tips
1. **Use context budget** - Don't waste tokens
2. **Prune old turns** - Keep last 3-5 turns
3. **Archive large outputs** - If >8K tokens
4. **Use delimiters** - `### HEADER` for sections
5. **Feed relevant last** - Most recent info last

### Cost Optimization
1. **Track tokens used** - Use metrics tracking
2. **Choose right temperature** - Lower = cheaper
3. **Prune context** - Reduce token usage
4. **Batch operations** - Combine similar tasks
5. **Use reasoning mode wisely** - More tokens = more cost

## 📞 Get Help

### Check Logs
```bash
# View debug logs
tail -f logs/cortex.log
```

### Check Metrics
```python
from cortex.core.metrics import MetricsTracker

tracker = MetricsTracker()
metrics = tracker.get_metrics_for_model("mimo-v2-flash")
print(metrics)
```

### Run Diagnostics
```bash
# Check model profile
python -c "from cortex.core.model_capabilities import get_model_profile; print(get_model_profile('mimo-v2-flash'))"

# Check adapter
python -c "from cortex.core.prompts import get_adapter; print(get_adapter('mimo-v2-flash'))"

# Run tests
python -m pytest tests/unit/core/test_mimo_integration.py -v
```

## 🎉 You're Ready!

Now you can:
- ✅ Use MiMo-V2-Flash with Cortex
- ✅ Leverage JSON schema enforcement
- ✅ Use temperature stratification
- ✅ Enable reasoning mode for complex tasks
- ✅ Track production metrics
- ✅ Deploy and optimize

**Happy coding with MiMo!** 🚀
