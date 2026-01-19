# Prompt System Architecture - Visual Overview

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROMPT SYSTEM ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     User Request                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Model Selection & Profile                  │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Model Name: "claude-3-5-sonnet"                   │  │  │
│  │  │  Profile Lookup: get_model_profile()               │  │  │
│  │  │  ┌────────────────────────────────────────────┐    │  │  │
│  │  │  │ Context: 200k, Tools: EXCELLENT            │    │  │  │
│  │  │  │ Reasoning: EXCELLENT, Style: DETAILED      │    │  │  │
│  │  │  └────────────────────────────────────────────┘    │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROMPT BUILDER LAYER                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              PromptBuilder Instance                      │  │
│  │  • Model Profile: <ModelProfile object>                  │  │
│  │  • Tool Formatter: <ToolFormatter object>                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              build_system_prompt()                       │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  1. Core Identity (Model-specific style)          │  │  │
│  │  │  2. Tool Documentation (Formatted by style)       │  │  │
│  │  │  3. Planning Guidance (If enabled)                │  │  │
│  │  │  4. Memory Guidance (If enabled)                  │  │  │
│  │  │  5. State Context (Current task)                  │  │  │
│  │  │  6. Project Context (AGENT.md)                    │  │  │
│  │  │  7. Custom Instructions                           │  │  │
│  │  │  8. Model Adaptations (Capability-based)          │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ADAPTATION LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          ToolFormatter (Capability-based)                │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  DETAILED → Full docs with examples               │  │  │
│  │  │  CONCISE → Short format, key info                 │  │  │
│  │  │  EXPLICIT → Step-by-step instructions              │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         ModelAdapter (Family-specific)                   │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  ClaudeAdapter → Large context tips               │  │  │
│  │  │  GPTAdapter → Concise responses                   │  │  │
│  │  │  OllamaAdapter → Explicit formatting              │  │  │
│  │  │  CodeAdapter → Code-specific guidance             │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │    PromptAdapter (High-level API)                        │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  get_model_adaptation_notes()                      │  │  │
│  │  │  should_simplify_tools()                           │  │  │
│  │  │  get_tool_priority_list()                          │  │  │
│  │  │  get_context_budget()                              │  │  │
│  │  │  adapt_system_prompt()                             │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Final Adapted Prompt                        │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  # Cortex AI Assistant                             │  │  │
│  │  │  [Model-specific core instructions]                │  │  │
│  │  │  # Available Tools (Detailed format)               │  │  │
│  │  │  [Tool documentation with examples]                │  │  │
│  │  │  # Response Guidelines (Claude)                    │  │  │
│  │  │  [Model-specific adaptations]                      │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Example

### Scenario: User selects "Mistral 7B"

```
1. Model Selection
   └─> "mistral" → get_model_profile("mistral")
       └─> Returns:
           • context_window: 8192
           • tool_following: MODERATE
           • reasoning: MODERATE
           • prompt_style: EXPLICIT
           • max_tools: 10
           • supports_json_mode: False

2. PromptBuilder Initialization
   └─> PromptBuilder("mistral")
       └─> Creates:
           • profile: <ModelProfile object>
           • tool_formatter: ToolFormatter(profile)
           • model_name: "mistral"

3. Build Core Section
   └─> _build_core_section()
       └─> style == EXPLICIT
           └─> Returns:
               "# CORTEX AI ASSISTANT
                You are Cortex, an AI assistant...
                IMPORTANT RULES:
                1. Use tools provided...
                2. Be precise..."

4. Format Tools
   └─> tool_formatter.format_tools(tools)
       └─> style == EXPLICIT
           └─> Returns:
               "# TOOLS - READ CAREFULLY
                To use a tool, you MUST format...
                
                ## read_file
                WHAT IT DOES: Read contents of a file
                REQUIRED PARAMETERS: path
                PARAMETERS:
                  - path* (string): Path to the file
                EXAMPLE:
                read_file({\"path\": \"/path/to/file\"})"

5. Build Adaptations
   └─> _build_model_adaptation()
       └─> tool_following == MODERATE
           └─> Returns:
               "## Notes
                - Focus on using one tool at a time
                - Verify results before proceeding
                - Format tool arguments as JSON"

6. Final Assembly
   └─> join sections with "---" separator
       └─> Complete prompt with all adaptations
```

## Capability-Based Adaptation Matrix

| Model Family | Context | Tool Following | Reasoning | Style | Adaptations |
|-------------|---------|----------------|-----------|-------|-------------|
| **Claude-3.5** | 200k | EXCELLENT | EXCELLENT | DETAILED | Minimal, large context tips |
| **GPT-4** | 128k | EXCELLENT | EXCELLENT | DETAILED | Concise responses |
| **DeepSeek** | 64k | GOOD | EXCELLENT | DETAILED | Thinking tags, code focus |
| **Llama 3.2** | 8k | GOOD | GOOD | CONCISE | Moderate guidance |
| **Mistral 7B** | 8k | MODERATE | MODERATE | EXPLICIT | Full step-by-step |
| **Phi-3** | 4k | MODERATE | MODERATE | EXPLICIT | Maximum guidance |

## Tool Prioritization Flow

```
Input: All available tools (20+)
                    │
                    ▼
    ┌───────────────────────────────────┐
    │ Count > model.max_tools?          │
    └───────────────────────────────────┘
            │                   │
        Yes │                   │ No
            ▼                   ▼
    ┌─────────────┐      ┌─────────────┐
    │ Prioritize  │      │ Use all     │
    └─────────────┘      └─────────────┘
            │                   │
            └─────────┬─────────┘
                      ▼
    ┌──────────────────────────────┐
    │ Priority Order:              │
    │ 1. read_file, write_file     │
    │ 2. edit_file                 │
    │ 3. grep_search, glob_files   │
    │ 4. bash                      │
    │ 5. planning tools            │
    │ 6. web tools                 │
    │ 7. memory tools              │
    │ 8. AST tools                 │
    └──────────────────────────────┘
                      │
                      ▼
    ┌──────────────────────────────┐
    │ Select top N for model:      │
    │ • Claude: 64 tools           │
    │ • GPT-4: 128 tools           │
    │ • Llama 3.2: 20 tools        │
    │ • Mistral: 10 tools          │
    └──────────────────────────────┘
```

## Context Budget Allocation

```
Model: claude-3-5-sonnet (200k tokens)
┌─────────────────────────────────────────┐
│ Total Context: 200,000 tokens          │
├─────────────────────────────────────────┤
│ System Prompt:   30,000 (15%)          │
│ Tools:           20,000 (10%)          │
│ Conversation:   120,000 (60%)          │
│ State Context:   20,000 (10%)          │
│ Reserve:         10,000 (5%)           │
└─────────────────────────────────────────┘

Model: llama-3.2 (8k tokens)
┌─────────────────────────────────────────┐
│ Total Context: 8,192 tokens            │
├─────────────────────────────────────────┤
│ System Prompt:   1,638 (20%)           │
│ Tools:             819 (10%)           │
│ Conversation:    4,096 (50%)           │
│ State Context:     819 (10%)           │
│ Reserve:           820 (10%)           │
└─────────────────────────────────────────┘
```

## Test Coverage

```
tests/unit/core/test_prompt_system.py
├── TestToolFormatter (3 tests)
│   ├── test_format_tools_detailed
│   ├── test_format_tools_concise
│   └── test_format_tools_explicit
│
├── TestPromptBuilder (5 tests)
│   ├── test_builder_initialization
│   ├── test_build_system_prompt_basic
│   ├── test_build_system_prompt_with_planning
│   ├── test_build_system_prompt_with_memory
│   ├── test_build_system_prompt_with_state_context
│   └── test_get_profile_summary
│
└── TestPromptAdapter (9 tests)
    ├── test_get_model_adaptation_notes_capable_model
    ├── test_get_model_adaptation_notes_smaller_model
    ├── test_should_simplify_tools
    ├── test_get_tool_priority_list
    ├── test_get_context_budget
    ├── test_adapt_system_prompt
    ├── test_adapt_system_prompt_disabled
    └── test_get_profile_info

Total: 17 tests - All passing ✅
```

## Extension Points

### Adding a New Model

```python
# 1. Add to model_capabilities.py
MODEL_PROFILES["new-model"] = ModelProfile(
    name="New Model",
    context_window=32000,
    tool_following=CapabilityLevel.GOOD,
    reasoning=CapabilityLevel.GOOD,
    prompt_style=PromptStyle.CONCISE,
    supports_json_mode=True,
    max_tools_per_prompt=20,
)

# 2. Add adapter if needed (adapters.py)
class NewModelAdapter(BaseAdapter):
    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        return "new-model" in model_name.lower()
    
    @classmethod
    def get_response_format_hint(cls) -> str:
        return "## Response Guidelines (New Model)\n\n..."

# 3. Add to ADAPTERS list
ADAPTERS = [ClaudeAdapter, GPTAdapter, NewModelAdapter, ...]

# Done! System automatically adapts prompts
```

### Adding a New Adaptation Dimension

```python
# In model_capabilities.py
@dataclass
class ModelProfile:
    # Add new field
    supports_function_calling: bool = True
    recommended_temperature: float = 0.7
    notes: str = ""
    
# In prompt_adapter.py
def get_model_adaptation_notes(model_name: str) -> str:
    profile = get_model_profile(model_name)
    notes = []
    
    # Add new adaptation logic
    if not profile.supports_function_calling:
        notes.append("Format tool calls manually as JSON")
    
    if profile.recommended_temperature > 0.8:
        notes.append("Use higher temperature for creative tasks")
    
    return "\n".join(notes)
```

## Key Design Patterns Used

1. **Strategy Pattern**: Different formatting strategies (DETAILED/CONCISE/EXPLICIT)
2. **Factory Pattern**: Adapter factory for model families
3. **Template Method**: PromptBuilder builds in fixed order with variable sections
4. **Composition**: ModelProfile contains CapabilityLevel, PromptStyle enums
5. **Registry Pattern**: ADAPTERS list for dynamic adapter selection
6. **Observer Pattern**: Could be extended for prompt performance tracking

## Performance Characteristics

- **Profile Lookup**: O(n) where n = number of models (30), optimized with prefix matching
- **Prompt Building**: O(t + f) where t = tools, f = features enabled
- **Tool Formatting**: O(t) where t = number of tools (max 128)
- **Memory**: Each ModelProfile is ~200 bytes, total < 10KB for all models

## Conclusion

The prompt system architecture is:
- ✅ **Highly extensible** (easy to add new models)
- ✅ **Well-adapted** (multiple layers of customization)
- ✅ **Efficient** (caching, prioritization)
- ✅ **Tested** (17 comprehensive tests)
- ✅ **Documented** (clear separation of concerns)
- ✅ **Production-ready** (used in main agent flow)

**Recommended enhancements:**
1. Add dynamic capability learning
2. Implement A/B testing framework
3. Add multi-modal adaptations
4. Add cost-aware optimization
