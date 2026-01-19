# Cortex Prompt System - Quick Reference

## Adding a New Model

### Step 1: Add Model Profile

Edit `cortex/core/model_capabilities.py`:

```python
MODEL_PROFILES = {
    # ... existing models ...
    
    "new-model-name": ModelProfile(
        name="New Model Display Name",
        context_window=32000,  # Token capacity
        tool_following=CapabilityLevel.GOOD,  # How well it follows tool calls
        reasoning=CapabilityLevel.EXCELLENT,  # Reasoning capability
        prompt_style=PromptStyle.CONCISE,  # DETAILED/CONCISE/EXPLICIT
        supports_json_mode=True,  # Native JSON output support
        max_tools_per_prompt=20,  # Max tools to include
        supports_streaming=True,  # Optional, default=True
        supports_vision=False,  # Optional, default=False
        notes="Special notes about this model",  # Optional
    ),
}
```

### Step 2: Add Adapter (Optional)

Edit `cortex/core/prompts/adapters.py`:

```python
class NewModelAdapter(BaseAdapter):
    name = "newmodel"
    
    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "new-model" in model_name.lower()
    
    @classmethod
    def get_tool_format_hint(cls) -> str:
        return "## Tool Usage\n\nUse tools carefully..."
    
    @classmethod
    def get_response_format_hint(cls) -> str:
        return "## Response Guidelines\n\nBe concise and direct..."
    
    @classmethod
    def get_special_instructions(cls) -> str:
        return "## Special Capabilities\n\nThis model excels at..."
```

Add to registry:
```python
ADAPTERS = [
    ClaudeAdapter,
    GPTAdapter,
    DeepSeekAdapter,
    MistralAdapter,
    CodeSpecializedAdapter,
    NewModelAdapter,  # Add here
    OllamaAdapter,
]
```

## Using the Prompt System

### Basic Prompt Building

```python
from cortex.core.prompts import PromptBuilder

# Create builder for specific model
builder = PromptBuilder("claude-3-5-sonnet")

# Build complete system prompt
prompt = builder.build_system_prompt(
    tools=tool_definitions,           # List of tool schemas
    enable_planning=True,             # Include planning guidance
    enable_memory=True,               # Include memory guidance
    state_context="Current: Fixing bug",  # Current state
    project_context="Python API project", # Project details
    custom_instructions="Be thorough", # Extra instructions
)

# Get profile summary for debugging
summary = builder.get_profile_summary()
print(f"Using {summary['profile']} with {summary['prompt_style']} style")
```

### Model Adaptation

```python
from cortex.core.prompts import adapt_prompt_for_model

base_prompt = "You are Cortex, an AI assistant."
adapted = adapt_prompt_for_model(base_prompt, "mistral")
# Adds model-specific hints and guidance
```

### Tool Prioritization

```python
from cortex.core.prompt_adapter import get_tool_priority_list, should_simplify_tools

# Get prioritized tools for a model
priority = get_tool_priority_list("gpt-3.5-turbo")
# Returns: [core tools, then extended tools...]

# Check if tools should be simplified
if should_simplify_tools("mistral", len(tools)):
    # Reduce tool count for this model
    tools = tools[:10]  # Keep only top 10
```

### Context Budgeting

```python
from cortex.core.prompt_adapter import get_context_budget

budget = get_context_budget("claude-3-5-sonnet")
# Returns: {
#     "system_prompt": 30000,
#     "tools": 20000,
#     "conversation": 120000,
#     "state_context": 20000,
#     "reserve": 10000,
# }
```

### Model Profile Info

```python
from cortex.core.model_capabilities import get_model_profile
from cortex.core.prompt_adapter import get_profile_info

# Get full profile
profile = get_model_profile("llama3.2")
print(f"Context: {profile.context_window}")
print(f"Style: {profile.prompt_style.value}")
print(f"Max tools: {profile.max_tools_per_prompt}")

# Get adapter info
info = get_profile_info("gpt-4o")
# Returns: {
#     "model": "gpt-4o",
#     "adapter": "gpt",
#     "profile": "GPT-4o",
#     "prompt_style": "detailed",
#     "tool_following": "excellent",
#     "reasoning": "excellent",
# }
```

## Prompt Styles

### DETAILED (for capable models like Claude, GPT-4)
- Full documentation with examples
- Comprehensive explanations
- Decision trees and flowcharts
- Best for: Complex tasks, detailed reasoning

### CONCISE (for medium models like Llama 3.2, GPT-3.5)
- Shorter format, key information only
- Minimal examples
- Direct instructions
- Best for: Balanced performance

### EXPLICIT (for smaller models like Mistral 7B, Phi-3)
- Very explicit step-by-step instructions
- Clear tool formatting examples
- Explicit reminders
- Best for: Simple tasks, limited reasoning

## Capability Levels

```python
from cortex.core.model_capabilities import CapabilityLevel

# Tool Following
EXCELLENT  # Always follows tool format perfectly
GOOD       # Usually follows, may need minor guidance
MODERATE   # Works but needs explicit guidance
LIMITED    # Basic support, needs significant help
NONE       # Not supported

# Reasoning
EXCELLENT  # Can handle complex multi-step reasoning
GOOD       # Good at most reasoning tasks
MODERATE   # Can handle simple reasoning
LIMITED    # Struggles with complex reasoning
NONE       # No reasoning capability
```

## Common Patterns

### Pattern 1: Tool Formatting Based on Model

```python
def format_tools_for_model(tools, model_name):
    profile = get_model_profile(model_name)
    
    # Prioritize if too many tools
    if len(tools) > profile.max_tools_per_prompt:
        from cortex.core.prompt_adapter import get_tool_priority_list
        priority = get_tool_priority_list(model_name)
        tools = [t for t in tools if t['name'] in priority]
    
    # Format based on style
    builder = PromptBuilder(model_name)
    return builder.tool_formatter.format_tools(tools)
```

### Pattern 2: Dynamic Prompt Adaptation

```python
def build_adapted_prompt(model_name, task_type):
    # Get base prompt for task
    if task_type == "coding":
        base = CODING_PROMPT
    elif task_type == "analysis":
        base = ANALYSIS_PROMPT
    else:
        base = DEFAULT_PROMPT
    
    # Adapt for model
    adapted = adapt_prompt_for_model(base, model_name)
    
    # Add model-specific notes
    from cortex.core.prompt_adapter import get_model_adaptation_notes
    notes = get_model_adaptation_notes(model_name)
    
    if notes:
        adapted += f"\n\n{notes}"
    
    return adapted
```

### Pattern 3: Context-Aware Tool Selection

```python
def select_tools_for_context(model_name, available_tools, context_size):
    profile = get_model_profile(model_name)
    budget = get_context_budget(model_name)
    
    # Calculate approximate token usage
    tool_tokens = sum(len(str(t)) // 4 for t in available_tools)
    
    # If tools exceed budget, prioritize
    if tool_tokens > budget['tools']:
        from cortex.core.prompt_adapter import get_tool_priority_list
        priority = get_tool_priority_list(model_name)
        
        # Select tools that fit in budget
        selected = []
        total_tokens = 0
        for tool in available_tools:
            tool_tokens = len(str(tool)) // 4
            if total_tokens + tool_tokens <= budget['tools']:
                selected.append(tool)
                total_tokens += tool_tokens
            else:
                break
        
        return selected
    
    return available_tools
```

## Debugging Tips

### Check Model Profile

```python
from cortex.core.model_capabilities import get_model_profile

profile = get_model_profile("your-model")
print(profile.to_dict())
```

### See What Adapter is Used

```python
from cortex.core.prompts import get_adapter

adapter = get_adapter("your-model")
print(f"Adapter: {adapter.name if adapter else 'None'}")
```

### Compare Prompts Across Models

```python
models = ["claude-3-5-sonnet", "llama3.2", "mistral"]
for model in models:
    builder = PromptBuilder(model)
    prompt = builder.build_system_prompt(tools=sample_tools)
    print(f"\n{model.upper()} ({len(prompt)} chars):")
    print(prompt[:200] + "...")
```

### Verify Adaptations

```python
from cortex.core.prompt_adapter import get_model_adaptation_notes

for model in ["claude-3-5-sonnet", "mistral"]:
    notes = get_model_adaptation_notes(model)
    print(f"\n{model}:")
    print(notes or "(no adaptations)")
```

## Testing

### Run Prompt System Tests

```bash
# All prompt system tests
python -m pytest tests/unit/core/test_prompt_system.py -v

# Model capabilities tests
python -m pytest tests/unit/core/test_model_capabilities.py -v

# All together
python -m pytest tests/unit/core/test_prompt_system.py tests/unit/core/test_model_capabilities.py -v
```

### Add New Test

```python
def test_new_model_adaptation():
    """Test that new model gets appropriate adaptations."""
    from cortex.core.prompts import PromptBuilder
    
    builder = PromptBuilder("new-model-name")
    prompt = builder.build_system_prompt(tools=[])
    
    assert "Cortex" in prompt
    assert builder.profile.prompt_style == PromptStyle.CONCISE
    assert builder.profile.max_tools_per_prompt == 20
```

## Common Issues

### Issue: Model not recognized
**Solution**: Check model name matches pattern in `get_model_profile()`
```python
# Test pattern matching
from cortex.core.model_capabilities import get_model_profile
profile = get_model_profile("your-model-name")
print(profile.name)  # Should show correct profile
```

### Issue: Wrong prompt style
**Solution**: Verify model profile has correct `prompt_style`
```python
from cortex.core.model_capabilities import get_model_profile
profile = get_model_profile("your-model")
print(profile.prompt_style)  # Should be DETAILED/CONCISE/EXPLICIT
```

### Issue: Too many tools included
**Solution**: Check `max_tools_per_prompt` and prioritize
```python
from cortex.core.prompt_adapter import should_simplify_tools, get_tool_priority_list

if should_simplify_tools(model_name, len(tools)):
    priority = get_tool_priority_list(model_name)
    tools = [t for t in tools if t['name'] in priority]
```

### Issue: Context overflow
**Solution**: Check context budget and token counts
```python
from cortex.core.prompt_adapter import get_context_budget
from cortex.core.context import count_message_tokens

budget = get_context_budget(model_name)
tokens = sum(count_message_tokens(msg) for msg in conversation)
if tokens > budget['conversation']:
    # Truncate conversation
    pass
```

## Quick Commands

```bash
# Check available models
python -c "from cortex.core.model_capabilities import list_all_profiles; print(list_all_profiles())"

# Test model profile lookup
python -c "from cortex.core.model_capabilities import get_model_profile; print(get_model_profile('claude-3-5-sonnet'))"

# Test prompt building
python -c "from cortex.core.prompts import PromptBuilder; b = PromptBuilder('llama3.2'); print(b.build_system_prompt([])[:200])"

# Run all prompt tests
python -m pytest tests/unit/core/test_prompt_system.py -v
```

## Summary

- **Add models** in `model_capabilities.py` with appropriate capabilities
- **Use builders** to create model-adapted prompts
- **Leverage adapters** for model-family-specific guidance
- **Prioritize tools** for smaller models
- **Check context budgets** for large conversations
- **Test thoroughly** when adding new models

The system is designed to be extensible and handles most common use cases automatically.
