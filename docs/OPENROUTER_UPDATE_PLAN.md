# OpenRouter Update Plan: Specific Changes Required

## Executive Summary

OpenRouter provider integration is technically complete but missing from user-facing documentation and CLI interfaces. This document outlines the specific changes needed to fully integrate OpenRouter into Cortex.

## 1. CLI Updates (`cortex/cli.py`)

### 1.1 Update `list_providers()` Function

**Current Location**: Lines 51-87  
**Current State**: Missing OpenRouter entry

**Required Change**:
```python
def list_providers():
    """List available providers and models"""
    table = Table(
        title="Available Providers and Models", show_header=True, header_style="bold cyan"
    )
    table.add_column("Provider", style="cyan")
    table.add_column("Model Name", style="green")
    table.add_column("Description", style="dim")
    table.add_column("API Key Required", style="yellow")

    # Ollama
    table.add_row(
        "Ollama", "llama3.2, deepseek-r1:8b, qwen2.5:32b, etc.", "Local models via Ollama", "No"
    )

    # DeepSeek
    deepseek_key = "Yes" if os.getenv("DEEPSEEK_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "DeepSeek",
        "deepseek-chat, deepseek-coder, deepseek-reasoner",
        "Cloud API - Best for coding, cheapest",
        deepseek_key,
    )

    # Anthropic
    anthropic_key = "Yes" if os.getenv("ANTHROPIC_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "Anthropic",
        "claude-3-5-sonnet-20241022, claude-3-haiku-20240307, claude-3-opus-20240229",
        "Cloud API - Claude models",
        anthropic_key,
    )

    # OpenRouter - ADD THIS SECTION
    openrouter_key = "Yes" if os.getenv("OPENROUTER_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "OpenRouter",
        "devstral-2512, openrouter/* (any OpenRouter model)",
        "Cloud API - Access to multiple models via OpenRouter",
        openrouter_key,
    )

    console.print(table)
    console.print(
        "\n[dim]Note: Provider is auto-detected from model name. Use --provider to override.[/dim]"
    )
```

### 1.2 Update `validate_provider_setup()` Function

**Current Location**: Lines 90-143  
**Current State**: Missing OpenRouter API key validation

**Required Change**:
```python
def validate_provider_setup(model: str, provider_override: Optional[str] = None) -> bool:
    """Validate that provider is properly set up"""
    try:
        provider = ProviderFactory.get_provider(model, provider_override)

        # Check API key for cloud providers
        if not provider.validate_api_key():
            provider_name = ProviderFactory.get_provider_name(model)
            if provider_name == "deepseek":
                console.print(
                    Panel(
                        "[red]Error:[/red] DEEPSEEK_API_KEY not set\n\n"
                        "Get your API key from: [cyan]https://platform.deepseek.com/[/cyan]\n\n"
                        "Set it with:\n"
                        "  [cyan]export DEEPSEEK_API_KEY=your_key_here[/cyan]",
                        title="API Key Required",
                        border_style="red",
                    )
                )
            elif provider_name == "anthropic":
                console.print(
                    Panel(
                        "[red]Error:[/red] ANTHROPIC_API_KEY not set\n\n"
                        "Get your API key from: [cyan]https://console.anthropic.com/[/cyan]\n\n"
                        "Set it with:\n"
                        "  [cyan]export ANTHROPIC_API_KEY=your_key_here[/cyan]",
                        title="API Key Required",
                        border_style="red",
                    )
                )
            # ADD OPENROUTER CHECK
            elif provider_name == "openrouter":
                console.print(
                    Panel(
                        "[red]Error:[/red] OPENROUTER_API_KEY not set\n\n"
                        "Get your API key from: [cyan]https://openrouter.ai/[/cyan]\n\n"
                        "Set it with:\n"
                        "  [cyan]export OPENROUTER_API_KEY=your_key_here[/cyan]",
                        title="API Key Required",
                        border_style="red",
                    )
                )
            return False

        # Check Ollama connection if using Ollama provider
        provider_name = ProviderFactory.get_provider_name(model)
        if provider_name == "ollama" and not check_ollama():
            console.print(
                Panel(
                    "[red]Error:[/red] Cannot connect to Ollama\n\n"
                    "Make sure Ollama is running:\n"
                    "  [cyan]ollama serve[/cyan]\n\n"
                    "And you have a model pulled:\n"
                    "  [cyan]ollama pull llama3.2[/cyan]",
                    title="Ollama Not Found",
                    border_style="red",
                )
            )
            return False

        return True
    except ProviderError as e:
        console.print(
            Panel(f"[red]Error:[/red] {str(e)}", title="Provider Error", border_style="red")
        )
        return False
```

## 2. Documentation Updates

### 2.1 README.md Updates

#### Section 1: Features (Line 7)
```markdown
**Before**: "- **Flexible Models**: Use local models (Ollama) or cloud APIs (DeepSeek, Anthropic Claude)"
**After**: "- **Flexible Models**: Use local models (Ollama) or cloud APIs (DeepSeek, Anthropic Claude, OpenRouter)"
```

#### Section 2: Add OpenRouter API Setup (After Anthropic section, Line 140)
```markdown
#### OpenRouter API

1. Get your API key from [OpenRouter](https://openrouter.ai/)
2. Set environment variable:
   ```bash
   export OPENROUTER_API_KEY=your_key_here
   ```
3. Optionally set referral headers for OpenRouter rankings:
   ```bash
   export OPENROUTER_HTTP_REFERER="https://your-domain.com"
   export OPENROUTER_X_TITLE="Your App Name"
   ```
4. Use OpenRouter models:
   ```bash
   cortex --model devstral-2512
   cortex --model openrouter/meta-llama/llama-3.3-70b-instruct
   ```
```

#### Section 3: Provider Auto-Detection (Lines 150-157)
```markdown
**Before**:
- Models starting with `deepseek-` → DeepSeek API
- Models starting with `claude-` → Anthropic API
- All others → Ollama (local)

**After**:
- Models starting with `deepseek-` → DeepSeek API
- Models starting with `claude-` → Anthropic API
- Models containing `devstral` or starting with `openrouter/` → OpenRouter API
- All others → Ollama (local)
```

#### Section 4: Different Models Examples (Lines 100-114)
```markdown
**Add to Cloud APIs section**:
```bash
# Use OpenRouter (access to multiple providers)
cortex --model devstral-2512
cortex --model openrouter/meta-llama/llama-3.3-70b-instruct
```
```

#### Section 5: Cost Comparison Table (Lines 164-173)
```markdown
**Add row**:
| **OpenRouter Models** | OpenRouter | Varies by model | Varies by model | Access to multiple providers |
```

### 2.2 docs/COMMANDS.md Updates

#### Section: Cloud Models (Lines 61-70)
```markdown
**Add after Anthropic section**:
# OpenRouter (requires OPENROUTER_API_KEY)
localagent --model devstral-2512
localagent --model openrouter/meta-llama/llama-3.3-70b-instruct
```

#### Section: Provider Selection (Line 78)
```markdown
**Before**: "Options: `ollama`, `deepseek`, `anthropic`."
**After**: "Options: `ollama`, `deepseek`, `anthropic`, `openrouter`."
```

#### Section: Examples (Lines 80-84)
```markdown
**Add example**:
localagent --provider openrouter --model devstral-2512
```

### 2.3 CHANGELOG_CLOUD_API.md Updates

#### Add OpenRouter Section
```markdown
### OpenRouter Integration (2024-01-14)

- Added `OpenRouterProvider` for OpenRouter API access
- Supports models like `devstral-2512` and any OpenRouter model
- Uses OpenAI-compatible API with OpenRouter-specific headers
- Added comprehensive unit tests
- Updated provider factory auto-detection logic
- Added OpenRouter to CLI provider listing
- Added OpenRouter API key validation
```

## 3. Help System Updates

### 3.1 cortex/help/content.py

Check if there are provider-specific help entries. If the help system has model/provider documentation, add OpenRouter information.

**Search for existing provider mentions**: None found, but if added later, include OpenRouter.

## 4. Configuration File Updates

### 4.1 config/default.yaml

**Optional**: Add commented OpenRouter example
```yaml
# OpenRouter models: devstral-2512, openrouter/*
# provider: openrouter  # Uncomment to force OpenRouter provider
```

## 5. Additional Considerations

### 5.1 Environment Variable Documentation

Create or update environment variable documentation:
```markdown
### OpenRouter Environment Variables

- `OPENROUTER_API_KEY`: Required for OpenRouter API access
- `OPENROUTER_HTTP_REFERER`: Optional referral URL for OpenRouter rankings
- `OPENROUTER_X_TITLE`: Optional application title for OpenRouter
```

### 5.2 Error Message Consistency

Ensure all OpenRouter error messages follow the same pattern as other providers:
- Clear instruction with correct URL
- Environment variable syntax
- Consistent formatting

### 5.3 Test Coverage Verification

Verify existing tests cover:
- [x] OpenRouterProvider unit tests
- [ ] CLI integration with OpenRouter
- [ ] Error handling for missing API key
- [ ] Provider factory integration

## 6. Implementation Checklist

### High Priority
- [ ] Update `cortex/cli.py` `list_providers()` function
- [ ] Update `cortex/cli.py` `validate_provider_setup()` function  
- [ ] Update README.md Cloud API Setup section
- [ ] Update README.md Provider Auto-Detection section
- [ ] Update README.md Features list
- [ ] Update docs/COMMANDS.md Cloud Models section
- [ ] Update docs/COMMANDS.md Provider Selection section

### Medium Priority
- [ ] Update README.md Cost Comparison table
- [ ] Update README.md Different Models examples
- [ ] Update CHANGELOG_CLOUD_API.md
- [ ] Add OpenRouter to config/default.yaml comments

### Low Priority
- [ ] Check and update help system if needed
- [ ] Create OpenRouter-specific documentation page
- [ ] Add integration tests for OpenRouter

## 7. Testing Plan

### 7.1 Manual Testing Steps
1. Set OpenRouter API key: `export OPENROUTER_API_KEY=test_key`
2. Test provider listing: `cortex --list-providers`
3. Test model auto-detection: `cortex --model devstral-2512 --plan-mode -p "test"`
4. Test explicit provider: `cortex --provider openrouter --model test-model --plan-mode -p "test"`
5. Test missing API key error: `unset OPENROUTER_API_KEY; cortex --model devstral-2512`
6. Test with referral headers: `export OPENROUTER_HTTP_REFERER="http://test.com"; export OPENROUTER_X_TITLE="Test"`

### 7.2 Automated Test Verification
- Run existing unit tests: `pytest tests/unit/core/test_openrouter_provider.py -v`
- Run all provider tests: `pytest tests/unit/core/test_providers*.py -v`
- Run CLI tests: `pytest tests/test_cli_commands.py -v`

## 8. Rollout Strategy

### Phase 1: Documentation Updates
Update all documentation first as these are non-breaking changes.

### Phase 2: CLI Updates
Update CLI functions to include OpenRouter.

### Phase 3: Verification
Test thoroughly with actual OpenRouter API key if available.

### Phase 4: Announcement
Update changelog and consider release notes if making a new release.

## 9. Risk Assessment

### Low Risk
- Documentation updates are safe
- CLI updates are additive (adding new provider, not modifying existing logic)
- No breaking changes to existing functionality

### Medium Risk
- Potential for OpenRouter-specific bugs in provider implementation
- API key validation might have edge cases

### Mitigation
- Comprehensive testing
- Clear error messages
- Fallback to other providers if OpenRouter fails

## 10. Timeline

**Estimated Effort**: 2-4 hours for all changes  
**Priority**: High (OpenRouter is technically implemented but unusable without these updates)

---

## Appendix A: Code Change Diffs

### cortex/cli.py diff
```diff
@@ -75,6 +75,13 @@ def list_providers():
         "Cloud API - Claude models",
         anthropic_key,
     )
+    
+    # OpenRouter
+    openrouter_key = "Yes" if os.getenv("OPENROUTER_API_KEY") else "[red]Yes (not set)[/red]"
+    table.add_row(
+        "OpenRouter", "devstral-2512, openrouter/* (any OpenRouter model)",
+        "Cloud API - Access to multiple models via OpenRouter", openrouter_key
+    )
 
     console.print(table)
     console.print(
@@ -109,6 +116,17 @@ def validate_provider_setup(model: str, provider_override: Optional[str] = None)
                         title="API Key Required",
                         border_style="red",
                     )
+                )
+            elif provider_name == "openrouter":
+                console.print(
+                    Panel(
+                        "[red]Error:[/red] OPENROUTER_API_KEY not set\n\n"
+                        "Get your API key from: [cyan]https://openrouter.ai/[/cyan]\n\n"
+                        "Set it with:\n"
+                        "  [cyan]export OPENROUTER_API_KEY=your_key_here[/cyan]",
+                        title="API Key Required",
+                        border_style="red",
+                    )
                 )
             return False
```

### README.md diff examples
(Similar diffs for each section as outlined above)

---

**Last Updated**: 2024-01-15  
**Status**: Ready for Implementation