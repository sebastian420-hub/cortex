# Routing and Delegation System Separation Plan

**Document Status**: Research & Planning
**Created**: January 2026
**Scope**: System Architecture Separation, Prompt Framework Design

---

## Executive Summary

This document presents a comprehensive analysis of Cortex's two model coordination systems—**Routing** and **Delegation**—and proposes a clear separation strategy with an enhanced prompt framework that gives models a structured decision-making framework for delegation.

### Key Findings

1. **Routing** (pre-conversation) and **Delegation** (mid-conversation) are fundamentally different concerns that are currently conflated
2. The current prompt system lacks a structured decision framework for delegation
3. Models need explicit "when/why/how" guidance, not just capability descriptions
4. State tracking between delegations is weak (empty decisions, wrong file tracking)
5. The two systems can work synergistically when properly integrated

---

## Part 1: System Analysis

### 1.1 Current Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT STATE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                    ┌─────────────────┐                 │
│  │  ROUTING SYSTEM │                    │ DELEGATION SYSTEM│                │
│  │  (core/routing/)│                    │(core/orchestration)               │
│  │                 │                    │                  │                 │
│  │  Pre-conversation                    │ Mid-conversation │                 │
│  │  model selection                     │ model handoffs   │                 │
│  │                 │                    │                  │                 │
│  │  Status: Built  │                    │  Status: Built   │                 │
│  │  but UNUSED     │                    │  but WEAK        │                 │
│  └────────┬────────┘                    └────────┬─────────┘                │
│           │                                      │                           │
│           └──────────────┬───────────────────────┘                          │
│                          │                                                   │
│                          ▼                                                   │
│                   ┌──────────────┐                                           │
│                   │ --routing    │  ← Currently enables BOTH                 │
│                   │ flag         │    (confusing!)                           │
│                   └──────────────┘                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Routing System (core/routing/)

**Purpose**: Intelligent model selection BEFORE conversation begins

**Components**:
- `task_analysis.py` - Keyword-based task classification (9 types + complexity scoring)
- `orchestrator.py` - Decision engine with caching, fallbacks
- `factory.py` - Provider mapping and instantiation
- `cost_tracking.py` - Cost estimation and tracking
- `transparency.py` - Decision logging and display

**How It Works**:
```
User Request → Task Analysis → Model Selection → Provider Setup → Begin Conversation
```

**Current Status**: ✅ Fully built, ❌ Not integrated into agent loop

**Strengths**:
- Sophisticated task classification
- Cost-aware model selection
- Transparent decision logging
- Caching for performance

**Weaknesses**:
- Never called from agent.py
- No UI feedback for routing decisions
- Keyword-based analysis can miss nuance

### 1.3 Delegation System (core/orchestration.py)

**Purpose**: Allow models to hand off work to specialists DURING conversation

**Components**:
- `DelegationTracker` - Quota management (max 5 per request)
- `DelegationContext` - State container for handoffs
- `OrchestrationManager` - Central coordinator
- `delegation_tools.py` - Tools models use to delegate

**How It Works**:
```
Model A working → Recognizes need → delegate_to_model() → Model B continues
```

**Current Status**: ✅ Enabled by default, ⚠️ Weak state tracking

**Strengths**:
- Full conversation history preservation
- Loop prevention via quota
- Explicit handoff notes

**Critical Weaknesses**:
1. **State Summary is Broken**:
   ```python
   def _get_state_summary(self):
       return {
           "files_read": list(set(self._tools_used))[:20],  # WRONG: Uses tool names!
           "decisions": [],  # ALWAYS EMPTY!
           "current_model": self.model,
       }
   ```
2. **Returns count toward quota** (questionable design)
3. **No cost awareness** before delegating to expensive models
4. **No integration with routing** for initial model choice

### 1.4 Prompt System (core/prompts/)

**Components**:
- `profiles.py` - Role-based prompt profiles (coordinator, reasoner, coder, etc.)
- `builder.py` - Dynamic prompt construction based on model capabilities
- `adapters.py` - Model family-specific adaptations

**Current Profile Structure**:
```python
PromptProfile:
    name: str
    role_description: str        # What you are
    capabilities: List[str]      # What you can do
    workflow: str                # How you work
    delegation_guidance: str     # When to delegate
    return_guidance: str         # When to return
```

**Critical Gaps**:
1. **No Decision Framework** - Profiles describe "when to delegate" but don't provide a structured decision process
2. **No Task Assessment Protocol** - Models don't know how to evaluate if delegation is needed
3. **No Cost/Capability Matching** - No guidance on choosing WHICH specialist
4. **No Context Verification** - Models don't verify they have sufficient context before delegating

---

## Part 2: Problems Identified

### 2.1 System Separation Issues

| Problem | Impact | Root Cause |
|---------|--------|------------|
| Single `--routing` flag enables both systems | User confusion | Design conflation |
| Routing decisions not displayed to user | No transparency | Missing UI integration |
| Delegation ignores routing suggestions | Inefficient model selection | No cross-system communication |
| No flag for delegation-only mode | Limited control | Missing CLI option |

### 2.2 Delegation Prompt Issues

| Problem | Impact | Root Cause |
|---------|--------|------------|
| Vague "when to delegate" guidance | Inconsistent delegation | No decision framework |
| No task complexity assessment | Over/under-delegation | Missing assessment protocol |
| No specialist selection criteria | Wrong specialist chosen | Capability not matched to task |
| No context verification step | Incomplete handoffs | Missing pre-delegation checklist |
| Empty decisions array | Lost decision context | No memory bank integration |
| Wrong file tracking | Misleading state | Uses tool names instead of files |

### 2.3 Cross-System Issues

| Problem | Impact | Root Cause |
|---------|--------|------------|
| Routing and delegation don't share task analysis | Duplicate work | Isolated systems |
| Delegation doesn't consider model costs | Budget overruns | No cost awareness |
| No performance metrics | Can't optimize | Missing telemetry |
| Routing can't suggest delegation targets | Missed opportunities | One-way information flow |

---

## Part 3: Proposed Solution Architecture

### 3.1 System Separation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROPOSED STATE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                    ┌─────────────────┐                 │
│  │  ROUTING SYSTEM │                    │ DELEGATION SYSTEM│                │
│  │                 │                    │                  │                 │
│  │  --routing flag │                    │  --delegation    │                 │
│  │                 │                    │  flag            │                 │
│  └────────┬────────┘                    └────────┬─────────┘                │
│           │                                      │                           │
│           │    ┌──────────────────────┐         │                           │
│           └───→│ Shared Task Analysis │←────────┘                           │
│                └──────────┬───────────┘                                     │
│                           │                                                  │
│                           ▼                                                  │
│              ┌────────────────────────┐                                     │
│              │ Unified Cost Tracker   │                                     │
│              └────────────────────────┘                                     │
│                                                                              │
│  Modes:                                                                      │
│  • --routing only     : Smart initial selection, no mid-conversation switch │
│  • --delegation only  : Manual initial model, allow mid-conversation switch │
│  • --routing --delegation : Best of both worlds                             │
│  • Neither (default)  : Use specified model, no switches                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 CLI Changes

```bash
# Proposed flag structure
cortex                              # Default: no routing, no delegation
cortex --routing                    # Pre-conversation routing only
cortex --delegation                 # Mid-conversation delegation only
cortex --routing --delegation       # Both systems active

# With model override
cortex --routing --model llama3.2   # Route but suggest, use llama as fallback
cortex --delegation --model mimo    # Start with mimo, allow delegation
```

### 3.3 Configuration Structure

```yaml
# config.yaml proposed structure

routing:
  enabled: false                    # Explicit opt-in
  mode: "rule_based"               # Phase 1: rule_based, Phase 2: ai_assisted
  task_analysis_enabled: true
  prefer_local_models: true
  cost_optimization_enabled: true
  display_decisions: true           # NEW: Show routing decisions

delegation:
  enabled: false                    # Explicit opt-in (separate from routing)
  max_delegations_per_request: 5
  count_returns_as_delegation: false  # NEW: Don't penalize returns
  cost_warning_threshold: 0.10     # NEW: Warn before expensive delegates
  require_context_verification: true  # NEW: Force context check

shared:
  task_analysis_cache: true        # Share analysis between systems
  unified_cost_tracking: true       # Single cost tracker
```

---

## Part 4: Enhanced Prompt Framework for Delegation

### 4.1 The Problem with Current Prompts

Current prompts tell models WHAT they can do but not HOW to decide:

```markdown
# CURRENT (Vague)
"Delegate when you recognize:
- Complex planning/reasoning → deepseek-reasoner
- Code implementation → gpt-5.1-codex-mini"
```

This leads to:
- Inconsistent delegation decisions
- Wrong specialist selection
- Incomplete context handoffs

### 4.2 Proposed: Structured Decision Framework

Replace vague guidance with a **Decision Protocol** that models must follow:

```markdown
# PROPOSED: Delegation Decision Protocol

## Before Delegating: The 4-Check Framework

### Check 1: NECESSITY Assessment
Ask yourself:
- Can I complete this task with my current capabilities? (Yes → Don't delegate)
- Is this task outside my expertise area? (Yes → Consider delegation)
- Would a specialist complete this significantly better? (Yes → Consider delegation)
- Is the task simple enough that delegation overhead > benefit? (Yes → Don't delegate)

Delegation is EXPENSIVE (uses quota, adds latency). Only delegate when clear benefit.

### Check 2: CONTEXT Verification
Before delegating, verify you have:
□ Clear task description (what needs to be done)
□ Relevant files identified (which files are involved)
□ Constraints documented (what must/must not happen)
□ Success criteria defined (how to know task is complete)

If any box is unchecked, gather more context first.

### Check 3: SPECIALIST Selection
Match task to specialist based on capabilities:

| Task Type | Best Specialist | Fallback | Avoid |
|-----------|-----------------|----------|-------|
| Architecture/Planning | deepseek-reasoner | hermes-3-405b | coders |
| Code Implementation | gpt-5.1-codex-mini | grok-code-fast-1 | reviewers |
| Complex Debugging | hermes-3-405b | deepseek-reasoner | researchers |
| Security Review | dolphin-24b | hermes-3-405b | coders |
| Web Research | sonar-pro-search | (none - return to coordinator) | all others |

### Check 4: HANDOFF Preparation
Your handoff notes MUST include:
1. **Task**: Clear, actionable description
2. **Context**: What you've learned so far
3. **Files**: Specific files to examine/modify
4. **Constraints**: What must be preserved
5. **Expected Outcome**: What success looks like

## After Receiving Delegation: The 3-Step Protocol

### Step 1: ACKNOWLEDGE
Confirm you understand:
- Who delegated to you and why
- What specific task you're assigned
- What context/files are provided
- How many delegations remain

### Step 2: EXECUTE
Work efficiently:
- Don't re-read files already examined (check handoff notes)
- Focus on your specific task
- Document decisions as you make them
- Stop if you need information not provided

### Step 3: RETURN
When complete, provide:
- Summary of what was accomplished
- List of files changed
- Any issues or concerns
- Recommendations for next steps
```

### 4.3 Updated Profile Structure

```python
@dataclass
class EnhancedPromptProfile:
    """Enhanced prompt profile with decision framework."""

    name: str
    role_description: str
    capabilities: List[str]

    # NEW: Structured decision components
    delegation_decision_tree: str      # Decision tree for when to delegate
    specialist_matching_table: str     # Table mapping tasks to specialists
    context_checklist: List[str]       # Required context before delegating
    handoff_template: str              # Template for handoff notes

    # NEW: Receiving delegation
    acknowledgment_protocol: str       # How to confirm understanding
    execution_guidelines: str          # How to work on delegated task
    return_template: str               # Template for return summary

    # Existing
    workflow: str
    return_guidance: str
```

### 4.4 Decision Tree Visualization

Include in prompts for visual clarity:

```
                    ┌─────────────────────┐
                    │ New Task/Subtask    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Can I do this well? │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
         ┌────▼────┐                      ┌─────▼─────┐
         │  YES    │                      │    NO     │
         └────┬────┘                      └─────┬─────┘
              │                                 │
    ┌─────────▼─────────┐            ┌─────────▼─────────┐
    │ Is it complex     │            │ Identify needed   │
    │ enough to justify │            │ capability        │
    │ delegation?       │            └─────────┬─────────┘
    └─────────┬─────────┘                      │
              │                                │
    ┌────┬────┴────┬────┐           ┌─────────▼─────────┐
    │    │         │    │           │ Match to          │
   YES  MAYBE      NO   │           │ specialist        │
    │    │         │    │           └─────────┬─────────┘
    │    │         │    │                     │
    │    ▼         ▼    │           ┌─────────▼─────────┐
    │ Consider  Handle  │           │ Verify context    │
    │ yourself  self    │           │ is complete       │
    │    │              │           └─────────┬─────────┘
    │    │              │                     │
    ▼    ▼              │              ┌──────┴──────┐
 ┌──────────────┐       │              │             │
 │ Check 2-4    │       │           COMPLETE    INCOMPLETE
 │ then         │       │              │             │
 │ delegate     │       │              ▼             ▼
 └──────────────┘       │         DELEGATE      GATHER MORE
                        │                       CONTEXT
                        │
                        ▼
                   EXECUTE TASK
```

### 4.5 Example: Coordinator Profile with Framework

```python
COORDINATOR_PROFILE = EnhancedPromptProfile(
    name="Coordinator",
    role_description="""You are the main coordinator model. You:
1. Understand and clarify user requests
2. Decide if tasks need specialist help
3. Coordinate work between specialists
4. Synthesize results for users""",

    capabilities=[
        "Understanding user intent",
        "Task decomposition",
        "Coordination and synthesis",
        "General conversation",
    ],

    delegation_decision_tree="""
## Delegation Decision Tree

START: New user request or subtask
  │
  ├─► Simple question/clarification?
  │     └─► YES: Handle directly, NO delegation needed
  │
  ├─► File read/search?
  │     └─► YES: Use tools directly, NO delegation needed
  │
  ├─► Requires complex reasoning/planning?
  │     └─► YES: Check context → Delegate to deepseek-reasoner
  │
  ├─► Requires code implementation?
  │     └─► YES: Check context → Delegate to coder (gpt-5.1-codex-mini)
  │
  ├─► Requires debugging?
  │     └─► YES: Check context → Delegate to hermes-3-405b
  │
  ├─► Requires security analysis?
  │     └─► YES: Check context → Delegate to dolphin-24b
  │
  └─► Requires web research?
        └─► YES: Check context → Delegate to sonar-pro-search
""",

    specialist_matching_table="""
| Need | Delegate To | Why |
|------|-------------|-----|
| Multi-step plan | deepseek-reasoner | Excels at systematic breakdown |
| Write new code | gpt-5.1-codex-mini | Optimized for code generation |
| Fix bugs | hermes-3-405b | Strong at tracing and analysis |
| Security review | dolphin-24b | Specialized for vulnerability detection |
| Find docs/info | sonar-pro-search | Has web access |
""",

    context_checklist=[
        "Task description is clear and specific",
        "Relevant files have been identified",
        "Any constraints are documented",
        "Success criteria are defined",
    ],

    handoff_template="""
**Task**: [What needs to be done - be specific]

**Context**:
- [What I've learned so far]
- [Key decisions already made]

**Files**:
- [Specific files to examine]
- [Files to modify]

**Constraints**:
- [What must not change]
- [Requirements to respect]

**Expected Outcome**:
- [What success looks like]
- [How to verify completion]
""",

    acknowledgment_protocol="N/A - Coordinator receives final results",

    execution_guidelines="""
1. Synthesize specialist results
2. Verify task completion against original request
3. Communicate clearly with user
4. Suggest next steps if applicable
""",

    return_template="N/A - Coordinator reports to user directly",

    workflow="""
1. Receive user request
2. Analyze: Can I handle this directly?
3. If YES: Use tools, complete task
4. If NO: Run decision tree, delegate appropriately
5. When specialist returns: Verify, synthesize, respond to user
""",

    return_guidance="As coordinator, you report to the user, not another model.",
)
```

---

## Part 5: State Tracking Improvements

### 5.1 Fix Files Tracking

**Current (Broken)**:
```python
def _get_state_summary(self):
    return {
        "files_read": list(set(self._tools_used))[:20],  # Wrong!
```

**Proposed Fix**:
```python
def _get_state_summary(self) -> Dict[str, Any]:
    """Get accurate state summary for delegation context."""
    return {
        "files_read": list(self._files_accessed)[:20],  # Track actual files
        "files_modified": list(self._files_modified)[:10],  # Track writes
        "decisions": self._decision_log[:10],  # Real decisions
        "errors_encountered": self._errors[:5],  # Relevant errors
        "tools_used_count": len(self._tools_used),  # How many tool calls
        "current_model": self.model,
        "elapsed_time_seconds": time.time() - self._request_start_time,
    }
```

### 5.2 Decision Logging

Add explicit decision tracking:

```python
class DecisionLogger:
    """Tracks decisions made during request processing."""

    def __init__(self):
        self.decisions: List[Dict[str, Any]] = []

    def log_decision(
        self,
        decision_type: str,  # "delegation", "tool_choice", "approach"
        description: str,
        reasoning: str,
        alternatives_considered: Optional[List[str]] = None,
    ):
        self.decisions.append({
            "type": decision_type,
            "description": description,
            "reasoning": reasoning,
            "alternatives": alternatives_considered,
            "timestamp": datetime.now().isoformat(),
        })

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.decisions[-limit:]

    def format_for_handoff(self) -> str:
        """Format decisions for delegation context."""
        if not self.decisions:
            return "(No explicit decisions logged)"

        lines = []
        for d in self.decisions[-5:]:  # Last 5 decisions
            lines.append(f"- {d['description']}: {d['reasoning'][:50]}...")
        return "\n".join(lines)
```

### 5.3 File Access Tracking

```python
class FileAccessTracker:
    """Tracks file operations during request processing."""

    def __init__(self):
        self.reads: Dict[str, datetime] = {}  # path -> last read time
        self.writes: Dict[str, datetime] = {}  # path -> last write time
        self.searches: List[str] = []  # search patterns used

    def record_read(self, path: str):
        self.reads[path] = datetime.now()

    def record_write(self, path: str):
        self.writes[path] = datetime.now()

    def record_search(self, pattern: str):
        self.searches.append(pattern)

    def get_read_files(self, limit: int = 20) -> List[str]:
        """Get most recently read files."""
        sorted_files = sorted(
            self.reads.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [f[0] for f in sorted_files[:limit]]

    def get_modified_files(self, limit: int = 10) -> List[str]:
        """Get most recently modified files."""
        sorted_files = sorted(
            self.writes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [f[0] for f in sorted_files[:limit]]
```

---

## Part 6: Integration Architecture

### 6.1 Unified Task Analysis

Both routing and delegation should share task analysis:

```python
class UnifiedTaskAnalyzer:
    """Shared task analysis for routing and delegation."""

    def __init__(self):
        self.analysis_cache: Dict[str, TaskAnalysis] = {}

    def analyze(self, request: str, context: Optional[Dict] = None) -> TaskAnalysis:
        """Analyze request for task type, complexity, etc."""
        cache_key = self._cache_key(request)

        if cache_key in self.analysis_cache:
            return self.analysis_cache[cache_key]

        analysis = self._perform_analysis(request, context)
        self.analysis_cache[cache_key] = analysis
        return analysis

    def suggest_model(self, analysis: TaskAnalysis) -> ModelSuggestion:
        """Suggest model based on analysis (used by both systems)."""
        return ModelSuggestion(
            primary=self._get_primary_model(analysis),
            fallbacks=self._get_fallbacks(analysis),
            reasoning=self._build_reasoning(analysis),
        )
```

### 6.2 Cross-System Communication

```python
class OrchestrationCoordinator:
    """Coordinates between routing and delegation systems."""

    def __init__(
        self,
        router: Optional[RoutingOrchestrator] = None,
        orchestrator: Optional[OrchestrationManager] = None,
        task_analyzer: Optional[UnifiedTaskAnalyzer] = None,
    ):
        self.router = router
        self.orchestrator = orchestrator
        self.task_analyzer = task_analyzer or UnifiedTaskAnalyzer()

    def route_initial_request(self, request: str) -> RoutingDecision:
        """Route initial request (if routing enabled)."""
        if not self.router:
            return None

        analysis = self.task_analyzer.analyze(request)
        return self.router.route_request(request, analysis=analysis)

    def suggest_delegation_target(
        self,
        task: str,
        current_model: str,
    ) -> Optional[str]:
        """Suggest delegation target based on task analysis."""
        analysis = self.task_analyzer.analyze(task)
        suggestion = self.task_analyzer.suggest_model(analysis)

        # Don't suggest current model
        if suggestion.primary != current_model:
            return suggestion.primary
        return suggestion.fallbacks[0] if suggestion.fallbacks else None
```

---

## Part 7: Implementation Phases

### Phase 1: System Separation (Week 1-2)

**Goals**:
- Add `--delegation` flag to CLI
- Separate configuration for routing vs delegation
- Update defaults (both OFF by default)
- Add migration warnings for legacy users

**Files to Modify**:
- `cortex/cli.py` - Add new flag, separate configuration
- `cortex/config.py` - Separate routing/delegation configs
- `cortex/agent.py` - Respect separate flags

**Success Criteria**:
- `--routing` only enables routing
- `--delegation` only enables delegation
- Both can be combined
- Clear CLI help text explains difference

### Phase 2: Prompt Framework (Week 3-4)

**Goals**:
- Implement decision framework in prompts
- Add context checklist enforcement
- Improve handoff templates
- Add acknowledgment protocol

**Files to Modify**:
- `cortex/core/prompts/profiles.py` - Add decision framework
- `cortex/core/prompts/builder.py` - Include framework in system prompts
- `cortex/tools/delegation_tools.py` - Validate context checklist

**Success Criteria**:
- Models receive decision tree in system prompt
- Delegation requires context verification
- Handoff notes follow template
- Receiving models acknowledge delegation

### Phase 3: State Tracking (Week 5-6)

**Goals**:
- Fix file tracking (actual files, not tool names)
- Add decision logging
- Improve state summary for handoffs
- Track elapsed time and errors

**Files to Modify**:
- `cortex/agent.py` - Add FileAccessTracker, DecisionLogger
- `cortex/core/orchestration.py` - Use accurate state summary
- `cortex/tools/*.py` - Track file operations

**Success Criteria**:
- `_get_state_summary()` returns accurate data
- Decisions are logged and passed to delegates
- File access is tracked correctly
- Handoff context is rich and accurate

### Phase 4: Integration (Week 7-8)

**Goals**:
- Share task analysis between systems
- Add delegation suggestions to routing
- Unified cost tracking
- Cross-system transparency

**Files to Modify**:
- `cortex/core/routing/task_analysis.py` - Extract to shared module
- `cortex/core/routing/orchestrator.py` - Accept delegation hints
- `cortex/core/orchestration.py` - Use routing suggestions

**Success Criteria**:
- Task analysis is shared (no duplicate work)
- Routing suggests delegation targets
- Costs tracked across both systems
- Unified transparency display

---

## Part 8: Success Metrics

### Separation Metrics

| Metric | Target |
|--------|--------|
| Users understand flag difference | >90% (survey) |
| Configuration errors | <5% of users |
| Legacy migration warnings acknowledged | 100% |

### Delegation Quality Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Appropriate delegations | Unknown | >85% |
| Complete handoff context | ~40% | >90% |
| Correct specialist chosen | Unknown | >80% |
| Unnecessary delegations | Unknown | <10% |

### State Tracking Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Files tracked accurately | 0% | 100% |
| Decisions logged | 0% | >80% |
| Context completeness | ~40% | >90% |

---

## Part 9: Open Questions

### Design Decisions Needed

1. **Should returns count toward delegation quota?**
   - Current: Yes (seems wrong)
   - Proposed: No (returns are free)
   - Rationale: Returning is not delegation, it's completion

2. **Should routing be able to FORCE model selection?**
   - Option A: Routing suggests, user can override
   - Option B: Routing is advisory, delegation takes precedence
   - Recommendation: Option A (user control)

3. **How to handle delegation to offline/unavailable model?**
   - Option A: Fail and return error
   - Option B: Automatically fallback to similar model
   - Recommendation: Option B with user notification

4. **Should context checklist be enforced or advisory?**
   - Option A: Block delegation if incomplete
   - Option B: Warn but allow
   - Recommendation: Configurable, default to warn

### Technical Questions

1. How to share task analysis without circular imports?
2. Where should unified cost tracker live?
3. How to persist decision logs across sessions?
4. How to handle routing when provider is unavailable?

---

## Appendix A: File Change Summary

### Files to Create
- `cortex/core/shared/task_analyzer.py` - Unified task analysis
- `cortex/core/shared/cost_tracker.py` - Unified cost tracking
- `cortex/core/tracking/decisions.py` - Decision logger
- `cortex/core/tracking/files.py` - File access tracker

### Files to Modify
- `cortex/cli.py` - Add --delegation flag, separate configs
- `cortex/config.py` - Separate routing/delegation configuration
- `cortex/agent.py` - Respect separate flags, add trackers
- `cortex/core/prompts/profiles.py` - Add decision framework
- `cortex/core/prompts/builder.py` - Include framework
- `cortex/core/orchestration.py` - Fix state summary
- `cortex/tools/delegation_tools.py` - Context validation

### Tests to Add
- `tests/test_system_separation.py` - Flag independence tests
- `tests/test_decision_framework.py` - Prompt framework tests
- `tests/test_state_tracking.py` - Tracker tests
- `tests/integration/test_routing_delegation.py` - Cross-system tests

---

## Appendix B: Decision Framework Quick Reference

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DELEGATION DECISION QUICK REFERENCE              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ✓ CHECK 1: NECESSITY                                               │
│    → Can I do this myself? (Yes = Don't delegate)                   │
│    → Would specialist be significantly better? (Yes = Consider)     │
│                                                                      │
│  ✓ CHECK 2: CONTEXT                                                 │
│    □ Task description clear?                                        │
│    □ Files identified?                                              │
│    □ Constraints documented?                                        │
│    □ Success criteria defined?                                      │
│                                                                      │
│  ✓ CHECK 3: SPECIALIST                                              │
│    Planning/Architecture → deepseek-reasoner                        │
│    Code Implementation   → gpt-5.1-codex-mini                       │
│    Debugging            → hermes-3-405b                             │
│    Security Review      → dolphin-24b                               │
│    Web Research         → sonar-pro-search                          │
│                                                                      │
│  ✓ CHECK 4: HANDOFF                                                 │
│    Include: Task, Context, Files, Constraints, Expected Outcome     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

*End of Document*
