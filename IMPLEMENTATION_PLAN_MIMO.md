# MiMo-V2-Flash Implementation Plan

## Overview
This plan implements comprehensive support for Xiaomi's MiMo-V2-Flash model in Cortex, incorporating insights from the MiMo prompt guide and enhancing the existing prompt system.

## Phase 1: Core Model Integration (Priority: HIGH)

### Task 1.1: Add Model Profile
**File**: `cortex/core/model_capabilities.py`

**Action**: Add MiMo-V2-Flash profile to MODEL_PROFILES

```python
"mimo-v2-flash": ModelProfile(
    name="MiMo-V2-Flash",
    context_window=256000,
    tool_following=CapabilityLevel.EXCELLENT,
    reasoning=CapabilityLevel.EXCELLENT,
    prompt_style=PromptStyle.DETAILED,
    supports_json_mode=True,
    max_tools_per_prompt=64,
    supports_streaming=True,
    supports_vision=False,
    supports_function_calling=True,
    recommended_temperature=0.3,  # Low for coding/planning
    notes="Use JSON schema enforcement; supports reasoning mode via enable_thinking",
    exposes_thinking=True,
    thinking_field="reasoning_content",
),
```

**Why**: MiMo has excellent tool following and reasoning, but requires JSON schema enforcement. Temperature 0.3 is optimal for coding/agentic workflows.

**Acceptance Criteria**:
- ✅ Profile loads correctly via `get_model_profile("mimo-v2-flash")`
- ✅ Returns correct context window (256K)
- ✅ Returns correct capability levels
- ✅ Recommended temperature is 0.3

**Estimated Effort**: 15 minutes

---

### Task 1.2: Add MiMo-Specific Adapter
**File**: `cortex/core/prompts/adapters.py`

**Action**: Create `MiMoAdapter` class and add to registry

```python
class MiMoAdapter(BaseAdapter):
    """Adapter for Xiaomi MiMo-V2-Flash model."""
    
    name = "mimo"
    
    @classmethod
    def applies_to(cls, model_name: str) -> bool:
        model_lower = model_name.lower()
        return "mimo" in model_lower
    
    @classmethod
    def get_tool_format_hint(cls) -> str:
        return """## Tool Format (MiMo)
        
ALL tool calls MUST be valid JSON with this structure:
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "your chain-of-thought (< 150 words)",
  "commands": [{"cmd": "...", "cwd": "...", "explanation": "..."}],
  "edits": [{"file": "...", "action": "create|modify|delete", "content": "..."}],
  "answer": "natural language response"
}

**Mode semantics**:
- `plan`: Multi-step; return commands/edits without executing; ask for approval
- `run_command`: Execute immediately (safety checks pass)
- `edit_file`: Modify single file; await approval unless auto-approved
- `answer`: Return only natural language
- `reasoning`: Thinking-heavy; return chain-of-thought
"""
    
    @classmethod
    def get_response_format_hint(cls) -> str:
        return """## Response Guidelines (MiMo)

- Be explicit, never implicit - restate constraints when in doubt
- Keep reasoning sections under 150 words
- Use step-by-step planning for complex tasks
- Validate file paths and command syntax before proposing
- Reference line numbers and prior errors explicitly
"""
    
    @classmethod
    def get_special_instructions(cls) -> str:
        return """## MiMo-Specific Capabilities

- Use enhanced reasoning capabilities for complex problems
- For routine tasks, respond directly without over-explaining
- Knowledge cutoff: December 2024 - state when uncertain about recent changes
- SWA architecture: Keep most relevant content in accessible windows
- Multi-turn stability: Restate constraints every 3-4 turns
"""
```

**Add to registry**:
```python
ADAPTERS = [
    ClaudeAdapter,
    GPTAdapter,
    DeepSeekAdapter,
    MiMoAdapter,  # NEW
    MistralAdapter,
    CodeSpecializedAdapter,
    OllamaAdapter,
]
```

**Why**: MiMo requires strict JSON schema enforcement and has specific architectural considerations (SWA, reasoning mode).

**Acceptance Criteria**:
- ✅ `get_adapter("mimo-v2-flash")` returns MiMoAdapter
- ✅ Adapter adds JSON schema enforcement to prompts
- ✅ Adapter adds MiMo-specific instructions
- ✅ `adapt_prompt_for_model()` works correctly

**Estimated Effort**: 45 minutes

---

### Task 1.3: Add Date/Cutoff Awareness
**File**: `cortex/core/prompts/builder.py`

**Action**: Add date and knowledge cutoff to system prompts

```python
class PromptBuilder:
    def __init__(self, model_name: str, project_dir: Optional[Path] = None):
        # ... existing code ...
        self.knowledge_cutoff = "December 2024"  # MiMo-specific
        self.current_date = datetime.now().strftime("%B %d, %Y")
    
    def _build_core_section(self) -> str:
        # ... existing implementation ...
        base_prompt = existing_implementation()
        
        # Add date/cutoff for models that need it
        if self.profile.exposes_thinking or "mimo" in self.model_name.lower():
            date_section = f"""## Date & Knowledge

Today's date: {self.current_date}
Knowledge cutoff: {self.knowledge_cutoff}

For events after the cutoff, use reasoning based on prior patterns. When uncertain, state it clearly.
"""
            return base_prompt + "\n\n" + date_section
        
        return base_prompt
```

**Why**: MiMo's guide explicitly recommends date/cutoff awareness for factual grounding.

**Acceptance Criteria**:
- ✅ MiMo prompts include date and cutoff
- ✅ Other models unaffected
- ✅ Date format is human-readable

**Estimated Effort**: 30 minutes

---

### Task 1.4: Add JSON Schema Enforcement
**File**: `cortex/core/prompts/builder.py`

**Action**: Add output schema section for models with JSON support

```python
def _build_output_schema_section(self) -> str:
    """Add JSON schema enforcement for models that support it."""
    if not self.profile.supports_json_mode:
        return ""
    
    return """## Output Format

ALL responses MUST be valid JSON matching this schema:

```json
{
  "mode": "plan" | "run_command" | "edit_file" | "answer" | "reasoning",
  "reasoning": "brief chain-of-thought (< 150 words)",
  "commands": [
    {
      "cmd": "shell command",
      "cwd": "working directory",
      "explanation": "why this is needed"
    }
  ],
  "edits": [
    {
      "file": "relative/path/to/file",
      "action": "create" | "modify" | "delete",
      "content": "file content or patch"
    }
  ],
  "answer": "natural language response"
}
```

**Mode semantics**:
- `plan`: Multiple steps needed; return commands + edits without executing yet; ask for approval
- `run_command`: Execute shell command immediately (only if safety checks pass)
- `edit_file`: Modify a single file (propose change, await approval unless auto-approved)
- `answer`: Return only natural language answer in the "answer" field
- `reasoning`: Thinking-heavy response; return chain-of-thought in "reasoning"

**Security Constraints**:
- NEVER run destructive commands without explicit approval (rm -rf, > /dev/null, network changes)
- ALWAYS validate file paths; reject attempts to write outside allowed directories
- ALWAYS explain your reasoning in < 150 words
- Always output valid JSON; never output raw shell or code without the schema wrapper
"""
```

**Then add to build_system_prompt**:
```python
def build_system_prompt(self, tools: List[Dict[str, Any]], ...):
    sections = []
    
    # 1. Core identity
    sections.append(self._build_core_section())
    
    # 2. Output schema (NEW - for models that need it)
    if self.profile.supports_json_mode:
        sections.append(self._build_output_schema_section())
    
    # 3. Tools (existing)
    if tools:
        sections.append(self.tool_formatter.format_tools(tools))
        sections.append(self._build_tool_guide())
    
    # ... rest of sections ...
```

**Why**: MiMo requires explicit JSON schema enforcement. This also benefits GPT and Claude models.

**Acceptance Criteria**:
- ✅ MiMo prompts include JSON schema
- ✅ GPT/Claude prompts include schema (they support JSON mode)
- ✅ Smaller models (Mistral, Llama) don't get schema (they don't support it)
- ✅ Schema is comprehensive and well-formatted

**Estimated Effort**: 60 minutes

---

## Phase 2: Context Management Enhancements (Priority: MEDIUM)

### Task 2.1: Add SWA-Aware Context Pruning
**File**: `cortex/core/context.py`

**Action**: Create pruning function that respects sliding window attention

```python
def prune_context_swa(
    messages: List[Dict[str, Any]],
    context_window: int = 256000,
    swa_window: int = 128,
    max_turns: int = 5
) -> List[Dict[str, Any]]:
    """
    Prune conversation history respecting SWA architecture.
    
    MiMo's SWA means content within 128-token windows is more accessible.
    Keep system/session in first window, recent turns in accessible windows.
    
    Args:
        messages: Full message history
        context_window: Total context size (256K for MiMo)
        swa_window: SWA window size (128 tokens for MiMo)
        max_turns: Keep last N turns
    
    Returns:
        Pruned message list
    """
    # Keep system message (always)
    system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
    
    # Keep session context (project info, tools)
    # Assume session context is in system message for now
    
    # Keep last N turns (most relevant for SWA)
    other_messages = messages[1:] if system_msg else messages
    
    if len(other_messages) <= max_turns:
        return messages
    
    # Keep last max_turns turns
    kept_messages = other_messages[-max_turns:]
    
    if system_msg:
        return [system_msg] + kept_messages
    
    return kept_messages
```

**Add to count_message_tokens**:
```python
def count_message_tokens(message: Dict[str, Any], model: str = "gpt-4") -> int:
    # ... existing implementation ...
    
    # MiMo-specific token counting (SWA-aware)
    model_lower = model.lower()
    if "mimo" in model_lower:
        # MiMo's SWA has different overhead
        # Add penalty for content far from current context
        # This is a simplification - actual SWA is more complex
        base_tokens = estimate_tokens(message, model)
        
        # Add overhead for role/content structure
        # MiMo specifically needs explicit delimiters
        return base_tokens + 5  # Add 5 tokens for structure
```

**Why**: MiMo's SWA architecture means context accessibility is non-uniform. This optimization keeps relevant content in accessible windows.

**Acceptance Criteria**:
- ✅ Function exists and is tested
- ✅ Keeps system message
- ✅ Keeps last 5 turns by default
- ✅ Respects context window limit
- ✅ Works specifically for MiMo model

**Estimated Effort**: 60 minutes

---

### Task 2.2: Add Reasoning Mode Support
**File**: `cortex/core/model_capabilities.py`

**Action**: Extend ModelProfile and create reasoning mode helper

```python
@dataclass
class ModelProfile:
    # ... existing fields ...
    reasoning_mode_enabled: bool = False  # For models like MiMo, DeepSeek
    reasoning_mode_kwargs: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.reasoning_mode_kwargs is None:
            self.reasoning_mode_kwargs = {}
```

**Add helper function**:
```python
def get_reasoning_mode_config(model_name: str) -> Dict[str, Any]:
    """
    Get reasoning mode configuration for models that support it.
    
    Returns:
        Dict with enable_thinking flag and other kwargs
    """
    profile = get_model_profile(model_name)
    
    if not profile.exposes_thinking:
        return {}
    
    # MiMo specific config
    if "mimo" in model_name.lower():
        return {
            "enable_thinking": True,
            "max_tokens": 4096,
            "temperature": 0.7,  # Higher for reasoning mode
        }
    
    # DeepSeek specific config
    if "deepseek-reasoner" in model_name.lower():
        return {
            "enable_thinking": True,
            "max_tokens": 4096,
            "temperature": 0.7,
        }
    
    return {}
```

**Why**: MiMo supports reasoning mode (similar to o1) for complex tasks. This needs to be exposed to the calling code.

**Acceptance Criteria**:
- ✅ Configuration returned for MiMo
- ✅ Empty dict for models without reasoning mode
- ✅ Includes enable_thinking, max_tokens, temperature

**Estimated Effort**: 30 minutes

---

## Phase 3: Temperature & Generation Settings (Priority: MEDIUM)

### Task 3.1: Add Temperature Stratification
**File**: `cortex/core/model_capabilities.py`

**Action**: Extend ModelProfile with multiple temperature settings

```python
@dataclass
class ModelProfile:
    # ... existing fields ...
    recommended_temperatures: Dict[str, float] = None
    
    def __post_init__(self):
        if self.recommended_temperatures is None:
            self.recommended_temperatures = {
                "coding_planning": 0.3,
                "debugging": 0.5,
                "reasoning": 0.7,
                "creative": 0.9,
            }
```

**Update MiMo profile**:
```python
"mimo-v2-flash": ModelProfile(
    # ... existing fields ...
    recommended_temperatures={
        "coding_planning": 0.3,
        "debugging": 0.5,
        "reasoning": 0.7,
        "creative": 0.9,
    },
),
```

**Add helper function**:
```python
def get_temperature_for_task(model_name: str, task_type: str) -> float:
    """
    Get recommended temperature for a specific task type.
    
    Args:
        model_name: Model identifier
        task_type: "coding_planning", "debugging", "reasoning", "creative"
    
    Returns:
        Recommended temperature
    """
    profile = get_model_profile(model_name)
    return profile.recommended_temperatures.get(task_type, profile.recommended_temperature)
```

**Why**: MiMo's guide provides specific temperatures for different scenarios. This makes that guidance accessible.

**Acceptance Criteria**:
- ✅ Temperature function exists
- ✅ Returns correct values for MiMo
- ✅ Falls back to default for unknown models
- ✅ Handles invalid task types gracefully

**Estimated Effort**: 30 minutes

---

## Phase 4: Production Metrics & Monitoring (Priority: LOW)

### Task 4.1: Add Success Metrics Tracking
**File**: `cortex/core/metrics.py` (NEW FILE)

**Action**: Create metrics tracking system

```python
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
import json

@dataclass
class PromptMetrics:
    """Track prompt system performance metrics."""
    
    model_name: str
    timestamp: datetime
    
    # MiMo-inspired metrics
    json_validity_rate: float = 0.0
    tool_call_accuracy: float = 0.0
    instruction_compliance: float = 0.0
    reasoning_brevity: float = 0.0  # Average words
    context_efficiency: float = 0.0  # Tokens per task
    multi_turn_stability: float = 0.0
    
    # Custom metrics
    response_count: int = 0
    error_count: int = 0
    total_tokens_used: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "model": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "json_validity_rate": self.json_validity_rate,
            "tool_call_accuracy": self.tool_call_accuracy,
            "instruction_compliance": self.instruction_compliance,
            "reasoning_brevity": self.reasoning_brevity,
            "context_efficiency": self.context_efficiency,
            "multi_turn_stability": self.multi_turn_stability,
            "response_count": self.response_count,
            "error_count": self.error_count,
            "total_tokens_used": self.total_tokens_used,
        }


class MetricsTracker:
    """Track and analyze prompt system metrics."""
    
    def __init__(self):
        self.metrics: List[PromptMetrics] = []
    
    def record_response(
        self,
        model_name: str,
        json_valid: bool,
        tool_success: bool,
        instruction_compliant: bool,
        reasoning_words: int,
        tokens_used: int,
    ) -> PromptMetrics:
        """Record metrics for a single response."""
        
        # Find or create metrics for this model
        existing = None
        for m in self.metrics:
            if m.model_name == model_name:
                existing = m
                break
        
        if existing is None:
            existing = PromptMetrics(model_name=model_name, timestamp=datetime.now())
            self.metrics.append(existing)
        
        # Update metrics
        existing.response_count += 1
        if not json_valid:
            existing.error_count += 1
        
        # Calculate running averages
        if existing.response_count > 0:
            existing.json_validity_rate = (
                (existing.json_validity_rate * (existing.response_count - 1)) +
                (1.0 if json_valid else 0.0)
            ) / existing.response_count
            
            existing.tool_call_accuracy = (
                (existing.tool_call_accuracy * (existing.response_count - 1)) +
                (1.0 if tool_success else 0.0)
            ) / existing.response_count
            
            existing.instruction_compliance = (
                (existing.instruction_compliance * (existing.response_count - 1)) +
                (1.0 if instruction_compliant else 0.0)
            ) / existing.response_count
            
            existing.reasoning_brevity = (
                (existing.reasoning_brevity * (existing.response_count - 1)) +
                reasoning_words
            ) / existing.response_count
            
            existing.context_efficiency = (
                (existing.context_efficiency * (existing.response_count - 1)) +
                tokens_used
            ) / existing.response_count
        
        existing.total_tokens_used += tokens_used
        
        return existing
    
    def get_metrics_for_model(self, model_name: str) -> PromptMetrics:
        """Get metrics for a specific model."""
        for m in self.metrics:
            if m.model_name == model_name:
                return m
        
        return PromptMetrics(model_name=model_name, timestamp=datetime.now())
    
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file."""
        data = [m.to_dict() for m in self.metrics]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_summary(self) -> Dict[str, any]:
        """Get summary of all metrics."""
        return {
            "total_models": len(self.metrics),
            "total_responses": sum(m.response_count for m in self.metrics),
            "average_json_validity": sum(m.json_validity_rate for m in self.metrics) / len(self.metrics) if self.metrics else 0,
            "average_tool_accuracy": sum(m.tool_call_accuracy for m in self.metrics) / len(self.metrics) if self.metrics else 0,
        }
```

**Why**: MiMo's guide defines success metrics. This makes them trackable in production.

**Acceptance Criteria**:
- ✅ MetricsTracker class exists
- ✅ Can record responses
- ✅ Can calculate running averages
- ✅ Can export to JSON
- ✅ Can get summary statistics

**Estimated Effort**: 90 minutes

---

## Phase 5: Integration & Testing (Priority: HIGH)

### Task 5.1: Add MiMo Tests
**File**: `tests/unit/core/test_mimo_integration.py` (NEW FILE)

**Action**: Create comprehensive test suite

```python
import pytest
from unittest.mock import patch, MagicMock
from cortex.core.model_capabilities import (
    get_model_profile,
    get_reasoning_mode_config,
    get_temperature_for_task,
)
from cortex.core.prompts import PromptBuilder, get_adapter, adapt_prompt_for_model


class TestMiMoProfile:
    """Test MiMo model profile."""
    
    def test_mimo_profile_exists(self):
        profile = get_model_profile("mimo-v2-flash")
        assert profile.name == "MiMo-V2-Flash"
        assert profile.context_window == 256000
        assert profile.tool_following.value == "excellent"
        assert profile.reasoning.value == "excellent"
        assert profile.prompt_style.value == "detailed"
        assert profile.supports_json_mode is True
        assert profile.max_tools_per_prompt == 64
        assert profile.recommended_temperature == 0.3
        assert profile.exposes_thinking is True
        assert profile.thinking_field == "reasoning_content"
    
    def test_mimo_temperature_stratification(self):
        assert get_temperature_for_task("mimo-v2-flash", "coding_planning") == 0.3
        assert get_temperature_for_task("mimo-v2-flash", "debugging") == 0.5
        assert get_temperature_for_task("mimo-v2-flash", "reasoning") == 0.7
        assert get_temperature_for_task("mimo-v2-flash", "creative") == 0.9


class TestMiMoAdapter:
    """Test MiMo adapter."""
    
    def test_mimo_adapter_applies(self):
        adapter = get_adapter("mimo-v2-flash")
        assert adapter is not None
        assert adapter.name == "mimo"
    
    def test_mimo_adapter_adds_json_schema(self):
        adapter = get_adapter("mimo-v2-flash")
        profile = get_model_profile("mimo-v2-flash")
        
        prompt = "You are Cortex."
        adapted = adapter.adapt_prompt(prompt, profile)
        
        assert "Output Format" in adapted
        assert "JSON" in adapted
        assert "mode" in adapted


class TestMiMoPromptBuilder:
    """Test MiMo prompt building."""
    
    def test_mimo_includes_date_cutoff(self):
        builder = PromptBuilder("mimo-v2-flash")
        prompt = builder.build_system_prompt(tools=[])
        
        assert "Today's date:" in prompt
        assert "Knowledge cutoff:" in prompt
        assert "December 2024" in prompt
    
    def test_mimo_includes_json_schema(self):
        builder = PromptBuilder("mimo-v2-flash")
        prompt = builder.build_system_prompt(tools=[])
        
        assert "Output Format" in prompt
        assert "mode" in prompt
        assert "commands" in prompt
        assert "edits" in prompt
    
    def test_mimo_adaptations_present(self):
        builder = PromptBuilder("mimo-v2-flash")
        prompt = builder.build_system_prompt(tools=[])
        
        assert "MiMo" in prompt
        assert "reasoning" in prompt.lower()
        assert "explicit" in prompt.lower()


class TestMiMoReasoningMode:
    """Test MiMo reasoning mode configuration."""
    
    def test_mimo_reasoning_mode_config(self):
        config = get_reasoning_mode_config("mimo-v2-flash")
        
        assert config["enable_thinking"] is True
        assert config["max_tokens"] == 4096
        assert config["temperature"] == 0.7
    
    def test_other_models_no_reasoning_mode(self):
        config = get_reasoning_mode_config("llama3.2")
        assert config == {}


class TestMiMoContextPruning:
    """Test MiMo-specific context pruning."""
    
    def test_prune_context_swa(self):
        from cortex.core.context import prune_context_swa
        
        messages = [
            {"role": "system", "content": "You are MiMo"},
            {"role": "user", "content": "Fix bug 1"},
            {"role": "assistant", "content": "I'll help"},
            {"role": "user", "content": "Fix bug 2"},
            {"role": "assistant", "content": "Done"},
            {"role": "user", "content": "Fix bug 3"},
            {"role": "assistant", "content": "Done"},
            {"role": "user", "content": "Fix bug 4"},
        ]
        
        pruned = prune_context_swa(messages, context_window=256000, max_turns=3)
        
        assert len(pruned) == 4  # system + last 3 turns
        assert pruned[0]["role"] == "system"
        assert "Fix bug 4" in pruned[-1]["content"]


class TestMiMoMetrics:
    """Test MiMo metrics tracking."""
    
    def test_metrics_tracking(self):
        from cortex.core.metrics import MetricsTracker
        
        tracker = MetricsTracker()
        
        # Record some responses
        tracker.record_response(
            model_name="mimo-v2-flash",
            json_valid=True,
            tool_success=True,
            instruction_compliant=True,
            reasoning_words=50,
            tokens_used=500,
        )
        
        tracker.record_response(
            model_name="mimo-v2-flash",
            json_valid=False,
            tool_success=False,
            instruction_compliant=True,
            reasoning_words=100,
            tokens_used=800,
        )
        
        metrics = tracker.get_metrics_for_model("mimo-v2-flash")
        
        assert metrics.response_count == 2
        assert metrics.json_validity_rate == 0.5  # 1/2 valid
        assert metrics.tool_call_accuracy == 0.5  # 1/2 successful
        assert metrics.instruction_compliance == 1.0  # Both compliant
        assert metrics.reasoning_brevity == 75  # Average of 50 and 100
```

**Why**: Comprehensive testing ensures MiMo integration works correctly and doesn't break existing functionality.

**Acceptance Criteria**:
- ✅ All tests pass
- ✅ Tests cover all new functionality
- ✅ Tests don't interfere with existing tests
- ✅ Tests use proper mocking

**Estimated Effort**: 120 minutes

---

### Task 5.2: Update Existing Tests
**File**: `tests/unit/core/test_model_capabilities.py`

**Action**: Add MiMo to existing test suite

```python
def test_mimo_profile():
    """Test MiMo model profile."""
    profile = get_model_profile("mimo-v2-flash")
    assert profile.name == "MiMo-V2-Flash"
    assert profile.context_window == 256000


def test_mimo_family_pattern_match():
    """Test MiMo family pattern matching."""
    profile = get_model_profile("mimo-v2-flash")
    assert profile.name == "MiMo-V2-Flash"
```

**Why**: Ensure MiMo is covered in existing model capability tests.

**Estimated Effort**: 15 minutes

---

### Task 5.3: Integration Testing
**File**: `tests/integration/test_mimo_integration.py` (NEW FILE)

**Action**: Test MiMo in realistic agent scenarios

```python
import pytest
from unittest.mock import patch, MagicMock
from cortex.agent import Agent


class TestMiMoAgentIntegration:
    """Test MiMo integration with agent system."""
    
    def test_agent_with_mimo(self):
        """Test agent using MiMo model."""
        agent = Agent(model="mimo-v2-flash")
        
        assert agent.model == "mimo-v2-flash"
        assert agent.profile is not None
        assert agent.profile.context_window == 256000
    
    @patch('cortex.agent.ModelProvider')
    def test_mimo_prompt_generation(self, mock_provider):
        """Test that MiMo gets correct prompt structure."""
        agent = Agent(model="mimo-v2-flash")
        
        # Mock the provider
        mock_response = MagicMock()
        mock_response.content = '{"mode": "answer", "reasoning": "Test", "answer": "Hello"}'
        mock_provider.return_value.call.return_value = mock_response
        
        # Trigger prompt generation
        with patch('cortex.agent.get_model_profile') as mock_profile:
            mock_profile.return_value = MagicMock(
                supports_json_mode=True,
                context_window=256000,
            )
            
            # This would normally call the model
            # For testing, we just verify the prompt structure
            pass
```

**Why**: Test that MiMo works end-to-end in the agent system.

**Estimated Effort**: 60 minutes

---

## Phase 6: Documentation & Examples (Priority: MEDIUM)

### Task 6.1: Update Model Documentation
**File**: `docs/models/mimo-v2-flash.md` (NEW FILE)

**Action**: Create comprehensive model documentation

```markdown
# MiMo-V2-Flash Model Guide

## Overview

Xiaomi's MiMo-V2-Flash is a 309B parameter Mixture-of-Experts model with 15B active parameters per request.

## Key Features

- 256K context window
- Sliding Window Attention (128-token windows)
- Reasoning mode support
- JSON schema enforcement required
- Excellent for coding and planning

## Prompt System

MiMo requires:
1. Date and knowledge cutoff awareness
2. JSON schema enforcement for responses
3. Explicit constraint restatement in multi-turn
4. Temperature stratification (0.3-0.9)

## Usage Examples

### Basic Usage
```python
from cortex.core.prompts import PromptBuilder

builder = PromptBuilder("mimo-v2-flash")
prompt = builder.build_system_prompt(tools=tool_definitions)
```

### With Reasoning Mode
```python
from cortex.core.model_capabilities import get_reasoning_mode_config

config = get_reasoning_mode_config("mimo-v2-flash")
# Returns: {"enable_thinking": True, "max_tokens": 4096, "temperature": 0.7}
```

### Temperature Selection
```python
from cortex.core.model_capabilities import get_temperature_for_task

# For coding/planning (default)
temp = get_temperature_for_task("mimo-v2-flash", "coding_planning")  # 0.3

# For debugging complex issues
temp = get_temperature_for_task("mimo-v2-flash", "debugging")  # 0.5

# For complex reasoning
temp = get_temperature_for_task("mimo-v2-flash", "reasoning")  # 0.7
```

## Integration

### API Endpoint
```python
import requests

response = requests.post(
    "http://localhost:9001/v1/chat/completions",
    json={
        "model": "XiaomiMiMo/MiMo-V2-Flash",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
        "chat_template_kwargs": {"enable_thinking": False}
    }
)
```

### Reasoning Mode
```python
response = requests.post(
    "http://localhost:9001/v1/chat/completions",
    json={
        "model": "XiaomiMiMo/MiMo-V2-Flash",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "chat_template_kwargs": {"enable_thinking": True}
    }
)
```

## Best Practices

1. **Always validate JSON responses** - MiMo requires schema enforcement
2. **Restate constraints every 3-4 turns** - Prevent instruction drift
3. **Use temperature 0.3 for coding** - Lower for deterministic tool calls
4. **Enable reasoning mode for complex tasks** - Use 0.7 temperature
5. **Keep reasoning under 150 words** - Be concise in reasoning sections
6. **Reference line numbers explicitly** - Helps with code analysis
7. **Use delimiters** - `### HEADER` for semantic boundaries

## Context Management

With 256K context:
- Keep system + session in first window
- Keep last 3-5 turns in accessible windows
- Archive old outputs if >8K tokens
- Use SWA locality (128-token windows)

## Success Metrics

Track these for MiMo:
- JSON validity rate: >98%
- Tool call accuracy: >90%
- Instruction compliance: 100%
- Reasoning brevity: <150 words
- Context efficiency: <2000 tokens/request
- Multi-turn stability: >95%

## Common Issues

| Issue | Solution |
|-------|----------|
| Invalid JSON | Include in-prompt JSON examples |
| Instruction drift | Restate constraints every turn |
| Long reasoning | Add "Keep under 150 words" to prompt |
| Tool inconsistency | Validate output immediately |
| Context degradation | Use delimiters and feed relevant last |
| Knowledge cutoff | State cutoff date; clarify when uncertain |

## References

- [MiMo-V2-Flash GitHub](https://github.com/XiaomiMiMo/MiMo-V2-Flash)
- [MiMo Complete Guide](https://dev.to/czmilo/xiaomi-mimo-v2-flash-complete-guide-to-the-309b-parameter-moe-model-2025-bg6)
- [MiMo Technical Report](https://arxiv.org/html/2601.02780v1)
- [SGLang MiMo Support](https://lmsys.org/blog/2025-12-16-mimo-v2-flash/)
```

**Why**: Users need to understand MiMo-specific requirements and how to use it effectively.

**Acceptance Criteria**:
- ✅ Documentation exists
- ✅ Covers all MiMo-specific features
- ✅ Includes code examples
- ✅ References source material
- ✅ Clear and well-structured

**Estimated Effort**: 90 minutes

---

### Task 6.2: Update README
**File**: `README.md`

**Action**: Add MiMo to model list

```markdown
## Supported Models

### MiMo Family
- **MiMo-V2-Flash** (Xiaomi) - 309B MoE, 256K context, reasoning mode
  - JSON schema enforcement
  - Temperature stratification
  - SWA-aware context management
```

**Estimated Effort**: 15 minutes

---

## Phase 7: Deployment & Production (Priority: HIGH)

### Task 7.1: Add MiMo to Agent Configuration
**File**: `cortex/config/agents.yaml` (or equivalent)

**Action**: Add MiMo model configuration

```yaml
models:
  mimo-v2-flash:
    provider: openrouter  # or sglang, vllm
    endpoint: "https://openrouter.ai/api/v1/chat/completions"
    api_key: "${OPENROUTER_API_KEY}"
    default_temperature: 0.3
    context_window: 256000
    supports_reasoning_mode: true
    max_tokens: 1024
    reasoning_max_tokens: 4096
```

**Why**: Make MiMo configurable for deployment.

**Estimated Effort**: 30 minutes

---

### Task 7.2: Add Deployment Scripts
**File**: `scripts/deploy_mimo.sh` (NEW FILE)

**Action**: Create deployment script for MiMo

```bash
#!/bin/bash
# deploy_mimo.sh - Deploy MiMo-V2-Flash with SGLang

set -e

echo "Deploying MiMo-V2-Flash..."

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Python 3 required"
    exit 1
fi

# Install SGLang if not present
if ! python3 -c "import sglang" &> /dev/null; then
    echo "Installing SGLang..."
    pip install sglang[srt]
fi

# Download model (if using local deployment)
# echo "Downloading MiMo-V2-Flash..."
# huggingface-cli download XiaomiMiMo/MiMo-V2-Flash --local-dir ./models/mimo-v2-flash

# Start SGLang server
echo "Starting SGLang server..."
python3 -m sglang.launch_server \
    --model-path XiaomiMiMo/MiMo-V2-Flash \
    --host 0.0.0.0 \
    --port 9001 \
    --tp-size 4 \
    --mem-fraction-static 0.8 \
    --max-total-tokens 256000 \
    --chat-template mistral \
    --enable-p2p-check &

SERVER_PID=$!
echo "SGLang server started (PID: $SERVER_PID)"

# Wait for server to be ready
echo "Waiting for server to be ready..."
sleep 30

# Test the server
echo "Testing server..."
curl -X POST http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "XiaomiMiMo/MiMo-V2-Flash",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.3,
    "max_tokens": 100
  }'

echo ""
echo "MiMo-V2-Flash deployment complete!"
echo "Server running on http://localhost:9001"
echo "PID: $SERVER_PID"
echo ""
echo "To stop: kill $SERVER_PID"
```

**Why**: Make deployment easy for users.

**Estimated Effort**: 60 minutes

---

## Phase 8: Enhancements & Improvements (Priority: LOW)

### Task 8.1: Add A/B Testing Framework
**File**: `cortex/core/prompt_variants.py` (NEW FILE)

**Action**: Support prompt variants for optimization

```python
from dataclasses import dataclass
from typing import List, Dict, Any
import random

@dataclass
class PromptVariant:
    name: str
    prompt_template: str
    success_rate: float = 0.0
    usage_count: int = 0

class PromptVariantManager:
    """Manage A/B testing of prompt variants."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.variants: List[PromptVariant] = []
    
    def add_variant(self, name: str, template: str):
        self.variants.append(PromptVariant(name=name, prompt_template=template))
    
    def get_variant(self) -> PromptVariant:
        """Get variant using multi-armed bandit (UCB1)."""
        if not self.variants:
            raise ValueError("No variants configured")
        
        # If first time, use all variants
        if all(v.usage_count == 0 for v in self.variants):
            return random.choice(self.variants)
        
        # UCB1: Upper Confidence Bound
        import math
        total_usage = sum(v.usage_count for v in self.variants)
        
        best_variant = None
        best_score = -float('inf')
        
        for variant in self.variants:
            if variant.usage_count == 0:
                return variant  # Try unexplored
            
            # UCB1 formula
            avg_reward = variant.success_rate
            exploration = math.sqrt(2 * math.log(total_usage) / variant.usage_count)
            score = avg_reward + exploration
            
            if score > best_score:
                best_score = score
                best_variant = variant
        
        return best_variant or self.variants[0]
    
    def record_result(self, variant_name: str, success: bool):
        """Record success/failure for a variant."""
        for variant in self.variants:
            if variant.name == variant_name:
                variant.usage_count += 1
                # Update running average
                variant.success_rate = (
                    (variant.success_rate * (variant.usage_count - 1)) +
                    (1.0 if success else 0.0)
                ) / variant.usage_count
                break
    
    def get_best_variant(self) -> PromptVariant:
        """Get variant with highest success rate."""
        if not self.variants:
            raise ValueError("No variants configured")
        
        return max(self.variants, key=lambda v: v.success_rate)
```

**Why**: Enables continuous optimization of prompts for MiMo.

**Acceptance Criteria**:
- ✅ Variant manager exists
- ✅ UCB1 bandit algorithm implemented
- ✅ Success rate tracking
- ✅ Best variant selection

**Estimated Effort**: 120 minutes

---

### Task 8.2: Add Dynamic Capability Learning
**File**: `cortex/core/learning.py` (NEW FILE)

**Action**: Track actual model performance and adjust profiles

```python
from dataclasses import dataclass
from typing import Dict, List
import json
from datetime import datetime

@dataclass
class ModelPerformance:
    """Track actual model performance over time."""
    
    model_name: str
    timestamp: datetime
    
    # Tool calling performance
    tool_success_rate: float = 0.0
    tool_call_count: int = 0
    
    # Reasoning performance
    reasoning_effectiveness: float = 0.0
    reasoning_count: int = 0
    
    # Token efficiency
    tokens_per_success: float = 0.0
    success_count: int = 0
    
    def update_tool_performance(self, success: bool):
        """Update tool calling performance."""
        self.tool_call_count += 1
        self.tool_success_rate = (
            (self.tool_success_rate * (self.tool_call_count - 1)) +
            (1.0 if success else 0.0)
        ) / self.tool_call_count
    
    def update_reasoning_performance(self, effectiveness: float):
        """Update reasoning performance (0-1)."""
        self.reasoning_count += 1
        self.reasoning_effectiveness = (
            (self.reasoning_effectiveness * (self.reasoning_count - 1)) +
            effectiveness
        ) / self.reasoning_count
    
    def update_token_efficiency(self, tokens: int, success: bool):
        """Update token efficiency metrics."""
        if success:
            self.success_count += 1
            self.tokens_per_success = (
                (self.tokens_per_success * (self.success_count - 1)) +
                tokens
            ) / self.success_count


class LearningManager:
    """Manage dynamic capability learning."""
    
    def __init__(self):
        self.performance_data: Dict[str, ModelPerformance] = {}
        self.learning_file = "data/model_performance.json"
    
    def record_interaction(
        self,
        model_name: str,
        tool_success: bool,
        reasoning_effectiveness: float,
        tokens_used: int,
    ):
        """Record model interaction for learning."""
        
        if model_name not in self.performance_data:
            self.performance_data[model_name] = ModelPerformance(
                model_name=model_name,
                timestamp=datetime.now(),
            )
        
        perf = self.performance_data[model_name]
        perf.update_tool_performance(tool_success)
        perf.update_reasoning_performance(reasoning_effectiveness)
        perf.update_token_efficiency(tokens_used, tool_success)
    
    def get_learned_profile(self, model_name: str) -> Dict[str, Any]:
        """Get learned capabilities for a model."""
        if model_name not in self.performance_data:
            return {}
        
        perf = self.performance_data[model_name]
        
        return {
            "tool_success_rate": perf.tool_success_rate,
            "tool_call_count": perf.tool_call_count,
            "reasoning_effectiveness": perf.reasoning_effectiveness,
            "reasoning_count": perf.reasoning_count,
            "tokens_per_success": perf.tokens_per_success,
            "success_count": perf.success_count,
        }
    
    def should_adjust_capability(self, model_name: str) -> bool:
        """Check if enough data to adjust capabilities."""
        if model_name not in self.performance_data:
            return False
        
        perf = self.performance_data[model_name]
        return perf.tool_call_count >= 10  # Need at least 10 samples
    
    def save_learning(self):
        """Save learned data to file."""
        data = {
            model: {
                "timestamp": perf.timestamp.isoformat(),
                "tool_success_rate": perf.tool_success_rate,
                "tool_call_count": perf.tool_call_count,
                "reasoning_effectiveness": perf.reasoning_effectiveness,
                "reasoning_count": perf.reasoning_count,
                "tokens_per_success": perf.tokens_per_success,
                "success_count": perf.success_count,
            }
            for model, perf in self.performance_data.items()
        }
        
        import os
        os.makedirs(os.path.dirname(self.learning_file), exist_ok=True)
        
        with open(self.learning_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_learning(self):
        """Load learned data from file."""
        import os
        if os.path.exists(self.learning_file):
            with open(self.learning_file, 'r') as f:
                data = json.load(f)
            
            for model, perf_data in data.items():
                self.performance_data[model] = ModelPerformance(
                    model_name=model,
                    timestamp=datetime.fromisoformat(perf_data["timestamp"]),
                    tool_success_rate=perf_data["tool_success_rate"],
                    tool_call_count=perf_data["tool_call_count"],
                    reasoning_effectiveness=perf_data["reasoning_effectiveness"],
                    reasoning_count=perf_data["reasoning_count"],
                    tokens_per_success=perf_data["tokens_per_success"],
                    success_count=perf_data["success_count"],
                )
```

**Why**: MiMo's guide defines success metrics. This enables learning from actual usage and adjusting capabilities over time.

**Acceptance Criteria**:
- ✅ LearningManager exists
- ✅ Can record interactions
- ✅ Can get learned profiles
- ✅ Can save/load learning data
- ✅ Determines when to adjust capabilities

**Estimated Effort**: 150 minutes

---

## Implementation Timeline

### Week 1: Core Integration (Phases 1-2)
- Day 1-2: Tasks 1.1-1.4 (Model profile, adapter, date awareness, JSON schema)
- Day 3-4: Tasks 2.1-2.2 (SWA pruning, reasoning mode)
- Day 5: Testing (Task 5.1)

### Week 2: Production Features (Phases 3-5)
- Day 1-2: Tasks 3.1, 5.2, 5.3 (Temperature, tests, integration)
- Day 3-4: Tasks 4.1, 6.1 (Metrics, documentation)
- Day 5: Deployment (Task 7.1-7.2)

### Week 3: Enhancements (Phase 8, Optional)
- Task 8.1: A/B testing framework
- Task 8.2: Dynamic learning

## Success Criteria

### Functional
- ✅ MiMo model profile loads correctly
- ✅ MiMo adapter adds JSON schema enforcement
- ✅ Date/cutoff awareness in prompts
- ✅ Reasoning mode configuration available
- ✅ Temperature stratification works
- ✅ SWA-aware context pruning works
- ✅ Metrics tracking works
- ✅ All tests pass

### Non-Functional
- ✅ No breaking changes to existing models
- ✅ Performance impact < 5%
- ✅ Documentation complete
- ✅ Deployment scripts work
- ✅ Code follows existing patterns

### Production Readiness
- ✅ Comprehensive test coverage
- ✅ Error handling
- ✅ Logging
- ✅ Configuration management
- ✅ Deployment scripts

## Risk Mitigation

### Risk: Breaking existing functionality
**Mitigation**: 
- Comprehensive test suite
- Feature flags for new functionality
- Staged rollout

### Risk: MiMo API incompatibility
**Mitigation**:
- Use OpenAI-compatible API format
- Test with multiple endpoints
- Provide fallback configurations

### Risk: Performance degradation
**Mitigation**:
- Benchmark before/after
- Profile context pruning
- Optimize JSON validation

### Risk: Documentation gaps
**Mitigation**:
- Include examples in tests
- User acceptance testing
- Update README and guides

## Files to Create/Modify

### New Files
1. `cortex/core/prompts/adapters.py` (add MiMoAdapter)
2. `cortex/core/metrics.py` (NEW - metrics tracking)
3. `cortex/core/learning.py` (NEW - dynamic learning)
4. `cortex/core/prompt_variants.py` (NEW - A/B testing)
5. `tests/unit/core/test_mimo_integration.py` (NEW)
6. `tests/integration/test_mimo_integration.py` (NEW)
7. `docs/models/mimo-v2-flash.md` (NEW)
8. `scripts/deploy_mimo.sh` (NEW)
9. `IMPLEMENTATION_PLAN_MIMO.md` (NEW - this file)

### Modified Files
1. `cortex/core/model_capabilities.py` (add MiMo profile)
2. `cortex/core/prompts/builder.py` (add date/cutoff, JSON schema)
3. `cortex/core/context.py` (add SWA pruning)
4. `tests/unit/core/test_model_capabilities.py` (add MiMo tests)
5. `README.md` (add MiMo to model list)
6. `cortex/config/agents.yaml` (add MiMo config)

## Testing Strategy

### Unit Tests (80% coverage)
- Model profile tests
- Adapter tests
- Prompt builder tests
- Context pruning tests
- Metrics tracking tests
- Learning tests

### Integration Tests (20% coverage)
- Agent integration
- End-to-end workflow
- API compatibility

### Manual Testing
- Deploy MiMo locally
- Run through typical agentic tasks
- Verify JSON schema enforcement
- Test reasoning mode
- Validate context pruning

## Success Metrics

### Code Quality
- Test coverage: >80%
- All tests passing
- No breaking changes
- Code follows patterns

### Performance
- Prompt building: < 100ms
- Context pruning: < 50ms
- Metrics tracking: < 10ms overhead
- No regression for existing models

### Usability
- Documentation complete
- Examples work
- Deployment scripts work
- User can add MiMo in < 5 minutes

---

## Summary

This plan implements **comprehensive MiMo-V2-Flash support** with:

1. **Core Integration** (Phase 1) - Model profile, adapter, date awareness, JSON schema
2. **Context Management** (Phase 2) - SWA-aware pruning, reasoning mode
3. **Temperature Settings** (Phase 3) - Stratified temperatures
4. **Production Metrics** (Phase 4) - MiMo-inspired success tracking
5. **Testing** (Phase 5) - Comprehensive unit and integration tests
6. **Documentation** (Phase 6) - Model guide, examples
7. **Deployment** (Phase 7) - Configuration, deployment scripts
8. **Enhancements** (Phase 8) - A/B testing, dynamic learning

**Total Estimated Effort**: 12-15 hours (1-2 weeks of work)

**Risk Level**: LOW (follows existing patterns, well-tested)

**Priority**: HIGH (MiMo is a strong model for agentic workflows)

---

## Next Steps

1. **Immediate** (Week 1):
   - Add model profile (Task 1.1)
   - Create MiMo adapter (Task 1.2)
   - Add date/cutoff awareness (Task 1.3)
   - Add JSON schema enforcement (Task 1.4)

2. **Short-term** (Week 2):
   - Add context pruning (Task 2.1)
   - Add reasoning mode support (Task 2.2)
   - Add temperature stratification (Task 3.1)
   - Create comprehensive tests (Task 5.1)
   - Update documentation (Task 6.1)

3. **Medium-term** (Week 3, Optional):
   - Add metrics tracking (Task 4.1)
   - Create deployment scripts (Task 7.2)
   - Add A/B testing framework (Task 8.1)
   - Add dynamic learning (Task 8.2)

4. **Long-term** (Future):
   - Monitor production metrics
   - Optimize based on learning
   - Add more prompt variants
   - Expand to other models
