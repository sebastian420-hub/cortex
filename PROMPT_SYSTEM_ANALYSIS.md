# Prompt System Analysis - Cortex AI

## Overview

The Cortex prompt system is **highly adaptable and well-architected** for different LLM models. It uses a multi-layered approach to adapt prompts based on model capabilities, which is an excellent design pattern.

## Architecture Components

### 1. **Model Capability Profiling** (`cortex/core/model_capabilities.py`)

**What it does:**
- Defines capability profiles for 30+ LLM models (GPT, Claude, Llama, Mistral, DeepSeek, etc.)
- Captures model-specific attributes:
  - Context window size
  - Tool following capability (excellent/good/moderate/limited/none)
  - Reasoning capability
  - Prompt style preference (detailed/concise/explicit)
  - JSON mode support
  - Maximum tools per prompt
  - Vision support
  - Streaming support
  - Temperature recommendations

**Key Features:**
- `CapabilityLevel` enum (EXCELLENT → NONE)
- `PromptStyle` enum (DETAILED, CONCISE, EXPLICIT)
- `ModelProfile` dataclass with all model attributes
- Automatic model matching with prefix/substring/pattern matching
- Default profile for unknown models

### 2. **Prompt Builder** (`cortex/core/prompts/builder.py`)

**What it does:**
- Dynamically builds prompts based on model profile
- Adapts prompt content and structure for different capability levels

**Key Components:**

#### ToolFormatter
Formats tool documentation differently for each model type:
- **DETAILED**: Full documentation with parameters, examples (for Claude, GPT-4)
- **CONCISE**: Short format with essentials (for medium models)
- **EXPLICIT**: Step-by-step instructions (for smaller models)

#### PromptBuilder
Builds complete system prompts with sections:
1. Core identity (adapted to model style)
2. Tool documentation (formatted by ToolFormatter)
3. Planning guidance (if enabled)
4. Memory guidance (if enabled)
5. State/project context
6. Model-specific adaptations

### 3. **Model Adapters** (`cortex/core/prompts/adapters.py`)

**What it does:**
- Provides model-family-specific prompt adaptations
- Adds extra instructions tailored to model strengths/weaknesses

**Available Adapters:**
- `ClaudeAdapter`: Leverages Claude's large context and reasoning
- `GPTAdapter`: Concise, direct responses for OpenAI models
- `DeepSeekAdapter`: Uses thinking tags and code capabilities
- `MistralAdapter`: Tool format hints for Mistral/Mixtral
- `CodeSpecializedAdapter`: For code-focused models
- `OllamaAdapter`: Catch-all for local models with explicit guidance

### 4. **Prompt Adapter** (`cortex/core/prompt_adapter.py`)

**What it does:**
- High-level API for prompt adaptation
- Generates adaptation notes for system prompts
- Manages tool prioritization and simplification
- Provides context budget allocation

**Key Functions:**
- `get_model_adaptation_notes()`: Adds capability-specific guidance
- `should_simplify_tools()`: Determines if tool count should be reduced
- `get_tool_priority_list()`: Ranks tools by importance
- `get_context_budget()`: Allocates context space (system/tools/conversation)
- `adapt_system_prompt()`: Applies adaptations to base prompts

## How It Works - Example Flow

```
User Query → Model Selected → Build Prompt → Adapt to Model
    ↓            ↓              ↓              ↓
"What to      "claude-3-5-   Generate      Add Claude-specific
fix?"          sonnet"        base prompt   guidance and
                                   ↓         large context tips
                              Format tools
                              (DETAILED style)
```

## Adaptation Examples

### For **Claude-3-5-Sonnet** (High Capability):
- **Tool format**: Detailed documentation with examples
- **Prompt style**: DETAILED with comprehensive explanations
- **Adaptations**: Minimal (just response guidelines)
- **Context budget**: 15% system, 60% conversation
- **Tool limit**: 64 tools (can handle many)

### For **Llama 3.2** (Medium Capability):
- **Tool format**: Concise format with key info only
- **Prompt style**: CONCISE with shorter sections
- **Adaptations**: Moderate (tool usage reminders)
- **Context budget**: 15% system, 55% conversation
- **Tool limit**: 20 tools (needs prioritization)

### For **Mistral 7B** (Smaller Capability):
- **Tool format**: EXPLICIT with step-by-step instructions
- **Prompt style**: EXPLICIT with very clear guidance
- **Adaptations**: Extensive (explicit tool formatting, problem-solving approach)
- **Context budget**: 20% system, 50% conversation
- **Tool limit**: 10 tools (must be simplified)

## Integration Points

The prompt system integrates with:

1. **Agent System** (`cortex/agent.py`): Uses `PromptBuilder` to construct system prompts
2. **Delegation System** (`cortex/agent_delegation.py`): Adapts prompts for model handoffs
3. **CLI** (`cortex/cli.py`): Displays profile information
4. **Tests** (`tests/unit/core/test_prompt_system.py`): Comprehensive test coverage

## Strengths

✅ **Comprehensive Coverage**: 30+ models with detailed profiles

✅ **Layered Adaptation**: Multiple adaptation layers (capability → builder → adapter)

✅ **Flexible Styles**: Three prompt verbosity levels

✅ **Tool Prioritization**: Automatic tool selection for smaller models

✅ **Context Budgeting**: Smart context allocation per model

✅ **Extensible**: Easy to add new models or adapters

✅ **Well-Tested**: 17 unit tests covering all components

## Potential Improvements

### 1. **Dynamic Capability Learning**
Currently capabilities are hardcoded. Could be enhanced:
```python
# Could track model performance over time
# and adjust capabilities dynamically
class LearnedProfile:
    actual_tool_success_rate: float  # Track success/failure
    effective_context_window: int     # Adjust based on usage
    suggested_temperature: float      # Learn optimal settings
```

### 2. **Model-Specific Token Budgets**
```python
# Different models have different token efficiencies
if model_family == "claude":
    tokens_per_tool_call = 150
elif model_family == "gpt-4":
    tokens_per_tool_call = 120
elif model_family == "llama":
    tokens_per_tool_call = 200  # Less efficient
```

### 3. **Multi-Modal Support**
The system has `supports_vision` flag but could expand:
- Image-specific instructions for vision models
- Audio/video processing guidance
- Multi-modal tool recommendations

### 4. **Temperature and Sampling Adaptation**
```python
# Currently only recommended_temperature in profile
# Could add:
- Top-p sampling recommendations
- Frequency/presence penalties
- Stop sequences for different models
```

### 5. **Streaming Adaptation**
```python
# Models handle streaming differently
if model.supports_streaming:
    if model.capability == CapabilityLevel.LIMITED:
        # Add streaming hints for limited models
        prompt += "\n\n(Stream responses when possible)"
```

### 6. **Cost/Performance Balancing**
```python
# Add cost-aware adaptations
class CostProfile:
    cost_per_million_tokens: float
    speed_per_token_ms: float
    recommended_use_cases: List[str]
```

### 7. **Prompt Versioning**
```python
# Track prompt evolution
class PromptVersion:
    version: str
    prompt_template: str
    model_assumptions: Dict[str, Any]
    performance_metrics: Dict[str, float]
```

### 8. **A/B Testing Support**
```python
# Enable prompt variant testing
def get_prompt_variants(model_name: str) -> List[PromptVariant]:
    return [
        PromptVariant(name="control", prompt=base_prompt),
        PromptVariant(name="more_examples", prompt=prompt_with_examples),
        PromptVariant(name="less_formal", prompt=informal_prompt),
    ]
```

## Usage Examples

### Basic Usage
```python
from cortex.core.prompts import PromptBuilder

# Build prompt for specific model
builder = PromptBuilder("claude-3-5-sonnet")
prompt = builder.build_system_prompt(
    tools=tool_definitions,
    enable_planning=True,
    enable_memory=True,
)
```

### Model Adaptation
```python
from cortex.core.prompts import adapt_prompt_for_model

# Adapt a base prompt
base = "You are an AI assistant."
adapted = adapt_prompt_for_model(base, "mistral")
# Result includes explicit tool formatting hints
```

### Tool Prioritization
```python
from cortex.core.prompt_adapter import get_tool_priority_list

# Get tools prioritized for specific model
priority = get_tool_priority_list("gpt-3.5-turbo")
# Returns: [core tools only for smaller context]
```

## Conclusion

The Cortex prompt system is **exceptionally well-designed** for model adaptability. It uses:

- **Capability-based profiling** to understand model strengths
- **Multi-layered adaptation** (capability → builder → adapter)
- **Style-based formatting** (detailed/concise/explicit)
- **Tool prioritization** for context-limited models
- **Context budgeting** for optimal token allocation

**Recommendations for enhancement:**
1. Add token efficiency metrics per model
2. Implement dynamic capability learning
3. Add multi-modal instruction templates
4. Create prompt variant testing system
5. Add cost/performance tracking

The current system is production-ready and demonstrates best practices for LLM-agnostic prompt engineering.
