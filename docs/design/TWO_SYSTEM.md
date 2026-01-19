┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
                                        Executive Summary

```

Currently, Cortex's --routing flag confusingly enables both pre-conversation model selection (routing)

and mid-conversation model handoffs (delegation). This plan outlines how to separate these distinct

capabilities into clear, independent flags with proper integration.

```
                                 Current Architecture Assessment

                                        Existing Systems

```

1 Routing System (core/routing/): Intelligent model selection based on task analysis
• Status: Fully implemented but unused
• Entry point: route_request() method (not integrated)
2 Delegation System (core/orchestration.py): Model-to-model task delegation
• Status: Enabled by default but not exposed
• Entry point: delegate_to_model() tool
3 Configuration Defaults:
• Routing: Disabled (enabled: false)
• Orchestration: Enabled (enabled: true)
• Default coordinator: "xiaomi/mimo-v2-flash:free"

```
                            Phase 1: Flag Separation and CLI Changes

                                  1.1 Add New --delegation Flag

```

File: cortex/cli.py

# Add to argument parser (around line 203)

parser.add_argument(
"--delegation",
action="store_true",
help="Enable model-to-model delegation (mid-conversation handoffs)"
)

# Update routing flag help text

parser.add_argument(
"--routing",
action="store_true",
help="Enable intelligent model routing (pre-conversation model selection)"
)

```
                                1.2 Separate Configuration Logic

```

File: cortex/cli.py (lines 277-293)

# SEPARATED: Routing configuration only

if args.routing:
config.routing["enabled"] = True
console.print("[cyan]Intelligent model routing enabled[/cyan]")

# NEW: Delegation configuration

if args.delegation:
# Ensure orchestration config exists
if not hasattr(config, "orchestration"):
config.orchestration = {}
config.orchestration["enabled"] = True

```
 # Set default coordinator if no model specified
 if not args.model:
     config.model = "xiaomi/mimo-v2-flash:free"
     config.provider = "openrouter"
     console.print("[cyan]Model delegation enabled - using xiaomi/mimo-v2-flash:free as

```

coordinator[/cyan]")
else:
console.print("[cyan]Model delegation enabled (self-orchestrating models)[/cyan]")

```
                                1.3 Update Default Configuration

```

File: cortex/config.py (line 278)

# Disable orchestration by default for clear opt-in

self._orchestration_enabled = orchestration_config.get("enabled", False)  # Changed from True

```
                                  1.4 Update Help Documentation

```

File: docs/CLI_REFERENCE.md

## New Flags

### `-delegation`

Enables model-to-model delegation during conversation. Models can hand off tasks to specialized models

when appropriate.

**Examples:**

```bash
cortex --delegation  # Enable delegation with default coordinator
cortex --delegation --model llama3.3:70b  # Use specific model as coordinator

                                               --routing

Enables intelligent pre-conversation model selection. Analyzes the task and selects optimal model.

Examples:

cortex --routing  # Enable intelligent routing
cortex --routing --delegation  # Enable both systems

                                            Combined Usage

• --routing only: Choose best model initially, no mid-conversation switches
• --delegation only: Start with specified/default model, allow delegation when needed
• Both flags: Intelligent initial selection + dynamic handoffs

## Phase 2: Routing System Integration

### 2.1 Integrate `route_request()` into Main Loop
**File:** `cortex/agent.py`
```python
def _process_user_request(self, user_request: str) -> None:
    """Process a single user request with optional routing."""

    # PHASE 2: Add routing decision if enabled
    routing_decision = None
    if self._routing_enabled and self.router:
        routing_decision = self.route_request(user_request)

        if routing_decision and routing_decision.target_model != self.model:
            # Switch to routed model
            self.switch_model(
                routing_decision.target_model,
                f"Routing decision: {routing_decision.reasoning.summary}"
            )

    # Continue with existing processing...

                                     2.2 Add Routing Display to UI

File: cortex/ui/console.py

def show_routing_decision(self, decision: RoutingDecision) -> None:
    """Display routing decision to user."""
    if not decision:
        return

    self.print(Panel.fit(
        f"[bold cyan]Routing Decision[/bold cyan]\\n\\n"
        f"Selected Model: [bold]{decision.target_model}[/bold]\\n"
        f"Provider: {decision.target_provider}\\n"
        f"Reason: {decision.reasoning.summary}\\n"
        f"Confidence: {decision.confidence:.1%}\\n"
        f"Estimated Cost: ${decision.cost_estimate.total_cost:.4f}",
        title="🤖 Intelligent Routing",
        border_style="cyan"
    ))

                                      2.3 Add Routing Statistics

File: cortex/core/routing/orchestrator.py

def get_statistics(self) -> Dict[str, Any]:
    """Get routing statistics for display."""
    return {
        "total_requests": self.stats["total_requests"],
        "cache_hits": self.stats["cache_hits"],
        "cache_misses": self.stats["cache_misses"],
        "avg_analysis_time_ms": (
            self.stats["task_analysis_time_ms"] / max(1, self.stats["total_requests"])
        ),
        "success_rate": (
            (self.stats["total_requests"] - self.stats["errors"]) /
            max(1, self.stats["total_requests"])
        )
    }

                            Phase 3: Enhanced Coordination Between Systems

                                     3.1 Routing-Aware Delegation

File: cortex/core/routing/orchestrator.py

def route_request_with_delegation(
    self,
    user_request: str,
    context: Optional[RoutingContext] = None,
    allow_delegation: bool = True
) -> RoutingDecision:
    """
    Route request considering delegation capabilities.

    Args:
        allow_delegation: If True, may select coordinator models that can delegate
    """
    decision = self.route_request(user_request, context)

    if allow_delegation:
        # Enhance decision with delegation info
        model_registry = get_model_registry()
        model_config = model_registry.get_model(decision.target_model)

        if model_config and model_config.can_delegate:
            decision.metadata["supports_delegation"] = True
            decision.metadata["delegation_targets"] = (
                model_registry.get_delegation_targets(decision.target_model)
            )

    return decision

                                   3.2 Combined System Transparency

File: cortex/core/transparency.py

def show_combined_decision(
    routing_decision: Optional[RoutingDecision],
    delegation_context: Optional[DelegationContext]
) -> None:
    """Show combined routing + delegation information."""

    lines = []

    if routing_decision:
        lines.extend([
            f"[bold]Initial Routing:[/bold]",
            f"  Model: {routing_decision.target_model}",
            f"  Reason: {routing_decision.reasoning.summary}",
            ""
        ])

    if delegation_context:
        lines.extend([
            f"[bold]Delegation Context:[/bold]",
            f"  Coordinator: {delegation_context.coordinator_model}",
            f"  Remaining Delegations: {delegation_context.remaining_delegations}",
            f"  History: {len(delegation_context.delegation_history)} handoffs",
            ""
        ])

    if lines:
        console.print(Panel.fit("\\n".join(lines), title="🔄 Model Coordination"))

                                     3.3 Configuration Validation

File: cortex/config.py

def validate_orchestration_config(self) -> List[str]:
    """Validate orchestration configuration."""
    warnings = []

    # Check if routing enabled but provider can't route
    if self.routing.get("enabled", False):
        if self.provider == "ollama":
            # Ollama has limited routing capabilities
            warnings.append(
                "Routing with Ollama provider may have limited model selection. "
                "Consider using OpenRouter for full routing capabilities."
            )

    # Check if delegation enabled but no coordinator model
    orchestration_config = getattr(self, "orchestration", {})
    if orchestration_config.get("enabled", False):
        if not self.model:
            warnings.append(
                "Delegation enabled but no model specified. "
                "Using default coordinator: xiaomi/mimo-v2-flash:free"
            )

    return warnings

                                    Phase 4: Testing and Validation

                                          4.1 Test Scenarios

# Test file: tests/test_routing_delegation.py

class TestSeparatedSystems:
    """Test routing and delegation as separate systems."""

    def test_routing_only(self):
        """Test --routing flag without delegation."""
        agent = Cortex(routing=True, delegation=False)
        # Should use routing but not show delegation tools
        assert agent._routing_enabled is True
        assert agent._orchestration_enabled is False
        assert "delegate_to_model" not in agent.get_available_tools()

    def test_delegation_only(self):
        """Test --delegation flag without routing."""
        agent = Cortex(routing=False, delegation=True)
        # Should have delegation enabled but no pre-routing
        assert agent._routing_enabled is False
        assert agent._orchestration_enabled is True
        assert "delegate_to_model" in agent.get_available_tools()

    def test_combined_systems(self):
        """Test both flags together."""
        agent = Cortex(routing=True, delegation=True)
        # Should have both systems active
        assert agent._routing_enabled is True
        assert agent._orchestration_enabled is True
        # Should show delegation in routing decisions
        decision = agent.route_request("Write complex Python code")
        assert decision.metadata.get("supports_delegation") is True

    def test_flag_independence(self):
        """Test that flags don't affect each other."""
        # Default state
        agent1 = Cortex()
        assert agent1._routing_enabled is False
        assert agent1._orchestration_enabled is False

        # Only routing
        agent2 = Cortex(routing=True)
        assert agent2._routing_enabled is True
        assert agent2._orchestration_enabled is False

        # Only delegation
        agent3 = Cortex(delegation=True)
        assert agent3._routing_enabled is False
        assert agent3._orchestration_enabled is True

                                         4.2 Integration Tests

# Test actual workflow scenarios

def test_coding_task_with_routing():
    """Test coding task gets routed to coding-specialized model."""
    agent = Cortex(routing=True)
    decision = agent.route_request("Write a Python REST API with FastAPI")
    assert "code" in decision.reasoning.keywords
    assert decision.target_model in ["gpt-4", "claude-3-opus", "llama-code"]

def test_security_task_with_delegation():
    """Test security analysis delegates to specialist."""
    agent = Cortex(delegation=True, model="llama3.2")
    # Simulate delegation request
    result = agent._handle_delegation_action({
        "action": "delegate",
        "target_model": "security-specialist",
        "reason": "Security analysis requires specialized knowledge"
    })
    assert result is True
    assert agent.model == "security-specialist"

def test_combined_workflow():
    """Test complete workflow: route -> process -> delegate."""
    agent = Cortex(routing=True, delegation=True)

    # Initial routing for complex task
    decision = agent.route_request("Analyze this code for security vulnerabilities")
    assert decision.target_model == "security-specialist"

    # Model decides to delegate specific aspect
    delegation_result = agent._handle_delegation_action({
        "action": "delegate",
        "target_model": "malware-analysis",
        "reason": "Found suspicious code patterns"
    })
    assert delegation_result is True

                               Phase 5: Documentation and User Guidance

                                        5.1 Updated User Guide

File: docs/USER_GUIDE.md

## Model Coordination Features

Cortex now offers two distinct model coordination features:

### Intelligent Routing (`--routing`)
*Analyzes your request before processing and selects the optimal model.*

**When to use:**
- Starting complex, unfamiliar tasks
- Cost optimization across providers
- Ensuring task-type/model alignment

**Example:**
```bash
cortex --routing
> "Write a neural network in PyTorch"
# Router selects GPT-4 for complex coding task

                                    Model Delegation (--delegation)

Allows models to hand off tasks to specialists during conversation.

When to use:

• Multi-step tasks requiring different expertise
• When stuck on specific sub-tasks
• Collaborative problem solving

Example:

cortex --delegation --model llama3.2
> "First help me code, then analyze for security issues"
# llama3.2 codes, then delegates to security specialist

                                            Combined Power

cortex --routing --delegation
# Best of both: optimal initial selection + dynamic handoffs

                                      5.2 Configuration Examples

File: config/examples/routing_delegation.yaml

# Example 1: Routing only (no mid-conversation switches)
routing:
  enabled: true
  mode: "rule_based"
  prefer_local_models: true
  allow_cloud_fallback: true

# Example 2: Delegation only (start with trusted model)
orchestration:
  enabled: true
  default_model: "llama3.2"  # Trusted coordinator
  max_delegations_per_request: 3

# Example 3: Combined with preferences
routing:
  enabled: true
  task_analysis_enabled: true
  cost_optimization_enabled: true

orchestration:
  enabled: true
  default_model: "auto"  # Let router decide
  allowed_delegation_targets:
    - "code-specialist"
    - "security-analyst"
    - "documentation-writer"

                             Phase 6: Migration and Backward Compatibility

                                   6.1 Legacy --routing Flag Support

File: cortex/cli.py

def _handle_legacy_routing_flag(self, args):
    """
    Handle legacy --routing flag that enabled both systems.
    Provides migration path with warning.
    """
    if args.routing and not args.delegation:
        # Legacy behavior: enable both
        console.print("[yellow]Warning:[/yellow] Legacy --routing flag detected.")
        console.print("  This flag previously enabled both routing AND delegation.")
        console.print("  Consider using: --routing --delegation (explicit)")
        console.print("  Or just: --routing (routing only, new default)")

        # Ask user preference
        response = input("Enable delegation as well? (y/N): ").strip().lower()
        if response == 'y':
            args.delegation = True
            console.print("[cyan]Both routing and delegation enabled[/cyan]")
        else:
            console.print("[cyan]Routing only enabled (new behavior)[/cyan]")

    return args

                                      6.2 Configuration Migration

File: cortex/config.py

def migrate_legacy_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate legacy config where routing enabled both systems.
    """
    if config_dict.get("routing", {}).get("enabled", False):
        # Check if this is legacy config (orchestration not explicitly set)
        if "orchestration" not in config_dict:
            config_dict["orchestration"] = {"enabled": True}
            config_dict["_migrated"] = True
            config_dict["_migration_note"] = (
                "Legacy routing config migrated to separate systems. "
                "Update to explicit routing/delegation settings."
            )

    return config_dict

                                        Implementation Timeline

                                          Week 1: Foundation

• [ ] Phase 1.1: Add --delegation flag
• [ ] Phase 1.2: Separate configuration logic
• [ ] Phase 1.3: Update default configuration
• [ ] Basic unit tests for flag parsing

                                      Week 2: Routing Integration

• [ ] Phase 2.1: Integrate route_request() into main loop
• [ ] Phase 2.2: Add routing display to UI
• [ ] Phase 2.3: Add routing statistics
• [ ] Integration tests for routing workflow

                                     Week 3: Enhanced Coordination

• [ ] Phase 3.1: Routing-aware delegation
• [ ] Phase 3.2: Combined system transparency
• [ ] Phase 3.3: Configuration validation
• [ ] Test combined workflows

                                   Week 4: Polish and Documentation

• [ ] Phase 4: Comprehensive testing suite
• [ ] Phase 5: User documentation
• [ ] Phase 6: Migration path
• [ ] Performance benchmarking

                                            Success Metrics

1 Clear Separation: Users understand difference between routing and delegation
2 Independent Functionality: Each system works alone and together
3 Performance: Routing adds <100ms overhead, delegation <500ms handoff
4 Adoption: >80% of users use explicit flags within 1 month
5 Error Reduction: <5% configuration-related support requests

                                         Risks and Mitigations

 Risk                          Impact   Mitigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Breaking existing workflows   High     Phase 6 migration path with warnings
 Performance degradation       Medium   Benchmarking, caching optimizations
 User confusion                Medium   Clear documentation, interactive prompts
 Increased complexity          Low      Gradual rollout, user feedback loops

                                              Conclusion

This plan provides a clear path to separate Cortex's routing and delegation systems, addressing the
current confusion while leveraging existing infrastructure. The phased approach ensures backward
compatibility while delivering clearer user experience and more flexible configuration options.

The separation aligns with the architectural reality of two distinct systems and empowers users with
precise control over model coordination behavior.
```